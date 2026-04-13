# 接口文档

本文档整理当前已经落地的后端接口，便于前后端联调与后台页面对接。

## 基础信息

- 基础前缀：`/api/v1`
- 默认开发地址：`http://127.0.0.1:3900`
- Swagger：`/docs`
- OpenAPI JSON：`/openapi.json`
- 统一响应结构：

```json
{
  "success": true,
  "message": "ok",
  "data": {}
}
```

- 统一错误响应结构：

```json
{
  "success": false,
  "message": "错误说明",
  "error_code": "业务错误码",
  "data": null
}
```

## 鉴权说明

除 `POST /api/v1/auth/login`、`GET /api/v1/auth/captcha` 和 `GET /api/v1/health` 外，其余接口默认需要请求头：

```http
Authorization: Bearer <ACCESS_TOKEN>
```

说明：

- 当前返回给前端的是 `加密后的密文 token`
- 前端不需要解析，也不需要校验
- 前端只需要原样保存，并在后续请求中原样回传
- 后端会先解密，再做 JWT 验签和用户校验

## 已实现接口总览

### 1. 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/auth/captcha` | 获取图片验证码，返回 base64 图片和 captcha_key |
| POST | `/api/v1/auth/login` | 用户登录，返回密文 token |

### 权限说明

- `管理员接口`：系统配置、存储配置、Provider、线路管理、用户管理、线路分配、质检规则
- `普通用户接口`：话术、名单、任务、媒体、运行调试、当前用户可见范围内的质检结果
- 普通用户默认只能看到自己创建的数据，以及管理员分配给自己的线路

### 2. 系统

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 服务健康检查 |
| GET | `/api/v1/system/configs` | 获取系统配置 |
| GET | `/api/v1/system/me` | 获取当前登录用户 |

### 2.1 用户管理

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/users` | 获取用户列表，仅管理员 |
| POST | `/api/v1/users` | 创建用户，仅管理员 |
| GET | `/api/v1/users/{user_id}` | 获取用户详情，仅管理员 |
| PUT | `/api/v1/users/{user_id}` | 更新用户，仅管理员 |
| GET | `/api/v1/users/{user_id}/trunks` | 获取用户已分配线路，仅管理员 |
| PUT | `/api/v1/users/{user_id}/trunks` | 覆盖用户线路分配，仅管理员 |

### 3. 存储配置

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/storage/profiles` | 获取存储配置列表 |
| POST | `/api/v1/storage/profiles` | 创建存储配置 |
| POST | `/api/v1/storage/profiles/probe` | 检测存储配置是否可用 |
| GET | `/api/v1/storage/profiles/default` | 获取默认存储配置 |
| GET | `/api/v1/storage/profiles/{profile_id}` | 获取存储配置详情 |
| PUT | `/api/v1/storage/profiles/{profile_id}` | 更新存储配置 |
| POST | `/api/v1/storage/profiles/{profile_id}/default` | 设置默认存储配置 |
| DELETE | `/api/v1/storage/profiles/{profile_id}` | 删除存储配置 |

### 4. 语音接口配置

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/providers` | 获取 ASR/TTS 接口配置列表，系统会自动补齐默认的本地流式 ASR、阿里百炼实时 ASR 与 MiniMax TTS 模板 |
| POST | `/api/v1/providers` | 创建接口配置 |
| GET | `/api/v1/providers/{provider_id}` | 获取接口配置详情 |
| POST | `/api/v1/providers/{provider_id}/health-check` | 检测接口连通性与密钥配置是否有效，支持本地流式 ASR、阿里百炼实时 ASR 与 MiniMax TTS |
| PUT | `/api/v1/providers/{provider_id}` | 更新接口配置 |
| DELETE | `/api/v1/providers/{provider_id}` | 删除接口配置 |

### 5. SIP 线路

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/trunks` | 获取线路列表 |
| POST | `/api/v1/trunks` | 创建线路 |
| GET | `/api/v1/trunks/{trunk_id}` | 获取线路详情 |
| PUT | `/api/v1/trunks/{trunk_id}` | 更新线路 |
| PATCH | `/api/v1/trunks/{trunk_id}/status` | 更新线路状态 |
| POST | `/api/v1/trunks/{trunk_id}/probe` | 检测线路连通性和注册准备状态 |

说明：

- 线路支持两种类型：`sip_account`、`gateway`
- `sip_account` 模式提交 `domain`、`full_name`、`username`、`password_cipher`
- `gateway` 模式提交 `ip_address`、`port`、`caller_id_number`
- `support_concurrency=false` 时后端会自动把 `max_concurrency` 归一为 `1`
- 线路检测接口当前支持：
  - `gateway`：执行 TCP 连通检测
  - `sip_account + tcp/tls`：执行 TCP 连通检测并返回注册准备状态
  - `sip_account + udp`：执行 UDP 地址解析检测，并提示当前未接入完整 SIP REGISTER 检测

### 6. 话术管理

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/scripts` | 获取话术列表 |
| POST | `/api/v1/scripts` | 创建话术 |
| POST | `/api/v1/scripts/demo/kids-coding` | 为当前用户导入系统内置的少儿编程教育推广示例 |
| POST | `/api/v1/scripts/demo/wine-tasting` | 为当前用户导入系统内置的名酒品鉴会邀约示例 |
| GET | `/api/v1/scripts/{script_id}` | 获取话术详情 |
| PUT | `/api/v1/scripts/{script_id}` | 更新话术 |
| DELETE | `/api/v1/scripts/{script_id}` | 删除话术 |
| GET | `/api/v1/scripts/{script_id}/versions` | 获取话术版本列表 |
| POST | `/api/v1/scripts/{script_id}/versions` | 创建话术版本 |
| DELETE | `/api/v1/scripts/{script_id}/versions/{version_id}` | 删除话术版本 |
| POST | `/api/v1/scripts/{script_id}/versions/{version_id}/publish` | 发布话术版本 |
| GET | `/api/v1/scripts/versions/{script_version_id}/nodes` | 获取节点列表 |
| POST | `/api/v1/scripts/versions/{script_version_id}/nodes` | 创建节点 |
| PUT | `/api/v1/scripts/nodes/{node_id}` | 更新节点，支持拖拽后保存位置 |
| DELETE | `/api/v1/scripts/nodes/{node_id}` | 删除节点 |
| GET | `/api/v1/scripts/versions/{script_version_id}/edges` | 获取连线列表 |
| POST | `/api/v1/scripts/versions/{script_version_id}/edges` | 创建连线 |
| PUT | `/api/v1/scripts/edges/{edge_id}` | 更新连线 |
| DELETE | `/api/v1/scripts/edges/{edge_id}` | 删除连线 |
| PUT | `/api/v1/scripts/versions/{version_id}` | 更新版本画布信息和起始节点 |

### 7. 名单与联系人

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/contacts/batches` | 获取名单批次列表 |
| POST | `/api/v1/contacts/batches` | 创建名单批次，仅需批次名称与备注 |
| GET | `/api/v1/contacts/batches/{batch_id}` | 获取名单批次详情 |
| DELETE | `/api/v1/contacts/batches/{batch_id}` | 删除名单批次 |
| GET | `/api/v1/contacts/records` | 获取联系人列表 |
| POST | `/api/v1/contacts/records` | 单个创建联系人，仅需所属批次、客户姓名和手机号 |
| POST | `/api/v1/contacts/records/import` | 批量导入联系人，支持 txt、csv、excel 解析后入库 |
| GET | `/api/v1/contacts/records/{record_id}` | 获取联系人详情 |
| DELETE | `/api/v1/contacts/records/{record_id}` | 删除联系人 |

### 8. 任务与会话

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/tasks` | 获取任务列表 |
| POST | `/api/v1/tasks` | 创建任务 |
| GET | `/api/v1/tasks/{task_id}` | 获取任务详情 |
| PUT | `/api/v1/tasks/{task_id}` | 更新任务 |
| PATCH | `/api/v1/tasks/{task_id}/status` | 更新任务状态 |
| DELETE | `/api/v1/tasks/{task_id}` | 删除任务 |
| GET | `/api/v1/tasks/{task_id}/runs` | 获取任务执行批次列表 |
| GET | `/api/v1/tasks/{task_id}/sessions` | 获取任务下的通话会话列表 |

- 任务会话已按“执行批次”归档。
- 每次重新运行任务时，系统会创建新的执行批次，并把本次分发表、会话、外呼结果全部挂到该批次下。
- `/api/v1/tasks/{task_id}/sessions` 会返回 `task_run_id / task_run_no / task_run_code / task_run_status` 等字段，前端可按当前批次与历史批次分组展示。
- 任务创建和更新接口支持 `trunk_ids` 数组；当一次绑定多条 `SIP` 线路时，后端会自动维护任务专属线路池，并按每条线路的可用并发分配外呼。

### 9. 质检

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/qc/rules` | 获取质检规则列表 |
| POST | `/api/v1/qc/rules` | 创建质检规则 |
| GET | `/api/v1/qc/rules/{rule_id}` | 获取质检规则详情 |
| PUT | `/api/v1/qc/rules/{rule_id}` | 更新质检规则 |
| DELETE | `/api/v1/qc/rules/{rule_id}` | 删除质检规则 |
| GET | `/api/v1/qc/results` | 获取质检结果列表 |

### 10. 录音管理与转写结果

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/media/audio-assets` | 获取音频资源列表 |
| POST | `/api/v1/media/audio-assets` | 创建音频资源元数据 |
| POST | `/api/v1/media/audio-assets/generate-tts` | 根据播报文案真实生成在线 TTS 语音文件并缓存落盘 |
| GET | `/api/v1/media/audio-assets/{asset_id}` | 获取音频资源详情 |
| DELETE | `/api/v1/media/audio-assets/{asset_id}` | 删除音频资源 |
| GET | `/api/v1/media/recordings` | 获取录音文件列表，返回通话编码、客户信息、试听地址、下载地址、最近一次转写状态 |
| GET | `/api/v1/media/recordings/{recording_file_id}/content` | 在线试听录音文件 |
| GET | `/api/v1/media/recordings/{recording_file_id}/download` | 下载录音文件 |
| POST | `/api/v1/media/recordings/upload` | 上传录音文件并按默认存储配置保存 |
| GET | `/api/v1/media/transcripts` | 获取转写结果列表，返回通话信息和关联录音地址 |
| POST | `/api/v1/media/transcripts` | 对指定录音文件发起在线 ASR 转写 |
| GET | `/api/v1/media/transcripts/{transcript_task_id}/segments` | 获取转写分段列表，返回客服 / 客户角色、时间戳和文本内容 |

### 11. 运行态

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/runtime/scripts/{script_version_id}/step` | 执行话术单步推进 |
| POST | `/api/v1/runtime/scripts/{script_version_id}/simulate` | 模拟执行整个话术流程 |
| POST | `/api/v1/runtime/tasks/{task_id}/queue` | 生成任务分发表并入队 |
| GET | `/api/v1/runtime/tasks/{task_id}/dispatches/pending` | 拉取任务待调度联系人 |
| POST | `/api/v1/runtime/tasks/{task_id}/sessions` | 为分发记录创建会话 |
| PATCH | `/api/v1/runtime/sessions/{session_id}/progress` | 推进会话状态与事件 |

### 11.1 真实生成在线 TTS 音频

请求：

```http
POST /api/v1/media/audio-assets/generate-tts
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
```

```json
{
  "asset_name": "开场白录音",
  "prompt_text": "您好，这里是智能外呼测试语音。",
  "tts_provider_id": null,
  "tts_voice_profile": null,
  "channels": 1
}
```

说明：

- 当前真实生成已改为只依赖线上 TTS 接口，不再使用本地 `local say`
- 若未选择 `tts_provider_id`，后端会自动选择首个“已启用且已配置 API Key”的在线 TTS 接口
- 当前默认在线 TTS 模板为 MiniMax WebSocket 接口，真实生成前请先在“语音接口”页面填写有效 API Key
- 当前真实生成文件会按“默认存储配置”自动落到本地目录或上传到 S3 兼容存储
- 返回值为标准 `AudioAssetItem`，可直接用于话术节点绑定本地录音

### 11.2 上传录音文件

请求：

```http
POST /api/v1/media/recordings/upload
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: multipart/form-data
```

表单字段：

- `session_id`：已有通话会话主键
- `record_type`：录音类型，支持 `mixed / caller / callee`
- `file`：录音文件本体

说明：

- 上传录音后，后端会优先使用“默认存储配置”保存文件；未配置时自动回落到项目内 `data/recorder`
- 当默认存储为 MinIO / S3 兼容时，录音文件会直接上传到对象存储
- 对象存储录音在发起阿里百炼转写时，后端会自动生成可访问地址，无需手工再改录音记录
- 录音列表接口会直接返回 `preview_url / download_url`，前端无需再手工拼接本地路径
- 转写分段接口会返回 `speaker_role`，前端可直接按“客服 / 客户”聊天记录样式展示

## 关键接口示例

### 1. 登录

请求：

```http
POST /api/v1/auth/login
Content-Type: application/json
```

```json
{
  "captcha_key": "0d5b9c8f4c6140f4b9f9f6bf14b9d6b8",
  "captcha_code": "1234",
  "username": "admin",
  "password": "<YOUR_ADMIN_PASSWORD>"
}
```

响应：

```json
{
  "success": true,
  "message": "login_success",
  "data": {
    "access_token": "1419d6b1d43abc90ef4528f1e914a35b...",
    "token_type": "Bearer",
    "expires_in": 86400,
    "user": {
      "id": 1,
      "username": "admin",
      "display_name": "系统管理员",
      "status": "active",
      "role_codes": ["super_admin"]
    }
  }
}
```

### 2. 创建 SIP 线路

请求：

```http
POST /api/v1/trunks
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
```

```json
{
  "trunk_code": "demo_trunk_001",
  "trunk_name": "演示线路1",
  "server_host": "sip.demo.local",
  "server_port": 5060,
  "transport": "udp",
  "username": "demo_user",
  "password_cipher": "demo_pass",
  "auth_realm": "demo",
  "outbound_proxy": null,
  "from_user": "1001",
  "contact_user": "1001",
  "caller_id_number": "02112345678",
  "max_concurrency": 10,
  "cps_limit": 2,
  "register_enabled": true,
  "route_strategy": "single",
  "extra_config": {
    "note": "created_by_api"
  },
  "trunk_status": "draft"
}
```

### 3. 创建话术

请求：

```json
{
  "script_code": "script_demo_001",
  "script_name": "房产邀约话术",
  "business_type": "real_estate",
  "description": "房产邀约测试话术",
  "created_by": 1
}
```

### 4. 创建任务

请求：

```json
{
  "task_code": "task_demo_001",
  "task_name": "房产邀约任务",
  "task_type": "outbound",
  "script_id": 1,
  "script_version_id": 1,
  "trunk_id": 1,
  "trunk_ids": [1, 2, 3],
  "trunk_group_id": null,
  "batch_id": 1,
  "max_concurrency": 10,
  "cps_limit": 2,
  "retry_limit": 1,
  "retry_interval_seconds": 300,
  "call_time_range": {
    "start": "09:00",
    "end": "18:00"
  },
  "created_by": 1,
  "extra_config": {
    "note": "demo"
  }
}
```

### 5. 话术单步执行

请求：

```http
POST /api/v1/runtime/scripts/{script_version_id}/step
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
```

```json
{
  "current_node_code": null,
  "asr_text": "可以",
  "intent_code": null,
  "matched_keywords": ["可以"],
  "timeout": false,
  "silence": false,
  "nomatch": false,
  "variables": {}
}
```

响应：

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "current_node": {
      "node_code": "start_1",
      "node_type": "start"
    },
    "next_edge": {
      "edge_code": "edge_1",
      "condition_type": "always"
    },
    "next_node": {
      "node_code": "start_1",
      "node_type": "start"
    },
    "trace": [
      {
        "node_code": "start_1",
        "matched_edge_code": "edge_1",
        "next_node_code": "start_1"
      }
    ]
  }
}
```

### 6. 任务入队

请求：

```http
POST /api/v1/runtime/tasks/{task_id}/queue
Authorization: Bearer <ACCESS_TOKEN>
```

响应：

```json
{
  "success": true,
  "message": "queued",
  "data": {
    "task_id": 1,
    "total_contacts": 100,
    "created_dispatches": 100,
    "skipped_existing": 0
  }
}
```

### 7. 拉取待调度联系人

请求：

```http
GET /api/v1/runtime/tasks/{task_id}/dispatches/pending?limit=20
Authorization: Bearer <ACCESS_TOKEN>
```

### 8. 创建会话

请求：

```http
POST /api/v1/runtime/tasks/{task_id}/sessions
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
```

```json
{
  "dispatch_id": 1,
  "caller_number": "02100000000",
  "callee_number": "13800138000",
  "sip_call_id": "sip-test-001",
  "extra_meta": {
    "source": "runtime_test"
  }
}
```

### 9. 推进会话状态

请求：

```http
PATCH /api/v1/runtime/sessions/{session_id}/progress
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
```

```json
{
  "session_status": "completed",
  "answer_status": "answered",
  "current_node_code": "start_1",
  "hangup_cause": "NORMAL_CLEARING",
  "result_code": "SUCCESS",
  "intent_level": "A",
  "billsec": 12,
  "duration": 18,
  "event_type": "hangup",
  "payload": {
    "note": "runtime_test_done"
  }
}
```

## 常见错误码

| 错误码 | 说明 |
|---|---|
| `unauthorized` | 未登录或令牌无效 |
| `validation_error` | 请求参数校验失败 |
| `not_found` | 资源不存在 |
| `conflict` | 资源冲突 |
| `db_unique_violation` | 数据唯一约束冲突 |
| `db_foreign_key_violation` | 外键引用失败 |
| `db_check_violation` | 数据检查约束不通过 |
| `db_not_null_violation` | 缺少必填字段 |
| `internal_server_error` | 服务器内部错误 |
| `script_runtime_invalid` | 话术运行态参数或节点无效 |
| `task_queue_invalid` | 任务入队条件不满足 |
| `task_dispatch_invalid` | 调度拉取条件不满足 |
| `task_session_invalid` | 会话创建条件不满足 |

## 备注

- 当前接口大多已经具备增删改查能力，但仍属于 `平台基础接口阶段`
- 目前尚未实现基于角色的细粒度权限控制
- 当前已经实现基础运行态能力：
  - 话术单步执行
  - 话术全流程模拟
  - 任务入队
  - 待拨联系人拉取
  - 会话创建
  - 会话状态推进
- 当前仍未实现真正的外呼媒体流、SIP 对接执行器和实时流式 ASR 编排；但已支持在线 TTS 生成以及对可访问录音 URL 发起在线 ASR 转写
