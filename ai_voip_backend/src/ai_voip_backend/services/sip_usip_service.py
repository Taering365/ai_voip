"""基于 uSIP 的 SIP 外呼执行器。"""

from __future__ import annotations

import asyncio
import base64
import importlib
import io
import json
import logging
import queue
import random
import re
import socket
import ssl
import struct
import subprocess
import threading
import time
import uuid
import wave
import audioop
import httpx
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from psycopg import Connection
from websockets.asyncio.client import connect as websocket_connect

from ..config import SipRuntimeConfig
from ..db import connect_db
from ..errors import AppError
from .provider_service import (
    build_qwen_stream_asr_base_url,
    build_qwen_stream_chunk_payload,
    build_qwen_stream_start_payload,
    get_runtime_asr_driver_priority,
    list_speech_providers,
    normalize_runtime_asr_provider_item,
)
from .runtime_service import progress_call_session
from .task_service import get_call_task_by_id
from .trunk_service import get_trunk_password_by_id


@dataclass(slots=True)
class RegistrationTracker:
    """记录单个 SIP 客户端的注册状态。

    属性:
        finished_event: 注册流程结束时触发的事件对象。
        current_state: 当前注册状态字符串，例如 REGISTERING、REGISTERED、FAILED。
        detail: 当前注册过程的附加描述信息，便于记录日志和错误原因。
    """

    finished_event: threading.Event = field(default_factory=threading.Event)
    current_state: str | None = None
    detail: str | None = None


@dataclass(slots=True)
class CallTracker:
    """记录单通呼叫的实时状态。

    属性:
        call_id: 当前呼叫在 SIP 库中的唯一标识。
        connected_event: 通话接通时触发的事件对象。
        finished_event: 通话结束时触发的事件对象。
        current_state: 当前呼叫状态字符串，例如 CALLING、RINGING、CONNECTED。
        last_reported_state: 最近一次已经写入数据库的呼叫状态，防止重复回写。
        answer_timestamp: 当前通话首次接通的时间戳。
        end_timestamp: 当前通话结束的时间戳。
        end_reason: 当前通话结束原因或库返回的错误说明。
        remote_rtp_address: 当前通话对端 RTP 地址与协商编码信息，格式为 (host, port, payload_type, codec_name)。
        local_rtp_port: 当前通话本地用于发送 RTP 的端口。
        rtp_socket: 当前通话复用的 RTP 套接字对象，用于同时发送和接收媒体。
        inbound_audio_frames: 当前已接收到的上行音频包数量。
        inbound_audio_bytes: 当前已累计接收到的上行音频原始字节数。
        inbound_pcm_bytes: 当前已解码得到的上行 PCM 音频字节数组。
        outbound_pcm_bytes: 当前已按通话时间轴累计的下行播报 PCM 音频字节数组。
        audio_timeline_started_at: 当前通话录音时间轴起点时间戳，首次收发音频时初始化。
    """

    call_id: str | None = None
    connected_event: threading.Event = field(default_factory=threading.Event)
    finished_event: threading.Event = field(default_factory=threading.Event)
    current_state: str | None = None
    last_reported_state: str | None = None
    answer_timestamp: float | None = None
    end_timestamp: float | None = None
    end_reason: str | None = None
    remote_rtp_address: tuple[str, int, int, str] | None = None
    local_rtp_port: int | None = None
    rtp_socket: Any | None = None
    inbound_audio_frames: int = 0
    inbound_audio_bytes: int = 0
    inbound_pcm_bytes: bytearray = field(default_factory=bytearray)
    outbound_pcm_bytes: bytearray = field(default_factory=bytearray)
    audio_timeline_started_at: float | None = None


@dataclass(slots=True)
class RealtimeAsrTracker:
    """记录单次识别窗口内实时 ASR WebSocket 会话状态。

    属性:
        started_event: 阿里云实时 ASR 返回 `task-started` 后触发的事件对象。
        completed_event: 阿里云实时 ASR 返回 `task-finished` 或 `task-failed` 后触发的事件对象。
        stop_event: 本地停止继续送音后触发的事件对象。
        audio_queue: 待发送到百炼 WebSocket 的 PCM 音频块队列。
        partial_text: 当前识别中的中间文本。
        final_text: 当前识别窗口内最终文本。
        submitted_audio_bytes: 当前已提交到百炼的 PCM 字节数。
        submitted_audio_frames: 当前已提交到百炼的音频块数量。
        latest_text_event: 当前收到新的识别文本后触发的事件对象，便于发送线程短暂等待增量结果。
        latest_result_index: 当前已收到的识别结果序号，用于判断某个音频块发送后是否产生新文本。
        latest_result_at: 最近一次收到识别文本的时间戳，用于判断识别结果是否已经稳定。
        task_id: 当前阿里云实时识别任务 ID，供收尾时发送 `finish-task` 复用。
        driver_name: 当前实时 ASR 会话使用的驱动标识，便于按不同引擎应用不同收尾策略。
        client_chunk_bytes: 当前实时 ASR 会话每次向识别引擎提交的 PCM 字节块大小。
        local_vad_min_speech_ms: 本地 HTTP ASR 模式下，判定用户已经开口所需的最小时长。
        local_vad_silence_ms: 本地 HTTP ASR 模式下，判定一句话已结束所需的静音时长。
        local_vad_speech_active: 本地 HTTP ASR 模式下，当前是否已进入语音段。
        local_vad_speech_ms: 本地 HTTP ASR 模式下，当前语音段累计的有效说话时长。
        local_vad_silence_ms_accumulated: 本地 HTTP ASR 模式下，当前语音段尾部累计的静音时长。
        local_segment_finalize_ready: 本地 HTTP ASR 模式下，当前语音段是否已满足立即收尾条件。
        speech_started: 服务端是否已识别到语音开始。
        error_message: 当前 WebSocket 会话内捕获到的错误说明。
        worker_thread: 后台 WebSocket 线程对象，便于收尾时等待退出。
    """

    started_event: threading.Event = field(default_factory=threading.Event)
    completed_event: threading.Event = field(default_factory=threading.Event)
    stop_event: threading.Event = field(default_factory=threading.Event)
    audio_queue: queue.Queue[bytes] = field(default_factory=queue.Queue)
    partial_text: str = ""
    final_text: str = ""
    submitted_audio_bytes: int = 0
    submitted_audio_frames: int = 0
    latest_text_event: threading.Event = field(default_factory=threading.Event)
    latest_result_index: int = 0
    latest_result_at: float = 0.0
    task_id: str = ""
    driver_name: str = ""
    client_chunk_bytes: int = 3200
    local_vad_min_speech_ms: int = 80
    local_vad_silence_ms: int = 320
    local_vad_speech_active: bool = False
    local_vad_speech_ms: float = 0.0
    local_vad_silence_ms_accumulated: float = 0.0
    local_segment_finalize_ready: bool = False
    speech_started: bool = False
    error_message: str | None = None
    worker_thread: threading.Thread | None = None


class SipUsipExecutor:
    """封装基于 uSIP 的 SIP 外呼执行器。

    当前实现负责把任务调度、真实注册、真实拨号、实时状态回写和
    话术起始音频播放串联起来。若运行环境尚未安装 `sip_client/usip`
    依赖，执行器会抛出明确错误，避免任务静默失败。
    """

    def __init__(self, runtime_config: SipRuntimeConfig, project_root: Path, postgres_config) -> None:
        """初始化 SIP 外呼执行器。

        参数:
            runtime_config: SIP 运行时配置对象。
            project_root: 当前后端项目根目录。
            postgres_config: PostgreSQL 连接配置对象，供后台线程和回调线程回写状态时复用。

        返回:
            None: 构造函数仅完成执行器基础属性初始化。
        """

        self.runtime_config = runtime_config
        self.project_root = project_root
        self.postgres_config = postgres_config
        self.logger = logging.getLogger("ai_voip.sip")
        self._endpoint_lock = threading.Lock()
        self._endpoint_started = False
        self._usip_runtime: dict[str, Any] | None = None
        self._active_call_threads: dict[int, threading.Thread] = {}

    def ensure_ready(self) -> None:
        """确保当前执行器对应的 uSIP 运行时已准备就绪。

        返回:
            None: 准备完成后不返回业务数据，缺依赖时抛出异常。
        """

        with self._endpoint_lock:
            if self._endpoint_started:
                return
            self._usip_runtime = import_usip_runtime()
            self._endpoint_started = True
            self.logger.info("uSIP SIP 执行器已完成依赖检查，等待真实外呼任务")

    def submit_call_task(
        self,
        task_item: dict,
        session_item: dict,
        trunk_item: dict,
        playback_plan: list[dict],
        await_reply_config: dict | None = None,
    ) -> None:
        """提交一条真实外呼任务到后台线程中执行。

        参数:
            task_item: 当前外呼任务对象。
            session_item: 当前通话会话对象。
            trunk_item: 当前绑定的线路对象。
            playback_plan: 当前会话需要按顺序播放的音频计划列表。
            await_reply_config: 当前识别节点等待回复和兜底播放配置，可为空。

        返回:
            None: 提交成功后不返回业务数据，执行结果通过会话状态回写体现。
        """

        self.ensure_ready()
        worker_thread = threading.Thread(
            target=self._run_call_worker,
            args=(task_item, session_item, trunk_item, playback_plan, await_reply_config),
            daemon=True,
            name=f"sip-call-{session_item['id']}",
        )
        self._active_call_threads[session_item["id"]] = worker_thread
        worker_thread.start()

    def _run_call_worker(
        self,
        task_item: dict,
        session_item: dict,
        trunk_item: dict,
        playback_plan: list[dict],
        await_reply_config: dict | None,
    ) -> None:
        """在后台线程中执行单通真实 SIP 外呼与话术播放。

        参数:
            task_item: 当前外呼任务对象。
            session_item: 当前通话会话对象。
            trunk_item: 当前绑定的线路对象。
            playback_plan: 当前会话需要播放的音频动作数组。
            await_reply_config: 当前识别节点等待回复和兜底播放配置，可为空。

        返回:
            None: 执行结果通过数据库状态回写，不直接返回业务数据。
        """

        connection = connect_db(self.postgres_config)
        client = None
        call_tracker = CallTracker()
        try:
            if self._usip_runtime is None:
                raise AppError("usip_missing", "当前运行环境缺少 uSIP 依赖，无法执行真实 SIP 外呼")
            self.logger.info(
                "准备发起 SIP 外呼: task_id=%s session_id=%s callee=%s trunk_id=%s playback_count=%s",
                task_item["id"],
                session_item["id"],
                session_item["callee_number"],
                trunk_item["id"],
                len(playback_plan),
            )
            client = self._create_sip_client(connection, trunk_item)
            registration_tracker = RegistrationTracker()
            call_tracker.local_rtp_port = find_available_udp_port()
            call_tracker.rtp_socket = create_bound_rtp_socket(call_tracker.local_rtp_port)
            client.rtp_port = call_tracker.local_rtp_port
            self._bind_client_callbacks(client, session_item, registration_tracker, call_tracker)
            self._start_client(client)
            self._register_client_if_needed(client, trunk_item, registration_tracker)
            self._dial_call(client, session_item, trunk_item, call_tracker)
            self._wait_for_call_connected(session_item, call_tracker)
            self._playback_call_plan(connection, client, task_item, session_item, call_tracker, playback_plan)
            self._wait_for_reply_window(connection, task_item, session_item, call_tracker, await_reply_config)
            self._hangup_if_active(client, call_tracker)
            self._wait_for_call_finished(session_item, client, call_tracker)
        except Exception as exc:  # noqa: BLE001
            self.logger.error(
                "SIP 外呼执行失败: task_id=%s session_id=%s detail=%r",
                task_item["id"],
                session_item["id"],
                exc,
                exc_info=True,
            )
            progress_call_session(
                connection,
                session_item["id"],
                build_session_progress_payload(
                    session_status="failed",
                    answer_status="timeout",
                    result_code="sip_call_failed",
                    hangup_cause=str(exc),
                    event_type="system",
                    payload={"stage": "dial"},
                ),
            )
            if client is not None:
                with suppress(Exception):
                    self._hangup_if_active(client, call_tracker)
        finally:
            if client is not None:
                with suppress(Exception):
                    client.stop()
            if call_tracker.rtp_socket is not None:
                with suppress(Exception):
                    call_tracker.rtp_socket.close()
            with suppress(Exception):
                self._save_call_recording_if_available(connection, session_item, call_tracker)
            connection.close()
            self._active_call_threads.pop(session_item["id"], None)

    def _create_sip_client(self, connection: Connection, trunk_item: dict):
        """根据线路配置创建单次呼叫使用的 uSIP 客户端对象。

        参数:
            connection: 当前后台线程使用的 PostgreSQL 数据库连接对象。
            trunk_item: 当前绑定的线路对象。

        返回:
            Any: 返回已经实例化的 uSIP 客户端对象。
        """

        if self._usip_runtime is None:
            raise AppError("usip_missing", "当前运行环境缺少 uSIP 依赖，无法创建 SIP 客户端")
        sip_password = get_trunk_password_by_id(connection, trunk_item["id"])
        if trunk_item["trunk_type"] == "sip_account" and not sip_password:
            raise AppError("sip_password_missing", "当前 SIP 账号线路缺少密码配置")
        account = build_usip_account(
            runtime_objects=self._usip_runtime,
            trunk_item=trunk_item,
            sip_password=sip_password,
        )
        client_class = self._usip_runtime["SIPClient"]
        return client_class(account)

    def _bind_client_callbacks(
        self,
        client: Any,
        session_item: dict,
        registration_tracker: RegistrationTracker,
        call_tracker: CallTracker,
    ) -> None:
        """把 SIP 库的回调绑定到当前通话的状态跟踪器。

        参数:
            client: 当前单通呼叫使用的 uSIP 客户端对象。
            session_item: 当前通话会话对象。
            registration_tracker: 当前注册状态跟踪对象。
            call_tracker: 当前呼叫状态跟踪对象。

        返回:
            None: 绑定成功后不返回业务数据。
        """

        def on_registration_state(state: Any) -> None:
            """处理注册状态变化回调。

            参数:
                state: SIP 库回传的注册状态对象或枚举值。

            返回:
                None: 当前函数仅更新内存状态并输出日志。
            """

            normalized_state = normalize_usip_state_value(state)
            registration_tracker.current_state = normalized_state
            registration_tracker.detail = normalized_state
            self.logger.info(
                "SIP 注册状态变化: session_id=%s state=%s",
                session_item["id"],
                normalized_state,
            )
            if normalized_state in {"REGISTERED", "FAILED", "UNREGISTERED"}:
                registration_tracker.finished_event.set()

        def on_call_state(call_info: Any) -> None:
            """处理呼叫状态变化回调。

            参数:
                call_info: SIP 库回传的呼叫信息对象，通常包含 call_id、state、duration 等字段。

            返回:
                None: 当前函数仅更新内存状态并触发数据库会话回写。
            """

            call_id = str(getattr(call_info, "call_id", "") or "")
            if call_tracker.call_id and call_id and call_id != call_tracker.call_id:
                return
            if call_id and not call_tracker.call_id:
                call_tracker.call_id = call_id
            normalized_state = normalize_usip_state_value(getattr(call_info, "state", None))
            call_tracker.current_state = normalized_state
            if normalized_state == "CONNECTED" and call_tracker.answer_timestamp is None:
                call_tracker.answer_timestamp = time.time()
                call_tracker.connected_event.set()
            if normalized_state in {"DISCONNECTED", "FAILED", "BUSY"}:
                call_tracker.end_timestamp = time.time()
                call_tracker.end_reason = normalized_state
                call_tracker.finished_event.set()
            self._report_call_state_change(session_item["id"], call_tracker, normalized_state, call_info)

        def on_message(message: str, addr: str) -> None:
            """处理底层 SIP 报文回调并提取 SDP 中的远端 RTP 地址。

            参数:
                message: SIP 库回传的原始 SIP 文本报文。
                addr: SIP 库回传的消息来源地址字符串。

            返回:
                None: 当前函数仅负责解析远端媒体地址并更新本地跟踪状态。
            """

            del addr
            remote_rtp_address = extract_remote_rtp_address_from_sip_message(message, call_tracker.call_id)
            if remote_rtp_address:
                call_tracker.remote_rtp_address = remote_rtp_address
                self.logger.info(
                    "已解析远端 RTP 地址: session_id=%s call_id=%s remote=%s",
                    session_item["id"],
                    call_tracker.call_id,
                    remote_rtp_address,
                )

        client.on_registration_state = on_registration_state
        client.on_call_state = on_call_state
        client.on_message = on_message

    def _start_client(self, client: Any) -> None:
        """启动 uSIP 客户端底层网络与媒体资源。

        参数:
            client: 当前单通呼叫使用的 uSIP 客户端对象。

        返回:
            None: 启动成功后不返回业务数据，失败时抛出异常。
        """

        start_result = client.start()
        if start_result is False:
            raise AppError("usip_start_failed", "uSIP 客户端启动失败，无法发起外呼")

    def _register_client_if_needed(
        self,
        client: Any,
        trunk_item: dict,
        registration_tracker: RegistrationTracker,
    ) -> None:
        """在 SIP 账号线路场景下执行注册并等待结果。

        参数:
            client: 当前单通呼叫使用的 uSIP 客户端对象。
            trunk_item: 当前绑定的线路对象。
            registration_tracker: 当前注册状态跟踪对象。

        返回:
            None: 注册通过后不返回业务数据，失败时抛出异常。
        """

        if trunk_item["trunk_type"] != "sip_account":
            return
        register_result = client.register()
        if register_result is False:
            raise AppError("sip_register_failed", "SIP 注册请求已发起但返回失败")
        if not registration_tracker.finished_event.wait(timeout=15):
            raise AppError("sip_register_timeout", "SIP 注册超时，请检查线路账号、网络和服务端配置")
        if registration_tracker.current_state != "REGISTERED":
            raise AppError("sip_register_failed", f"SIP 注册失败，当前状态为 {registration_tracker.current_state or 'UNKNOWN'}")

    def _dial_call(self, client: Any, session_item: dict, trunk_item: dict, call_tracker: CallTracker) -> None:
        """发起真实 SIP 呼叫并写入初始会话信息。

        参数:
            client: 当前单通呼叫使用的 uSIP 客户端对象。
            session_item: 当前通话会话对象。
            trunk_item: 当前绑定的线路对象。
            call_tracker: 当前呼叫状态跟踪对象。

        返回:
            None: 发起成功后不返回业务数据，失败时抛出异常。
        """

        target_uri = build_sip_target_uri(trunk_item, str(session_item["callee_number"]))
        call_id = client.make_call(target_uri)
        if not call_id:
            raise AppError("sip_call_create_failed", "SIP 拨号失败，未获得有效 call_id")
        call_tracker.call_id = str(call_id)
        self._write_progress_update(
            session_item["id"],
            build_session_progress_payload(
                session_status="dialing",
                answer_status="unanswered",
                event_type="dial",
                payload={
                    "sip_call_id": call_tracker.call_id,
                    "target_uri": target_uri,
                    "transport": trunk_item["transport"],
                },
            ),
        )

    def _wait_for_call_connected(self, session_item: dict, call_tracker: CallTracker) -> None:
        """等待呼叫进入接通状态。

        参数:
            session_item: 当前通话会话对象。
            call_tracker: 当前呼叫状态跟踪对象。

        返回:
            None: 接通后不返回业务数据，失败或超时则抛出异常。
        """

        wait_deadline = time.time() + 45
        while time.time() < wait_deadline:
            if call_tracker.remote_rtp_address is not None:
                # 振铃阶段对端也可能已经开始回传早期媒体，录音需要从这段媒体开始对齐时间轴。
                self._collect_inbound_audio_packets(
                    call_tracker,
                    max_packets=40,
                    max_duration_seconds=0.02,
                    allow_blocking=False,
                )
            if call_tracker.connected_event.wait(timeout=0.1):
                if call_tracker.remote_rtp_address:
                    return
            if call_tracker.finished_event.is_set():
                raise AppError("sip_call_ended_early", call_tracker.end_reason or "通话在接通前已结束")
        if call_tracker.connected_event.is_set() and not call_tracker.remote_rtp_address:
            raise AppError("sip_remote_rtp_missing", "通话已接通，但未从 SIP/SDP 中解析到远端 RTP 地址")
        if call_tracker.current_state and str(call_tracker.current_state).upper() == "RINGING":
            raise AppError("sip_call_ring_timeout", "呼叫长时间振铃未接听，系统已按超时结束")
        raise AppError("sip_call_answer_timeout", f"呼叫接通超时，当前状态为 {call_tracker.current_state or 'UNKNOWN'}")

    def _playback_call_plan(
        self,
        connection: Connection,
        client: Any,
        task_item: dict,
        session_item: dict,
        call_tracker: CallTracker,
        playback_plan: list[dict],
    ) -> None:
        """按顺序把话术起始音频计划推送到当前通话。

        参数:
            connection: 当前后台线程使用的 PostgreSQL 数据库连接对象。
            client: 当前单通呼叫使用的 uSIP 客户端对象。
            task_item: 当前外呼任务对象。
            session_item: 当前通话会话对象。
            call_tracker: 当前呼叫状态跟踪对象。
            playback_plan: 当前会话需要播放的音频动作数组。

        返回:
            None: 播放完成后不返回业务数据，播放失败时抛出异常。
        """

        if not playback_plan:
            self._write_progress_update(
                session_item["id"],
                build_session_progress_payload(
                    session_status="completed",
                    answer_status="answered",
                    result_code="no_playback_plan",
                    event_type="hangup",
                    billsec=1,
                    duration=1,
                    payload={"task_id": task_item["id"], "playback_count": 0},
                ),
            )
            return
        total_duration = 0
        for playback_item in playback_plan:
            audio_path = Path(str(playback_item["audio_path"]))
            self.logger.info(
                "开始向通话推送节点音频: session_id=%s node_code=%s audio_path=%s",
                session_item["id"],
                playback_item["node_code"],
                audio_path,
            )
            progress_call_session(
                connection,
                session_item["id"],
                build_session_progress_payload(
                    session_status="answered",
                    answer_status="answered",
                    current_node_code=playback_item["node_code"],
                    event_type="node_enter",
                    payload={
                        "audio_path": str(audio_path),
                        "playback_source": playback_item["playback_source"],
                        "prompt_text": str(playback_item.get("prompt_text") or "").strip(),
                        "speaker_role": "agent",
                    },
                ),
            )
            played_duration = play_audio_file_over_rtp(
                audio_path=audio_path,
                remote_rtp_address=call_tracker.remote_rtp_address,
                local_rtp_port=call_tracker.local_rtp_port,
                rtp_socket=call_tracker.rtp_socket,
                on_packet_sent=lambda pcm_frame: self._handle_packet_sent(call_tracker, pcm_frame),
            )
            total_duration += played_duration
            if call_tracker.finished_event.is_set():
                raise AppError("sip_call_ended_during_playback", call_tracker.end_reason or "通话在音频播放过程中已结束")
        self._write_progress_update(
            session_item["id"],
            build_session_progress_payload(
                session_status="answered",
                answer_status="answered",
                event_type="playback_completed",
                billsec=max(1, int(total_duration)),
                duration=max(1, int(total_duration) + 1),
                payload={"task_id": task_item["id"], "playback_count": len(playback_plan)},
            ),
        )

    def _wait_for_reply_window(
        self,
        connection: Connection,
        task_item: dict,
        session_item: dict,
        call_tracker: CallTracker,
        await_reply_config: dict | None,
    ) -> None:
        """在欢迎语播放完成后按识别节点配置等待回复，并实时把上行音频送入百炼 ASR。

        参数:
            connection: 当前后台线程使用的 PostgreSQL 数据库连接对象。
            task_item: 当前外呼任务对象。
            session_item: 当前通话会话对象。
            call_tracker: 当前呼叫状态跟踪对象。
            await_reply_config: 当前识别节点等待回复和兜底播放配置，可为空。

        返回:
            None: 等待结束后不返回业务数据；若通话已结束则提前返回。
        """

        if call_tracker.finished_event.is_set() or not await_reply_config:
            return
        wait_seconds = max(1, int(await_reply_config.get("timeout_seconds") or 5))
        sentence_silence_ms = max(100, int(await_reply_config.get("sentence_silence_ms") or 400))
        asr_preroll_bytes = calculate_asr_preroll_bytes(0.5)
        realtime_asr_tracker: RealtimeAsrTracker | None = None
        try:
            asr_provider_item = self._resolve_realtime_asr_provider(connection)
            realtime_asr_tracker = self._start_realtime_asr_session(asr_provider_item, await_reply_config)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "ASR 诊断: session_id=%s asr_node=%s 当前无法启动实时 ASR，将按超时兜底继续流程 detail=%r",
                session_item["id"],
                await_reply_config.get("asr_node_code"),
                exc,
            )
        streamed_pcm_offset = max(0, len(call_tracker.inbound_pcm_bytes) - asr_preroll_bytes)
        self.logger.info(
            "ASR 诊断: session_id=%s task_id=%s asr_node=%s timeout_seconds=%s realtime_asr_enabled=%s preroll_bytes=%s mode=%s",
            session_item["id"],
            task_item["id"],
            await_reply_config.get("asr_node_code"),
            wait_seconds,
            realtime_asr_tracker is not None,
            asr_preroll_bytes,
            "当前版本会在等待窗口内实时收集上行 RTP 音频，并通过百炼 WebSocket 实时识别",
        )
        self._write_progress_update(
            session_item["id"],
            build_session_progress_payload(
                session_status="answered",
                answer_status="answered",
                event_type="system",
                current_node_code=str(await_reply_config.get("asr_node_code") or "") or None,
                payload={
                    "stage": "await_reply",
                    "wait_seconds": wait_seconds,
                    "sentence_silence_ms": sentence_silence_ms,
                    "asr_node_code": await_reply_config.get("asr_node_code"),
                },
            ),
        )
        deadline = time.time() + wait_seconds
        elapsed_tenths = 0
        recognized_text = ""
        early_finalize_idle_seconds = max(0.15, min(1.5, sentence_silence_ms / 1000))
        early_partial_idle_seconds = max(0.12, min(1.0, early_finalize_idle_seconds * 0.6))
        if realtime_asr_tracker is not None and str(realtime_asr_tracker.driver_name or "").strip() == "qwen_stream_asr_http":
            early_finalize_idle_seconds = max(0.15, min(0.8, sentence_silence_ms / 1000))
            early_partial_idle_seconds = max(0.1, min(0.5, early_finalize_idle_seconds * 0.55))
        try:
            while time.time() < deadline:
                if call_tracker.finished_event.wait(timeout=0.2):
                    return
                self._collect_inbound_audio_packets(call_tracker)
                if realtime_asr_tracker is not None:
                    streamed_pcm_offset = self._push_new_pcm_frames_to_realtime_asr(
                        call_tracker,
                        realtime_asr_tracker,
                        streamed_pcm_offset,
                    )
                elapsed_tenths += 1
                if (
                    realtime_asr_tracker is not None
                    and realtime_asr_tracker.completed_event.is_set()
                    and realtime_asr_tracker.error_message
                ):
                    recognized_text = normalize_effective_recognized_text(
                        realtime_asr_tracker.final_text or realtime_asr_tracker.partial_text
                    )
                    self.logger.warning(
                        "ASR 诊断: session_id=%s asr_node=%s 实时识别提前结束，准备使用当前结果 detail=%s",
                        session_item["id"],
                        await_reply_config.get("asr_node_code"),
                        realtime_asr_tracker.error_message,
                    )
                    if not recognized_text:
                        self.logger.info(
                            "ASR 诊断: session_id=%s asr_node=%s 当前最终文本被判定为无效短句，继续等待客户有效回复 raw_text=%s",
                            session_item["id"],
                            await_reply_config.get("asr_node_code"),
                            str(realtime_asr_tracker.final_text or realtime_asr_tracker.partial_text).strip(),
                        )
                    if recognized_text or realtime_asr_tracker.error_message:
                        break
                if should_finalize_realtime_asr_early(
                    realtime_asr_tracker,
                    early_finalize_idle_seconds,
                ):
                    self.logger.info(
                        "ASR 诊断: session_id=%s asr_node=%s 已获得稳定最终句，提前结束等待窗口 final_text=%s",
                        session_item["id"],
                        await_reply_config.get("asr_node_code"),
                        realtime_asr_tracker.final_text,
                    )
                    break
                if self._should_finalize_from_partial_result(
                    connection=connection,
                    session_item=session_item,
                    await_reply_config=await_reply_config,
                    tracker=realtime_asr_tracker,
                    idle_seconds=early_partial_idle_seconds,
                ):
                    recognized_text = normalize_effective_recognized_text(realtime_asr_tracker.partial_text)
                    self.logger.info(
                        "ASR 诊断: session_id=%s asr_node=%s 已获得可命中分支的稳定中间结果，提前推进 transcript=%s",
                        session_item["id"],
                        await_reply_config.get("asr_node_code"),
                        recognized_text,
                    )
                    break
                if self._should_finalize_local_asr_segment_early(realtime_asr_tracker):
                    self.logger.info(
                        "ASR 诊断: session_id=%s asr_node=%s 本地语音段已满足静音收尾条件，准备立即结束当前识别分段",
                        session_item["id"],
                        await_reply_config.get("asr_node_code"),
                    )
                    break
                if elapsed_tenths % 5 == 0:
                    elapsed_seconds = elapsed_tenths // 5
                    self.logger.info(
                        "ASR 诊断心跳: session_id=%s asr_node=%s elapsed=%ss/%ss inbound_audio_frames=%s submitted_asr_frames=%s recognized_text=%s",
                        session_item["id"],
                        await_reply_config.get("asr_node_code"),
                        elapsed_seconds,
                        wait_seconds,
                        call_tracker.inbound_audio_frames,
                        realtime_asr_tracker.submitted_audio_frames if realtime_asr_tracker is not None else 0,
                        realtime_asr_tracker.partial_text if realtime_asr_tracker is not None else "",
                    )
            if not recognized_text and realtime_asr_tracker is not None:
                self._finish_realtime_asr_session(realtime_asr_tracker)
                raw_recognized_text = str(realtime_asr_tracker.final_text or realtime_asr_tracker.partial_text).strip()
                recognized_text = normalize_effective_recognized_text(raw_recognized_text)
                if raw_recognized_text and not recognized_text:
                    self.logger.info(
                        "ASR 诊断: session_id=%s asr_node=%s 已过滤无效短句，继续按未识别路径处理 raw_text=%s",
                        session_item["id"],
                        await_reply_config.get("asr_node_code"),
                        raw_recognized_text,
                    )
        finally:
            if realtime_asr_tracker is not None:
                self._close_realtime_asr_session(realtime_asr_tracker)

        if recognized_text:
            self.logger.info(
                "ASR 诊断结果: session_id=%s asr_node=%s transcript=%s submitted_asr_frames=%s",
                session_item["id"],
                await_reply_config.get("asr_node_code"),
                recognized_text,
                realtime_asr_tracker.submitted_audio_frames if realtime_asr_tracker is not None else 0,
            )
            reply_bundle = self._resolve_reply_bundle(
                connection=connection,
                task_item=task_item,
                session_item=session_item,
                await_reply_config=await_reply_config,
                recognized_text=recognized_text,
            )
            reply_playback_plan = reply_bundle.get("playback_plan") or []
            if reply_playback_plan:
                self.logger.info(
                    "识别节点已命中回复分支，开始执行后续播报: session_id=%s asr_node=%s playback_count=%s",
                    session_item["id"],
                    await_reply_config.get("asr_node_code"),
                    len(reply_playback_plan),
                )
                self._playback_call_plan(
                    connection,
                    None,
                    task_item,
                    session_item,
                    call_tracker,
                    reply_playback_plan,
                )
                next_await_reply = reply_bundle.get("await_reply")
                if next_await_reply and not call_tracker.finished_event.is_set():
                    self._wait_for_reply_window(connection, task_item, session_item, call_tracker, next_await_reply)
                return
            self.logger.warning(
                "ASR 诊断结果: session_id=%s asr_node=%s 已识别文本但未命中任何分支，准备走兜底分支",
                session_item["id"],
                await_reply_config.get("asr_node_code"),
            )
        else:
            self.logger.warning(
                "ASR 诊断结果: session_id=%s asr_node=%s 未获得可用实时识别文本，准备走兜底分支 detail=%s",
                session_item["id"],
                await_reply_config.get("asr_node_code"),
                realtime_asr_tracker.error_message if realtime_asr_tracker is not None else "",
            )
        fallback_plan = await_reply_config.get("fallback_plan") or []
        if fallback_plan and not call_tracker.finished_event.is_set():
            self.logger.info(
                "识别节点等待超时，开始执行兜底播报: session_id=%s asr_node=%s playback_count=%s",
                session_item["id"],
                await_reply_config.get("asr_node_code"),
                len(fallback_plan),
            )
            self._playback_call_plan(
                connection,
                None,
                task_item,
                session_item,
                call_tracker,
                fallback_plan,
            )
            fallback_await_reply = await_reply_config.get("fallback_await_reply")
            if fallback_await_reply and not call_tracker.finished_event.is_set():
                self._wait_for_reply_window(connection, task_item, session_item, call_tracker, fallback_await_reply)

    def _handle_packet_sent(self, call_tracker: CallTracker, pcm_frame: bytes) -> None:
        """在每次发送下行 RTP 音频包后同步记录下行音频并收集上行音频。

        参数:
            call_tracker: 当前呼叫状态跟踪对象。
            pcm_frame: 当前已发送给客户的 16bit PCM 音频帧。

        返回:
            None: 当前函数仅负责同步更新内存中的上下行音频缓存。
        """

        self._append_outbound_pcm_frame(call_tracker, pcm_frame)
        self._collect_inbound_audio_packets(
            call_tracker,
            max_packets=2,
            max_duration_seconds=0.002,
            allow_blocking=False,
        )

    def _append_outbound_pcm_frame(self, call_tracker: CallTracker, pcm_frame: bytes) -> None:
        """把当前发送给客户的 PCM 音频帧补齐到通话时间轴中。

        参数:
            call_tracker: 当前呼叫状态跟踪对象。
            pcm_frame: 当前下行 16bit PCM 音频帧。

        返回:
            None: 当前函数仅负责把下行音频写入内存缓冲区。
        """

        if not pcm_frame:
            return
        current_timestamp = time.time()
        reference_timestamp = self._resolve_audio_timeline_reference(call_tracker, current_timestamp)
        expected_offset_bytes = align_pcm_sample_offset_bytes(
            max(0, int((current_timestamp - reference_timestamp) * 8000 * 2))
        )
        if len(call_tracker.outbound_pcm_bytes) < expected_offset_bytes:
            call_tracker.outbound_pcm_bytes.extend(b"\x00" * (expected_offset_bytes - len(call_tracker.outbound_pcm_bytes)))
        call_tracker.outbound_pcm_bytes.extend(pcm_frame)

    def _save_call_recording_if_available(self, connection: Connection, session_item: dict, call_tracker: CallTracker) -> None:
        """在通话结束后把当前会话的上下行音频合成为录音文件并落库。

        参数:
            connection: 当前后台线程使用的 PostgreSQL 数据库连接对象。
            session_item: 当前通话会话对象。
            call_tracker: 当前呼叫状态跟踪对象。

        返回:
            None: 保存成功后不返回业务数据，失败时记录日志并忽略。
        """

        from .media_service import create_recording_file_from_bytes

        inbound_pcm_bytes = bytes(call_tracker.inbound_pcm_bytes)
        outbound_pcm_bytes = bytes(call_tracker.outbound_pcm_bytes)
        if not inbound_pcm_bytes and not outbound_pcm_bytes:
            self.logger.info("当前通话没有可保存的录音数据，跳过自动录音: session_id=%s", session_item["id"])
            return

        stereo_pcm_bytes = build_stereo_call_recording_pcm(inbound_pcm_bytes, outbound_pcm_bytes)
        session_code = str(session_item.get("session_code") or f"session_{session_item['id']}")
        recording_file_name = f"{session_code}.wav"
        recording_item = create_recording_file_from_bytes(
            connection=connection,
            session_id=int(session_item["id"]),
            file_bytes=build_wav_bytes_from_pcm(stereo_pcm_bytes, channels=2),
            project_root=self.project_root,
            record_type="mixed",
            upload_filename=recording_file_name,
            mime_type="audio/wav",
        )
        self.logger.info(
            "已自动保存通话录音: session_id=%s recording_file_id=%s storage_key=%s",
            session_item["id"],
            recording_item.get("id"),
            recording_item.get("storage_key"),
        )

    def _resolve_audio_timeline_reference(self, call_tracker: CallTracker, current_timestamp: float) -> float:
        """解析当前通话录音时间轴的统一起点，保证上下行音频按同一基准对齐。

        参数:
            call_tracker: 当前呼叫状态跟踪对象，内部会缓存已经确定的时间轴起点。
            current_timestamp: 当前收发音频时刻的 UNIX 时间戳。

        返回:
            float: 返回本次音频应使用的统一时间轴起点秒值。
        """

        if call_tracker.audio_timeline_started_at is None:
            # 录音时间轴优先以接通时间为基准；若极端情况下回调稍晚，则退化为首次收发音频时间。
            call_tracker.audio_timeline_started_at = call_tracker.answer_timestamp or current_timestamp
        return call_tracker.audio_timeline_started_at

    def _resolve_realtime_asr_provider(self, connection: Connection) -> dict:
        """解析当前通话实时识别应使用的在线或本地 ASR 接口配置。

        参数:
            connection: 当前后台线程使用的 PostgreSQL 数据库连接对象。

        返回:
            dict: 已通过校验的在线 ASR 接口配置字典。
        """

        available_provider_items: list[dict] = []
        provider_items = sorted(
            list_speech_providers(connection),
            key=lambda item: (get_runtime_asr_driver_priority(item.get("driver_name") or ""), item.get("id") or 0),
        )
        for provider_item in provider_items:
            if provider_item.get("provider_type") != "asr" or not provider_item.get("is_enabled"):
                continue
            config_json = provider_item.get("config_json") or {}
            driver_name = str(provider_item.get("driver_name") or "").strip()
            if driver_name != "qwen_stream_asr_http" and not str(config_json.get("api_key") or "").strip():
                continue
            if not str(config_json.get("endpoint") or "").strip():
                continue
            available_provider_items.append(provider_item)
        if not available_provider_items:
            raise AppError("asr_provider_missing", "未找到可用的在线 ASR 接口，请先在“语音接口”中配置有效密钥")
        return normalize_runtime_asr_provider_item(available_provider_items[0])

    def _start_realtime_asr_session(self, provider_item: dict, await_reply_config: dict) -> RealtimeAsrTracker:
        """启动一个实时 ASR 会话线程。

        参数:
            provider_item: 当前用于实时识别的 ASR 接口配置字典。
            await_reply_config: 当前识别节点等待配置字典，用于生成识别会话参数。

        返回:
            RealtimeAsrTracker: 返回实时 ASR 会话跟踪对象。
        """

        normalized_provider_item = apply_runtime_asr_overrides(provider_item, await_reply_config)
        config_json = normalized_provider_item.get("config_json") or {}
        custom_params = dict(config_json.get("custom_params") or {})
        client_chunk_seconds = max(0.04, float(custom_params.get("client_chunk_size_sec") or 0.1))
        client_chunk_bytes = max(int(16000 * client_chunk_seconds) * 2, 1280)
        sentence_silence_ms = max(120, int(custom_params.get("max_sentence_silence") or await_reply_config.get("sentence_silence_ms") or 320))
        tracker = RealtimeAsrTracker(
            driver_name=str(normalized_provider_item.get("driver_name") or "").strip(),
            client_chunk_bytes=client_chunk_bytes,
            local_vad_min_speech_ms=80,
            local_vad_silence_ms=sentence_silence_ms,
        )
        worker_thread = threading.Thread(
            target=self._run_realtime_asr_session_worker,
            args=(normalized_provider_item, await_reply_config, tracker),
            daemon=True,
            name=f"realtime-asr-{uuid.uuid4().hex[:8]}",
        )
        tracker.worker_thread = worker_thread
        worker_thread.start()
        return tracker

    def _run_realtime_asr_session_worker(
        self,
        provider_item: dict,
        await_reply_config: dict,
        tracker: RealtimeAsrTracker,
    ) -> None:
        """在线程中运行实时 ASR 会话。

        参数:
            provider_item: 当前用于实时识别的 ASR 接口配置字典。
            await_reply_config: 当前识别节点等待配置字典。
            tracker: 当前实时 ASR 会话跟踪对象。

        返回:
            None: 当前函数仅负责运行后台识别线程，不直接返回业务数据。
        """

        try:
            asyncio.run(self._run_realtime_asr_session_async(provider_item, await_reply_config, tracker))
        except Exception as exc:  # noqa: BLE001
            config_json = provider_item.get("config_json") or {}
            tracker.error_message = f"实时 ASR 会话启动失败：{exc!r}"
            tracker.completed_event.set()
            self.logger.warning(
                "ASR 诊断: 实时 ASR 会话启动失败 provider_id=%s driver=%s endpoint=%s detail=%r",
                provider_item.get("id"),
                provider_item.get("driver_name"),
                config_json.get("endpoint"),
                exc,
            )

    async def _run_realtime_asr_session_async(
        self,
        provider_item: dict,
        await_reply_config: dict,
        tracker: RealtimeAsrTracker,
    ) -> None:
        """在协程中连接实时 ASR 服务并持续发送音频数据。

        参数:
            provider_item: 当前用于实时识别的 ASR 接口配置字典。
            await_reply_config: 当前识别节点等待配置字典。
            tracker: 当前实时 ASR 会话跟踪对象。

        返回:
            None: 当前函数仅负责管理实时 WebSocket 生命周期。
        """

        runtime_provider_item = apply_runtime_asr_overrides(provider_item, await_reply_config)
        driver_name = str(provider_item.get("driver_name") or "").strip()
        if driver_name == "qwen_stream_asr_http":
            await self._run_qwen_stream_asr_session_async(runtime_provider_item, tracker)
            return
        await self._run_aliyun_ws_asr_session_async(runtime_provider_item, tracker)

    async def _run_aliyun_ws_asr_session_async(self, provider_item: dict, tracker: RealtimeAsrTracker) -> None:
        """在协程中连接阿里云实时 ASR 并持续发送音频数据。

        参数:
            provider_item: 当前用于实时识别的 ASR 接口配置字典。
            tracker: 当前实时 ASR 会话跟踪对象。

        返回:
            None: 当前函数仅负责管理阿里云实时 WebSocket 生命周期。
        """

        config_json = provider_item.get("config_json") or {}
        endpoint = build_aliyun_ws_asr_endpoint(config_json)
        api_key = str(config_json.get("api_key") or "").strip()
        ssl_context = ssl.create_default_context()
        tracker.task_id = uuid.uuid4().hex
        headers = {"Authorization": f"Bearer {api_key}"}
        workspace_id = str(
            config_json.get("workspace_id")
            or (config_json.get("custom_params") or {}).get("workspace_id")
            or ""
        ).strip()
        if workspace_id:
            headers["X-DashScope-WorkSpace"] = workspace_id
        self.logger.info(
            "ASR 诊断: 准备建立阿里云实时 ASR 连接 endpoint=%s model=%s provider_id=%s",
            endpoint,
            config_json.get("model"),
            provider_item.get("id"),
        )
        async with websocket_connect(
            endpoint,
            additional_headers=headers,
            ssl=ssl_context,
            max_size=8 * 1024 * 1024,
            ping_interval=20,
            ping_timeout=20,
        ) as websocket:
            self.logger.info(
                "ASR 诊断: 阿里云实时 ASR WebSocket 已连接 endpoint=%s provider_id=%s",
                endpoint,
                provider_item.get("id"),
            )
            receiver_task = asyncio.create_task(self._receive_realtime_asr_messages(websocket, tracker))
            try:
                await websocket.send(
                    json.dumps(
                        build_aliyun_ws_run_task_payload(config_json, tracker.task_id),
                        ensure_ascii=False,
                    )
                )
                self.logger.info("ASR 诊断: 已发送 run-task，等待 task-started")
                await asyncio.wait_for(asyncio.to_thread(tracker.started_event.wait), timeout=8)
                self.logger.info("ASR 诊断: 阿里云实时 ASR 任务已启动，开始发送上行音频")
                while True:
                    if tracker.stop_event.is_set() and tracker.audio_queue.empty():
                        break
                    try:
                        pcm_chunk = tracker.audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        await asyncio.sleep(0.02)
                        continue
                    if not pcm_chunk:
                        continue
                    await self._send_pcm_chunk_to_aliyun_ws(websocket, tracker, pcm_chunk)
                    if tracker.completed_event.is_set():
                        break
                await websocket.send(
                    json.dumps(
                        build_aliyun_ws_finish_task_payload(tracker.task_id),
                        ensure_ascii=False,
                    )
                )
                self.logger.info(
                    "ASR 诊断: 已发送 finish-task submitted_audio_frames=%s submitted_audio_bytes=%s",
                    tracker.submitted_audio_frames,
                    tracker.submitted_audio_bytes,
                )
                with suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(asyncio.to_thread(tracker.completed_event.wait), timeout=5)
            finally:
                receiver_task.cancel()
                with suppress(asyncio.CancelledError):
                    await receiver_task

    async def _run_qwen_stream_asr_session_async(self, provider_item: dict, tracker: RealtimeAsrTracker) -> None:
        """在协程中连接本地三段式流式 ASR 并持续发送音频数据。

        参数:
            provider_item: 当前用于实时识别的本地 ASR 接口配置字典。
            tracker: 当前实时 ASR 会话跟踪对象。

        返回:
            None: 当前函数仅负责管理本地 HTTP ASR 会话生命周期。
        """

        config_json = provider_item.get("config_json") or {}
        endpoint = build_qwen_stream_asr_base_url(config_json)
        self.logger.info(
            "ASR 诊断: 准备建立本地流式 ASR 连接 endpoint=%s model=%s provider_id=%s",
            endpoint,
            config_json.get("model"),
            provider_item.get("id"),
        )
        async with httpx.AsyncClient(timeout=30.0) as client:
            start_response = await client.post(
                f"{endpoint}/start",
                json=build_qwen_stream_start_payload(config_json),
            )
            start_response.raise_for_status()
            start_data = start_response.json()
            tracker.task_id = str((start_data.get("data") or {}).get("session_id") or "").strip()
            if start_data.get("code") != 200 or not tracker.task_id:
                raise AppError("asr_start_failed", f"本地流式 ASR start 失败：{start_data}")
            tracker.started_event.set()
            self.logger.info(
                "ASR 诊断: 本地流式 ASR 会话已建立 endpoint=%s provider_id=%s session_id=%s",
                endpoint,
                provider_item.get("id"),
                tracker.task_id,
            )
            while True:
                if tracker.stop_event.is_set() and tracker.audio_queue.empty():
                    break
                try:
                    pcm_chunk = tracker.audio_queue.get(timeout=0.1)
                except queue.Empty:
                    await asyncio.sleep(0.02)
                    continue
                if not pcm_chunk:
                    continue
                await self._send_pcm_chunk_to_qwen_stream(client, endpoint, tracker, pcm_chunk)
                if tracker.completed_event.is_set():
                    break
            finish_response = await client.post(
                f"{endpoint}/finish",
                json={"session_id": tracker.task_id},
            )
            finish_response.raise_for_status()
            finish_data = finish_response.json()
            if finish_data.get("code") != 200:
                raise AppError("asr_finish_failed", f"本地流式 ASR finish 失败：{finish_data}")
            final_text = str((finish_data.get("data") or {}).get("text") or "").strip()
            if final_text:
                tracker.final_text = final_text
                tracker.partial_text = final_text
                tracker.latest_result_index += 1
                tracker.latest_result_at = time.time()
                tracker.latest_text_event.set()
                self.logger.info(
                    "ASR 诊断: 收到本地流式 ASR 最终文本 text=%s",
                    final_text,
                )
            tracker.completed_event.set()

    async def _send_pcm_chunk_to_aliyun_ws(self, websocket: Any, tracker: RealtimeAsrTracker, pcm_chunk: bytes) -> None:
        """向阿里云实时 ASR WebSocket 发送单个 PCM 音频块。

        参数:
            websocket: 当前阿里云实时 ASR WebSocket 连接对象。
            tracker: 当前实时 ASR 会话跟踪对象。
            pcm_chunk: 当前待发送的 PCM16LE 音频块。

        返回:
            None: 当前函数只负责发送音频并等待短暂增量结果。
        """

        result_index_before = tracker.latest_result_index
        tracker.submitted_audio_bytes += len(pcm_chunk)
        tracker.submitted_audio_frames += 1
        if tracker.submitted_audio_frames <= 3:
            self.logger.info(
                "ASR 诊断: 已向阿里云发送音频块 frame_index=%s bytes=%s",
                tracker.submitted_audio_frames,
                len(pcm_chunk),
            )
        await websocket.send(pcm_chunk)
        if tracker.latest_result_index == result_index_before:
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.to_thread(tracker.latest_text_event.wait), timeout=0.08)
            tracker.latest_text_event.clear()

    async def _send_pcm_chunk_to_qwen_stream(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        tracker: RealtimeAsrTracker,
        pcm_chunk: bytes,
    ) -> None:
        """向本地流式 HTTP ASR 发送单个 PCM 音频块。

        参数:
            client: 当前本地 HTTP ASR 使用的异步 HTTP 客户端。
            endpoint: 当前本地流式 ASR 基础地址。
            tracker: 当前实时 ASR 会话跟踪对象。
            pcm_chunk: 当前待发送的 PCM16LE 音频块。

        返回:
            None: 当前函数只负责提交音频并更新最近一次识别文本。
        """

        tracker.submitted_audio_bytes += len(pcm_chunk)
        tracker.submitted_audio_frames += 1
        if tracker.submitted_audio_frames <= 3:
            self.logger.info(
                "ASR 诊断: 已向本地流式 ASR 发送音频块 frame_index=%s bytes=%s",
                tracker.submitted_audio_frames,
                len(pcm_chunk),
            )
        response = await client.post(
            f"{endpoint}/chunk",
            json=build_qwen_stream_chunk_payload(tracker.task_id, pcm_chunk),
        )
        response.raise_for_status()
        body = response.json()
        if body.get("code") != 200:
            raise AppError("asr_chunk_failed", f"本地流式 ASR chunk 失败：{body}")
        response_data = body.get("data") or {}
        chunk_debug = response_data.get("chunk_debug") or {}
        text = str(response_data.get("text") or "").strip()
        if tracker.submitted_audio_frames <= 6 or tracker.submitted_audio_frames % 10 == 0:
            self.logger.info(
                "ASR 诊断: 本地流式 ASR chunk 返回 frame_index=%s text=%s dropped_by_vad=%s accepted_by_model=%s input_rms=%s output_rms=%s",
                tracker.submitted_audio_frames,
                text,
                chunk_debug.get("dropped_by_vad"),
                chunk_debug.get("accepted_by_model"),
                chunk_debug.get("input_rms"),
                chunk_debug.get("output_rms"),
            )
        if text:
            if text != str(tracker.partial_text or "").strip():
                tracker.partial_text = text
                tracker.latest_result_index += 1
                tracker.latest_result_at = time.time()
                tracker.latest_text_event.set()
                self.logger.info(
                    "ASR 诊断: 收到本地流式 ASR 中间文本 text=%s",
                    text,
                )

    async def _receive_realtime_asr_messages(self, websocket: Any, tracker: RealtimeAsrTracker) -> None:
        """持续接收阿里云实时 ASR 服务端消息并提取识别状态。

        参数:
            websocket: 当前阿里云 WebSocket 连接对象。
            tracker: 当前实时 ASR 会话跟踪对象。

        返回:
            None: 当前函数仅负责更新实时识别状态。
        """

        while True:
            raw_message = await websocket.recv()
            message = parse_aliyun_ws_asr_message(raw_message)
            header = message.get("header") or {}
            event_type = str(header.get("event") or "").strip()
            transcript_text, is_final = extract_aliyun_ws_asr_result(message)
            self.logger.info("ASR 诊断: 收到阿里云事件 type=%s", event_type or "unknown")
            if event_type == "task-started":
                tracker.started_event.set()
                self.logger.info("ASR 诊断: 收到阿里云 task-started")
                continue
            if transcript_text:
                self.logger.info(
                    "ASR 诊断: 收到阿里云识别文本 event_type=%s is_final=%s text=%s",
                    event_type,
                    is_final,
                    transcript_text,
                )
                tracker.partial_text = transcript_text
                tracker.latest_result_index += 1
                tracker.latest_result_at = time.time()
                tracker.latest_text_event.set()
                if is_final:
                    tracker.final_text = transcript_text
                continue
            if event_type == "task-finished":
                tracker.completed_event.set()
                tracker.started_event.set()
                self.logger.info("ASR 诊断: 收到阿里云 task-finished")
                continue
            if event_type == "task-failed":
                tracker.error_message = extract_aliyun_ws_asr_error_message(message)
                tracker.completed_event.set()
                tracker.started_event.set()
                tracker.latest_text_event.set()
                self.logger.warning("ASR 诊断: 阿里云返回错误 detail=%s", tracker.error_message)

    def _push_new_pcm_frames_to_realtime_asr(
        self,
        call_tracker: CallTracker,
        tracker: RealtimeAsrTracker,
        streamed_pcm_offset: int,
    ) -> int:
        """把最新收到的上行 PCM 音频切块后推送到实时 ASR 队列。

        参数:
            call_tracker: 当前呼叫状态跟踪对象，内部保存累计的 PCM 音频。
            tracker: 当前实时 ASR 会话跟踪对象。
            streamed_pcm_offset: 已经推送到实时 ASR 的 PCM 字节偏移量。

        返回:
            int: 返回本次推送后的最新 PCM 偏移量。
        """

        if streamed_pcm_offset >= len(call_tracker.inbound_pcm_bytes):
            return streamed_pcm_offset
        pending_pcm = bytes(call_tracker.inbound_pcm_bytes[streamed_pcm_offset:])
        chunk_size = max(int(tracker.client_chunk_bytes or 3200), 1280)
        complete_length = len(pending_pcm) - (len(pending_pcm) % chunk_size)
        if complete_length <= 0:
            return streamed_pcm_offset
        for offset in range(0, complete_length, chunk_size):
            pcm_chunk = pending_pcm[offset : offset + chunk_size]
            self._update_local_asr_segment_state(tracker, pcm_chunk)
            tracker.audio_queue.put(pcm_chunk)
        return streamed_pcm_offset + complete_length

    def _update_local_asr_segment_state(self, tracker: RealtimeAsrTracker, pcm_chunk: bytes) -> None:
        """根据当前送入本地 ASR 的 PCM 音频块更新语音段收尾状态。

        参数:
            tracker: 当前实时 ASR 会话跟踪对象，仅在本地 HTTP ASR 驱动下启用该状态机。
            pcm_chunk: 当前准备送入本地 ASR 的 PCM16LE 单声道音频块。

        返回:
            None: 当前函数只负责更新本地语音段状态，不直接返回识别结果。
        """

        if str(tracker.driver_name or "").strip() != "qwen_stream_asr_http":
            return
        if not pcm_chunk:
            return
        chunk_ms = (len(pcm_chunk) / 2 / 8000) * 1000
        if chunk_ms <= 0:
            return
        chunk_rms = float(audioop.rms(pcm_chunk, 2))
        if chunk_rms >= 200.0:
            tracker.local_vad_speech_active = True
            tracker.local_vad_speech_ms += chunk_ms
            tracker.local_vad_silence_ms_accumulated = 0.0
            tracker.local_segment_finalize_ready = False
            return
        if not tracker.local_vad_speech_active:
            return
        tracker.local_vad_silence_ms_accumulated += chunk_ms
        if (
            tracker.local_vad_speech_ms >= float(tracker.local_vad_min_speech_ms)
            and tracker.local_vad_silence_ms_accumulated >= float(tracker.local_vad_silence_ms)
        ):
            tracker.local_segment_finalize_ready = True

    def _should_finalize_local_asr_segment_early(self, tracker: RealtimeAsrTracker | None) -> bool:
        """判断本地 HTTP ASR 是否已经满足“句尾静音后立即收尾”的条件。

        参数:
            tracker: 当前实时 ASR 会话跟踪对象；为空时表示当前未启用实时识别。

        返回:
            bool: 仅当本地语音段已经检测到有效说话并累计到足够静音时返回 True。
        """

        if tracker is None:
            return False
        if str(tracker.driver_name or "").strip() != "qwen_stream_asr_http":
            return False
        if not tracker.local_segment_finalize_ready:
            return False

        # 本地 HTTP ASR 出现“啊、嗯、喂”这类无效短句时，不允许它们直接结束等待窗口并触发后续流程。
        return bool(normalize_effective_recognized_text(tracker.final_text or tracker.partial_text))

    def _finish_realtime_asr_session(self, tracker: RealtimeAsrTracker) -> None:
        """通知实时 ASR 会话结束送音，并等待服务端返回最终结果。

        参数:
            tracker: 当前实时 ASR 会话跟踪对象。

        返回:
            None: 当前函数只负责收尾，不直接返回业务数据。
        """

        tracker.stop_event.set()
        if tracker.worker_thread is not None:
            tracker.worker_thread.join(timeout=4)

    def _close_realtime_asr_session(self, tracker: RealtimeAsrTracker) -> None:
        """确保实时 ASR 会话线程已停止，避免后台线程泄漏。

        参数:
            tracker: 当前实时 ASR 会话跟踪对象。

        返回:
            None: 当前函数只负责清理线程与停止标记。
        """

        tracker.stop_event.set()
        if tracker.worker_thread is not None and tracker.worker_thread.is_alive():
            tracker.worker_thread.join(timeout=1)

    def _collect_inbound_audio_packets(
        self,
        call_tracker: CallTracker,
        max_packets: int = 80,
        max_duration_seconds: float = 0.08,
        allow_blocking: bool = True,
    ) -> None:
        """从当前 RTP 套接字读取上行音频包并累计解码后的 PCM 数据。

        参数:
            call_tracker: 当前呼叫状态跟踪对象，内部包含 RTP 套接字和远端媒体协商信息。
            max_packets: 当前单次最多处理的 RTP 包数量，避免长期占用线程。
            max_duration_seconds: 当前单次最多允许消耗的处理时长，单位为秒。
            allow_blocking: 当前是否允许按套接字超时配置阻塞等待数据；播报阶段应关闭以免影响发包节奏。

        返回:
            None: 当前函数仅负责收包与累计统计，不直接返回业务数据。
        """

        if call_tracker.rtp_socket is None or call_tracker.remote_rtp_address is None:
            return
        remote_host, remote_port, _, codec_name = call_tracker.remote_rtp_address
        started_at = time.perf_counter()
        processed_packets = 0
        original_timeout = None
        while True:
            if processed_packets >= max(1, int(max_packets)):
                return
            if time.perf_counter() - started_at >= max(0.0005, float(max_duration_seconds)):
                return
            try:
                if original_timeout is None:
                    original_timeout = call_tracker.rtp_socket.gettimeout()
                    if not allow_blocking:
                        call_tracker.rtp_socket.settimeout(0.0)
                packet_bytes, packet_addr = call_tracker.rtp_socket.recvfrom(4096)
            except BlockingIOError:
                return
            except TimeoutError:
                return
            except OSError:
                return
            finally:
                if original_timeout is not None and not allow_blocking:
                    with suppress(OSError):
                        call_tracker.rtp_socket.settimeout(original_timeout)
                    original_timeout = None
            packet_host, packet_port = packet_addr[0], int(packet_addr[1])
            if packet_host != remote_host or packet_port != remote_port:
                continue
            audio_payload = extract_rtp_audio_payload(packet_bytes)
            if not audio_payload:
                continue
            pcm_payload = decode_rtp_audio_payload(audio_payload, codec_name)
            if not pcm_payload:
                continue
            processed_packets += 1
            call_tracker.inbound_audio_frames += 1
            call_tracker.inbound_audio_bytes += len(audio_payload)
            current_timestamp = time.time()
            reference_timestamp = self._resolve_audio_timeline_reference(call_tracker, current_timestamp)
            expected_offset_bytes = align_pcm_sample_offset_bytes(
                max(0, int((current_timestamp - reference_timestamp) * 8000 * 2))
            )
            if len(call_tracker.inbound_pcm_bytes) < expected_offset_bytes:
                # 上行音频也要按真实收包时间补齐静音，否则客户声音会被整体前移，导致和客服播报错位。
                call_tracker.inbound_pcm_bytes.extend(b"\x00" * (expected_offset_bytes - len(call_tracker.inbound_pcm_bytes)))
            call_tracker.inbound_pcm_bytes.extend(pcm_payload)

    def _resolve_reply_bundle(
        self,
        connection: Connection,
        task_item: dict,
        session_item: dict,
        await_reply_config: dict,
        recognized_text: str,
    ) -> dict:
        """根据识别文本推进话术分支，并生成后续播放与等待配置。

        参数:
            connection: 当前后台线程使用的 PostgreSQL 数据库连接对象。
            task_item: 当前外呼任务对象，用于获取任务所属用户和话术版本信息。
            session_item: 当前通话会话对象，内部会用于变量替换和后续 TTS 生成。
            await_reply_config: 当前识别节点等待回复配置，内部必须包含识别节点编码。
            recognized_text: 当前等待窗口内识别得到的文本内容。

        返回:
            dict: 返回命中分支后的播放计划和下一轮等待配置；若未命中任何分支则返回空字典。
        """

        from ..api.schemas.runtime import ScriptStepRequest
        from .call_playback_service import build_call_bundle_from_node_code
        from .runtime_service import execute_script_step

        script_version_id = int(session_item.get("script_version_id") or 0)
        if script_version_id <= 0:
            return {}
        asr_node_code = str(await_reply_config.get("asr_node_code") or "").strip()
        if not asr_node_code:
            return {}
        step_result = execute_script_step(
            connection,
            script_version_id,
            ScriptStepRequest(current_node_code=asr_node_code, asr_text=recognized_text),
        )
        next_node = step_result.get("next_node")
        if not next_node:
            return {}
        owner_user_id = resolve_task_owner_id(connection, int(task_item["id"]))
        bundle = build_call_bundle_from_node_code(
            connection=connection,
            script_version_id=script_version_id,
            session_item=session_item,
            project_root=self.project_root,
            owner_user_id=owner_user_id,
            start_node_code=str(next_node.get("node_code") or ""),
        )
        self._write_progress_update(
            session_item["id"],
            build_session_progress_payload(
                session_status="answered",
                answer_status="answered",
                event_type="asr_result",
                current_node_code=str(next_node.get("node_code") or "") or None,
                payload={
                    "stage": "reply_recognized",
                    "asr_node_code": asr_node_code,
                    "recognized_text": recognized_text,
                    "text_content": recognized_text,
                    "matched_edge_code": (step_result.get("next_edge") or {}).get("edge_code"),
                    "next_node_code": next_node.get("node_code"),
                    "speaker_role": "customer",
                },
            ),
        )
        return bundle

    def _should_finalize_from_partial_result(
        self,
        connection: Connection,
        session_item: dict,
        await_reply_config: dict,
        tracker: RealtimeAsrTracker | None,
        idle_seconds: float,
    ) -> bool:
        """判断当前中间识别结果是否已经稳定且可直接命中某个分支。

        参数:
            connection: 当前后台线程使用的 PostgreSQL 数据库连接对象。
            session_item: 当前通话会话对象，用于读取话术版本信息。
            await_reply_config: 当前识别节点等待配置，内部包含识别节点编码。
            tracker: 当前实时 ASR 会话跟踪对象。
            idle_seconds: 中间结果在无更新状态下需要稳定的秒数，超过后才允许提前推进。

        返回:
            bool: 返回当前中间结果是否已经足够稳定且可直接命中后续分支。
        """

        if tracker is None:
            return False
        partial_text = str(tracker.partial_text or "").strip()
        if not partial_text:
            return False
        if str(tracker.final_text or "").strip():
            return False
        if tracker.latest_result_at <= 0:
            return False
        if (time.time() - tracker.latest_result_at) < max(0.2, float(idle_seconds)):
            return False
        return self._can_recognized_text_hit_any_branch(connection, session_item, await_reply_config, partial_text)

    def _can_recognized_text_hit_any_branch(
        self,
        connection: Connection,
        session_item: dict,
        await_reply_config: dict,
        recognized_text: str,
    ) -> bool:
        """判断当前识别文本是否已经能命中识别节点任意一条业务分支。

        参数:
            connection: 当前后台线程使用的 PostgreSQL 数据库连接对象。
            session_item: 当前通话会话对象，用于读取绑定的话术版本。
            await_reply_config: 当前识别节点等待配置，内部包含识别节点编码。
            recognized_text: 当前需要判断的识别文本，可以是中间结果或最终结果。

        返回:
            bool: 返回当前文本是否已命中任意非兜底业务分支；命中时可用于提前推进流程。
        """

        from ..api.schemas.runtime import ScriptStepRequest
        from .runtime_service import execute_script_step

        script_version_id = int(session_item.get("script_version_id") or 0)
        if script_version_id <= 0:
            return False
        asr_node_code = str(await_reply_config.get("asr_node_code") or "").strip()
        if not asr_node_code or not str(recognized_text or "").strip():
            return False
        step_result = execute_script_step(
            connection,
            script_version_id,
            ScriptStepRequest(current_node_code=asr_node_code, asr_text=recognized_text),
        )
        next_edge = step_result.get("next_edge") or {}
        next_node = step_result.get("next_node") or {}
        if not next_node:
            return False
        condition_type = str(next_edge.get("condition_type") or "").strip()
        return condition_type not in {"nomatch", "timeout", "silence"}

    def _hangup_if_active(self, client: Any, call_tracker: CallTracker) -> None:
        """在通话仍处于活动状态时主动挂机。

        参数:
            client: 当前单通呼叫使用的 uSIP 客户端对象。
            call_tracker: 当前呼叫状态跟踪对象。

        返回:
            None: 当前函数仅尝试结束通话，不保证一定产生返回值。
        """

        if not call_tracker.call_id or call_tracker.finished_event.is_set():
            return
        with suppress(Exception):
            client.hangup(call_tracker.call_id)

    def _wait_for_call_finished(self, session_item: dict, client: Any, call_tracker: CallTracker) -> None:
        """等待通话结束并在必要时补全结束状态。

        参数:
            session_item: 当前通话会话对象。
            client: 当前单通呼叫使用的 uSIP 客户端对象。
            call_tracker: 当前呼叫状态跟踪对象。

        返回:
            None: 通话正常结束后不返回业务数据。
        """

        if call_tracker.finished_event.wait(timeout=15):
            return
        self._hangup_if_active(client, call_tracker)
        if call_tracker.finished_event.wait(timeout=5):
            return
        self._write_progress_update(
            session_item["id"],
            build_session_progress_payload(
                session_status="completed",
                answer_status="answered",
                result_code="forced_hangup",
                hangup_cause="通话已完成音频播放，但 SIP 库未及时返回挂断事件，系统已主动结束",
                event_type="hangup",
                payload={"stage": "hangup"},
            ),
        )

    def _report_call_state_change(self, session_id: int, call_tracker: CallTracker, state_name: str, call_info: Any) -> None:
        """把 uSIP 的呼叫状态变化映射为系统会话状态并写回数据库。

        参数:
            session_id: 当前通话会话主键。
            call_tracker: 当前呼叫状态跟踪对象。
            state_name: 当前库回调中的归一化状态名称。
            call_info: SIP 库回传的原始呼叫信息对象。

        返回:
            None: 当前函数仅用于状态回写，不直接返回业务数据。
        """

        if not state_name or call_tracker.last_reported_state == state_name:
            return
        call_tracker.last_reported_state = state_name
        duration_seconds = extract_call_duration_seconds(call_info, call_tracker)
        if state_name == "CALLING":
            payload = build_session_progress_payload(
                session_status="dialing",
                answer_status="unanswered",
                event_type="dialing",
                payload={"sip_call_id": call_tracker.call_id},
            )
        elif state_name == "RINGING":
            payload = build_session_progress_payload(
                session_status="ringing",
                answer_status="unanswered",
                event_type="ringing",
                payload={"sip_call_id": call_tracker.call_id},
            )
        elif state_name == "CONNECTED":
            payload = build_session_progress_payload(
                session_status="answered",
                answer_status="answered",
                event_type="answer",
                billsec=duration_seconds,
                duration=duration_seconds,
                payload={"sip_call_id": call_tracker.call_id},
            )
        elif state_name == "BUSY":
            payload = build_session_progress_payload(
                session_status="failed",
                answer_status="rejected",
                result_code="busy",
                hangup_cause="被叫忙线",
                event_type="hangup",
                duration=duration_seconds,
                payload={"sip_call_id": call_tracker.call_id},
            )
        elif state_name == "FAILED":
            payload = build_session_progress_payload(
                session_status="failed",
                answer_status="timeout",
                result_code="call_failed",
                hangup_cause=call_tracker.end_reason or "SIP 呼叫失败",
                event_type="hangup",
                duration=duration_seconds,
                payload={"sip_call_id": call_tracker.call_id},
            )
        elif state_name == "DISCONNECTED":
            session_status = "completed" if call_tracker.answer_timestamp else "failed"
            answer_status = "answered" if call_tracker.answer_timestamp else "timeout"
            payload = build_session_progress_payload(
                session_status=session_status,
                answer_status=answer_status,
                result_code="hangup",
                hangup_cause="对方挂断" if call_tracker.answer_timestamp else (call_tracker.end_reason or "通话超时结束"),
                event_type="hangup",
                billsec=duration_seconds if call_tracker.answer_timestamp else None,
                duration=duration_seconds,
                payload={"sip_call_id": call_tracker.call_id},
            )
        else:
            return
        self._write_progress_update(session_id, payload)

    def _write_progress_update(self, session_id: int, payload: Any) -> None:
        """使用独立数据库连接回写一次会话状态。

        参数:
            session_id: 当前通话会话主键。
            payload: 会话状态推进请求对象。

        返回:
            None: 当前函数仅负责状态回写。
        """

        connection = connect_db(self.postgres_config)
        try:
            progress_call_session(connection, session_id, payload)
        finally:
            connection.close()


def import_usip_runtime() -> dict[str, Any]:
    """动态导入 uSIP 运行时对象并在缺失时给出明确错误。

    返回:
        dict[str, Any]: 返回 SIPClient、SIPAccount 等运行时对象字典。
    """

    try:
        sip_client_module = importlib.import_module("sip_client")
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            "usip_missing",
            "当前环境未安装 uSIP 依赖，请先执行 uv sync 并确保系统已安装 portaudio 后再启用 SIP 外呼执行器",
        ) from exc
    sip_client_class = getattr(sip_client_module, "SIPClient", None)
    sip_account_class = getattr(sip_client_module, "SIPAccount", None)
    if sip_client_class is None or sip_account_class is None:
        raise AppError("usip_runtime_invalid", "uSIP 安装结果异常，缺少 SIPClient 或 SIPAccount 入口")
    patch_usip_runtime(
        importlib.import_module("sip_client.sip.messages"),
        importlib.import_module("sip_client.sip.protocol"),
        importlib.import_module("sip_client.sip.authentication"),
    )
    return {
        "module": sip_client_module,
        "SIPClient": sip_client_class,
        "SIPAccount": sip_account_class,
    }


def build_usip_account(runtime_objects: dict[str, Any], trunk_item: dict, sip_password: str | None) -> Any:
    """根据线路配置构造 uSIP 所需的账号对象。

    参数:
        runtime_objects: 当前已加载的 uSIP 运行时对象字典。
        trunk_item: 当前绑定的线路对象。
        sip_password: 当前线路解密后的 SIP 密码，可为空。

    返回:
        Any: 返回 uSIP 的 SIPAccount 实例对象。
    """

    account_class = runtime_objects["SIPAccount"]
    username = str(trunk_item.get("username") or trunk_item.get("caller_id_number") or "")
    if trunk_item["trunk_type"] == "sip_account" and not username:
        raise AppError("sip_username_missing", "当前 SIP 账号线路缺少用户名配置")
    if not str(trunk_item.get("server_host") or "").strip():
        raise AppError("sip_server_missing", "当前线路缺少 SIP 服务器地址")
    local_sip_port = find_available_udp_port()
    local_ip = resolve_local_ip_for_target(str(trunk_item["server_host"]).strip())
    account = account_class(
        username=username,
        password=str(sip_password or ""),
        domain=str(trunk_item["server_host"]).strip(),
        port=local_sip_port,
        display_name=str(trunk_item.get("full_name") or trunk_item.get("trunk_name") or username or "AI-VOIP"),
    )
    setattr(account, "server_port", int(trunk_item["server_port"]))
    setattr(account, "server_transport", str(trunk_item.get("transport") or "udp").lower())
    setattr(account, "local_ip", local_ip)
    return account


def normalize_usip_state_value(raw_state: Any) -> str:
    """把 uSIP 回调返回的状态对象统一转换为大写字符串。

    参数:
        raw_state: SIP 库返回的状态枚举、对象或字符串。

    返回:
        str: 返回统一的大写状态值，无法识别时返回 UNKNOWN。
    """

    if raw_state is None:
        return "UNKNOWN"
    if hasattr(raw_state, "value"):
        return str(getattr(raw_state, "value")).upper()
    if hasattr(raw_state, "name"):
        return str(getattr(raw_state, "name")).upper()
    return str(raw_state).upper()


def play_audio_file_over_rtp(
    audio_path: Path,
    remote_rtp_address: tuple[str, int, int, str] | None,
    local_rtp_port: int | None,
    rtp_socket: Any | None = None,
    on_packet_sent: Any | None = None,
) -> int:
    """把本地音频文件转换为 8k 单声道 PCM 后按 PCMU RTP 包推送给对端。

    参数:
        audio_path: 当前需要播放的本地音频文件路径。
        remote_rtp_address: 当前通话对端 RTP 地址与编码信息，格式为 (host, port, payload_type, codec_name)。
        local_rtp_port: 当前通话本地用于发送 RTP 的端口，可为空。
        rtp_socket: 当前通话复用的 RTP 套接字对象，可为空；为空时函数内部会临时创建。
        on_packet_sent: 当前每发送一个 RTP 音频包后触发的回调函数，回调会收到当前已发送的 PCM 音频帧，
            可用于同步记录下行音频和收集对端上行音频。

    返回:
        int: 返回实际推送的音频时长，单位秒。
    """

    if remote_rtp_address is None:
        raise AppError("sip_remote_rtp_missing", "当前通话缺少远端 RTP 地址，无法推送话术音频")
    prepared_wav_path = transcode_audio_to_pcm_wav(audio_path)
    remote_host, remote_port, payload_type, codec_name = remote_rtp_address
    sequence = random.randint(0, 65535)
    timestamp = random.randint(0, 2**31 - 1)
    ssrc = random.randint(1, 2**31 - 1)
    packet_duration = 0.02
    total_frames = 0
    sock = rtp_socket or socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    owns_socket = rtp_socket is None
    try:
        if owns_socket:
            bind_port = int(local_rtp_port or 0)
            sock.bind(("0.0.0.0", bind_port))
        next_send_time = time.perf_counter()
        with wave.open(str(prepared_wav_path), "rb") as wav_file:
            if wav_file.getframerate() != 8000 or wav_file.getnchannels() != 1 or wav_file.getsampwidth() != 2:
                raise AppError("rtp_audio_invalid", "话术音频转码失败，未得到 8k/单声道/16bit PCM WAV")
            while True:
                pcm_frame = wav_file.readframes(160)
                if not pcm_frame:
                    break
                if len(pcm_frame) < 320:
                    pcm_frame = pcm_frame.ljust(320, b"\x00")
                if codec_name == "PCMA":
                    encoded_frame = audioop.lin2alaw(pcm_frame, 2)
                else:
                    encoded_frame = audioop.lin2ulaw(pcm_frame, 2)
                rtp_header = struct.pack(
                    "!BBHII",
                    0x80,
                    payload_type & 0x7F,
                    sequence & 0xFFFF,
                    timestamp & 0xFFFFFFFF,
                    ssrc & 0xFFFFFFFF,
                )
                sleep_seconds = next_send_time - time.perf_counter()
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
                sock.sendto(rtp_header + encoded_frame, (remote_host, remote_port))
                if callable(on_packet_sent):
                    on_packet_sent(pcm_frame)
                sequence += 1
                timestamp += 160
                total_frames += 160
                next_send_time += packet_duration
    finally:
        if owns_socket:
            sock.close()
        if prepared_wav_path != audio_path:
            prepared_wav_path.unlink(missing_ok=True)
    return max(1, int(total_frames / 8000))


def calculate_asr_preroll_bytes(preroll_seconds: float) -> int:
    """把抢话保护时间换算成 8k 单声道 16bit PCM 字节数。

    参数:
        preroll_seconds: 当前希望在 TTS 播报结束前保留的预收音时长，单位为秒。

    返回:
        int: 返回需要回溯送入 ASR 的 PCM 字节数，最小值为 0。
    """

    normalized_preroll_seconds = max(0.0, float(preroll_seconds))
    sample_rate = 8000
    sample_width = 2
    return int(normalized_preroll_seconds * sample_rate * sample_width)


def apply_runtime_asr_overrides(provider_item: dict, await_reply_config: dict) -> dict:
    """把识别节点运行时配置覆盖到 ASR 接口配置上。

    参数:
        provider_item: 当前命中的 ASR 接口配置对象。
        await_reply_config: 当前识别节点等待配置，内部可包含断句静音时间等运行时参数。

    返回:
        dict: 返回已经合并运行时参数的新接口配置对象，不会修改原始字典。
    """

    config_json = dict(provider_item.get("config_json") or {})
    custom_params = dict(config_json.get("custom_params") or {})
    sentence_silence_ms = int(await_reply_config.get("sentence_silence_ms") or 0)
    if sentence_silence_ms > 0:
        custom_params["max_sentence_silence"] = sentence_silence_ms
        custom_params["sentence_silence_ms"] = sentence_silence_ms
    config_json["custom_params"] = custom_params
    return {
        **provider_item,
        "config_json": config_json,
    }


def should_finalize_realtime_asr_early(
    tracker: RealtimeAsrTracker | None,
    idle_seconds: float,
) -> bool:
    """判断当前实时 ASR 会话是否已经可以提前结束等待窗口。

    参数:
        tracker: 当前实时 ASR 会话跟踪对象；为空时表示当前没有启用实时识别。
        idle_seconds: 最近一次收到识别文本后允许继续等待的空闲秒数，超过后视为结果稳定。

    返回:
        bool: 返回是否可以提前结束等待窗口；仅当已拿到最终句且一段时间没有新文本时返回 True。
    """

    if tracker is None:
        return False
    if not normalize_effective_recognized_text(tracker.final_text):
        return False
    if tracker.latest_result_at <= 0:
        return False
    return (time.time() - tracker.latest_result_at) >= max(0.2, float(idle_seconds))


def normalize_effective_recognized_text(source_text: str | None) -> str:
    """把实时 ASR 文本规整成可参与业务分支判断的有效文本。

    参数:
        source_text: 当前实时 ASR 返回的原始文本，可能包含标点、空白和语气词。

    返回:
        str: 返回过滤后的有效文本；若当前文本只是无意义短句或语气词，则返回空字符串。
    """

    raw_text = str(source_text or "").strip()
    if not raw_text:
        return ""

    # 先移除常见中文标点和空白，保证“啊。”与“啊”按同一规则过滤。
    normalized_text = re.sub(r"[，。！？、；：,.!?;:\"'“”‘’（）()【】\\[\\]\\-—_\\s]+", "", raw_text.lower())
    if not normalized_text:
        return ""

    # 这些短句通常只是起音、应答音或无业务含义的语气词，不应直接推进分支或触发兜底。
    invalid_short_phrases = {
        "啊",
        "阿",
        "嗯",
        "恩",
        "哦",
        "喔",
        "噢",
        "哎",
        "诶",
        "欸",
        "唉",
        "喂",
        "哈",
        "呵",
    }
    if normalized_text in invalid_short_phrases:
        return ""

    # 连续重复的单个语气字也视为无效短句，例如“啊啊”“嗯嗯”“喂喂”。
    if len(set(normalized_text)) == 1 and normalized_text[0] in "".join(sorted(invalid_short_phrases)) and len(normalized_text) <= 3:
        return ""

    return raw_text


def transcode_audio_to_pcm_wav(audio_path: Path) -> Path:
    """使用 ffmpeg 把任意输入音频转成 8k 单声道 16bit PCM WAV。

    参数:
        audio_path: 当前需要转码的音频文件路径。

    返回:
        Path: 返回转码后的临时 WAV 文件路径；若原文件已满足要求，则仍返回可用 WAV 路径。
    """

    if audio_path.suffix.lower() == ".wav":
        try:
            with wave.open(str(audio_path), "rb") as wav_file:
                if wav_file.getframerate() == 8000 and wav_file.getnchannels() == 1 and wav_file.getsampwidth() == 2:
                    return audio_path
        except Exception:
            pass
    with NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        output_path = Path(temp_file.name)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(audio_path),
        "-ac",
        "1",
        "-ar",
        "8000",
        "-acodec",
        "pcm_s16le",
        str(output_path),
    ]
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        output_path.unlink(missing_ok=True)
        raise AppError(
            "ffmpeg_transcode_failed",
            f"话术音频转码失败，请确认 ffmpeg 可用。stderr={process.stderr.strip() or 'unknown'}",
        )
    return output_path


def estimate_audio_duration_seconds(audio_path: Path) -> int:
    """估算本地音频文件的播放时长。

    参数:
        audio_path: 当前需要估算时长的本地音频文件路径。

    返回:
        int: 返回估算的播放时长，单位秒，最小值为 1。
    """

    try:
        if audio_path.suffix.lower() == ".wav":
            with wave.open(str(audio_path), "rb") as wav_file:
                frame_count = wav_file.getnframes()
                frame_rate = wav_file.getframerate()
                if frame_rate > 0:
                    return max(1, int(frame_count / frame_rate))
    except Exception:
        pass
    return max(1, int(audio_path.stat().st_size / 64000))


def find_available_udp_port() -> int:
    """查找一个可用的本地 UDP 端口用于 RTP 发送。

    参数:
        无: 当前函数内部自行向系统申请临时端口。

    返回:
        int: 返回系统当前可用的 UDP 端口号。
    """

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("0.0.0.0", 0))
        return int(sock.getsockname()[1])


def create_bound_rtp_socket(local_rtp_port: int) -> socket.socket:
    """创建并绑定当前通话复用的 RTP 套接字。

    参数:
        local_rtp_port: 当前通话本地 RTP 端口。

    返回:
        socket.socket: 返回已绑定并设置超时的 UDP 套接字对象。
    """

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", int(local_rtp_port)))
    sock.settimeout(0.2)
    return sock


def extract_rtp_audio_payload(packet_bytes: bytes) -> bytes:
    """从 RTP 数据包中提取音频负载字节。

    参数:
        packet_bytes: 当前收到的 RTP 原始二进制数据。

    返回:
        bytes: 返回剥离 RTP 头后的音频负载字节，格式异常时返回空字节串。
    """

    if len(packet_bytes) < 12:
        return b""
    first_byte = packet_bytes[0]
    csrc_count = first_byte & 0x0F
    has_extension = bool(first_byte & 0x10)
    header_length = 12 + (csrc_count * 4)
    if len(packet_bytes) < header_length:
        return b""
    if has_extension:
        if len(packet_bytes) < header_length + 4:
            return b""
        extension_length = struct.unpack("!H", packet_bytes[header_length + 2 : header_length + 4])[0] * 4
        header_length += 4 + extension_length
    if len(packet_bytes) <= header_length:
        return b""
    return packet_bytes[header_length:]


def decode_rtp_audio_payload(encoded_payload: bytes, codec_name: str) -> bytes:
    """把 RTP 负载按协商编码解码为 16bit PCM 数据。

    参数:
        encoded_payload: 当前 RTP 包中的音频负载字节。
        codec_name: 当前 RTP 协商编码名称，支持 `PCMA` 与 `PCMU`。

    返回:
        bytes: 返回解码后的 16bit PCM 字节流；不支持的编码返回空字节串。
    """

    normalized_codec_name = str(codec_name or "").upper()
    if normalized_codec_name == "PCMA":
        return audioop.alaw2lin(encoded_payload, 2)
    if normalized_codec_name == "PCMU":
        return audioop.ulaw2lin(encoded_payload, 2)
    return b""


def build_wav_bytes_from_pcm(pcm_bytes: bytes, sample_rate: int = 8000, channels: int = 1) -> bytes:
    """把内存中的 PCM 字节流封装成标准 WAV 文件字节串。

    参数:
        pcm_bytes: 当前需要封装的 16bit PCM 音频字节流。
        sample_rate: 当前音频采样率，默认 8000Hz。
        channels: 当前音频通道数，默认单声道。

    返回:
        bytes: 返回完整的 WAV 文件字节串。
    """

    with io.BytesIO() as buffer:
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
        return buffer.getvalue()


def align_pcm_sample_offset_bytes(offset_bytes: int, sample_width: int = 2) -> int:
    """把 PCM 时间轴偏移量对齐到完整采样边界，避免样本字节错位。

    参数:
        offset_bytes: 当前根据时间差换算得到的原始字节偏移量。
        sample_width: 当前 PCM 单个采样占用的字节数，16bit 单声道默认 2 字节。

    返回:
        int: 返回按完整采样边界对齐后的字节偏移量。
    """

    normalized_offset_bytes = max(0, int(offset_bytes))
    normalized_sample_width = max(1, int(sample_width))
    return normalized_offset_bytes - (normalized_offset_bytes % normalized_sample_width)


def build_stereo_call_recording_pcm(inbound_pcm_bytes: bytes, outbound_pcm_bytes: bytes) -> bytes:
    """把上下行 PCM 音频按时间轴对齐后封装为双声道通话录音。

    参数:
        inbound_pcm_bytes: 当前通话上行 PCM 音频字节流，通常代表客户声音。
        outbound_pcm_bytes: 当前通话下行 PCM 音频字节流，通常代表系统播报声音。

    返回:
        bytes: 返回左右声道交错后的双声道 PCM 字节流，左声道为客服播报，右声道为客户声音。
    """

    max_length = max(len(inbound_pcm_bytes), len(outbound_pcm_bytes))
    if max_length <= 0:
        return b""
    if max_length % 2 != 0:
        max_length += 1

    # 双声道录音保留原始上下行波形，避免单声道强行相加造成削顶爆音和听感失真。
    normalized_inbound_pcm = inbound_pcm_bytes.ljust(max_length, b"\x00")
    normalized_outbound_pcm = outbound_pcm_bytes.ljust(max_length, b"\x00")
    stereo_frames = bytearray(max_length * 2)
    target_offset = 0
    for source_offset in range(0, max_length, 2):
        stereo_frames[target_offset : target_offset + 2] = normalized_outbound_pcm[source_offset : source_offset + 2]
        stereo_frames[target_offset + 2 : target_offset + 4] = normalized_inbound_pcm[source_offset : source_offset + 2]
        target_offset += 4
    return bytes(stereo_frames)


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


def build_aliyun_ws_run_task_payload(config_json: dict, task_id: str) -> dict:
    """构造阿里云实时 ASR 的 `run-task` 指令。

    参数:
        config_json: 当前 ASR 接口配置中的 `config_json` 字典。
        task_id: 当前识别任务 ID，后续 `finish-task` 需要复用该值。

    返回:
        dict: 返回可直接发送到 WebSocket 的任务启动事件对象。
    """

    custom_params = config_json.get("custom_params") or {}
    sample_rate = int(custom_params.get("sample_rate") or 8000)
    language_hints = build_aliyun_ws_language_hints(custom_params)
    parameters: dict[str, Any] = {
        "format": "pcm",
        "sample_rate": 8000 if sample_rate not in {8000, 16000} else sample_rate,
        "semantic_punctuation_enabled": bool(custom_params.get("semantic_punctuation_enabled", False)),
        "max_sentence_silence": int(custom_params.get("max_sentence_silence") or custom_params.get("silence_duration_ms") or 500),
        "multi_threshold_mode_enabled": bool(custom_params.get("multi_threshold_mode_enabled", False)),
        "disfluency_removal_enabled": bool(custom_params.get("disfluency_removal_enabled", True)),
        "punctuation_prediction_enabled": bool(custom_params.get("punctuation_prediction_enabled", True)),
        "inverse_text_normalization_enabled": bool(custom_params.get("inverse_text_normalization_enabled", True)),
        "heartbeat": bool(custom_params.get("heartbeat", False)),
    }
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
        }
    }


def build_aliyun_ws_finish_task_payload(task_id: str) -> dict:
    """构造阿里云实时 ASR 的 `finish-task` 指令。

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
    """把阿里云实时 ASR 配置中的语言提示转换为列表。

    参数:
        custom_params: 当前 ASR 接口自定义参数字典。

    返回:
        list[str]: 返回已经去除空白项的语言提示数组。
    """

    raw_value = str(custom_params.get("language_hints") or custom_params.get("language") or "").replace("，", ",")
    if not raw_value:
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def parse_aliyun_ws_asr_message(raw_message: Any) -> dict:
    """把阿里云实时 ASR WebSocket 消息解析为统一字典结构。

    参数:
        raw_message: WebSocket 收到的原始消息对象，可能为字符串、字节串或字典。

    返回:
        dict: 返回解析后的消息字典，异常时抛出业务错误。
    """

    if isinstance(raw_message, dict):
        return raw_message
    if isinstance(raw_message, bytes):
        raw_message = raw_message.decode("utf-8")
    try:
        return json.loads(str(raw_message))
    except Exception as exc:  # noqa: BLE001
        raise AppError("asr_message_invalid", f"阿里云实时 ASR 返回了无法解析的消息：{exc!r}") from exc


def extract_aliyun_ws_asr_result(message: dict) -> tuple[str, bool]:
    """从阿里云实时 ASR 的 `result-generated` 事件中提取文本与终句标记。

    参数:
        message: 当前阿里云实时 ASR 服务端返回的消息字典。

    返回:
        tuple[str, bool]: 返回 `(文本内容, 是否为最终句)`，没有可用结果时返回 `("", False)`。
    """

    payload = message.get("payload") or {}
    output = payload.get("output") or {}
    sentence = output.get("sentence") or {}
    if not sentence or sentence.get("heartbeat") is True:
        return "", False
    text = str(sentence.get("text") or "").strip()
    return text, bool(sentence.get("sentence_end"))


def extract_aliyun_ws_asr_error_message(message: dict) -> str:
    """从阿里云实时 ASR 错误消息中提取可读错误说明。

    参数:
        message: 当前阿里云实时 ASR 服务端返回的消息字典。

    返回:
        str: 返回适合记录日志的错误说明文本。
    """

    header = message.get("header") or {}
    for key in ("error_message", "error_msg", "message"):
        value = str(header.get(key) or message.get(key) or "").strip()
        if value:
            return value
    return "阿里云实时 ASR 返回未知错误"


def resolve_local_ip_for_target(target_host: str) -> str:
    """根据目标 SIP 服务器地址推导本机应对外通告的局域网 IP。

    参数:
        target_host: 当前 SIP 服务端主机地址。

    返回:
        str: 返回当前机器到目标主机的最佳本地出口 IP。
    """

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((target_host, 5060))
            return str(sock.getsockname()[0])
    except Exception:
        return "127.0.0.1"


def extract_remote_rtp_address_from_sip_message(message: str, call_id: str | None) -> tuple[str, int, int, str] | None:
    """从 SIP 响应报文的 SDP 内容中解析远端 RTP 地址。

    参数:
        message: 当前收到的原始 SIP 文本报文。
        call_id: 当前通话在 SIP 库中的唯一标识，用于过滤非当前通话报文。

    返回:
        tuple[str, int, int, str] | None: 解析成功时返回远端 RTP 地址、负载类型和编码名称，否则返回 None。
    """

    if not call_id or "SIP/2.0" not in message:
        return None
    normalized_message = message.replace("\r\n", "\n")
    if f"Call-ID: {call_id}" not in normalized_message and f"Call-Id: {call_id}" not in normalized_message:
        return None
    body_parts = re.split(r"\r?\n\r?\n", message, maxsplit=1)
    if len(body_parts) != 2:
        return None
    sdp_body = body_parts[1].replace("\r\n", "\n")
    connection_match = re.search(r"^c=IN IP4 ([^\r\n]+)$", sdp_body, re.MULTILINE)
    media_match = re.search(r"^m=audio (\d+) [^\r\n]* ([0-9 ]+)$", sdp_body, re.MULTILINE)
    if not connection_match or not media_match:
        return None
    host = connection_match.group(1).strip()
    port = int(media_match.group(1))
    payload_types = [int(item) for item in media_match.group(2).split() if item.strip().isdigit()]
    rtpmap_matches = re.findall(r"^a=rtpmap:(\d+) ([^/\r\n]+)", sdp_body, re.MULTILINE)
    codec_mapping = {int(payload): str(codec).upper() for payload, codec in rtpmap_matches}

    for payload_type in payload_types:
        codec_name = codec_mapping.get(payload_type)
        if payload_type == 8 or codec_name == "PCMA":
            return host, port, 8, "PCMA"
        if payload_type == 0 or codec_name == "PCMU":
            return host, port, 0, "PCMU"

    return host, port, 0, "PCMU"


def patch_usip_runtime(messages_module: Any, protocol_module: Any, authentication_module: Any) -> None:
    """为第三方 uSIP 运行时打补丁，修正本地地址、端口与鉴权重发逻辑。

    参数:
        messages_module: `sip_client.sip.messages` 模块对象。
        protocol_module: `sip_client.sip.protocol` 模块对象。
        authentication_module: `sip_client.sip.authentication` 模块对象。

    返回:
        None: 当前函数仅修改运行时行为，不直接返回业务数据。
    """

    if getattr(protocol_module, "_aivoip_patched", False):
        return

    def generate_call_id_for_runtime(domain: str) -> str:
        """从 uSIP 协议模块生成 Call-ID，避免误从 messages 模块取不到函数。

        参数:
            domain: 当前 SIP 域名或服务端地址。

        返回:
            str: 返回符合当前 uSIP 版本的 Call-ID 字符串。
        """

        return str(protocol_module.generate_call_id(domain))

    def generate_tag_for_runtime() -> str:
        """从 uSIP 协议模块生成本地 tag。

        参数:
            无: 当前函数内部直接调用协议模块工具函数。

        返回:
            str: 返回本次 SIP 会话使用的本地 tag。
        """

        return str(protocol_module.generate_tag())

    def generate_branch_for_runtime() -> str:
        """从 uSIP 协议模块生成 Via branch。

        参数:
            无: 当前函数内部直接调用协议模块工具函数。

        返回:
            str: 返回本次 SIP 事务使用的 branch 标识。
        """

        return str(protocol_module.generate_branch())

    def get_runtime_host() -> str:
        """读取当前补丁上下文中的本地通告地址。

        参数:
            无: 当前函数通过模块级共享状态读取地址。

        返回:
            str: 返回当前需要写入 SIP 报文的本地地址。
        """

        return str(getattr(messages_module, "_aivoip_local_host", "127.0.0.1"))

    def patched_send_message(self, message: str, address: tuple[str, int] | None = None) -> bool:
        """修正 uSIP 默认发送地址逻辑，使其使用远端服务端口而非本地监听端口。

        参数:
            self: 当前 SIPProtocol 实例对象。
            message: 当前需要发送的 SIP 报文文本。
            address: 外部显式指定的目标地址，可为空。

        返回:
            bool: 发送成功返回 True，失败返回 False。
        """

        try:
            if address is None:
                remote_port = int(getattr(self.account, "server_port", self.account.port))
                address = (self.account.domain, remote_port)
            self.socket.sendto(message.encode(), address)
            protocol_module.logger.debug(f"Sent message to {address}: {message}")
            return True
        except Exception as exc:  # noqa: BLE001
            protocol_module.logger.error(f"Failed to send message: {exc}")
            return False

    def patched_start(self) -> bool:
        """修正 uSIP 的启动逻辑，使 SIP 套接字绑定到正确的本地端口。

        参数:
            self: 当前 SIPProtocol 实例对象。

        返回:
            bool: 启动成功返回 True，失败返回 False。
        """

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            local_ip = str(getattr(self.account, "local_ip", "0.0.0.0"))
            self.socket.bind((local_ip, int(self.account.port)))
            self.socket.settimeout(10)
            self.listening = True
            self.message_thread = threading.Thread(target=self._message_listener, daemon=True)
            self.message_thread.start()
            protocol_module.logger.info("SIP protocol started")
            return True
        except Exception as exc:  # noqa: BLE001
            protocol_module.logger.error(f"Failed to start SIP protocol: {exc}")
            return False

    client_module = importlib.import_module("sip_client.client")
    call_model_module = importlib.import_module("sip_client.models.call")
    enum_module = importlib.import_module("sip_client.models.enums")
    helper_module = importlib.import_module("sip_client.utils.helpers")

    original_send_register = protocol_module.SIPProtocol.send_register
    original_send_invite = protocol_module.SIPProtocol.send_invite
    original_handle_auth_challenge = protocol_module.SIPProtocol.handle_auth_challenge
    original_make_call = client_module.SIPClient.make_call
    original_start_keepalive = client_module.SIPClient._start_keepalive

    def patched_send_register(self, expires: int = 3600) -> bool:
        """在发送 REGISTER 前注入正确的本地通告地址。

        参数:
            self: 当前 SIPProtocol 实例对象。
            expires: REGISTER 有效期，单位秒。

        返回:
            bool: 发送成功返回 True，失败返回 False。
        """

        messages_module._aivoip_local_host = str(getattr(self.account, "local_ip", "127.0.0.1"))
        try:
            call_id = generate_call_id_for_runtime(self.account.domain)
            local_tag = generate_tag_for_runtime()
            branch = generate_branch_for_runtime()
            setattr(self, "_aivoip_last_register_call_id", call_id)
            setattr(self, "_aivoip_last_register_local_tag", local_tag)
            uri = f"sip:{self.account.domain}"
            headers = messages_module.SIPMessageBuilder.create_register_headers(
                self.account.username,
                self.account.domain,
                self.account.port,
                local_tag,
                branch,
                call_id,
                self.cseq,
                expires,
            )
            message = messages_module.SIPMessageBuilder.create_message("REGISTER", uri, headers)
            result = self.send_message(message)
            if result:
                self.cseq += 1
            return result
        except Exception as exc:  # noqa: BLE001
            protocol_module.logger.error(f"Failed to send REGISTER: {exc}")
            return False

    def patched_send_invite(self, target_uri: str, rtp_port: int = 10000):
        """在发送 INVITE 前注入正确的本地通告地址和当前 RTP 端口。

        参数:
            self: 当前 SIPProtocol 实例对象。
            target_uri: 当前被叫 SIP URI。
            rtp_port: 当前通话使用的本地 RTP 端口。

        返回:
            object: 返回第三方库原始 `send_invite` 的结果值。
        """

        messages_module._aivoip_local_host = str(getattr(self.account, "local_ip", "127.0.0.1"))
        messages_module._aivoip_rtp_port = int(rtp_port)
        setattr(self.account, "rtp_port", int(rtp_port))
        try:
            if not target_uri.startswith("sip:"):
                target_uri = f"sip:{target_uri}@{self.account.domain};user=phone"
            elif ";user=phone" not in target_uri:
                target_uri = f"{target_uri};user=phone"
            call_id = generate_call_id_for_runtime(self.account.domain)
            local_tag = generate_tag_for_runtime()
            branch = generate_branch_for_runtime()
            headers = messages_module.SIPMessageBuilder.create_invite_headers(
                self.account.username,
                self.account.domain,
                self.account.port,
                target_uri,
                local_tag,
                branch,
                call_id,
                self.cseq,
            )
            body = messages_module.SIPMessageBuilder.create_sdp_body(self.account.username, rtp_port)
            message = messages_module.SIPMessageBuilder.create_message("INVITE", target_uri, headers, body)
            setattr(
                self,
                "_aivoip_last_invite_context",
                {
                    "call_id": call_id,
                    "local_tag": local_tag,
                    "target_uri": target_uri,
                    "rtp_port": int(rtp_port),
                    "invite_cseq": int(self.cseq),
                    "auth_resend_count": 0,
                    "has_provisional_response": False,
                },
            )
            protocol_module.logger.info(
                "Sending INVITE: uri=%s call_id=%s local_tag=%s cseq=%s rtp_port=%s",
                target_uri,
                call_id,
                local_tag,
                self.cseq,
                rtp_port,
            )
            result = self.send_message(message)
            if result:
                self.cseq += 1
                return call_id
            return None
        except Exception as exc:  # noqa: BLE001
            protocol_module.logger.error(f"Failed to send INVITE: {exc}")
            return None

    def patched_handle_auth_challenge(self, response: str, method: str, uri: str) -> bool:
        """在处理 401/407 鉴权重发前补入正确的本地地址上下文。

        参数:
            self: 当前 SIPProtocol 实例对象。
            response: 服务端返回的鉴权挑战报文。
            method: 当前需要重发鉴权的 SIP 方法。
            uri: 当前请求 URI。

        返回:
            bool: 重发成功返回 True，失败返回 False。
        """

        messages_module._aivoip_local_host = str(getattr(self.account, "local_ip", "127.0.0.1"))
        messages_module._aivoip_rtp_port = int(getattr(self.account, "rtp_port", 10000))
        try:
            challenge = self.authenticator.parse_auth_challenge(response)
            if not challenge:
                return False
            response_code = messages_module.SIPMessageParser.get_response_code(response)
            protocol_module.logger.info(
                "收到 SIP 鉴权挑战: method=%s uri=%s code=%s",
                method,
                uri,
                response_code,
            )
            header_name = "Proxy-Authorization" if response_code == 407 else "Authorization"
            auth_header = self.authenticator.create_auth_response(challenge, method, uri)
            if method == "REGISTER":
                call_id = str(getattr(self, "_aivoip_last_register_call_id", generate_call_id_for_runtime(self.account.domain)))
                local_tag = str(getattr(self, "_aivoip_last_register_local_tag", generate_tag_for_runtime()))
                headers = messages_module.SIPMessageBuilder.create_register_headers(
                    self.account.username,
                    self.account.domain,
                    self.account.port,
                    local_tag,
                    generate_branch_for_runtime(),
                    call_id,
                    self.cseq,
                    3600,
                )
                headers[header_name] = auth_header
                request_message = messages_module.SIPMessageBuilder.create_message("REGISTER", f"sip:{self.account.domain}", headers)
            elif method == "INVITE":
                response_headers = messages_module.SIPMessageParser.parse_headers(response)
                invite_context = getattr(self, "_aivoip_last_invite_context", {}) or {}
                call_id = str(
                    response_headers.get("Call-ID")
                    or response_headers.get("Call-Id")
                    or invite_context.get("call_id")
                    or generate_call_id_for_runtime(self.account.domain)
                )
                local_tag = str(
                    messages_module.SIPMessageParser.extract_tag(str(response_headers.get("From") or ""))
                    or invite_context.get("local_tag")
                    or generate_tag_for_runtime()
                )
                invite_uri = str(invite_context.get("target_uri") or uri)
                headers = messages_module.SIPMessageBuilder.create_invite_headers(
                    self.account.username,
                    self.account.domain,
                    self.account.port,
                    invite_uri,
                    local_tag,
                    generate_branch_for_runtime(),
                    call_id,
                    self.cseq,
                )
                headers[header_name] = auth_header
                body = messages_module.SIPMessageBuilder.create_sdp_body(
                    self.account.username,
                    int(invite_context.get("rtp_port") or getattr(self.account, "rtp_port", 10000)),
                )
                request_message = messages_module.SIPMessageBuilder.create_message("INVITE", invite_uri, headers, body)
            else:
                return original_handle_auth_challenge(self, response, method, uri)

            if method == "INVITE":
                provisional_started = bool(invite_context.get("has_provisional_response"))
                auth_resend_count = int(invite_context.get("auth_resend_count") or 0)
                if provisional_started or auth_resend_count >= 1:
                    protocol_module.logger.info(
                        "忽略重复 INVITE 鉴权挑战: uri=%s call_id=%s provisional=%s auth_resend_count=%s",
                        invite_uri,
                        call_id,
                        provisional_started,
                        auth_resend_count,
                    )
                    return True
            result = self.send_message(request_message)
            if result:
                if method == "INVITE":
                    invite_context["auth_resend_count"] = int(invite_context.get("auth_resend_count") or 0) + 1
                    setattr(self, "_aivoip_last_invite_context", invite_context)
                protocol_module.logger.info(
                    "Resent %s after auth challenge: uri=%s call_id=%s local_tag=%s cseq=%s header=%s",
                    method,
                    f"sip:{self.account.domain}" if method == "REGISTER" else invite_uri,
                    call_id,
                    local_tag,
                    self.cseq,
                    header_name,
                )
                self.cseq += 1
            return result
        except Exception as exc:  # noqa: BLE001
            protocol_module.logger.error(f"Failed to handle auth challenge: {exc}")
            return False

    def patched_start_keepalive(self) -> None:
        """修正 uSIP 的保活定时器，避免重复创建多个 REGISTER 续订线程。

        参数:
            self: 当前 SIPClient 实例对象。

        返回:
            None: 当前函数仅负责维护单例保活定时器。
        """

        existing_timer = getattr(self, "keepalive_timer", None)
        if existing_timer is not None:
            with suppress(Exception):
                existing_timer.cancel()

        def keepalive() -> None:
            """按固定间隔执行单次续订注册请求。

            参数:
                无: 当前闭包直接使用外层 SIPClient 实例。

            返回:
                None: 当前函数仅触发续订请求。
            """

            if self.registration_state == enum_module.RegistrationState.REGISTERED:
                self.register()
                self.keepalive_timer = threading.Timer(self.keepalive_interval, keepalive)
                self.keepalive_timer.daemon = True
                self.keepalive_timer.start()

        self.keepalive_timer = threading.Timer(self.keepalive_interval, keepalive)
        self.keepalive_timer.daemon = True
        self.keepalive_timer.start()

    def patched_make_call(self, target_uri: str, input_device: int | None = None, output_device: int | None = None):
        """修正 uSIP 的外呼竞态，确保首个 INVITE 响应到达时本地已有呼叫上下文。

        参数:
            target_uri: 当前被叫 SIP URI。
            input_device: 输入设备编号，可为空。
            output_device: 输出设备编号，可为空。

        返回:
            str | None: 拨号成功时返回 call_id，失败时返回 None。
        """

        if self.registration_state != enum_module.RegistrationState.REGISTERED:
            client_module.logger.error("Not registered")
            return None

        try:
            if not target_uri.startswith("sip:"):
                if not target_uri.startswith("+"):
                    target_uri = f"+1{target_uri}"
                target_uri = f"sip:{target_uri}@{self.account.domain}"

            if input_device is None:
                device = self.audio_manager.get_default_input_device()
                input_device = device.index if device else 0

            if output_device is None:
                device = self.audio_manager.get_default_output_device()
                output_device = device.index if device else 0

            setattr(
                self,
                "_aivoip_pending_invite_meta",
                {
                    "target_uri": target_uri,
                    "input_device": input_device,
                    "output_device": output_device,
                },
            )
            call_id = self.sip_protocol.send_invite(target_uri, self.rtp_port)
            if not call_id:
                return None

            call_info = self.calls.get(call_id)
            invite_context = getattr(self.sip_protocol, "_aivoip_last_invite_context", {}) or {}
            if call_info is None:
                call_info = call_model_module.CallInfo(
                    call_id=call_id,
                    local_uri=self.account.uri,
                    remote_uri=target_uri,
                    state=enum_module.CallState.CALLING,
                    direction="outgoing",
                    start_time=time.time(),
                    local_tag=str(invite_context.get("local_tag") or helper_module.generate_tag()),
                    input_device=input_device,
                    output_device=output_device,
                    cseq=int(invite_context.get("invite_cseq") or max(1, self.sip_protocol.cseq - 1)),
                )
                self.calls[call_id] = call_info
                self._set_call_state(call_info, enum_module.CallState.CALLING)
            else:
                call_info.remote_uri = target_uri
                call_info.input_device = input_device
                call_info.output_device = output_device
                call_info.local_tag = str(call_info.local_tag or invite_context.get("local_tag") or helper_module.generate_tag())
                call_info.cseq = int(invite_context.get("invite_cseq") or call_info.cseq or 1)

            client_module.logger.info(f"Call initiated: {call_id}")
            return call_id
        except Exception as exc:  # noqa: BLE001
            client_module.logger.error(f"Call error: {exc}")
            return None

    def patched_handle_sip_response(self, message: str, response_code: int) -> None:
        """按 CSeq 方法精确处理 SIP 响应，并补齐早到 INVITE 响应的呼叫上下文。

        参数:
            message: 当前收到的原始 SIP 响应报文。
            response_code: 当前响应码。

        返回:
            None: 当前函数仅负责更新 SIPClient 内部状态。
        """

        cseq_info = messages_module.SIPMessageParser.extract_cseq(message)
        method = str(cseq_info[1]).upper() if cseq_info else ""
        call_id = messages_module.SIPMessageParser.extract_call_id(message)
        client_module.logger.info(
            "收到 SIP 响应: method=%s code=%s call_id=%s",
            method or "UNKNOWN",
            response_code,
            call_id or "",
        )

        if method == "REGISTER":
            if response_code == 200:
                self._set_registration_state(enum_module.RegistrationState.REGISTERED)
                self._start_keepalive()
            elif response_code in [401, 407]:
                success = self.sip_protocol.handle_auth_challenge(message, "REGISTER", f"sip:{self.account.domain}")
                if not success:
                    self._set_registration_state(enum_module.RegistrationState.FAILED)
            else:
                self._set_registration_state(enum_module.RegistrationState.FAILED)
            return

        if method != "INVITE":
            return

        if call_id and call_id not in self.calls:
            invite_context = getattr(self.sip_protocol, "_aivoip_last_invite_context", {}) or {}
            pending_meta = getattr(self, "_aivoip_pending_invite_meta", {}) or {}
            if str(invite_context.get("call_id") or "") == str(call_id):
                self.calls[call_id] = call_model_module.CallInfo(
                    call_id=call_id,
                    local_uri=self.account.uri,
                    remote_uri=str(pending_meta.get("target_uri") or invite_context.get("target_uri") or ""),
                    state=enum_module.CallState.CALLING,
                    direction="outgoing",
                    start_time=time.time(),
                    local_tag=str(invite_context.get("local_tag") or helper_module.generate_tag()),
                    input_device=pending_meta.get("input_device"),
                    output_device=pending_meta.get("output_device"),
                    cseq=int(invite_context.get("invite_cseq") or max(1, self.sip_protocol.cseq - 1)),
                )

        if not call_id or call_id not in self.calls:
            return

        call_info = self.calls[call_id]
        if cseq_info:
            call_info.cseq = int(cseq_info[0])

        if response_code == 200:
            sip_info = self.sip_protocol.extract_sip_info(message)
            call_info.remote_tag = sip_info.get("to_tag")
            call_info.contact_uri = sip_info.get("contact_uri")
            remote_rtp_address = extract_remote_rtp_address_from_sip_message(message, call_id)
            if remote_rtp_address:
                client_module.logger.info(
                    "在 200 OK 中解析到远端 RTP 地址: call_id=%s remote=%s",
                    call_id,
                    remote_rtp_address,
                )
                on_message_handler = getattr(self, "on_message", None)
                if callable(on_message_handler):
                    with suppress(Exception):
                        on_message_handler(message, "")
            call_info.answer_time = time.time()
            self._set_call_state(call_info, enum_module.CallState.CONNECTED)
            self.sip_protocol.send_ack(call_info)
            client_module.logger.info(
                "通话已接通，跳过本地音频设备初始化，后续改由自定义 RTP 推送媒体: call_id=%s",
                call_id,
            )
        elif response_code == 180:
            invite_context = getattr(self.sip_protocol, "_aivoip_last_invite_context", {}) or {}
            if str(invite_context.get("call_id") or "") == str(call_id):
                invite_context["has_provisional_response"] = True
                setattr(self.sip_protocol, "_aivoip_last_invite_context", invite_context)
            self._set_call_state(call_info, enum_module.CallState.RINGING)
        elif response_code == 183:
            invite_context = getattr(self.sip_protocol, "_aivoip_last_invite_context", {}) or {}
            if str(invite_context.get("call_id") or "") == str(call_id):
                invite_context["has_provisional_response"] = True
                setattr(self.sip_protocol, "_aivoip_last_invite_context", invite_context)
            remote_rtp_address = extract_remote_rtp_address_from_sip_message(message, call_id)
            if remote_rtp_address:
                client_module.logger.info(
                    "在 183 中解析到远端 RTP 地址: call_id=%s remote=%s",
                    call_id,
                    remote_rtp_address,
                )
                on_message_handler = getattr(self, "on_message", None)
                if callable(on_message_handler):
                    with suppress(Exception):
                        on_message_handler(message, "")
            client_module.logger.info("收到 183 Session Progress: call_id=%s", call_id)
        elif response_code == 486:
            self._set_call_state(call_info, enum_module.CallState.BUSY)
            del self.calls[call_id]
        elif response_code in [401, 407]:
            invite_context = getattr(self.sip_protocol, "_aivoip_last_invite_context", {}) or {}
            if str(invite_context.get("call_id") or "") == str(call_id):
                if bool(invite_context.get("has_provisional_response")) or int(invite_context.get("auth_resend_count") or 0) >= 1:
                    client_module.logger.info(
                        "忽略迟到的 INVITE 鉴权挑战响应: code=%s call_id=%s state=%s auth_resend_count=%s",
                        response_code,
                        call_id,
                        call_info.state.value,
                        invite_context.get("auth_resend_count"),
                    )
                    return
            success = self.sip_protocol.handle_auth_challenge(message, "INVITE", call_info.remote_uri)
            if not success:
                self._set_call_state(call_info, enum_module.CallState.FAILED)
                del self.calls[call_id]
        elif response_code >= 300:
            self._set_call_state(call_info, enum_module.CallState.FAILED)
            del self.calls[call_id]

    original_create_sdp_body = messages_module.SIPMessageBuilder.create_sdp_body

    def patched_create_sdp_body(username: str, rtp_port: int) -> str:
        """修正 SDP 里写入的本地媒体地址，避免通告回环地址。

        参数:
            username: 当前 SIP 用户名。
            rtp_port: 当前本地 RTP 端口。

        返回:
            str: 返回修正后的 SDP 文本。
        """

        local_ip = get_runtime_host()
        actual_rtp_port = int(getattr(messages_module, "_aivoip_rtp_port", rtp_port))
        return (
            f"v=0\n"
            f"o={username} 123456 123456 IN IP4 {local_ip}\n"
            f"s=AI-VOIP SIP Client\n"
            f"c=IN IP4 {local_ip}\n"
            f"t=0 0\n"
            f"m=audio {actual_rtp_port} RTP/AVP 0 8 18 101\n"
            f"a=rtpmap:0 PCMU/8000\n"
            f"a=rtpmap:8 PCMA/8000\n"
            f"a=rtpmap:18 G729/8000\n"
            f"a=rtpmap:101 telephone-event/8000\n"
            f"a=fmtp:101 0-16\n"
            f"a=sendrecv\n"
        )

    original_auth_handle = authentication_module.SIPAuthenticator.handle_auth_challenge

    def patched_auth_handle(self, response: str, method: str, uri: str, local_tag: str, call_id: str, cseq: int):
        """修正鉴权重发时使用的本地地址和 RTP 端口上下文。

        参数:
            self: 当前 SIPAuthenticator 实例对象。
            response: 服务端返回的鉴权挑战报文。
            method: 当前需要重发鉴权的 SIP 方法。
            uri: 当前请求 URI。
            local_tag: 当前请求使用的本地标签。
            call_id: 当前请求使用的呼叫标识。
            cseq: 当前请求序列号。

        返回:
            object: 返回第三方库原始 `handle_auth_challenge` 的结果值。
        """

        messages_module._aivoip_local_host = str(getattr(self.account, "local_ip", "127.0.0.1"))
        messages_module._aivoip_rtp_port = int(getattr(self.account, "rtp_port", 10000))
        return original_auth_handle(self, response, method, uri, local_tag, call_id, cseq)

    messages_module.get_hostname = get_runtime_host
    messages_module.get_local_ip = get_runtime_host
    protocol_module.SIPProtocol.send_message = patched_send_message
    protocol_module.SIPProtocol.start = patched_start
    protocol_module.SIPProtocol.send_register = patched_send_register
    protocol_module.SIPProtocol.send_invite = patched_send_invite
    protocol_module.SIPProtocol.handle_auth_challenge = patched_handle_auth_challenge
    client_module.SIPClient.make_call = patched_make_call
    client_module.SIPClient._handle_sip_response = patched_handle_sip_response
    client_module.SIPClient._start_keepalive = patched_start_keepalive
    messages_module.SIPMessageBuilder.create_sdp_body = staticmethod(patched_create_sdp_body)
    authentication_module.SIPAuthenticator.handle_auth_challenge = patched_auth_handle
    protocol_module._aivoip_patched = True


def extract_call_duration_seconds(call_info: Any, call_tracker: CallTracker) -> int:
    """从 SIP 库回调对象和本地状态中推导当前通话时长。

    参数:
        call_info: SIP 库回传的原始呼叫信息对象。
        call_tracker: 当前呼叫状态跟踪对象。

    返回:
        int: 返回当前通话时长估算值，单位秒。
    """

    raw_duration = getattr(call_info, "duration", None)
    if raw_duration is not None:
        with suppress(Exception):
            return max(0, int(float(raw_duration)))
    if call_tracker.answer_timestamp and call_tracker.end_timestamp:
        return max(0, int(call_tracker.end_timestamp - call_tracker.answer_timestamp))
    if call_tracker.answer_timestamp:
        return max(0, int(time.time() - call_tracker.answer_timestamp))
    return 0


def build_session_progress_payload(
    session_status: str,
    answer_status: str | None,
    event_type: str,
    payload: dict,
    current_node_code: str | None = None,
    hangup_cause: str | None = None,
    result_code: str | None = None,
    billsec: int | None = None,
    duration: int | None = None,
) -> Any:
    """构造统一的会话状态推进请求对象。

    参数:
        session_status: 当前要写入的会话状态。
        answer_status: 当前会话应答状态。
        event_type: 当前事件类型。
        payload: 当前事件附加信息字典。
        current_node_code: 当前所在节点编码，可为空。
        hangup_cause: 当前挂机原因，可为空。
        result_code: 当前结果码，可为空。
        billsec: 当前计费时长，可为空。
        duration: 当前总时长，可为空。

    返回:
        Any: 返回可直接传给 `progress_call_session` 的请求对象。
    """

    from ..api.schemas.runtime import TaskSessionProgressRequest

    return TaskSessionProgressRequest(
        session_status=session_status,
        answer_status=answer_status,
        current_node_code=current_node_code,
        hangup_cause=hangup_cause,
        result_code=result_code,
        billsec=billsec,
        duration=duration,
        event_type=event_type,
        payload=payload,
    )


def build_sip_target_uri(trunk_item: dict, callee_number: str) -> str:
    """根据线路配置和被叫号码生成目标 SIP URI。

    参数:
        trunk_item: 当前绑定的线路对象。
        callee_number: 当前被叫号码。

    返回:
        str: 返回目标呼叫 URI。
    """

    host = str(trunk_item["server_host"]).strip()
    port = int(trunk_item["server_port"])
    if callee_number.startswith("sip:"):
        return callee_number
    return f"sip:{callee_number}@{host}:{port}"


def resolve_task_owner_id(connection: Connection, task_id: int) -> int | None:
    """读取指定任务的创建人主键，供运行时 TTS 生成复用。

    参数:
        connection: 当前请求使用的 PostgreSQL 数据库连接对象。
        task_id: 当前外呼任务主键。

    返回:
        int | None: 返回任务创建人主键，找不到时返回 None。
    """

    task_item = get_call_task_by_id(connection, task_id)
    if task_item is None:
        return None
    return task_item.get("created_by")
