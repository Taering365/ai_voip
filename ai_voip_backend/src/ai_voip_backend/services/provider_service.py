"""语音接口配置服务。"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import ssl
import uuid
from copy import deepcopy
from uuid import uuid4

import httpx
from psycopg import Connection
from websockets.asyncio.client import connect as websocket_connect

from ..errors import AppError
from ..api.schemas.provider import SpeechProviderCreateRequest, SpeechProviderUpdateRequest
from .common import jsonb_value, soft_delete_by_id


logger = logging.getLogger("ai_voip.provider")


DEFAULT_PROVIDER_DEFINITIONS = [
    {
        "provider_code": "default_asr_local_qwen_stream",
        "provider_name": "本地流式 ASR 默认接口",
        "provider_type": "asr",
        "driver_name": "qwen_stream_asr_http",
        "is_enabled": False,
        "config_json": {
            "vendor": "local",
            "interface_name": "本地流式 ASR",
            "protocol": "http",
            "auth_type": "none",
            "docs_url": "内部兼容 freeswitch_control 的 /start /chunk /finish 三段式流式 ASR 接口",
            "endpoint": "http://127.0.0.1:8000/api/asr/stream",
            "model": "qwen-stream-asr",
            "api_key": "local-http-no-key",
            "key_placeholder": "本地 ASR 默认无需密钥，如网关有鉴权可自行填写占位值",
            "custom_params": {
                "language": "Chinese",
                "context": "是,是的,是啊,是本人,是我,不是,不是本人,对,对的,对啊,可以,可以的,好的,好,嗯,在,在的,能听到,听得到,不需要,没兴趣",
                "chunk_size_sec": 0.24,
                "client_chunk_size_sec": 0.06,
                "unfixed_chunk_num": 1,
                "unfixed_token_num": 2,
                "vad": True,
                "denoise": True,
                "noise_threshold": 0.015,
                "sample_rate": 16000,
                "max_sentence_silence": 280,
            },
            "is_system_default": True,
        },
    },
    {
        "provider_code": "default_asr_aliyun_bailian",
        "provider_name": "阿里百炼 ASR 默认接口",
        "provider_type": "asr",
        "driver_name": "aliyun_bailian_asr_realtime_ws",
        "is_enabled": True,
        "config_json": {
            "vendor": "aliyun",
            "interface_name": "阿里百炼 ASR",
            "protocol": "websocket",
            "auth_type": "bearer",
            "docs_url": "https://help.aliyun.com/zh/model-studio/paraformer-real-time-speech-recognition-api",
            "endpoint": "wss://dashscope.aliyuncs.com/api-ws/v1/inference",
            "model": "paraformer-realtime-8k-v2",
            "api_key": "",
            "key_placeholder": "请填写阿里云百炼 API Key",
            "custom_params": {
                "language_hints": "zh,en",
                "sample_rate": 8000,
                "workspace_id": "",
                "semantic_punctuation_enabled": False,
                "max_sentence_silence": 400,
                "multi_threshold_mode_enabled": False,
                "disfluency_removal_enabled": True,
                "punctuation_prediction_enabled": True,
                "inverse_text_normalization_enabled": True,
                "heartbeat": False,
                "vocabulary_id": "",
            },
            "is_system_default": True,
        },
    },
    {
        "provider_code": "default_tts_minimax",
        "provider_name": "MiniMax TTS 默认接口",
        "provider_type": "tts",
        "driver_name": "minimax_tts_ws",
        "is_enabled": True,
        "config_json": {
            "vendor": "minimax",
            "interface_name": "MiniMax TTS",
            "protocol": "websocket",
            "auth_type": "bearer",
            "docs_url": "https://platform.minimaxi.com/docs/api-reference/speech-t2a-websocket",
            "endpoint": "wss://api.minimaxi.com/ws/v1/t2a_v2",
            "model": "speech-2.8-turbo",
            "api_key": "",
            "key_placeholder": "请填写 MiniMax API Key",
            "custom_params": {
                "language_boost": "Chinese",
                "voice_setting": {
                    "voice_id": "male-qn-qingse",
                    "speed": 1,
                    "vol": 1,
                    "pitch": 0,
                },
                "audio_setting": {
                    "sample_rate": 32000,
                    "bitrate": 128000,
                    "format": "mp3",
                    "channel": 1,
                },
            },
            "voice_profiles": [
                {
                    "value": "male-qn-qingse",
                    "label": "青涩男声",
                    "voice_id": "male-qn-qingse",
                    "voice_name": "青涩男声",
                    "speed": 1,
                },
                {
                    "value": "female-shaonv",
                    "label": "少女女声",
                    "voice_id": "female-shaonv",
                    "voice_name": "少女女声",
                    "speed": 1,
                },
            ],
            "default_voice_profile": "male-qn-qingse",
            "is_system_default": True,
        },
    },
]


SUPPORTED_PROVIDER_HEALTH_CHECK_DRIVERS = {
    "qwen_stream_asr_http",
    "aliyun_bailian_asr_realtime_ws",
    "aliyun_bailian_asr_file_transcription",
    "aliyun_bailian_asr_ws",
    "minimax_tts_ws",
}

LOCAL_STREAMING_ASR_DRIVERS = {"qwen_stream_asr_http"}
ALIYUN_STREAMING_ASR_DRIVERS = {
    "aliyun_bailian_asr_realtime_ws",
    "aliyun_bailian_asr_file_transcription",
    "aliyun_bailian_asr_ws",
}


def list_speech_providers(connection: Connection) -> list[dict]:
    """查询语音接口配置列表，并确保系统默认模板存在。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。

    返回:
        list[dict]: 语音接口配置字典列表。
    """

    ensure_default_speech_providers(connection)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, provider_code, provider_name, provider_type, driver_name,
                   is_enabled, config_json, created_at, updated_at
            FROM speech_provider
            WHERE deleted_at IS NULL
            ORDER BY
                CASE WHEN provider_type = 'asr' THEN 1 ELSE 2 END ASC,
                id ASC
            """
        )
        rows = cursor.fetchall()
    return [_build_provider_item(row) for row in rows]


def create_speech_provider(connection: Connection, payload: SpeechProviderCreateRequest) -> dict:
    """创建语音接口配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        payload: 创建语音接口配置的请求模型。

    返回:
        dict: 创建后的语音接口配置字典。
    """

    params = _build_provider_insert_params(payload)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO speech_provider (
                provider_code, provider_name, provider_type, driver_name,
                is_enabled, config_json
            ) VALUES (
                %(provider_code)s, %(provider_name)s, %(provider_type)s, %(driver_name)s,
                %(is_enabled)s, %(config_json)s
            )
            RETURNING id
            """,
            params,
        )
        provider_id = cursor.fetchone()[0]
    connection.commit()
    return get_speech_provider_by_id(connection, provider_id)  # type: ignore[return-value]


def get_speech_provider_by_id(connection: Connection, provider_id: int) -> dict | None:
    """按主键查询语音接口配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        provider_id: 接口配置主键。

    返回:
        dict | None: 找到记录时返回接口配置字典，否则返回 None。
    """

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, provider_code, provider_name, provider_type, driver_name,
                   is_enabled, config_json, created_at, updated_at
            FROM speech_provider
            WHERE deleted_at IS NULL
              AND id = %(provider_id)s
            LIMIT 1
            """,
            {"provider_id": provider_id},
        )
        row = cursor.fetchone()
    return _build_provider_item(row) if row else None


def update_speech_provider(
    connection: Connection,
    provider_id: int,
    payload: SpeechProviderUpdateRequest,
) -> dict | None:
    """更新语音接口配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        provider_id: 接口配置主键。
        payload: 更新语音接口配置的请求模型。

    返回:
        dict | None: 更新成功返回接口配置字典，否则返回 None。
    """

    current_item = get_speech_provider_by_id(connection, provider_id)
    if current_item is None:
        return None

    params = _build_provider_update_params(payload, current_item)
    params["provider_id"] = provider_id
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE speech_provider
            SET provider_name = %(provider_name)s,
                provider_type = %(provider_type)s,
                driver_name = %(driver_name)s,
                is_enabled = %(is_enabled)s,
                config_json = %(config_json)s,
                updated_at = NOW()
            WHERE id = %(provider_id)s
              AND deleted_at IS NULL
            """,
            params,
        )
        updated = cursor.rowcount > 0
    connection.commit()
    if not updated:
        return None
    return get_speech_provider_by_id(connection, provider_id)


def delete_speech_provider(connection: Connection, provider_id: int) -> bool:
    """软删除语音接口配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        provider_id: 接口配置主键。

    返回:
        bool: 删除成功返回 True，否则返回 False。
    """

    return soft_delete_by_id(connection, "speech_provider", provider_id)


def ensure_default_speech_providers(connection: Connection) -> None:
    """确保系统默认 ASR 与 TTS 接口模板存在。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。

    返回:
        None: 该函数只负责补齐默认配置，不返回业务数据。
    """

    changed = False
    with connection.cursor() as cursor:
        for definition in DEFAULT_PROVIDER_DEFINITIONS:
            cursor.execute(
                """
                SELECT id, deleted_at
                FROM speech_provider
                WHERE provider_code = %(provider_code)s
                LIMIT 1
                """,
                {"provider_code": definition["provider_code"]},
            )
            row = cursor.fetchone()
            config_json = jsonb_value(deepcopy(definition["config_json"]))
            if row is None:
                cursor.execute(
                    """
                    INSERT INTO speech_provider (
                        provider_code, provider_name, provider_type, driver_name,
                        is_enabled, config_json
                    ) VALUES (
                        %(provider_code)s, %(provider_name)s, %(provider_type)s, %(driver_name)s,
                        %(is_enabled)s, %(config_json)s
                    )
                    """,
                    {**definition, "config_json": config_json},
                )
                changed = True
                continue
            if row[1] is not None:
                cursor.execute(
                    """
                    UPDATE speech_provider
                    SET provider_name = %(provider_name)s,
                        provider_type = %(provider_type)s,
                        driver_name = %(driver_name)s,
                        is_enabled = %(is_enabled)s,
                        config_json = %(config_json)s,
                        deleted_at = NULL,
                        updated_at = NOW()
                    WHERE id = %(provider_id)s
                    """,
                    {
                        **definition,
                        "provider_id": row[0],
                        "config_json": config_json,
                    },
                )
                changed = True
    if changed:
        connection.commit()


def validate_speech_provider_health(provider_item: dict) -> dict:
    """检测指定语音接口的基础配置与连通状态。

    参数:
        provider_item: 当前待检测的语音接口配置字典。

    返回:
        dict: 返回检测结果字典，包含是否成功、接口摘要和服务端返回信息。
    """

    driver_name = str(provider_item.get("driver_name") or "").strip()
    if driver_name not in SUPPORTED_PROVIDER_HEALTH_CHECK_DRIVERS:
        raise AppError("provider_health_check_unsupported", f"暂不支持检测该接口驱动：{driver_name}")
    config_json = dict(provider_item.get("config_json") or {})
    api_key = str(config_json.get("api_key") or "").strip()
    endpoint = str(config_json.get("endpoint") or "").strip()
    if not endpoint:
        raise AppError("provider_endpoint_missing", "当前接口缺少 endpoint 配置")
    if driver_name not in LOCAL_STREAMING_ASR_DRIVERS and not api_key:
        raise AppError("provider_api_key_missing", "当前接口缺少 API Key，请先保存后再检测")
    if driver_name == "minimax_tts_ws":
        return asyncio.run(run_minimax_tts_health_check(provider_item))
    if driver_name in LOCAL_STREAMING_ASR_DRIVERS:
        normalized_local_item = normalize_runtime_asr_provider_item(provider_item)
        return asyncio.run(run_qwen_stream_asr_health_check(normalized_local_item))
    normalized_asr_item = normalize_realtime_asr_provider_item(provider_item)
    return asyncio.run(run_bailian_realtime_asr_health_check(normalized_asr_item))


def normalize_realtime_asr_provider_item(provider_item: dict) -> dict:
    """把数据库中的 ASR 配置归一化为阿里云实时 WebSocket ASR 配置。

    参数:
        provider_item: 当前数据库中的 ASR 接口配置字典。

    返回:
        dict: 返回可直接用于实时 ASR 检测或运行时接入的接口配置字典。
    """

    normalized_item = dict(provider_item)
    config_json = dict(provider_item.get("config_json") or {})
    custom_params = dict(config_json.get("custom_params") or {})
    driver_name = str(provider_item.get("driver_name") or "").strip()
    if driver_name == "aliyun_bailian_asr_realtime_ws":
        config_json["endpoint"] = str(config_json.get("endpoint") or "wss://dashscope.aliyuncs.com/api-ws/v1/inference").strip()
        config_json["model"] = str(config_json.get("model") or "paraformer-realtime-8k-v2").strip() or "paraformer-realtime-8k-v2"
        custom_params.setdefault("language_hints", "zh,en")
        custom_params.setdefault("sample_rate", 8000)
        custom_params.setdefault("workspace_id", "")
        custom_params.setdefault("semantic_punctuation_enabled", False)
        custom_params.setdefault("max_sentence_silence", 400)
        custom_params.setdefault("multi_threshold_mode_enabled", False)
        custom_params.setdefault("disfluency_removal_enabled", True)
        custom_params.setdefault("punctuation_prediction_enabled", True)
        custom_params.setdefault("inverse_text_normalization_enabled", True)
        custom_params.setdefault("heartbeat", False)
        custom_params.setdefault("vocabulary_id", "")
        config_json["custom_params"] = custom_params
        normalized_item["config_json"] = config_json
        return normalized_item
    if driver_name in {"aliyun_bailian_asr_file_transcription", "aliyun_bailian_asr_ws"}:
        config_json["endpoint"] = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
        config_json["protocol"] = "websocket"
        config_json["model"] = str(config_json.get("model") or "paraformer-realtime-8k-v2").strip() or "paraformer-realtime-8k-v2"
        if config_json["model"] in {"fun-asr", "qwen-asr-realtime"}:
            config_json["model"] = "paraformer-realtime-8k-v2"
        custom_params.setdefault("language_hints", "zh,en")
        custom_params.setdefault("sample_rate", 8000)
        custom_params.setdefault("workspace_id", "")
        custom_params.setdefault("semantic_punctuation_enabled", False)
        custom_params.setdefault("max_sentence_silence", 400)
        custom_params.setdefault("multi_threshold_mode_enabled", False)
        custom_params.setdefault("disfluency_removal_enabled", True)
        custom_params.setdefault("punctuation_prediction_enabled", True)
        custom_params.setdefault("inverse_text_normalization_enabled", True)
        custom_params.setdefault("heartbeat", False)
        custom_params.setdefault("vocabulary_id", "")
        config_json["custom_params"] = custom_params
        normalized_item["driver_name"] = "aliyun_bailian_asr_realtime_ws"
        normalized_item["config_json"] = config_json
        return normalized_item
    raise AppError("asr_driver_unsupported", f"当前接口不支持百炼实时 ASR 归一化：{driver_name}")


def normalize_runtime_asr_provider_item(provider_item: dict) -> dict:
    """把数据库中的 ASR 配置归一化为运行时可直接使用的实时 ASR 配置。

    参数:
        provider_item: 当前数据库中的 ASR 接口配置字典。

    返回:
        dict: 返回可直接用于运行时实时识别的接口配置字典。
    """

    driver_name = str(provider_item.get("driver_name") or "").strip()
    if driver_name in ALIYUN_STREAMING_ASR_DRIVERS:
        return normalize_realtime_asr_provider_item(provider_item)
    if driver_name in LOCAL_STREAMING_ASR_DRIVERS:
        normalized_item = dict(provider_item)
        config_json = dict(provider_item.get("config_json") or {})
        custom_params = dict(config_json.get("custom_params") or {})
        config_json["endpoint"] = str(config_json.get("endpoint") or "http://127.0.0.1:8000/api/asr/stream").strip()
        config_json["protocol"] = "http"
        config_json["model"] = str(config_json.get("model") or "qwen-stream-asr").strip() or "qwen-stream-asr"
        custom_params.setdefault("language", "Chinese")
        custom_params.setdefault(
            "context",
            "是,是的,是啊,是本人,是我,不是,不是本人,对,对的,对啊,可以,可以的,好的,好,嗯,在,在的,能听到,听得到,不需要,没兴趣",
        )
        custom_params.setdefault("chunk_size_sec", 0.24)
        custom_params.setdefault("client_chunk_size_sec", 0.06)
        custom_params.setdefault("unfixed_chunk_num", 1)
        custom_params.setdefault("unfixed_token_num", 2)
        custom_params.setdefault("vad", True)
        custom_params.setdefault("denoise", True)
        custom_params.setdefault("noise_threshold", 0.015)
        custom_params.setdefault("sample_rate", 16000)
        custom_params.setdefault("max_sentence_silence", 280)
        config_json["custom_params"] = custom_params
        normalized_item["config_json"] = config_json
        return normalized_item
    raise AppError("asr_driver_unsupported", f"当前接口不支持实时 ASR 归一化：{driver_name}")


def get_runtime_asr_driver_priority(driver_name: str) -> int:
    """返回实时 ASR 驱动的运行优先级。

    参数:
        driver_name: 当前接口驱动标识。

    返回:
        int: 返回驱动优先级数值，数值越小表示运行时越优先被选择。
    """

    normalized_driver_name = str(driver_name or "").strip()
    if normalized_driver_name in LOCAL_STREAMING_ASR_DRIVERS:
        return 0
    if normalized_driver_name in ALIYUN_STREAMING_ASR_DRIVERS:
        return 10
    return 99


async def run_bailian_realtime_asr_health_check(provider_item: dict) -> dict:
    """对阿里云实时 ASR WebSocket 接口执行连通性检测。

    参数:
        provider_item: 当前用于检测的 ASR 接口配置字典。

    返回:
        dict: 返回检测结果，包含服务端事件类型和关键摘要。
    """

    config_json = provider_item.get("config_json") or {}
    endpoint = build_aliyun_ws_asr_endpoint(config_json)
    api_key = str(config_json.get("api_key") or "").strip()
    ssl_context = ssl.create_default_context()
    headers = {"Authorization": f"Bearer {api_key}"}
    workspace_id = str(
        config_json.get("workspace_id")
        or (config_json.get("custom_params") or {}).get("workspace_id")
        or ""
    ).strip()
    if workspace_id:
        headers["X-DashScope-WorkSpace"] = workspace_id
    async with websocket_connect(
        endpoint,
        additional_headers=headers,
        ssl=ssl_context,
        max_size=8 * 1024 * 1024,
        ping_interval=20,
        ping_timeout=20,
    ) as websocket:
        task_id = uuid.uuid4().hex
        await websocket.send(json.dumps(build_aliyun_ws_run_task_payload(config_json, task_id), ensure_ascii=False))
        raw_message = await asyncio.wait_for(websocket.recv(), timeout=8)
        response_data = parse_provider_probe_message(raw_message)
        header = response_data.get("header") or {}
        response_type = str(header.get("event") or response_data.get("type") or "").strip()
        if response_type != "task-started":
            raise AppError("asr_health_check_failed", f"阿里云实时 ASR 检测失败，服务端返回事件：{response_type or 'unknown'}")
        await websocket.send(json.dumps(build_aliyun_ws_finish_task_payload(task_id), ensure_ascii=False))
        return {
            "ok": True,
            "provider_id": provider_item["id"],
            "provider_type": provider_item["provider_type"],
            "driver_name": provider_item["driver_name"],
            "endpoint": endpoint,
            "message": "ASR 实时接口连接成功",
            "server_event": response_type,
        }


async def run_qwen_stream_asr_health_check(provider_item: dict) -> dict:
    """对本地 Qwen 流式 HTTP ASR 接口执行最小可用性检测。

    参数:
        provider_item: 当前用于检测的本地 ASR 接口配置字典。

    返回:
        dict: 返回检测结果，包含接口摘要和服务端回包状态。
    """

    config_json = provider_item.get("config_json") or {}
    endpoint = build_qwen_stream_asr_base_url(config_json)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            start_response = await client.post(
                f"{endpoint}/start",
                json=build_qwen_stream_start_payload(config_json),
            )
            start_response.raise_for_status()
            start_data = start_response.json()
            session_id = str((start_data.get("data") or {}).get("session_id") or "").strip()
            if start_data.get("code") != 200 or not session_id:
                raise AppError("asr_health_check_failed", f"本地流式 ASR 检测失败，start 返回异常：{start_data}")
            finish_response = await client.post(
                f"{endpoint}/finish",
                json={"session_id": session_id},
            )
            finish_response.raise_for_status()
            finish_data = finish_response.json()
            if finish_data.get("code") != 200:
                raise AppError("asr_health_check_failed", f"本地流式 ASR 检测失败，finish 返回异常：{finish_data}")
            return {
                "ok": True,
                "provider_id": provider_item["id"],
                "provider_type": provider_item["provider_type"],
                "driver_name": provider_item["driver_name"],
                "endpoint": endpoint,
                "message": "本地流式 ASR 接口连接成功",
                "server_event": "http_start_finish_ok",
            }
    except AppError:
        raise
    except httpx.ConnectError as exc:
        # 连接失败通常表示本地 ASR 服务未启动、端口不通或 endpoint 写成了错误机器的 127.0.0.1。
        logger.error(
            "本地流式 ASR 健康检查连接失败: provider_id=%s driver=%s endpoint=%s detail=%r",
            provider_item.get("id"),
            provider_item.get("driver_name"),
            endpoint,
            exc,
            exc_info=True,
        )
        raise AppError(
            "asr_health_check_failed",
            f"本地流式 ASR 服务连接失败：{endpoint}，请检查服务是否启动、端口是否开放，以及 endpoint 是否为后端服务器可访问地址。",
        ) from exc
    except httpx.TimeoutException as exc:
        # 超时单独提示，便于运维区分网络不可达和服务响应过慢。
        logger.error(
            "本地流式 ASR 健康检查超时: provider_id=%s driver=%s endpoint=%s detail=%r",
            provider_item.get("id"),
            provider_item.get("driver_name"),
            endpoint,
            exc,
            exc_info=True,
        )
        raise AppError("asr_health_check_failed", f"本地流式 ASR 服务响应超时：{endpoint}，请检查服务负载和网络连通性。") from exc
    except httpx.HTTPStatusError as exc:
        # HTTP 状态异常说明服务有响应但协议或路径不符合预期。
        logger.error(
            "本地流式 ASR 健康检查 HTTP 状态异常: provider_id=%s driver=%s endpoint=%s status=%s detail=%r",
            provider_item.get("id"),
            provider_item.get("driver_name"),
            endpoint,
            exc.response.status_code if exc.response else "-",
            exc,
            exc_info=True,
        )
        raise AppError(
            "asr_health_check_failed",
            f"本地流式 ASR 服务返回异常状态：{exc.response.status_code if exc.response else 'unknown'}，请检查 endpoint 路径是否正确。",
        ) from exc
    except (ValueError, TypeError) as exc:
        # 返回体不是约定 JSON 时，转换成业务错误，避免前端只看到服务器 500。
        logger.error(
            "本地流式 ASR 健康检查返回体异常: provider_id=%s driver=%s endpoint=%s detail=%r",
            provider_item.get("id"),
            provider_item.get("driver_name"),
            endpoint,
            exc,
            exc_info=True,
        )
        raise AppError("asr_health_check_failed", f"本地流式 ASR 返回体无法解析，请检查服务协议是否兼容：{endpoint}") from exc


async def run_minimax_tts_health_check(provider_item: dict) -> dict:
    """对 MiniMax TTS WebSocket 接口执行基础连通性检测。

    参数:
        provider_item: 当前用于检测的 TTS 接口配置字典。

    返回:
        dict: 返回检测结果，包含服务端事件类型和关键摘要。
    """

    config_json = provider_item.get("config_json") or {}
    endpoint = str(config_json.get("endpoint") or "").strip()
    api_key = str(config_json.get("api_key") or "").strip()
    ssl_context = ssl.create_default_context()
    async with websocket_connect(
        endpoint,
        additional_headers={"Authorization": f"Bearer {api_key}"},
        ssl=ssl_context,
        max_size=None,
    ) as websocket:
        raw_message = await asyncio.wait_for(websocket.recv(), timeout=5)
        response_data = parse_provider_probe_message(raw_message)
        return {
            "ok": True,
            "provider_id": provider_item["id"],
            "provider_type": provider_item["provider_type"],
            "driver_name": provider_item["driver_name"],
            "endpoint": endpoint,
            "message": "TTS 接口连接成功",
            "server_event": str(response_data.get("event") or response_data.get("type") or "").strip() or "connected",
        }


def build_aliyun_ws_asr_endpoint(config_json: dict) -> str:
    """根据接口配置生成阿里云实时 ASR WebSocket 地址。

    参数:
        config_json: 当前 ASR 接口配置中的 `config_json` 字典。

    返回:
        str: 返回阿里云实时 ASR WebSocket 地址。
    """

    endpoint = str(config_json.get("endpoint") or "").strip()
    if not endpoint:
        raise AppError("asr_endpoint_missing", "当前实时 ASR 接口缺少 endpoint 配置")
    return endpoint


def build_qwen_stream_asr_base_url(config_json: dict) -> str:
    """根据接口配置生成本地流式 HTTP ASR 基础地址。

    参数:
        config_json: 当前 ASR 接口配置中的 `config_json` 字典。

    返回:
        str: 返回本地流式 HTTP ASR 基础地址。
    """

    endpoint = str(config_json.get("endpoint") or "").strip().rstrip("/")
    if not endpoint:
        raise AppError("asr_endpoint_missing", "当前本地流式 ASR 接口缺少 endpoint 配置")
    return endpoint


def build_qwen_stream_start_payload(config_json: dict) -> dict:
    """构造发送给本地流式 HTTP ASR `/start` 的请求体。

    参数:
        config_json: 当前 ASR 接口配置中的 `config_json` 字典。

    返回:
        dict: 返回可直接提交给本地 ASR `/start` 的请求参数。
    """

    custom_params = config_json.get("custom_params") or {}
    return {
        "language": str(custom_params.get("language") or "Chinese"),
        "chunk_size_sec": float(custom_params.get("chunk_size_sec") or 0.24),
        "context": str(custom_params.get("context") or ""),
        "unfixed_chunk_num": int(custom_params.get("unfixed_chunk_num") or 1),
        "unfixed_token_num": int(custom_params.get("unfixed_token_num") or 2),
        "vad": bool(custom_params.get("vad", True)),
        "denoise": bool(custom_params.get("denoise", True)),
        "noise_threshold": float(custom_params.get("noise_threshold") or 0.015),
        "max_sentence_silence": int(custom_params.get("max_sentence_silence") or custom_params.get("sentence_silence_ms") or 280),
    }


def build_qwen_stream_chunk_payload(session_id: str, audio_chunk: bytes) -> dict:
    """构造发送给本地流式 HTTP ASR `/chunk` 的请求体。

    参数:
        session_id: 当前本地 ASR 会话 ID。
        audio_chunk: 当前待提交的 PCM16LE 音频块。

    返回:
        dict: 返回可直接提交给本地 ASR `/chunk` 的请求参数。
    """

    return {
        "session_id": session_id,
        "audio_base64": base64.b64encode(audio_chunk).decode("utf-8"),
    }


def build_aliyun_ws_run_task_payload(config_json: dict, task_id: str) -> dict:
    """构造阿里云实时 ASR 检测用的 `run-task` 事件。

    参数:
        config_json: 当前 ASR 接口配置中的 `config_json` 字典。
        task_id: 当前识别任务 ID。

    返回:
        dict: 返回可直接发送到 WebSocket 的任务启动事件对象。
    """

    custom_params = config_json.get("custom_params") or {}
    parameters: dict[str, object] = {
        "format": "pcm",
        "sample_rate": int(custom_params.get("sample_rate") or 8000),
        "semantic_punctuation_enabled": bool(custom_params.get("semantic_punctuation_enabled", False)),
        "max_sentence_silence": int(custom_params.get("max_sentence_silence") or 400),
        "multi_threshold_mode_enabled": bool(custom_params.get("multi_threshold_mode_enabled", False)),
        "disfluency_removal_enabled": bool(custom_params.get("disfluency_removal_enabled", True)),
        "punctuation_prediction_enabled": bool(custom_params.get("punctuation_prediction_enabled", True)),
        "inverse_text_normalization_enabled": bool(custom_params.get("inverse_text_normalization_enabled", True)),
        "heartbeat": bool(custom_params.get("heartbeat", False)),
    }
    language_hints = build_aliyun_ws_language_hints(custom_params)
    if language_hints:
        parameters["language_hints"] = language_hints
    vocabulary_id = str(custom_params.get("vocabulary_id") or config_json.get("vocabulary_id") or "").strip()
    if vocabulary_id:
        parameters["vocabulary_id"] = vocabulary_id
    return {
        "header": {
            "action": "run-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {
            "task_group": "audio",
            "task": "asr",
            "function": "recognition",
            "model": str(config_json.get("model") or "paraformer-realtime-8k-v2").strip() or "paraformer-realtime-8k-v2",
            "parameters": parameters,
            "input": {},
        },
    }


def build_aliyun_ws_finish_task_payload(task_id: str) -> dict:
    """构造阿里云实时 ASR 检测用的 `finish-task` 事件。

    参数:
        task_id: 当前识别任务 ID。

    返回:
        dict: 返回可直接发送到 WebSocket 的任务结束事件对象。
    """

    return {
        "header": {
            "action": "finish-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {"input": {}},
    }


def build_aliyun_ws_language_hints(custom_params: dict) -> list[str]:
    """把阿里云实时 ASR 的语言提示字符串转换为数组。

    参数:
        custom_params: 当前 ASR 接口自定义参数字典。

    返回:
        list[str]: 返回去除空白项后的语言提示数组。
    """

    raw_value = str(custom_params.get("language_hints") or "").replace("，", ",")
    if not raw_value:
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def parse_provider_probe_message(raw_message: object) -> dict:
    """把接口检测返回的原始消息解析为统一字典结构。

    参数:
        raw_message: WebSocket 返回的原始消息对象。

    返回:
        dict: 返回解析后的消息字典，无法解析时抛出业务异常。
    """

    if isinstance(raw_message, dict):
        return raw_message
    if isinstance(raw_message, bytes):
        raw_message = raw_message.decode("utf-8")
    try:
        return json.loads(str(raw_message))
    except Exception as exc:  # noqa: BLE001
        raise AppError("provider_probe_invalid", f"接口检测返回了无法解析的消息：{exc!r}") from exc


def _build_provider_item(row: tuple) -> dict:
    """将语音接口配置查询结果转为响应字典。

    参数:
        row: 数据库单行元组数据。

    返回:
        dict: 适合接口层输出的语音接口配置字典。
    """

    return {
        "id": row[0],
        "provider_code": row[1],
        "provider_name": row[2],
        "provider_type": row[3],
        "driver_name": row[4],
        "is_enabled": row[5],
        "config_json": row[6],
        "created_at": row[7].isoformat(),
        "updated_at": row[8].isoformat(),
    }


def _build_provider_insert_params(payload: SpeechProviderCreateRequest) -> dict[str, object]:
    """构造新增语音接口配置的数据库参数。

    参数:
        payload: 前端提交的新增请求模型。

    返回:
        dict[str, object]: 可直接用于 SQL 的参数字典。
    """

    base_template = build_provider_template(payload.provider_type)
    merged_config = merge_provider_config(base_template["config_json"], payload.config_json)
    return {
        "provider_code": payload.provider_code.strip() or build_provider_code(payload.provider_type),
        "provider_name": payload.provider_name.strip(),
        "provider_type": payload.provider_type,
        "driver_name": payload.driver_name.strip() or str(base_template["driver_name"]),
        "is_enabled": payload.is_enabled,
        "config_json": jsonb_value(merged_config),
    }


def _build_provider_update_params(payload: SpeechProviderUpdateRequest, current_item: dict) -> dict[str, object]:
    """构造更新语音接口配置的数据库参数。

    参数:
        payload: 前端提交的更新请求模型。
        current_item: 当前数据库中已存在的接口配置对象。

    返回:
        dict[str, object]: 可直接用于 SQL 的参数字典。
    """

    base_template = build_provider_template(payload.provider_type)
    current_config = current_item.get("config_json") or {}
    merged_config = merge_provider_config(base_template["config_json"], {**current_config, **payload.config_json})
    return {
        "provider_name": payload.provider_name.strip(),
        "provider_type": payload.provider_type,
        "driver_name": payload.driver_name.strip() or str(base_template["driver_name"]),
        "is_enabled": payload.is_enabled,
        "config_json": jsonb_value(merged_config),
    }


def build_provider_template(provider_type: str) -> dict[str, object]:
    """按接口类型返回默认模板定义。

    参数:
        provider_type: 接口类型，仅支持 asr 或 tts。

    返回:
        dict[str, object]: 默认模板定义对象，包含驱动名与默认配置。
    """

    matched_item = next((item for item in DEFAULT_PROVIDER_DEFINITIONS if item["provider_type"] == provider_type), None)
    if matched_item is None:
        raise ValueError(f"不支持的接口类型: {provider_type}")
    return deepcopy(matched_item)


def merge_provider_config(base_config: dict, override_config: dict) -> dict:
    """把默认模板配置与用户自定义配置进行合并。

    参数:
        base_config: 系统默认模板配置。
        override_config: 用户输入或数据库已有的配置内容。

    返回:
        dict: 合并后的最终配置对象。
    """

    merged_config = deepcopy(base_config)
    for key, value in (override_config or {}).items():
        if isinstance(value, dict) and isinstance(merged_config.get(key), dict):
            merged_config[key] = {**merged_config[key], **value}
        else:
            merged_config[key] = value
    return merged_config


def build_provider_code(provider_type: str) -> str:
    """生成新的语音接口配置编码。

    参数:
        provider_type: 接口类型，用于拼接编码前缀。

    返回:
        str: 自动生成的唯一接口编码。
    """

    return f"{provider_type}_{uuid4().hex[:24]}"
