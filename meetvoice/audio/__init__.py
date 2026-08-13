"""音频采集与处理（§6.1）。

- capture：双路采集（系统声 WASAPI loopback + 麦克风），懒加载 sounddevice。
- resample：48k -> 24k 重采样，懒加载 librosa。
- vad：纯 numpy 能量 VAD（无外部依赖，供滚动窗口与流式预览复用）。
"""

from .vad import detect_silence, vad_energy

__all__ = ["detect_silence", "vad_energy"]
