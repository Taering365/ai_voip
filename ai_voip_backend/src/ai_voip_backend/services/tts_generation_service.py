"""TTS 在线语音生成服务。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import ssl
import tempfile
from datetime import datetime
from pathlib import Path

from psycopg import Connection
from websockets.asyncio.client import connect as websocket_connect

from ..api.schemas.media import AudioAssetCreateRequest, AudioAssetGenerateTtsRequest
from ..errors import AppError
from .media_service import create_audio_asset
from .provider_service import get_speech_provider_by_id, list_speech_providers
from .storage_service import build_storage_provider, get_default_storage_profile, resolve_storage_target_key


SUPPORTED_ONLINE_TTS_DRIVERS = {"minimax_tts_ws"}


def generate_tts_audio_asset(
    connection: Connection,
    payload: AudioAssetGenerateTtsRequest,
    project_root: Path,
    created_by: int,
) -> dict:
    """根据文案生成一条在线 TTS 音频资源记录。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        payload: TTS 生成请求模型，包含文案与可选的接口选择信息。
        project_root: 当前后端项目根目录，用于解析本地缓存存储路径。
        created_by: 当前登录用户主键，用于写入音频资源创建人字段。

    返回:
        dict: 返回生成完成后的音频资源详情字典。
    """

    provider_item = resolve_tts_provider_item(connection, payload.tts_provider_id)
    voice_profile = resolve_voice_profile(provider_item, payload.tts_voice_profile)
    output_format = resolve_output_format(provider_item)
    output_filename = build_output_filename(payload.prompt_text, output_format)
    storage_profile, storage_provider, storage_profile_id = resolve_target_storage(connection, project_root)
    relative_storage_key = resolve_storage_target_key(storage_profile, "tts_cache", output_filename)
    with tempfile.NamedTemporaryFile(suffix=f".{output_format}", delete=False) as temp_file:
        temp_file_path = Path(temp_file.name)

    run_tts_generation(provider_item, voice_profile, payload.prompt_text, temp_file_path)
    generated_file_size = temp_file_path.stat().st_size
    generated_file_hash = compute_file_hash_from_path_or_bytes(str(temp_file_path), None)
    with temp_file_path.open("rb") as file_stream:
        saved_object = storage_provider.save(file_stream, relative_storage_key)
    temp_file_path.unlink(missing_ok=True)

    created_asset = create_audio_asset(
        connection,
        AudioAssetCreateRequest(
            asset_code=f"tts_cache_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            asset_name=payload.asset_name or build_default_asset_name(payload.prompt_text),
            asset_type="tts_cache",
            storage_profile_id=storage_profile_id,
            storage_backend=saved_object.storage_backend,
            storage_key=saved_object.storage_key,
            local_path=saved_object.local_path,
            object_key=saved_object.object_key,
            file_hash=generated_file_hash,
            mime_type=resolve_mime_type(output_format),
            file_size=generated_file_size,
            duration_ms=None,
            sample_rate=resolve_sample_rate(provider_item),
            channels=payload.channels,
            asset_status="active",
            tags=["tts_cache", "generated", "online_tts"],
            extra_meta={
                "prompt_text": payload.prompt_text,
                "tts_provider_id": provider_item["id"],
                "tts_provider_name": provider_item["provider_name"],
                "tts_driver_name": provider_item["driver_name"],
                "tts_voice_profile": voice_profile.get("profile_value"),
                "voice_name": voice_profile.get("voice_name"),
                "voice_id": voice_profile.get("voice_id"),
                "rate": voice_profile.get("rate"),
                "audio_format": output_format,
            },
            created_by=created_by,
        ),
    )
    return created_asset


def resolve_tts_provider_item(connection: Connection, provider_id: int | None) -> dict:
    """解析当前请求应使用的在线 TTS 接口配置。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        provider_id: 前端提交的接口主键，可为空。

    返回:
        dict: 返回匹配到的在线 TTS 接口配置字典。
    """

    if provider_id:
        provider_item = get_speech_provider_by_id(connection, provider_id)
        if provider_item is None or provider_item["provider_type"] != "tts" or not provider_item["is_enabled"]:
            raise AppError("tts_provider_invalid", "所选 TTS 接口不存在或未启用")
        validate_online_tts_provider(provider_item)
        return provider_item

    available_items = []
    for item in list_speech_providers(connection):
        if item["provider_type"] != "tts" or not item["is_enabled"]:
            continue
        try:
            validate_online_tts_provider(item)
            available_items.append(item)
        except AppError:
            continue
    if not available_items:
        raise AppError("tts_provider_missing", "未找到可用的在线 TTS 接口，请先在“语音接口”中配置有效密钥")
    return available_items[0]


def validate_online_tts_provider(provider_item: dict) -> None:
    """校验在线 TTS 接口配置是否满足调用条件。

    参数:
        provider_item: 当前待校验的接口配置字典。

    返回:
        None: 校验通过时不返回内容，失败时抛出业务异常。
    """

    driver_name = str(provider_item.get("driver_name") or "")
    if driver_name not in SUPPORTED_ONLINE_TTS_DRIVERS:
        raise AppError("tts_driver_unsupported", f"当前仅支持在线 TTS 驱动，暂不支持 {driver_name}")
    config_json = provider_item.get("config_json") or {}
    if not str(config_json.get("endpoint") or "").strip():
        raise AppError("tts_endpoint_missing", "当前 TTS 接口缺少 endpoint 配置")
    if not str(config_json.get("api_key") or "").strip():
        raise AppError("tts_api_key_missing", "当前 TTS 接口缺少 API Key，请先完成接口配置")


def resolve_voice_profile(provider_item: dict, selected_profile: str | None) -> dict:
    """从接口配置中解析本次生成应使用的音色方案。

    参数:
        provider_item: 当前选中的 TTS 接口配置字典。
        selected_profile: 前端提交的音色方案值，可为空。

    返回:
        dict: 返回整理后的音色方案字典，至少包含 voice_id、voice_name、rate 等字段。
    """

    config_json = provider_item.get("config_json") or {}
    profile_items = config_json.get("voice_profiles") or config_json.get("voices") or config_json.get("voice_options") or []
    normalized_items = [normalize_voice_profile_item(item) for item in profile_items if normalize_voice_profile_item(item)]
    default_profile_value = selected_profile or config_json.get("default_voice_profile") or config_json.get("default_voice")
    if default_profile_value:
        matched_item = next((item for item in normalized_items if item["profile_value"] == str(default_profile_value)), None)
        if matched_item:
            return matched_item
    if normalized_items:
        return normalized_items[0]

    custom_params = config_json.get("custom_params") or {}
    voice_setting = custom_params.get("voice_setting") or {}
    default_voice_id = str(voice_setting.get("voice_id") or config_json.get("default_voice") or "male-qn-qingse")
    return {
        "profile_value": default_voice_id,
        "voice_name": default_voice_id,
        "voice_id": default_voice_id,
        "rate": float(voice_setting.get("speed") or 1),
    }


def normalize_voice_profile_item(raw_item: object) -> dict | None:
    """将接口配置中的音色项规范化为统一结构。

    参数:
        raw_item: 接口配置中的单条音色项，可能是字符串或字典。

    返回:
        dict | None: 返回规范化后的音色方案字典，无法识别时返回 None。
    """

    if isinstance(raw_item, str):
        return {
            "profile_value": raw_item,
            "voice_name": raw_item,
            "voice_id": raw_item,
            "rate": 1,
        }
    if not isinstance(raw_item, dict):
        return None
    profile_value = str(raw_item.get("value") or raw_item.get("profile_id") or raw_item.get("voice_id") or raw_item.get("id") or "")
    voice_name = str(raw_item.get("voice_name") or raw_item.get("name") or raw_item.get("label") or profile_value or "默认音色")
    if not profile_value:
        profile_value = voice_name
    return {
        "profile_value": profile_value,
        "voice_name": voice_name,
        "voice_id": str(raw_item.get("voice_id") or profile_value),
        "rate": float(raw_item.get("rate") or raw_item.get("speed") or 1),
        "pitch": raw_item.get("pitch"),
        "volume": raw_item.get("vol") or raw_item.get("volume"),
    }


def resolve_target_storage(connection: Connection, project_root: Path) -> tuple[dict, object, int | None]:
    """解析本次生成应使用的目标存储配置和存储提供者。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        project_root: 当前后端项目根目录。

    返回:
        tuple[dict, object, int | None]: 返回存储配置对象、存储提供者实例和存储配置主键。
    """

    storage_profile = get_default_storage_profile(connection)
    if storage_profile is None:
        storage_profile = {
            "id": None,
            "storage_backend": "local",
            "root_dir": str((project_root / "data/recorder").resolve()),
            "extra_config": {"subdirectories": {"tts_cache": "tts_cache"}},
        }
    storage_provider = build_storage_provider(storage_profile, project_root)
    return storage_profile, storage_provider, storage_profile.get("id")


def build_output_filename(prompt_text: str, output_format: str) -> str:
    """根据文案内容生成稳定且唯一的输出文件名。

    参数:
        prompt_text: 当前需要生成音频的文案内容。
        output_format: 当前接口要求输出的音频格式，例如 mp3 或 wav。

    返回:
        str: 返回带扩展名的缓存文件名。
    """

    digest = hashlib.sha1(f"{prompt_text}-{datetime.now().isoformat()}".encode("utf-8")).hexdigest()[:16]
    safe_extension = output_format.lower().strip() or "mp3"
    return f"tts_{digest}.{safe_extension}"


def build_default_asset_name(prompt_text: str) -> str:
    """根据播报文案生成默认音频名称。

    参数:
        prompt_text: 当前需要生成音频的文案内容。

    返回:
        str: 返回适合在音频库中展示的音频名称。
    """

    display_text = prompt_text.strip().replace("\n", " ")
    return f"TTS录音_{display_text[:18] or '未命名'}"


def resolve_output_format(provider_item: dict) -> str:
    """从接口配置中解析输出音频格式。

    参数:
        provider_item: 当前选中的 TTS 接口配置字典。

    返回:
        str: 当前应输出的音频扩展名。
    """

    config_json = provider_item.get("config_json") or {}
    custom_params = config_json.get("custom_params") or {}
    audio_setting = custom_params.get("audio_setting") or {}
    return str(audio_setting.get("format") or "mp3").lower()


def resolve_mime_type(output_format: str) -> str:
    """根据输出格式解析音频 MIME 类型。

    参数:
        output_format: 当前音频扩展名。

    返回:
        str: 对应的 MIME 类型字符串。
    """

    mime_map = {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "pcm": "audio/pcm",
        "flac": "audio/flac",
    }
    return mime_map.get(output_format.lower(), "application/octet-stream")


def resolve_sample_rate(provider_item: dict) -> int | None:
    """从接口配置中解析输出采样率。

    参数:
        provider_item: 当前选中的 TTS 接口配置字典。

    返回:
        int | None: 配置中存在采样率时返回整数，否则返回 None。
    """

    config_json = provider_item.get("config_json") or {}
    custom_params = config_json.get("custom_params") or {}
    audio_setting = custom_params.get("audio_setting") or {}
    sample_rate = audio_setting.get("sample_rate") or audio_setting.get("audio_sample_rate")
    return int(sample_rate) if sample_rate else None


def run_tts_generation(provider_item: dict, voice_profile: dict, prompt_text: str, output_path: Path) -> None:
    """执行真实的在线 TTS 合成并将结果写入缓存文件。

    参数:
        provider_item: 当前选中的 TTS 接口配置字典。
        voice_profile: 当前解析出的音色方案字典。
        prompt_text: 需要合成的播报文案。
        output_path: 本地缓存输出文件绝对路径。

    返回:
        None: 该函数只负责生成并落盘音频文件。
    """

    if prompt_text.strip() == "":
        raise AppError("tts_prompt_empty", "播报文案不能为空")

    driver_name = str(provider_item.get("driver_name") or "")
    if driver_name == "minimax_tts_ws":
        asyncio.run(run_minimax_tts_generation(provider_item, voice_profile, prompt_text, output_path))
        return

    raise AppError("tts_driver_unsupported", f"暂不支持的在线 TTS 驱动：{driver_name}")


async def run_minimax_tts_generation(
    provider_item: dict,
    voice_profile: dict,
    prompt_text: str,
    output_path: Path,
) -> None:
    """通过 MiniMax WebSocket 接口执行在线 TTS 合成。

    参数:
        provider_item: 当前选中的 MiniMax TTS 接口配置字典。
        voice_profile: 当前解析出的音色方案字典。
        prompt_text: 需要合成的播报文案。
        output_path: 本地缓存输出文件绝对路径。

    返回:
        None: 该函数只负责生成并落盘音频文件。
    """

    config_json = provider_item.get("config_json") or {}
    endpoint = str(config_json.get("endpoint") or "").strip()
    api_key = str(config_json.get("api_key") or "").strip()
    model_name = str(config_json.get("model") or "speech-2.8-turbo").strip()
    custom_params = config_json.get("custom_params") or {}
    voice_setting = build_minimax_voice_setting(custom_params, voice_profile)
    start_message = build_minimax_start_message(model_name, custom_params, voice_setting)
    continue_message = {"event": "task_continue", "text": prompt_text}
    finish_message = {"event": "task_finish"}
    ssl_context = ssl.create_default_context()
    audio_chunks: list[bytes] = []

    try:
        async with websocket_connect(
            endpoint,
            additional_headers={"Authorization": f"Bearer {api_key}"},
            ssl=ssl_context,
            max_size=None,
        ) as websocket:
            await receive_minimax_message(websocket)
            await websocket.send(json.dumps(start_message, ensure_ascii=False))
            await wait_minimax_task_started(websocket)
            await websocket.send(json.dumps(continue_message, ensure_ascii=False))
            while True:
                response = await receive_minimax_message(websocket)
                audio_bytes = extract_minimax_audio_bytes(response)
                if audio_bytes:
                    audio_chunks.append(audio_bytes)
                if response.get("event") == "task_failed":
                    raise AppError("tts_generation_failed", f"MiniMax TTS 生成失败：{extract_minimax_error_message(response)}")
                if response.get("event") == "task_finished" or response.get("is_final") is True:
                    break
            await websocket.send(json.dumps(finish_message, ensure_ascii=False))
    except AppError:
        raise
    except Exception as exc:
        raise AppError("tts_generation_failed", f"MiniMax TTS 调用失败：{exc!r}") from exc

    if not audio_chunks:
        raise AppError("tts_generation_empty", "MiniMax TTS 未返回有效音频数据")

    output_path.write_bytes(b"".join(audio_chunks))


def build_minimax_voice_setting(custom_params: dict, voice_profile: dict) -> dict:
    """构造 MiniMax WebSocket 请求中的音色参数。

    参数:
        custom_params: 接口配置中的自定义参数对象。
        voice_profile: 当前选中的音色方案对象。

    返回:
        dict: 可直接用于 task_start 的 voice_setting 参数。
    """

    base_voice_setting = dict(custom_params.get("voice_setting") or {})
    if voice_profile.get("voice_id"):
        base_voice_setting["voice_id"] = voice_profile["voice_id"]
    if voice_profile.get("rate") is not None:
        base_voice_setting["speed"] = voice_profile["rate"]
    if voice_profile.get("pitch") is not None:
        base_voice_setting["pitch"] = voice_profile["pitch"]
    if voice_profile.get("volume") is not None:
        base_voice_setting["vol"] = voice_profile["volume"]
    return base_voice_setting


def build_minimax_start_message(model_name: str, custom_params: dict, voice_setting: dict) -> dict:
    """构造 MiniMax WebSocket 的 task_start 请求体。

    参数:
        model_name: 当前接口配置中的模型名称。
        custom_params: 接口配置中的自定义参数对象。
        voice_setting: 当前请求最终使用的音色参数对象。

    返回:
        dict: 可直接发送给 MiniMax WebSocket 的启动消息体。
    """

    start_message = {
        "event": "task_start",
        "model": model_name,
        "voice_setting": voice_setting,
    }
    for key, value in custom_params.items():
        if key == "voice_setting":
            continue
        start_message[key] = value
    return start_message


async def wait_minimax_task_started(websocket) -> None:
    """等待 MiniMax 返回任务启动成功消息。

    参数:
        websocket: 当前已建立的 WebSocket 客户端连接对象。

    返回:
        None: 启动成功时直接返回，失败时抛出业务异常。
    """

    while True:
        response = await receive_minimax_message(websocket)
        if response.get("event") == "task_started":
            return
        if response.get("event") == "task_failed":
            raise AppError("tts_generation_failed", f"MiniMax TTS 启动失败：{extract_minimax_error_message(response)}")


async def receive_minimax_message(websocket) -> dict:
    """从 MiniMax WebSocket 中接收并解析单条 JSON 消息。

    参数:
        websocket: 当前已建立的 WebSocket 客户端连接对象。

    返回:
        dict: 解析后的响应 JSON 对象。
    """

    raw_message = await websocket.recv()
    if isinstance(raw_message, bytes):
        raw_message = raw_message.decode("utf-8")
    try:
        return json.loads(raw_message)
    except json.JSONDecodeError as exc:
        raise AppError("tts_generation_failed", f"MiniMax TTS 返回了无法解析的消息：{raw_message}") from exc


def extract_minimax_audio_bytes(response: dict) -> bytes | None:
    """从 MiniMax 响应中提取十六进制音频块并转换为字节串。

    参数:
        response: 当前收到的 MiniMax 响应 JSON 对象。

    返回:
        bytes | None: 提取成功时返回音频字节串，否则返回 None。
    """

    data = response.get("data") or {}
    if not isinstance(data, dict):
        return None
    audio_hex = data.get("audio")
    if not audio_hex:
        return None
    try:
        return bytes.fromhex(str(audio_hex))
    except ValueError as exc:
        raise AppError("tts_generation_failed", "MiniMax TTS 返回的音频片段格式不正确") from exc


def extract_minimax_error_message(response: dict) -> str:
    """从 MiniMax 错误响应中提取可读错误信息。

    参数:
        response: 当前收到的 MiniMax 响应 JSON 对象。

    返回:
        str: 面向前端展示的错误描述。
    """

    if response.get("error_msg"):
        return str(response["error_msg"])
    if response.get("message"):
        return str(response["message"])
    if isinstance(response.get("data"), dict) and response["data"].get("error_msg"):
        return str(response["data"]["error_msg"])
    return "未知错误"


def compute_file_hash_from_path_or_bytes(file_path: str | None, file_bytes: bytes | None) -> str | None:
    """计算目标文件或字节内容的 SHA256 哈希值。

    参数:
        file_path: 已生成的本地音频文件路径，可能为空。
        file_bytes: 已生成的二进制内容，当前未提供时可为空。

    返回:
        str | None: 返回文件内容对应的十六进制 SHA256 值；无法计算时返回 None。
    """

    if file_path is None and file_bytes is None:
        return None
    digest = hashlib.sha256()
    if file_path is not None:
        path_object = Path(file_path)
        with path_object.open("rb") as file_stream:
            while True:
                chunk = file_stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    else:
        digest.update(file_bytes or b"")
    return digest.hexdigest()
