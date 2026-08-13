"""双路音频采集（§6.1）：系统声 WASAPI loopback + 本机麦克风。

真实采集依赖 sounddevice（懒加载，未安装不影响导入）。本模块同时提供：
- `DualStreamCapture`：真实采集（48kHz float32，双路）。
- `IterableCapture`：从预置 numpy 块序列产出（双路），用于 headless / 单测，
  使 LiveSession 全链路可在无音频硬件环境下跑通。

接口约定：`stream_chunks()` 为生成器，产出 `(sys_chunk, mic_chunk)` 对
（均为 1D float32 numpy 数组）。LiveSession 与录制/转写层仅依赖该接口。
"""

from __future__ import annotations

import queue
import threading
from typing import Iterable, Iterator, Optional

import numpy as np


class DualStreamCapture:
    """真实双路采集（WASAPI loopback + 麦克风）。

    采用两条 sounddevice.InputStream（麦克风 + 系统声回环），各自回调把
    音频块入队；`stream_chunks()` 同步取两队，按块对齐产出。无音频设备时
    会抛 RuntimeError（由上层决定降级到 IterableCapture / 提示用户）。
    """

    def __init__(
        self,
        sample_rate: int = 48000,
        mic_device: Optional[str | int] = None,
        loopback_device: Optional[str | int] = None,
        blocksize: int = 4800,  # 100ms @48k
    ):
        self.sample_rate = sample_rate
        self.mic_device = mic_device
        self.loopback_device = loopback_device
        self.blocksize = blocksize
        self._mic_q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._sys_q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._mic_stream = None
        self._sys_stream = None
        self._stop = False
        self._paused = False

    @staticmethod
    def list_devices() -> list:
        import sounddevice as sd  # 懒加载

        return sd.query_devices()

    def _make_callback(self, q: "queue.Queue[np.ndarray]"):
        def cb(indata, frames, time_info, status):
            q.put(np.asarray(indata, dtype=np.float32).ravel().copy())

        return cb

    def open(self) -> None:
        import sounddevice as sd  # 懒加载

        self._stop = False
        self._mic_stream = sd.InputStream(
            device=self.mic_device,
            samplerate=self.sample_rate,
            channels=1,
            blocksize=self.blocksize,
            dtype="float32",
            callback=self._make_callback(self._mic_q),
        )
        # 系统声回环：WASAPI 回环设备；Windows 上 loopback 通过 wasapi 后端
        self._sys_stream = sd.InputStream(
            device=self.loopback_device,
            samplerate=self.sample_rate,
            channels=1,
            blocksize=self.blocksize,
            dtype="float32",
            callback=self._make_callback(self._sys_q),
            **({"flags": sd.WasapiFlags.LOOPBACK} if hasattr(sd, "WasapiFlags") else {}),
        )
        self._mic_stream.start()
        self._sys_stream.start()

    def stream_chunks(self, timeout: float = 5.0) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        while not self._stop:
            try:
                sys_c = self._sys_q.get(timeout=timeout)
                mic_c = self._mic_q.get(timeout=timeout)
            except queue.Empty:
                if self._stop:
                    break
                continue
            yield sys_c, mic_c

    def stop(self) -> None:
        self._stop = True
        for s in (self._mic_stream, self._sys_stream):
            if s is not None:
                try:
                    s.stop()
                    s.close()
                except Exception:
                    pass
        self._mic_stream = self._sys_stream = None

    def pause(self) -> None:
        """暂停采集：挂起两条输入流（回调停止，队列不再增长），释放硬件占用。"""
        if self._stop:
            return
        self._paused = True
        for s in (self._mic_stream, self._sys_stream):
            if s is not None:
                try:
                    s.stop()
                except Exception:
                    pass

    def resume(self) -> None:
        """恢复采集：重启输入流。"""
        if self._stop or not self._paused:
            return
        for s in (self._mic_stream, self._sys_stream):
            if s is not None:
                try:
                    s.start()
                except Exception:
                    pass
        self._paused = False


class IterableCapture:
    """从预置块序列产出双路音频（headless / 单测用）。

    `pairs` 为 `(sys_chunk, mic_chunk)` 序列；`loop` 为真则循环产出，
    便于模拟长会议。无外部依赖。
    """

    def __init__(
        self,
        pairs: Iterable[tuple[np.ndarray, np.ndarray]],
        loop: bool = False,
        sample_rate: int = 48000,
    ):
        self._pairs = list(pairs)
        self.loop = loop
        self.sample_rate = sample_rate
        self._stop = False
        self._paused = False

    def open(self) -> None:
        self._stop = False
        self._paused = False

    def stream_chunks(self) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        if not self._pairs:
            return
        while not self._stop:
            if self._paused:
                import time

                time.sleep(0.05)
                continue
            for pair in self._pairs:
                if self._stop:
                    return
                if self._paused:
                    break
                yield pair
            if not self.loop:
                break

    def stop(self) -> None:
        self._stop = True

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False
