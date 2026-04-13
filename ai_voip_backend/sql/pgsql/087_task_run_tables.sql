-- 为任务增加“执行批次”概念，确保同一个任务可以按天或按次重复运行，
-- 每次运行的分发表和会话都能独立归档，不会把历史外呼覆盖掉。

CREATE TABLE IF NOT EXISTS call_task_run (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES call_task(id),
    run_no INTEGER NOT NULL,
    run_code VARCHAR(64) NOT NULL UNIQUE,
    run_status VARCHAR(32) NOT NULL DEFAULT 'queued',
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT uq_call_task_run_task_id_run_no UNIQUE (task_id, run_no),
    CONSTRAINT ck_call_task_run_status CHECK (
        run_status IN ('queued', 'running', 'completed', 'terminated', 'failed')
    )
);

-- 任务表记录当前正在查看或当前正在执行的批次主键。
ALTER TABLE call_task
    ADD COLUMN IF NOT EXISTS current_run_id BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_call_task_current_run'
    ) THEN
        ALTER TABLE call_task
            ADD CONSTRAINT fk_call_task_current_run
            FOREIGN KEY (current_run_id) REFERENCES call_task_run(id);
    END IF;
END;
$$;

-- 分发表与会话表都挂到具体执行批次上。
ALTER TABLE call_task_dispatch
    ADD COLUMN IF NOT EXISTS task_run_id BIGINT;

ALTER TABLE call_session
    ADD COLUMN IF NOT EXISTS task_run_id BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_call_task_dispatch_task_run'
    ) THEN
        ALTER TABLE call_task_dispatch
            ADD CONSTRAINT fk_call_task_dispatch_task_run
            FOREIGN KEY (task_run_id) REFERENCES call_task_run(id);
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_call_session_task_run'
    ) THEN
        ALTER TABLE call_session
            ADD CONSTRAINT fk_call_session_task_run
            FOREIGN KEY (task_run_id) REFERENCES call_task_run(id);
    END IF;
END;
$$;

-- 为旧数据补一轮历史执行批次，避免升级后旧会话丢失归属。
INSERT INTO call_task_run (
    task_id, run_no, run_code, run_status, started_at, finished_at, created_at, updated_at
)
SELECT
    t.id,
    1,
    CONCAT('task_', t.id, '_run_1'),
    CASE
        WHEN t.task_status IN ('running', 'queued') THEN 'terminated'
        WHEN t.task_status IN ('completed', 'terminated', 'failed') THEN t.task_status
        ELSE 'completed'
    END,
    t.started_at,
    t.finished_at,
    NOW(),
    NOW()
FROM call_task t
WHERE t.deleted_at IS NULL
  AND EXISTS (
      SELECT 1
      FROM call_task_dispatch d
      WHERE d.task_id = t.id
        AND d.deleted_at IS NULL
  )
  AND NOT EXISTS (
      SELECT 1
      FROM call_task_run r
      WHERE r.task_id = t.id
        AND r.deleted_at IS NULL
  );

-- 把旧分发表与旧会话都挂到刚才补出来的历史执行批次上。
UPDATE call_task_dispatch d
SET task_run_id = r.id
FROM call_task_run r
WHERE d.task_id = r.task_id
  AND d.task_run_id IS NULL
  AND r.run_no = 1
  AND d.deleted_at IS NULL
  AND r.deleted_at IS NULL;

UPDATE call_session s
SET task_run_id = r.id
FROM call_task_run r
WHERE s.task_id = r.task_id
  AND s.task_run_id IS NULL
  AND r.run_no = 1
  AND s.deleted_at IS NULL
  AND r.deleted_at IS NULL;

-- 对于尚未设置 current_run_id 的任务，默认指向最新执行批次。
UPDATE call_task t
SET current_run_id = latest_run.id
FROM (
    SELECT DISTINCT ON (task_id) id, task_id
    FROM call_task_run
    WHERE deleted_at IS NULL
    ORDER BY task_id, run_no DESC, id DESC
) AS latest_run
WHERE t.id = latest_run.task_id
  AND t.current_run_id IS NULL
  AND t.deleted_at IS NULL;

-- 原有唯一约束只允许一个任务对一个联系人保留一条分发表，不适合多次运行。
ALTER TABLE call_task_dispatch
    DROP CONSTRAINT IF EXISTS call_task_dispatch_task_id_contact_record_id_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_call_task_dispatch_run_contact
ON call_task_dispatch (task_run_id, contact_record_id)
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_call_task_current_run_id ON call_task (current_run_id);
CREATE INDEX IF NOT EXISTS idx_call_task_run_task_id_run_no ON call_task_run (task_id, run_no DESC);
CREATE INDEX IF NOT EXISTS idx_call_task_dispatch_task_run_id_status ON call_task_dispatch (task_run_id, dispatch_status);
CREATE INDEX IF NOT EXISTS idx_call_session_task_run_id_started_at ON call_session (task_run_id, started_at DESC);

DROP TRIGGER IF EXISTS trg_call_task_run_updated_at ON call_task_run;
CREATE TRIGGER trg_call_task_run_updated_at BEFORE UPDATE ON call_task_run
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
