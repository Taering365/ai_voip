CREATE TABLE IF NOT EXISTS task_daily_stat (
    id BIGSERIAL PRIMARY KEY,
    stat_date DATE NOT NULL,
    task_id BIGINT NOT NULL REFERENCES call_task(id),
    total_count INTEGER NOT NULL DEFAULT 0,
    answered_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    intent_a_count INTEGER NOT NULL DEFAULT 0,
    intent_b_count INTEGER NOT NULL DEFAULT 0,
    intent_c_count INTEGER NOT NULL DEFAULT 0,
    total_billsec INTEGER NOT NULL DEFAULT 0,
    total_duration INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (stat_date, task_id)
);

CREATE TABLE IF NOT EXISTS trunk_daily_stat (
    id BIGSERIAL PRIMARY KEY,
    stat_date DATE NOT NULL,
    trunk_id BIGINT NOT NULL REFERENCES sip_trunk(id),
    total_count INTEGER NOT NULL DEFAULT 0,
    answer_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    busy_count INTEGER NOT NULL DEFAULT 0,
    reject_count INTEGER NOT NULL DEFAULT 0,
    timeout_count INTEGER NOT NULL DEFAULT 0,
    total_billsec INTEGER NOT NULL DEFAULT 0,
    total_duration INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (stat_date, trunk_id)
);

DROP TRIGGER IF EXISTS trg_task_daily_stat_updated_at ON task_daily_stat;
CREATE TRIGGER trg_task_daily_stat_updated_at BEFORE UPDATE ON task_daily_stat
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_trunk_daily_stat_updated_at ON trunk_daily_stat;
CREATE TRIGGER trg_trunk_daily_stat_updated_at BEFORE UPDATE ON trunk_daily_stat
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
