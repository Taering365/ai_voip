CREATE TABLE IF NOT EXISTS sip_trunk (
    id BIGSERIAL PRIMARY KEY,
    trunk_code VARCHAR(64) NOT NULL UNIQUE,
    trunk_name VARCHAR(128) NOT NULL,
    server_host VARCHAR(255) NOT NULL,
    server_port INTEGER NOT NULL DEFAULT 5060,
    transport VARCHAR(16) NOT NULL DEFAULT 'udp',
    username VARCHAR(128) NOT NULL,
    password_cipher TEXT NOT NULL,
    auth_realm VARCHAR(255),
    outbound_proxy VARCHAR(255),
    from_user VARCHAR(128),
    contact_user VARCHAR(128),
    caller_id_number VARCHAR(32),
    max_concurrency INTEGER NOT NULL DEFAULT 1,
    cps_limit INTEGER NOT NULL DEFAULT 1,
    register_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    trunk_status VARCHAR(32) NOT NULL DEFAULT 'draft',
    route_strategy VARCHAR(32) NOT NULL DEFAULT 'single',
    extra_config JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_sip_trunk_transport CHECK (transport IN ('udp', 'tcp', 'tls')),
    CONSTRAINT ck_sip_trunk_status CHECK (trunk_status IN ('draft', 'enabled', 'disabled', 'error')),
    CONSTRAINT ck_sip_trunk_route_strategy CHECK (route_strategy IN ('single', 'round_robin', 'weight', 'primary_backup'))
);

CREATE TABLE IF NOT EXISTS sip_trunk_group (
    id BIGSERIAL PRIMARY KEY,
    group_code VARCHAR(64) NOT NULL UNIQUE,
    group_name VARCHAR(128) NOT NULL,
    route_strategy VARCHAR(32) NOT NULL DEFAULT 'round_robin',
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    extra_config JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_sip_trunk_group_route_strategy CHECK (route_strategy IN ('round_robin', 'weight', 'primary_backup'))
);

CREATE TABLE IF NOT EXISTS sip_trunk_group_member (
    id BIGSERIAL PRIMARY KEY,
    group_id BIGINT NOT NULL REFERENCES sip_trunk_group(id),
    trunk_id BIGINT NOT NULL REFERENCES sip_trunk(id),
    weight INTEGER NOT NULL DEFAULT 100,
    priority INTEGER NOT NULL DEFAULT 100,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (group_id, trunk_id)
);

CREATE TABLE IF NOT EXISTS sip_trunk_health_log (
    id BIGSERIAL PRIMARY KEY,
    trunk_id BIGINT NOT NULL REFERENCES sip_trunk(id),
    check_type VARCHAR(32) NOT NULL,
    check_status VARCHAR(32) NOT NULL,
    latency_ms INTEGER,
    error_message TEXT,
    detail_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_sip_trunk_health_log_type CHECK (check_type IN ('register', 'invite', 'options', 'dtmf', 'recording')),
    CONSTRAINT ck_sip_trunk_health_log_status CHECK (check_status IN ('success', 'failed', 'warning'))
);

CREATE INDEX IF NOT EXISTS idx_sip_trunk_status ON sip_trunk (trunk_status);
CREATE INDEX IF NOT EXISTS idx_sip_trunk_health_log_trunk_id_checked_at
ON sip_trunk_health_log (trunk_id, checked_at DESC);

DROP TRIGGER IF EXISTS trg_sip_trunk_updated_at ON sip_trunk;
CREATE TRIGGER trg_sip_trunk_updated_at BEFORE UPDATE ON sip_trunk
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_sip_trunk_group_updated_at ON sip_trunk_group;
CREATE TRIGGER trg_sip_trunk_group_updated_at BEFORE UPDATE ON sip_trunk_group
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_sip_trunk_group_member_updated_at ON sip_trunk_group_member;
CREATE TRIGGER trg_sip_trunk_group_member_updated_at BEFORE UPDATE ON sip_trunk_group_member
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_sip_trunk_health_log_updated_at ON sip_trunk_health_log;
CREATE TRIGGER trg_sip_trunk_health_log_updated_at BEFORE UPDATE ON sip_trunk_health_log
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
