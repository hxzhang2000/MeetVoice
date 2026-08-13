"""滚动窗口（§6.5）：按 VAD/静音边界切分，避免切半句。

工作方式：
- `feed(chunk)` 持续追加音频（24kHz 单声道 float32）。
- 当缓冲达到 `size_sec` 且在其后找到一段 >= `silence_sec` 的静音边界时，
  `has_segment_ready()` 返回 True；`drain()` 取出该段并保留尾部作为下一窗口上下文。
- 若缓冲无静音且超过 2×size_sec，强制在 size_sec 处切分，避免延迟无限增大。
- 全部为纯 numpy 逻辑，便于单测（见 tests/test_window.py）。
"""

from __future__ import annotations

import numpy as np

from ..audio.vad import first_silence_after

DEFAULT_SR = 24000


class RollingWindow:
    def __init__(self, size_sec: int = 45, silence_sec: float = 0.6, sr: int = DEFAULT_SR):
        self.size_sec = size_sec
        self.silence_sec = silence_sec
        self.sr = sr
        self._buf = np.zeros(0, dtype=np.float32)
        self._ready_end: int | None = None  # 已确定的切分点（样本索引）

    @property
    def buffered_sec(self) -> float:
        return len(self._buf) / self.sr

    @property
    def buffered_len(self) -> int:
        """当前缓冲的样本数（LiveSession 用于计算片段相对会议起始的时间偏移）。"""
        return len(self._buf)

    def feed(self, chunk: np.ndarray) -> None:
        chunk = np.asarray(chunk, dtype=np.float32).ravel()
        self._buf = np.concatenate([self._buf, chunk])
        self._maybe_mark_ready()

    def _maybe_mark_ready(self) -> None:
        min_samples = int(self.size_sec * self.sr)
        if len(self._buf) < min_samples:
            return
        cut = first_silence_after(
            self._buf, self.sr, after_sec=self.size_sec, min_silence_sec=self.silence_sec
        )
        if cut is not None:
            self._ready_end = cut
            return
        # 无静音且缓冲过长 -> 强制切分，限制延迟
        hard = int(self.size_sec * 2 * self.sr)
        if len(self._buf) >= hard:
            self._ready_end = min_samples

    def has_segment_ready(self) -> bool:
        return self._ready_end is not None

    def drain(self) -> np.ndarray:
        """取出已就绪的片段，保留尾部作为下一窗口上下文（少量重叠）。"""
        if self._ready_end is None:
            return np.zeros(0, dtype=np.float32)
        end = self._ready_end
        seg = self._buf[:end].copy()
        # 保留 1s 尾部重叠，提升跨窗口连续性
        overlap = min(int(1.0 * self.sr), len(self._buf) - end)
        self._buf = self._buf[end - overlap:] if overlap > 0 else self._buf[end:]
        self._ready_end = None
        return seg

    def flush(self) -> np.ndarray:
        """结束录制时取出全部剩余音频。"""
        seg = self._buf.copy()
        self._buf = np.zeros(0, dtype=np.float32)
        self._ready_end = None
        return seg
