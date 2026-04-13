ALTER TABLE contact_record
ADD COLUMN IF NOT EXISTS created_by BIGINT REFERENCES sys_user(id);

ALTER TABLE audio_asset
ADD COLUMN IF NOT EXISTS created_by BIGINT REFERENCES sys_user(id);

CREATE TABLE IF NOT EXISTS user_trunk_assignment (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES sys_user(id),
    trunk_id BIGINT NOT NULL REFERENCES sip_trunk(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (user_id, trunk_id)
);

CREATE INDEX IF NOT EXISTS idx_user_trunk_assignment_user_id
ON user_trunk_assignment (user_id)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_user_trunk_assignment_trunk_id
ON user_trunk_assignment (trunk_id)
WHERE deleted_at IS NULL;

DROP TRIGGER IF EXISTS trg_user_trunk_assignment_updated_at ON user_trunk_assignment;
CREATE TRIGGER trg_user_trunk_assignment_updated_at BEFORE UPDATE ON user_trunk_assignment
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
