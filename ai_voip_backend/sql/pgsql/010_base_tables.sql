CREATE TABLE IF NOT EXISTS sys_role (
    id BIGSERIAL PRIMARY KEY,
    role_code VARCHAR(64) NOT NULL UNIQUE,
    role_name VARCHAR(128) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS sys_user (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    mobile VARCHAR(32),
    email VARCHAR(255),
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_sys_user_status CHECK (status IN ('active', 'disabled', 'locked'))
);

CREATE TABLE IF NOT EXISTS sys_user_role (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES sys_user(id),
    role_id BIGINT NOT NULL REFERENCES sys_role(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS sys_operation_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES sys_user(id),
    module_name VARCHAR(64) NOT NULL,
    action_name VARCHAR(64) NOT NULL,
    request_id UUID NOT NULL DEFAULT gen_random_uuid(),
    target_type VARCHAR(64),
    target_id VARCHAR(64),
    request_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
    response_payload JSONB NOT NULL DEFAULT '{}'::JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS sys_config (
    id BIGSERIAL PRIMARY KEY,
    config_key VARCHAR(128) NOT NULL UNIQUE,
    config_value JSONB NOT NULL DEFAULT '{}'::JSONB,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS storage_profile (
    id BIGSERIAL PRIMARY KEY,
    profile_code VARCHAR(64) NOT NULL UNIQUE,
    profile_name VARCHAR(128) NOT NULL,
    storage_backend VARCHAR(32) NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    root_dir TEXT,
    endpoint TEXT,
    bucket_name VARCHAR(255),
    access_key VARCHAR(255),
    secret_key VARCHAR(255),
    region_name VARCHAR(128),
    extra_config JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_storage_profile_backend CHECK (storage_backend IN ('local', 's3_compatible'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_storage_profile_default_true
ON storage_profile (is_default)
WHERE is_default = TRUE;

CREATE TABLE IF NOT EXISTS speech_provider (
    id BIGSERIAL PRIMARY KEY,
    provider_code VARCHAR(64) NOT NULL UNIQUE,
    provider_name VARCHAR(128) NOT NULL,
    provider_type VARCHAR(32) NOT NULL,
    driver_name VARCHAR(64) NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    config_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_speech_provider_type CHECK (provider_type IN ('asr', 'tts'))
);

CREATE INDEX IF NOT EXISTS idx_sys_operation_log_user_id ON sys_operation_log (user_id);
CREATE INDEX IF NOT EXISTS idx_sys_operation_log_created_at ON sys_operation_log (created_at DESC);

DROP TRIGGER IF EXISTS trg_sys_role_updated_at ON sys_role;
CREATE TRIGGER trg_sys_role_updated_at BEFORE UPDATE ON sys_role
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_sys_user_updated_at ON sys_user;
CREATE TRIGGER trg_sys_user_updated_at BEFORE UPDATE ON sys_user
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_sys_user_role_updated_at ON sys_user_role;
CREATE TRIGGER trg_sys_user_role_updated_at BEFORE UPDATE ON sys_user_role
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_sys_operation_log_updated_at ON sys_operation_log;
CREATE TRIGGER trg_sys_operation_log_updated_at BEFORE UPDATE ON sys_operation_log
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_sys_config_updated_at ON sys_config;
CREATE TRIGGER trg_sys_config_updated_at BEFORE UPDATE ON sys_config
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_storage_profile_updated_at ON storage_profile;
CREATE TRIGGER trg_storage_profile_updated_at BEFORE UPDATE ON storage_profile
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_speech_provider_updated_at ON speech_provider;
CREATE TRIGGER trg_speech_provider_updated_at BEFORE UPDATE ON speech_provider
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
