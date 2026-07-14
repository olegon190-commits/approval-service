"""Auth-заглушка.

Формат: заголовки запроса
  X-User-Id: usr_1                     — идентификатор пользователя
  X-Workspace-Id: ws_1                 — workspace пользователя
  X-Actions: approval:read,approval:create  — список разрешённых действий

В реальной системе это заменяется на JWT / OAuth middleware,
но интерфейс (user, workspace, actions) остаётся тем же.
"""
from dataclasses import dataclass
from typing import List
from fastapi import Header, HTTPException


@dataclass
class AuthContext:
    user_id: str
    workspace_id: str
    actions: List[str]

    def require(self, action: str):
        if action not in self.actions:
            raise HTTPException(status_code=403, detail=f"Missing permission: {action}")


def get_auth(
    x_user_id: str = Header(None),
    x_workspace_id: str = Header(None),
    x_actions: str = Header(None),
) -> AuthContext:
    if not x_user_id or not x_workspace_id:
        raise HTTPException(status_code=401, detail="Missing auth headers")
    actions = [a.strip() for a in (x_actions or "").split(",") if a.strip()]
    return AuthContext(user_id=x_user_id, workspace_id=x_workspace_id, actions=actions)
