"""重采样（懒加载 librosa）。

采集为 48kHz，送 ASR 前需转 24kHz（见 §3.2 契约）。librosa 为可选依赖，
首次调用时导入；未安装则给出明确提示。
"""

from __future__ import annotations

import numpy as np


def resample(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """重采样 float32 音频（1D）。src==dst 时原样返回。"""
    audio = np.asarray(audio, dtype=np.float32).ravel()
    if src_sr == dst_sr:
        return audio
    try:
        import librosa  # 懒加载（高质量，带抗混叠）

        out = librosa.resample(audio, orig_sr=src_sr, target_sr=dst_sr)
        return np.asarray(out, dtype=np.float32)
    except ImportError:
        # 降级：纯 numpy 线性插值（无抗混叠，仅用于无 librosa 的开发/测试环境）
        old_t = np.linspace(0, 1, len(audio), endpoint=False)
        new_n = max(1, int(round(len(audio) * dst_sr / src_sr)))
        new_t = np.linspace(0, 1, new_n, endpoint=False)
        return np.interp(new_t, old_t, audio).astype(np.float32)


def to_mono(audio: np.ndarray, channels: int = 1) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float32)
    if channels == 1 and audio.ndim > 1:
        return audio.mean(axis=1)
    return audio.ravel()
