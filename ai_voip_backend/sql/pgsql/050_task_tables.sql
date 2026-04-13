CREATE TABLE IF NOT EXISTS call_task (
    id BIGSERIAL PRIMARY KEY,
    task_code VARCHAR(64) NOT NULL UNIQUE,
    task_name VARCHAR(255) NOT NULL,
    task_type VARCHAR(32) NOT NULL DEFAULT 'outbound',
    script_id BIGINT NOT NULL REFERENCES script(id),
    script_version_id BIGINT NOT NULL REFERENCES script_version(id),
    trunk_id BIGINT REFERENCES sip_trunk(id),
    trunk_group_id BIGINT REFERENCES sip_trunk_group(id),
    batch_id BIGINT REFERENCES contact_batch(id),
    max_concurrency INTEGER NOT NULL DEFAULT 1,
    cps_limit INTEGER NOT NULL DEFAULT 1,
    retry_limit INTEGER NOT NULL DEFAULT 0,
    retry_interval_seconds INTEGER NOT NULL DEFAULT 300,
    call_time_range JSONB NOT NULL DEFAULT '{}'::JSONB,
    task_status VARCHAR(32) NOT NULL DEFAULT 'draft',
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_by BIGINT REFERENCES sys_user(id),
    extra_config JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_call_task_type CHECK (task_type IN ('outbound', 'notify', 'survey')),
    CONSTRAINT ck_call_task_status CHECK (
        task_status IN ('draft', 'queued', 'running', 'paused', 'completed', 'terminated', 'failed')
    )
);

CREATE TABLE IF NOT EXISTS call_task_dispatch (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES call_task(id),
    contact_record_id BIGINT NOT NULL REFERENCES contact_record(id),
    dispatch_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TIMESTAMPTZ,
    next_retry_at TIMESTAMPTZ,
    final_session_id BIGINT,
    result_code VARCHAR(64),
    result_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (task_id, contact_record_id),
    CONSTRAINT ck_call_task_dispatch_status CHECK (
        dispatch_status IN ('pending', 'dialing', 'success', 'failed', 'retry_wait', 'skipped', 'blocked')
    )
);

CREATE TABLE IF NOT EXISTS call_session (
    id BIGSERIAL PRIMARY KEY,
    session_code VARCHAR(64) NOT NULL UNIQUE,
    task_id BIGINT REFERENCES call_task(id),
    dispatch_id BIGINT REFERENCES call_task_dispatch(id),
    contact_record_id BIGINT REFERENCES contact_record(id),
    script_id BIGINT REFERENCES script(id),
    script_version_id BIGINT REFERENCES script_version(id),
    trunk_id BIGINT REFERENCES sip_trunk(id),
    trunk_group_id BIGINT REFERENCES sip_trunk_group(id),
    sip_call_id VARCHAR(255),
    caller_number VARCHAR(32),
    callee_number VARCHAR(32) NOT NULL,
    session_status VARCHAR(32) NOT NULL DEFAULT 'created',
    answer_status VARCHAR(32) NOT NULL DEFAULT 'unanswered',
    hangup_cause VARCHAR(64),
    current_node_code VARCHAR(64),
    started_at TIMESTAMPTZ,
    answered_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    billsec INTEGER NOT NULL DEFAULT 0,
    duration INTEGER NOT NULL DEFAULT 0,
    is_transfered BOOLEAN NOT NULL DEFAULT FALSE,
    intent_level VARCHAR(32),
    result_code VARCHAR(64),
    extra_meta JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_call_session_status CHECK (
        session_status IN ('created', 'dialing', 'ringing', 'answered', 'completed', 'failed', 'cancelled')
    ),
    CONSTRAINT ck_call_session_answer_status CHECK (
        answer_status IN ('unanswered', 'answered', 'voicemail', 'busy', 'rejected', 'timeout')
    ),
    CONSTRAINT ck_call_session_intent_level CHECK (
        intent_level IS NULL OR intent_level IN ('A', 'B', 'C', 'D', 'E', 'F')
    )
);

CREATE TABLE IF NOT EXISTS call_session_event (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES call_session(id),
    event_type VARCHAR(32) NOT NULL,
    node_code VARCHAR(64),
    payload JSONB NOT NULL DEFAULT '{}'::JSONB,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_call_session_event_type CHECK (
        event_type IN ('dial', 'ringing', 'answer', 'hangup', 'node_enter', 'node_exit', 'asr_result', 'transfer', 'system')
    )
);

CREATE TABLE IF NOT EXISTS call_session_variable (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES call_session(id),
    variable_key VARCHAR(128) NOT NULL,
    variable_value JSONB NOT NULL DEFAULT 'null'::JSONB,
    source_type VARCHAR(32) NOT NULL DEFAULT 'system',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (session_id, variable_key),
    CONSTRAINT ck_call_session_variable_source CHECK (source_type IN ('system', 'contact', 'asr', 'manual'))
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_call_task_dispatch_final_session'
    ) THEN
        ALTER TABLE call_task_dispatch
            ADD CONSTRAINT fk_call_task_dispatch_final_session
            FOREIGN KEY (final_session_id) REFERENCES call_session(id);
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_call_task_status ON call_task (task_status);
CREATE INDEX IF NOT EXISTS idx_call_task_dispatch_status ON call_task_dispatch (dispatch_status);
CREATE INDEX IF NOT EXISTS idx_call_session_task_id_started_at ON call_session (task_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_call_session_contact_record_id ON call_session (contact_record_id);
CREATE INDEX IF NOT EXISTS idx_call_session_status ON call_session (session_status);
CREATE INDEX IF NOT EXISTS idx_call_session_answer_status ON call_session (answer_status);
CREATE INDEX IF NOT EXISTS idx_call_session_event_session_id_occurred_at
ON call_session_event (session_id, occurred_at ASC);

DROP TRIGGER IF EXISTS trg_call_task_updated_at ON call_task;
CREATE TRIGGER trg_call_task_updated_at BEFORE UPDATE ON call_task
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_call_task_dispatch_updated_at ON call_task_dispatch;
CREATE TRIGGER trg_call_task_dispatch_updated_at BEFORE UPDATE ON call_task_dispatch
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_call_session_updated_at ON call_session;
CREATE TRIGGER trg_call_session_updated_at BEFORE UPDATE ON call_session
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_call_session_event_updated_at ON call_session_event;
CREATE TRIGGER trg_call_session_event_updated_at BEFORE UPDATE ON call_session_event
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_call_session_variable_updated_at ON call_session_variable;
CREATE TRIGGER trg_call_session_variable_updated_at BEFORE UPDATE ON call_session_variable
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
