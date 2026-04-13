CREATE TABLE IF NOT EXISTS audio_asset (
    id BIGSERIAL PRIMARY KEY,
    asset_code VARCHAR(64) NOT NULL UNIQUE,
    asset_name VARCHAR(255) NOT NULL,
    asset_type VARCHAR(32) NOT NULL,
    storage_profile_id BIGINT REFERENCES storage_profile(id),
    storage_backend VARCHAR(32) NOT NULL,
    storage_key TEXT NOT NULL,
    local_path TEXT,
    object_key TEXT,
    file_hash VARCHAR(128),
    mime_type VARCHAR(128),
    file_size BIGINT,
    duration_ms INTEGER,
    sample_rate INTEGER,
    channels INTEGER,
    asset_status VARCHAR(32) NOT NULL DEFAULT 'active',
    tags JSONB NOT NULL DEFAULT '[]'::JSONB,
    extra_meta JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_audio_asset_type CHECK (asset_type IN ('pre_recorded', 'tts_cache', 'upload')),
    CONSTRAINT ck_audio_asset_backend CHECK (storage_backend IN ('local', 's3_compatible')),
    CONSTRAINT ck_audio_asset_status CHECK (asset_status IN ('active', 'disabled'))
);

CREATE TABLE IF NOT EXISTS script (
    id BIGSERIAL PRIMARY KEY,
    script_code VARCHAR(64) NOT NULL UNIQUE,
    script_name VARCHAR(255) NOT NULL,
    business_type VARCHAR(64),
    description TEXT,
    current_version_id BIGINT,
    script_status VARCHAR(32) NOT NULL DEFAULT 'draft',
    created_by BIGINT REFERENCES sys_user(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_script_status CHECK (script_status IN ('draft', 'published', 'disabled'))
);

CREATE TABLE IF NOT EXISTS script_version (
    id BIGSERIAL PRIMARY KEY,
    script_id BIGINT NOT NULL REFERENCES script(id),
    version_no INTEGER NOT NULL,
    version_label VARCHAR(64) NOT NULL,
    version_status VARCHAR(32) NOT NULL DEFAULT 'draft',
    start_node_code VARCHAR(64),
    canvas_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    published_by BIGINT REFERENCES sys_user(id),
    published_at TIMESTAMPTZ,
    remark TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (script_id, version_no),
    CONSTRAINT ck_script_version_status CHECK (version_status IN ('draft', 'published', 'archived'))
);

CREATE TABLE IF NOT EXISTS script_node (
    id BIGSERIAL PRIMARY KEY,
    script_version_id BIGINT NOT NULL REFERENCES script_version(id),
    node_code VARCHAR(64) NOT NULL,
    node_name VARCHAR(255) NOT NULL,
    node_type VARCHAR(32) NOT NULL,
    position_x NUMERIC(12, 2) NOT NULL DEFAULT 0,
    position_y NUMERIC(12, 2) NOT NULL DEFAULT 0,
    audio_asset_id BIGINT REFERENCES audio_asset(id),
    node_config JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (script_version_id, node_code),
    CONSTRAINT ck_script_node_type CHECK (
        node_type IN ('start', 'playback', 'asr', 'branch', 'intent', 'confirm', 'transfer', 'fallback', 'end')
    )
);

CREATE TABLE IF NOT EXISTS script_edge (
    id BIGSERIAL PRIMARY KEY,
    script_version_id BIGINT NOT NULL REFERENCES script_version(id),
    edge_code VARCHAR(64) NOT NULL,
    from_node_code VARCHAR(64) NOT NULL,
    to_node_code VARCHAR(64) NOT NULL,
    condition_type VARCHAR(32) NOT NULL DEFAULT 'always',
    condition_config JSONB NOT NULL DEFAULT '{}'::JSONB,
    sort_order INTEGER NOT NULL DEFAULT 100,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (script_version_id, edge_code),
    CONSTRAINT ck_script_edge_condition_type CHECK (
        condition_type IN ('always', 'keyword', 'intent', 'timeout', 'silence', 'nomatch', 'expression')
    )
);

CREATE TABLE IF NOT EXISTS script_publish_log (
    id BIGSERIAL PRIMARY KEY,
    script_id BIGINT NOT NULL REFERENCES script(id),
    script_version_id BIGINT NOT NULL REFERENCES script_version(id),
    action_name VARCHAR(32) NOT NULL,
    operator_id BIGINT REFERENCES sys_user(id),
    remark TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_script_publish_log_action CHECK (action_name IN ('publish', 'rollback', 'clone', 'archive'))
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_script_current_version'
    ) THEN
        ALTER TABLE script
            ADD CONSTRAINT fk_script_current_version
            FOREIGN KEY (current_version_id) REFERENCES script_version(id);
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_script_status ON script (script_status);
CREATE INDEX IF NOT EXISTS idx_script_version_status ON script_version (version_status);
CREATE INDEX IF NOT EXISTS idx_script_node_version_id ON script_node (script_version_id);
CREATE INDEX IF NOT EXISTS idx_script_edge_version_id ON script_edge (script_version_id);

DROP TRIGGER IF EXISTS trg_audio_asset_updated_at ON audio_asset;
CREATE TRIGGER trg_audio_asset_updated_at BEFORE UPDATE ON audio_asset
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_script_updated_at ON script;
CREATE TRIGGER trg_script_updated_at BEFORE UPDATE ON script
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_script_version_updated_at ON script_version;
CREATE TRIGGER trg_script_version_updated_at BEFORE UPDATE ON script_version
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_script_node_updated_at ON script_node;
CREATE TRIGGER trg_script_node_updated_at BEFORE UPDATE ON script_node
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_script_edge_updated_at ON script_edge;
CREATE TRIGGER trg_script_edge_updated_at BEFORE UPDATE ON script_edge
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_script_publish_log_updated_at ON script_publish_log;
CREATE TRIGGER trg_script_publish_log_updated_at BEFORE UPDATE ON script_publish_log
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
