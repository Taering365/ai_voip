ALTER TABLE sip_trunk
    ADD COLUMN IF NOT EXISTS trunk_type VARCHAR(32) NOT NULL DEFAULT 'sip_account',
    ADD COLUMN IF NOT EXISTS full_name VARCHAR(128),
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS support_concurrency BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE sip_trunk
    ALTER COLUMN username DROP NOT NULL,
    ALTER COLUMN password_cipher DROP NOT NULL;

UPDATE sip_trunk
SET support_concurrency = CASE WHEN max_concurrency > 1 THEN TRUE ELSE FALSE END
WHERE support_concurrency IS DISTINCT FROM CASE WHEN max_concurrency > 1 THEN TRUE ELSE FALSE END;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_sip_trunk_type'
    ) THEN
        ALTER TABLE sip_trunk
            ADD CONSTRAINT ck_sip_trunk_type CHECK (trunk_type IN ('sip_account', 'gateway'));
    END IF;
END;
$$;
