-- Canonical grants: no credentials, payloads or provider secrets are stored here.
CREATE TABLE security_grants (
    tenant_id TEXT NOT NULL CHECK (length(tenant_id) BETWEEN 1 AND 200),
    kind TEXT NOT NULL CHECK (kind IN ('user','api')),
    subject_hash TEXT NOT NULL CHECK (subject_hash ~ '^[0-9a-f]{64}$'),
    fingerprint TEXT NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
    version BIGINT NOT NULL CHECK (version > 0),
    enabled BOOLEAN NOT NULL,
    PRIMARY KEY (tenant_id, kind, subject_hash)
);
CREATE TABLE security_authority_audit (
    audit_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    operation_id UUID NOT NULL,
    tenant_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    subject_hash TEXT NOT NULL,
    version BIGINT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('allow','deny','grant','revoke')),
    actor_hash TEXT NOT NULL,
    trace_hash TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX security_authority_audit_scope ON security_authority_audit(tenant_id,kind,subject_hash,audit_id);
