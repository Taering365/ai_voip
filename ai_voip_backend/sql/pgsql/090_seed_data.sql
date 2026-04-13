INSERT INTO sys_role (role_code, role_name, description)
VALUES
    ('super_admin', '超级管理员', '负责系统全局配置与权限管理'),
    ('enterprise_admin', '企业管理员', '负责企业后台中的系统设置与用户管理'),
    ('agent_user', '普通用户', '负责企业实际业务操作与任务执行'),
    ('ops_admin', '运营管理员', '负责线路、任务、话术与数据运营'),
    ('qc_admin', '质检员', '负责质检结果复核与标注'),
    ('viewer', '查看员', '只读查看报表、任务与通话记录')
ON CONFLICT (role_code) DO NOTHING;

INSERT INTO storage_profile (
    profile_code,
    profile_name,
    storage_backend,
    is_default,
    root_dir,
    extra_config
)
VALUES (
    'local_default',
    '本地默认存储',
    'local',
    TRUE,
    './data',
    '{"recordings_dir":"recordings","tts_dir":"tts","assets_dir":"assets","transcripts_dir":"transcripts","exports_dir":"exports"}'::JSONB
)
ON CONFLICT (profile_code) DO NOTHING;

INSERT INTO sys_config (config_key, config_value, description)
VALUES
    ('system.storage_backend', '"local"'::JSONB, '系统默认存储后端'),
    ('system.call.max_concurrency', '100'::JSONB, '系统默认全局最大并发'),
    ('system.recording.retain_days', '180'::JSONB, '录音默认保留天数'),
    ('system.models_root', '"./models"'::JSONB, '本地模型根目录')
ON CONFLICT (config_key) DO NOTHING;
