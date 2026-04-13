CREATE TABLE IF NOT EXISTS contact_batch (
    id BIGSERIAL PRIMARY KEY,
    batch_code VARCHAR(64) NOT NULL UNIQUE,
    batch_name VARCHAR(255) NOT NULL,
    source_type VARCHAR(32) NOT NULL DEFAULT 'csv',
    original_filename VARCHAR(255),
    import_total INTEGER NOT NULL DEFAULT 0,
    success_total INTEGER NOT NULL DEFAULT 0,
    failed_total INTEGER NOT NULL DEFAULT 0,
    import_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    error_report_path TEXT,
    extra_meta JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_by BIGINT REFERENCES sys_user(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_contact_batch_source_type CHECK (source_type IN ('csv', 'xlsx', 'manual', 'api')),
    CONSTRAINT ck_contact_batch_status CHECK (import_status IN ('pending', 'processing', 'completed', 'failed'))
);

CREATE TABLE IF NOT EXISTS contact_record (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT REFERENCES contact_batch(id),
    contact_code VARCHAR(64) NOT NULL UNIQUE,
    customer_name VARCHAR(255),
    mobile VARCHAR(32) NOT NULL,
    ext_fields JSONB NOT NULL DEFAULT '{}'::JSONB,
    contact_status VARCHAR(32) NOT NULL DEFAULT 'active',
    last_call_at TIMESTAMPTZ,
    next_retry_at TIMESTAMPTZ,
    last_intent_code VARCHAR(64),
    last_result_code VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_contact_record_status CHECK (contact_status IN ('active', 'invalid', 'blacklisted', 'archived'))
);

CREATE TABLE IF NOT EXISTS contact_tag (
    id BIGSERIAL PRIMARY KEY,
    tag_code VARCHAR(64) NOT NULL UNIQUE,
    tag_name VARCHAR(128) NOT NULL,
    tag_type VARCHAR(32) NOT NULL DEFAULT 'business',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_contact_tag_type CHECK (tag_type IN ('business', 'intent', 'risk', 'custom'))
);

CREATE TABLE IF NOT EXISTS contact_record_tag (
    id BIGSERIAL PRIMARY KEY,
    contact_record_id BIGINT NOT NULL REFERENCES contact_record(id),
    tag_id BIGINT NOT NULL REFERENCES contact_tag(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (contact_record_id, tag_id)
);

CREATE TABLE IF NOT EXISTS blacklist_phone (
    id BIGSERIAL PRIMARY KEY,
    phone_number VARCHAR(32) NOT NULL UNIQUE,
    source_type VARCHAR(32) NOT NULL DEFAULT 'manual',
    reason TEXT,
    expires_at TIMESTAMPTZ,
    created_by BIGINT REFERENCES sys_user(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_blacklist_phone_source CHECK (source_type IN ('manual', 'import', 'complaint', 'system'))
);

CREATE INDEX IF NOT EXISTS idx_contact_record_mobile ON contact_record (mobile);
CREATE INDEX IF NOT EXISTS idx_contact_record_status ON contact_record (contact_status);
CREATE INDEX IF NOT EXISTS idx_blacklist_phone_phone_number ON blacklist_phone (phone_number);

DROP TRIGGER IF EXISTS trg_contact_batch_updated_at ON contact_batch;
CREATE TRIGGER trg_contact_batch_updated_at BEFORE UPDATE ON contact_batch
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_contact_record_updated_at ON contact_record;
CREATE TRIGGER trg_contact_record_updated_at BEFORE UPDATE ON contact_record
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_contact_tag_updated_at ON contact_tag;
CREATE TRIGGER trg_contact_tag_updated_at BEFORE UPDATE ON contact_tag
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_contact_record_tag_updated_at ON contact_record_tag;
CREATE TRIGGER trg_contact_record_tag_updated_at BEFORE UPDATE ON contact_record_tag
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_blacklist_phone_updated_at ON blacklist_phone;
CREATE TRIGGER trg_blacklist_phone_updated_at BEFORE UPDATE ON blacklist_phone
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
