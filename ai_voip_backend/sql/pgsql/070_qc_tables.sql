CREATE TABLE IF NOT EXISTS qc_rule (
    id BIGSERIAL PRIMARY KEY,
    rule_code VARCHAR(64) NOT NULL UNIQUE,
    rule_name VARCHAR(255) NOT NULL,
    rule_type VARCHAR(32) NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    priority INTEGER NOT NULL DEFAULT 100,
    rule_config JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_qc_rule_type CHECK (rule_type IN ('keyword', 'intent', 'compliance', 'risk', 'flow'))
);

CREATE TABLE IF NOT EXISTS qc_result (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES call_session(id),
    score NUMERIC(6, 2),
    intent_level VARCHAR(32),
    manual_intent_level VARCHAR(32),
    flow_label VARCHAR(128),
    semantic_tags JSONB NOT NULL DEFAULT '[]'::JSONB,
    question_tags JSONB NOT NULL DEFAULT '[]'::JSONB,
    risk_tags JSONB NOT NULL DEFAULT '[]'::JSONB,
    summary_text TEXT,
    reviewed_by BIGINT REFERENCES sys_user(id),
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (session_id),
    CONSTRAINT ck_qc_result_intent_level CHECK (
        intent_level IS NULL OR intent_level IN ('A', 'B', 'C', 'D', 'E', 'F')
    ),
    CONSTRAINT ck_qc_result_manual_intent_level CHECK (
        manual_intent_level IS NULL OR manual_intent_level IN ('A', 'B', 'C', 'D', 'E', 'F')
    )
);

CREATE TABLE IF NOT EXISTS qc_rule_hit (
    id BIGSERIAL PRIMARY KEY,
    qc_result_id BIGINT NOT NULL REFERENCES qc_result(id),
    qc_rule_id BIGINT NOT NULL REFERENCES qc_rule(id),
    hit_source VARCHAR(32) NOT NULL DEFAULT 'system',
    hit_count INTEGER NOT NULL DEFAULT 1,
    payload JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_qc_rule_hit_source CHECK (hit_source IN ('system', 'manual'))
);

CREATE TABLE IF NOT EXISTS intent_label (
    id BIGSERIAL PRIMARY KEY,
    intent_code VARCHAR(64) NOT NULL UNIQUE,
    intent_name VARCHAR(128) NOT NULL,
    intent_level VARCHAR(32),
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_intent_label_level CHECK (
        intent_level IS NULL OR intent_level IN ('A', 'B', 'C', 'D', 'E', 'F')
    )
);

CREATE TABLE IF NOT EXISTS session_intent (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES call_session(id),
    intent_label_id BIGINT NOT NULL REFERENCES intent_label(id),
    source_type VARCHAR(32) NOT NULL DEFAULT 'system',
    confidence NUMERIC(5, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (session_id, intent_label_id),
    CONSTRAINT ck_session_intent_source CHECK (source_type IN ('system', 'manual'))
);

CREATE INDEX IF NOT EXISTS idx_qc_result_intent_level ON qc_result (intent_level);
CREATE INDEX IF NOT EXISTS idx_qc_rule_hit_qc_result_id ON qc_rule_hit (qc_result_id);
CREATE INDEX IF NOT EXISTS idx_session_intent_session_id ON session_intent (session_id);

DROP TRIGGER IF EXISTS trg_qc_rule_updated_at ON qc_rule;
CREATE TRIGGER trg_qc_rule_updated_at BEFORE UPDATE ON qc_rule
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_qc_result_updated_at ON qc_result;
CREATE TRIGGER trg_qc_result_updated_at BEFORE UPDATE ON qc_result
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_qc_rule_hit_updated_at ON qc_rule_hit;
CREATE TRIGGER trg_qc_rule_hit_updated_at BEFORE UPDATE ON qc_rule_hit
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_intent_label_updated_at ON intent_label;
CREATE TRIGGER trg_intent_label_updated_at BEFORE UPDATE ON intent_label
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_session_intent_updated_at ON session_intent;
CREATE TRIGGER trg_session_intent_updated_at BEFORE UPDATE ON session_intent
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
