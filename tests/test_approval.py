"""Автотесты approval-service"""
import os
import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_approval.db"

from app.main import app
from app.database import engine
from app import models

client = TestClient(app)

WS = "ws_1"
OTHER_WS = "ws_2"

FULL_ACTIONS = "approval:read,approval:create,approval:decide,approval:cancel"


def auth_headers(user="usr_1", ws=WS, actions=FULL_ACTIONS):
    return {
        "X-User-Id": user,
        "X-Workspace-Id": ws,
        "X-Actions": actions,
    }


def make_request_body(**kw):
    body = {
        "sourceType": "publication",
        "sourceId": "pub_123",
        "title": "Instagram reel draft",
        "description": "Needs final approval",
        "reviewerUserIds": ["usr_1", "usr_2"],
    }
    body.update(kw)
    return body


@pytest.fixture(autouse=True)
def clean_db():
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    yield


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready():
    r = client.get("/ready")
    assert r.status_code == 200


def test_create_request():
    r = client.post(
        f"/api/v1/workspaces/{WS}/approval-requests",
        json=make_request_body(),
        headers=auth_headers(),
    )
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "pending"
    assert data["title"] == "Instagram reel draft"
    assert data["workspaceId"] == WS
    assert data["createdBy"] == "usr_1"


def test_create_without_auth():
    r = client.post(f"/api/v1/workspaces/{WS}/approval-requests", json=make_request_body())
    assert r.status_code == 401


def test_create_without_permission():
    r = client.post(
        f"/api/v1/workspaces/{WS}/approval-requests",
        json=make_request_body(),
        headers=auth_headers(actions="approval:read"),
    )
    assert r.status_code == 403


def test_create_invalid_source_type():
    r = client.post(
        f"/api/v1/workspaces/{WS}/approval-requests",
        json=make_request_body(sourceType="invalid"),
        headers=auth_headers(),
    )
    assert r.status_code == 422


def test_idempotency_no_duplicates():
    headers = {**auth_headers(), "Idempotency-Key": "key-123"}
    r1 = client.post(f"/api/v1/workspaces/{WS}/approval-requests", json=make_request_body(), headers=headers)
    r2 = client.post(f"/api/v1/workspaces/{WS}/approval-requests", json=make_request_body(), headers=headers)
    assert r1.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]

    lst = client.get(f"/api/v1/workspaces/{WS}/approval-requests", headers=auth_headers())
    assert lst.json()["total"] == 1


def test_workspace_isolation():
    r = client.post(
        f"/api/v1/workspaces/{WS}/approval-requests",
        json=make_request_body(),
        headers=auth_headers(),
    )
    req_id = r.json()["id"]

    r2 = client.get(
        f"/api/v1/workspaces/{OTHER_WS}/approval-requests/{req_id}",
        headers=auth_headers(ws=OTHER_WS),
    )
    assert r2.status_code == 404

    r3 = client.get(
        f"/api/v1/workspaces/{WS}/approval-requests/{req_id}",
        headers=auth_headers(ws=OTHER_WS),
    )
    assert r3.status_code == 403


def test_list_requests():
    for i in range(3):
        client.post(
            f"/api/v1/workspaces/{WS}/approval-requests",
            json=make_request_body(title=f"Request {i}"),
            headers=auth_headers(),
        )
    r = client.get(f"/api/v1/workspaces/{WS}/approval-requests", headers=auth_headers())
    assert r.status_code == 200
    assert r.json()["total"] == 3


def test_get_single_request():
    r = client.post(
        f"/api/v1/workspaces/{WS}/approval-requests",
        json=make_request_body(),
        headers=auth_headers(),
    )
    req_id = r.json()["id"]
    r2 = client.get(f"/api/v1/workspaces/{WS}/approval-requests/{req_id}", headers=auth_headers())
    assert r2.status_code == 200
    assert r2.json()["id"] == req_id


def test_get_nonexistent():
    r = client.get(f"/api/v1/workspaces/{WS}/approval-requests/no-such-id", headers=auth_headers())
    assert r.status_code == 404


def test_approve():
    r = client.post(f"/api/v1/workspaces/{WS}/approval-requests", json=make_request_body(), headers=auth_headers())
    req_id = r.json()["id"]

    r2 = client.post(
        f"/api/v1/workspaces/{WS}/approval-requests/{req_id}/approve",
        json={"comment": "Approved"},
        headers=auth_headers(user="usr_2"),
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "approved"
    assert r2.json()["decidedBy"] == "usr_2"


def test_reject():
    r = client.post(f"/api/v1/workspaces/{WS}/approval-requests", json=make_request_body(), headers=auth_headers())
    req_id = r.json()["id"]

    r2 = client.post(
        f"/api/v1/workspaces/{WS}/approval-requests/{req_id}/reject",
        json={"reason": "Brand tone is wrong"},
        headers=auth_headers(),
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "rejected"


def test_cancel():
    r = client.post(f"/api/v1/workspaces/{WS}/approval-requests", json=make_request_body(), headers=auth_headers())
    req_id = r.json()["id"]

    r2 = client.post(
        f"/api/v1/workspaces/{WS}/approval-requests/{req_id}/cancel",
        json={"reason": "Draft was removed"},
        headers=auth_headers(),
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "cancelled"


def test_final_status_immutable():
    r = client.post(f"/api/v1/workspaces/{WS}/approval-requests", json=make_request_body(), headers=auth_headers())
    req_id = r.json()["id"]

    client.post(
        f"/api/v1/workspaces/{WS}/approval-requests/{req_id}/approve",
        json={"comment": "ok"},
        headers=auth_headers(),
    )

    r2 = client.post(
        f"/api/v1/workspaces/{WS}/approval-requests/{req_id}/reject",
        json={"reason": "changed my mind"},
        headers=auth_headers(),
    )
    assert r2.status_code == 409

    r3 = client.post(
        f"/api/v1/workspaces/{WS}/approval-requests/{req_id}/cancel",
        json={"reason": "too late"},
        headers=auth_headers(),
    )
    assert r3.status_code == 409


def test_reject_requires_reason():
    r = client.post(f"/api/v1/workspaces/{WS}/approval-requests", json=make_request_body(), headers=auth_headers())
    req_id = r.json()["id"]
    r2 = client.post(
        f"/api/v1/workspaces/{WS}/approval-requests/{req_id}/reject",
        json={},
        headers=auth_headers(),
    )
    assert r2.status_code == 422


def test_decide_requires_permission():
    r = client.post(f"/api/v1/workspaces/{WS}/approval-requests", json=make_request_body(), headers=auth_headers())
    req_id = r.json()["id"]
    r2 = client.post(
        f"/api/v1/workspaces/{WS}/approval-requests/{req_id}/approve",
        json={"comment": "ok"},
        headers=auth_headers(actions="approval:read,approval:create"),
    )
    assert r2.status_code == 403
