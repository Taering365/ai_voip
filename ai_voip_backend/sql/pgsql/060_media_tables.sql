CREATE TABLE IF NOT EXISTS recording_file (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES call_session(id),
    record_type VARCHAR(32) NOT NULL DEFAULT 'mixed',
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
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_recording_file_type CHECK (record_type IN ('mixed', 'caller', 'callee')),
    CONSTRAINT ck_recording_file_backend CHECK (storage_backend IN ('local', 's3_compatible'))
);

CREATE TABLE IF NOT EXISTS transcript_task (
    id BIGSERIAL PRIMARY KEY,
    transcript_code VARCHAR(64) NOT NULL UNIQUE,
    session_id BIGINT NOT NULL REFERENCES call_session(id),
    recording_file_id BIGINT REFERENCES recording_file(id),
    asr_provider_id BIGINT REFERENCES speech_provider(id),
    task_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    language_code VARCHAR(32) DEFAULT 'zh-CN',
    transcript_text TEXT,
    result_json JSONB NOT NULL DEFAULT '{}'::JSONB,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_transcript_task_status CHECK (
        task_status IN ('pending', 'processing', 'completed', 'failed')
    )
);

CREATE TABLE IF NOT EXISTS transcript_segment (
    id BIGSERIAL PRIMARY KEY,
    transcript_task_id BIGINT NOT NULL REFERENCES transcript_task(id),
    speaker_label VARCHAR(32),
    channel_no INTEGER,
    begin_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    text_content TEXT NOT NULL,
    confidence NUMERIC(5, 4),
    keywords JSONB NOT NULL DEFAULT '[]'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS tts_render_task (
    id BIGSERIAL PRIMARY KEY,
    render_code VARCHAR(64) NOT NULL UNIQUE,
    text_content TEXT NOT NULL,
    voice_code VARCHAR(64),
    speech_rate NUMERIC(6, 2),
    volume_rate NUMERIC(6, 2),
    sample_rate INTEGER,
    tts_provider_id BIGINT REFERENCES speech_provider(id),
    audio_asset_id BIGINT REFERENCES audio_asset(id),
    task_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    result_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT ck_tts_render_task_status CHECK (
        task_status IN ('pending', 'processing', 'completed', 'failed')
    )
);

CREATE INDEX IF NOT EXISTS idx_recording_file_session_id ON recording_file (session_id);
CREATE INDEX IF NOT EXISTS idx_transcript_task_session_id ON transcript_task (session_id);
CREATE INDEX IF NOT EXISTS idx_transcript_segment_task_id_begin_ms
ON transcript_segment (transcript_task_id, begin_ms ASC);

DROP TRIGGER IF EXISTS trg_recording_file_updated_at ON recording_file;
CREATE TRIGGER trg_recording_file_updated_at BEFORE UPDATE ON recording_file
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_transcript_task_updated_at ON transcript_task;
CREATE TRIGGER trg_transcript_task_updated_at BEFORE UPDATE ON transcript_task
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_transcript_segment_updated_at ON transcript_segment;
CREATE TRIGGER trg_transcript_segment_updated_at BEFORE UPDATE ON transcript_segment
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
DROP TRIGGER IF EXISTS trg_tts_render_task_updated_at ON tts_render_task;
CREATE TRIGGER trg_tts_render_task_updated_at BEFORE UPDATE ON tts_render_task
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
