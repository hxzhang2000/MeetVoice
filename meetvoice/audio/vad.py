"""能量 VAD（纯 numpy，无外部依赖）。

用于滚动窗口的静音边界切分与（可选）流式预览起点判定。
阈值采用相对能量（相对音频峰值的百分比），对音量波动更稳健。
"""

from __future__ import annotations

import numpy as np

__all__ = ["vad_energy", "detect_silence"]


def _frames(audio: np.ndarray, sr: int, frame_ms: int = 20) -> np.ndarray:
    """返回每帧的 RMS 能量（1D，len = 帧数）。"""
    audio = np.asarray(audio, dtype=np.float32).ravel()
    frame_len = max(1, int(sr * frame_ms / 1000))
    n = len(audio)
    n_frames = n // frame_len
    if n_frames == 0:
        return np.array([], dtype=np.float32)
    trimmed = audio[: n_frames * frame_len].reshape(n_frames, frame_len)
    # 去掉直流偏置
    trimmed = trimmed - trimmed.mean(axis=1, keepdims=True)
    return np.sqrt((trimmed**2).mean(axis=1) + 1e-12)


def vad_energy(audio: np.ndarray, sr: int, frame_ms: int = 20) -> np.ndarray:
    """每帧能量（与 `detect_silence` 同帧划分）。"""
    return _frames(audio, sr, frame_ms)


def detect_silence(
    audio: np.ndarray,
    sr: int,
    silence_sec: float = 0.6,
    thresh_ratio: float = 0.01,
    frame_ms: int = 20,
) -> list[tuple[int, int]]:
    """返回静音段的样本区间列表 [(start, end), ...]（相对整段音频）。

    - 能量低于 `峰值 * thresh_ratio` 判为静音帧。
    - 返回连续静音帧对应的样本区间；长度 >= 1 帧即计入（调用方按需过滤时长）。
    """
    energy = _frames(audio, sr, frame_ms)
    if energy.size == 0:
        return []
    peak = float(energy.max()) + 1e-9
    silent = energy < peak * thresh_ratio
    frame_len = max(1, int(sr * frame_ms / 1000))

    runs: list[tuple[int, int]] = []
    i = 0
    n = len(silent)
    while i < n:
        if silent[i]:
            j = i
            while j < n and silent[j]:
                j += 1
            start_sample = i * frame_len
            end_sample = min(j * frame_len, len(audio))
            runs.append((start_sample, end_sample))
            i = j
        else:
            i += 1
    return runs


def first_silence_after(
    audio: np.ndarray,
    sr: int,
    after_sec: float,
    min_silence_sec: float = 0.6,
    **kw,
) -> int | None:
    """在 `after_sec` 之后寻找第一个满足时长要求的静音段起点（样本索引）。

    用于滚动窗口切分：保证切点在句子边界（静音处），避免切半句。
    未找到返回 None。
    """
    runs = detect_silence(audio, sr, silence_sec=min_silence_sec, **kw)
    after_sample = int(after_sec * sr)
    for start, end in runs:
        if start >= after_sample and (end - start) / sr >= min_silence_sec:
            return start
    return None
