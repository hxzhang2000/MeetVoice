"""调度与编排（§6.5）：`LiveSession` 是应用唯一的状态源。

职责：串起「双路采集 → 重采样(48k→24k) → 滚动窗口(静音边界切分) → 串行 ASR
→ 滚动出稿(live.md) → 终稿(final.md) → 会后 LLM 总结(summary.md) → 回写会议记录」。

设计要点（详见 docs/开发方案.md §6.5）：
- 单一状态源：内部维护 `SessionState` 枚举，任何变更经 `on_state_change(state)` 广播；
  托盘/窗口/会议 UI 只订阅渲染，不持有状态副本。
- 后端线程运行 `run()`（同步方法，非 async），UI 主线程不被阻塞。
- 所有重型依赖（torch/funasr/sounddevice…）均在使用处懒加载；`capture`/`asr`/`recorder`/
  `writer` 均可在构造时注入，因此无音频硬件、无 GPU 也能跑通全链路（见 tests）。
- 双路音频在送 ASR 前混合并重采样到 24kHz（§3.2 契约）；滚动窗口按绝对时间偏移
  标注每段时间戳（避免每次窗口都从 0 开始）。
- 崩溃恢复：`recover_meeting()` 复用已落盘 wav 重跑终稿+总结（§6.5）。
"""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional

import numpy as np

from .._log import log
from ..audio.capture import DualStreamCapture
from ..audio.resample import resample
from ..config import Config
from ..meeting.store import MeetingStore
from ..orchestrator.window import RollingWindow
from ..recorder.wave_writer import WaveRecorder
from ..summary import MeetingSummarizer
from ..writer.markdown import MarkdownWriter
from ..asr.build_backend import build_backend


def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SessionState(str, Enum):
    """会话状态枚举（值即广播给 UI 的字符串）。"""

    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    PROCESSING = "processing"
    ERROR = "error"


class LiveSession:
    def __init__(
        self,
        cfg: Config,
        capture=None,
        asr=None,
        recorder=None,
        writer=None,
        on_state_change: Optional[Callable[[str], None]] = None,
    ):
        self.cfg = cfg
        self.capture = capture or DualStreamCapture(
            sample_rate=cfg.capture.sample_rate,
            mic_device=cfg.capture.mic_device,
            loopback_device=cfg.capture.loopback_device,
        )
        self.asr = asr or build_backend(cfg.asr)
        self.recorder = recorder  # 依赖 meeting_id，start() 内惰性创建
        self.writer = writer
        self.store = MeetingStore(
            cfg.recordings_dir,
            trash_dir=cfg.meetings.trash_dir if cfg.meetings.recycle else None,
        )
        self.window = RollingWindow(
            size_sec=cfg.window_sec,
            silence_sec=cfg.capture.silence_sec,
            sr=cfg.capture.target_sample_rate,
        )
        self.tasks = ThreadPoolExecutor(max_workers=1)  # 串行 ASR，防占满显存
        self._src_sr = cfg.capture.sample_rate
        self._sr = cfg.capture.target_sample_rate
        self._stop = False
        self._thread: Optional[threading.Thread] = None
        self.meeting = None
        self.on_state_change = on_state_change
        self._on_done: Optional[Callable[[], None]] = None
        self.state = SessionState.IDLE
        self._total_fed = 0  # 已送窗口的 24k 样本总数（用于时间戳偏移）
        self._pending: List[Future] = []
        self._max_backlog = 3  # 队列积压上限，超出丢最旧（已落盘录音兜底）

    # ---- 状态广播 ---------------------------------------------------- #
    def _set_state(self, state: SessionState) -> None:
        self.state = state
        if self.on_state_change is not None:
            try:
                self.on_state_change(state.value)
            except Exception as e:  # 回调异常不应影响主流程
                log.warning("on_state_change 回调异常：{}", e)

    # ---- 生命周期 ---------------------------------------------------- #
    def start(self) -> None:
        """后台线程启动采集+ASR，避免阻塞 UI 主线程。"""
        if self._thread is not None and self._thread.is_alive():
            return  # 已在运行
        self.meeting = self.store.create(
            sample_rate=self._sr, hotwords=list(self.cfg.asr.hotwords)
        )
        if self.recorder is None:
            self.recorder = WaveRecorder(
                self.cfg.recording_dir, self.meeting.meeting_id, sr=self._src_sr
            )
        if self.writer is None:
            self.writer = MarkdownWriter(self.cfg.notes_dir, self.meeting.meeting_id)
        self._stop = False
        self._total_fed = 0
        self._pending = []
        self.capture.open()
        self._set_state(SessionState.RECORDING)
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        """暂停采集但保留缓冲与状态。"""
        if self.state != SessionState.RECORDING:
            return
        self.capture.pause()
        self._set_state(SessionState.PAUSED)

    def resume(self) -> None:
        if self.state != SessionState.PAUSED:
            return
        self.capture.resume()
        self._set_state(SessionState.RECORDING)

    def stop_and_finalize(self, on_done: Optional[Callable[[], None]] = None) -> None:
        """用户点击「停止」：结束采集并触发终稿；on_done 在终稿完成后回调（回 idle）。"""
        self._on_done = on_done
        if self._thread is None or not self._thread.is_alive():
            # 未运行时直接视为完成
            self._set_state(SessionState.IDLE)
            if self._on_done:
                self._on_done()
            return
        self._stop = True
        self.capture.stop()  # 令 stream_chunks 退出循环

    def join(self, timeout: Optional[float] = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    # ---- 主循环 ------------------------------------------------------ #
    def run(self) -> None:
        try:
            self._record_loop()
            self._finalize()
        except Exception as e:
            log.error("LiveSession 运行异常：{}", e)
            self._set_state(SessionState.ERROR)
            if self.meeting is not None:
                try:
                    self.store.mark_failed(self.meeting, error=str(e))
                except Exception:
                    pass
            return
        # 成功路径：on_done 由 app 决定是否回到 idle（TrayApp 置 idle）
        if self._on_done is not None:
            try:
                self._on_done()
            except Exception as e:
                log.warning("on_done 回调异常：{}", e)

    def _record_loop(self) -> None:
        self.recorder.open()
        self.writer.open_live()
        for sys_chunk, mic_chunk in self.capture.stream_chunks():
            self.recorder.feed(sys_chunk, mic_chunk)
            # 双路混合并重采样到 24kHz 送 ASR（§3.2 契约）
            mixed = np.asarray(sys_chunk, dtype=np.float32).ravel() + np.asarray(
                mic_chunk, dtype=np.float32
            ).ravel()
            mixed_24k = resample(mixed, self._src_sr, self._sr)
            self._total_fed += len(mixed_24k)
            self.window.feed(mixed_24k)
            if self.window.has_segment_ready():
                # 片段相对会议起始的时间偏移 = 已送总量 - 当前缓冲长度
                base_sec = (self._total_fed - self.window.buffered_len) / self._sr
                audio = self.window.drain()
                self._submit_transcribe(audio, base_sec)
            if self._stop:
                break

    def _submit_transcribe(self, audio: np.ndarray, base_sec: float) -> None:
        # 积压保护：队列 >= 上限时丢弃最旧（已落盘录音兜底）
        self._pending = [f for f in self._pending if not f.done()]
        if len(self._pending) >= self._max_backlog:
            old = self._pending.pop(0)
            old.cancel()  # 尽力取消（已在跑则忽略）
        fut = self.tasks.submit(self._transcribe_and_write, audio, base_sec)
        self._pending.append(fut)

    def _transcribe_and_write(self, audio: np.ndarray, base_sec: float) -> None:
        try:
            result = self.asr.transcribe(
                audio, sr=self._sr, hotwords=list(self.cfg.asr.hotwords)
            )
            for s in result.segments:
                s.start += base_sec
                s.end += base_sec
            self.writer.append_live(result.segments)
        except Exception as e:
            log.warning("ASR/写入片段失败（已跳过，录音兜底）：{}", e)

    # ---- 终稿 + 总结 ------------------------------------------------- #
    def _finalize(self) -> None:
        self._set_state(SessionState.PROCESSING)
        self.recorder.close()
        full = self.recorder.load_full_audio()
        segs = []
        if len(full) > 0:
            full_24k = resample(full, self._src_sr, self._sr)
            result = self.asr.transcribe(
                full_24k, sr=self._sr, hotwords=list(self.cfg.asr.hotwords)
            )
            segs = result.segments
        self.writer.write_final(segs)

        # 会后 LLM 会议总结（§6.7）；未启用或失败时降级，保留 final.md
        summary_path = None
        if self.cfg.llm.enabled:
            try:
                transcript = self.writer.format_plain(segs)  # 纯文本，去 Markdown
                summary = MeetingSummarizer(self.cfg).summarize(transcript)
                summary_path = self.writer.write_summary(summary)
            except Exception as e:
                log.warning("会议总结失败，已保留转录稿：{}", e)

        # 回写会议记录（单一事实来源）：终稿/总结路径、说话人映射、状态
        arts: Dict[str, str] = {}
        arts.update(self.recorder.artifact_paths())
        arts.update(self.writer.artifact_paths(summary_path))
        self.store.mark_done(
            self.meeting,
            ended_at=_iso_now(),
            duration_sec=self.recorder.duration_sec,
            artifacts=arts,
            speaker_map=self.writer.speaker_map,
        )
        self._set_state(SessionState.IDLE)

    # ---- 崩溃恢复（§6.5）-------------------------------------------- #
    def recover(self, meeting_id: str):
        """复用已落盘 wav 重跑终稿+总结（无需重新录音）。"""
        return recover_meeting(self.cfg, meeting_id, asr=self.asr)


def recover_meeting(cfg: Config, meeting_id: str, asr=None):
    """对 status=recording/failed 的中断会议，基于已落盘 wav 重新生成终稿与总结。"""
    store = MeetingStore(
        cfg.recordings_dir,
        trash_dir=cfg.meetings.trash_dir if cfg.meetings.recycle else None,
    )
    rec = store.get(meeting_id)
    if rec is None:
        raise FileNotFoundError(f"会议不存在：{meeting_id}")
    if rec.status == "done":
        return rec
    recorder = WaveRecorder(cfg.recording_dir, meeting_id, sr=rec.sample_rate)
    writer = MarkdownWriter(cfg.notes_dir, meeting_id)
    writer.speaker_map = dict(rec.speaker_map)
    backend = asr or build_backend(cfg.asr)
    full = recorder.load_full_audio()
    segs = []
    if len(full) > 0:
        full_24k = resample(full, rec.sample_rate, cfg.capture.target_sample_rate)
        segs = backend.transcribe(
            full_24k,
            sr=cfg.capture.target_sample_rate,
            hotwords=list(cfg.asr.hotwords),
        ).segments
    writer.write_final(segs)
    summary_path = None
    if cfg.llm.enabled:
        try:
            transcript = writer.format_plain(segs)
            summary = MeetingSummarizer(cfg).summarize(transcript)
            summary_path = writer.write_summary(summary)
        except Exception as e:
            log.warning("恢复会议总结失败，已保留转录稿：{}", e)
    arts: Dict[str, str] = {}
    arts.update(rec.artifacts)  # 保留已有产物（如原始 wav 路径）
    arts.update(recorder.artifact_paths())
    arts.update(writer.artifact_paths(summary_path))
    store.mark_done(
        rec,
        ended_at=_iso_now(),
        duration_sec=recorder.duration_sec,
        artifacts=arts,
        speaker_map=writer.speaker_map,
    )
    return rec
