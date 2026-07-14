-- Migration 001: initial schema
-- approval_requests, audit_logs, outbox_events

CREATE TABLE IF NOT EXISTS approval_requests (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR NOT NULL,
    source_type VARCHAR(20) NOT NULL CHECK (source_type IN ('publication', 'scenario', 'edit', 'external')),
    source_id VARCHAR NOT NULL,
    title VARCHAR(500) NOT NULL,
    description VARCHAR(5000),
    reviewer_user_ids JSON NOT NULL DEFAULT '[]',
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    decision_comment VARCHAR(2000),
    decision_reason VARCHAR(2000),
    created_by VARCHAR NOT NULL,
    decided_by VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    idempotency_key VARCHAR
);

CREATE INDEX IF NOT EXISTS ix_approval_requests_workspace_id ON approval_requests(workspace_id);
CREATE INDEX IF NOT EXISTS ix_workspace_idempotency ON approval_requests(workspace_id, idempotency_key);

CREATE TABLE IF NOT EXISTS audit_logs (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR NOT NULL,
    request_id VARCHAR NOT NULL,
    actor_user_id VARCHAR NOT NULL,
    action VARCHAR(50) NOT NULL,
    details JSON,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_audit_logs_workspace_id ON audit_logs(workspace_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_request_id ON audit_logs(request_id);

CREATE TABLE IF NOT EXISTS outbox_events (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSON NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP WITH TIME ZONE
);
