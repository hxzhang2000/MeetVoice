"""双路 WAV 落盘（§6.2）。

设计要点：
- 用标准库 `wave` + numpy 写入 16-bit PCM，不依赖 soundfile。
- 系统声 / 麦克风分别存为 `wav_sys.wav` / `wav_mic.wav`（48kHz 单声道）。
- `load_full_audio()` 读取双路并合并为单路 float32（供终稿 ASR）。
- `duration_sec` 记录总时长。
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Dict, Optional

import numpy as np


class WaveRecorder:
    def __init__(self, recording_dir: str | Path, meeting_id: str, sr: int = 48000):
        self.recording_dir = Path(recording_dir)
        self.recording_dir.mkdir(parents=True, exist_ok=True)
        self.meeting_id = meeting_id
        self.sr = sr
        self.wav_sys_path = self.recording_dir / f"{meeting_id}_sys.wav"
        self.wav_mic_path = self.recording_dir / f"{meeting_id}_mic.wav"
        self._sys_wf = None
        self._mic_wf = None
        self._n_frames = 0
        self._open = False

    # ---- 写入 -------------------------------------------------------- #
    def open(self) -> None:
        self._sys_wf = wave.open(str(self.wav_sys_path), "wb")
        self._mic_wf = wave.open(str(self.wav_mic_path), "wb")
        for wf in (self._sys_wf, self._mic_wf):
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sr)
        self._open = True

    @staticmethod
    def _to_int16(chunk: np.ndarray) -> np.ndarray:
        chunk = np.asarray(chunk, dtype=np.float32).ravel()
        chunk = np.clip(chunk, -1.0, 1.0)
        return (chunk * 32767.0).astype("<i2")

    def feed(self, sys_chunk: np.ndarray, mic_chunk: np.ndarray) -> None:
        if not self._open:
            self.open()
        self._sys_wf.writeframes(self._to_int16(sys_chunk).tobytes())
        self._mic_wf.writeframes(self._to_int16(mic_chunk).tobytes())
        self._n_frames += len(self._to_int16(sys_chunk))

    def close(self) -> None:
        for wf in (self._sys_wf, self._mic_wf):
            if wf is not None:
                try:
                    wf.close()
                except Exception:
                    pass
        self._sys_wf = self._mic_wf = None
        self._open = False

    @property
    def duration_sec(self) -> float:
        return self._n_frames / self.sr if self.sr else 0.0

    # ---- 读取（终稿用）--------------------------------------------- #
    @staticmethod
    def _read_wav(path: Path) -> Optional[np.ndarray]:
        if not path.exists():
            return None
        with wave.open(str(path), "rb") as wf:
            n = wf.getnframes()
            raw = wf.readframes(n)
            arr = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        return arr

    def load_full_audio(self) -> np.ndarray:
        """读取双路并合并为单路 float32（48kHz）。系统声缺失时退化为麦克风。"""
        sys_a = self._read_wav(self.wav_sys_path)
        mic_a = self._read_wav(self.wav_mic_path)
        if sys_a is None and mic_a is None:
            return np.zeros(0, dtype=np.float32)
        if sys_a is None:
            return mic_a
        if mic_a is None:
            return sys_a
        # 对齐长度后取平均（简单混音）
        n = min(len(sys_a), len(mic_a))
        return ((sys_a[:n] + mic_a[:n]) / 2.0).astype(np.float32)

    def artifact_paths(self) -> Dict[str, str]:
        return {
            "wav_sys": str(self.wav_sys_path),
            "wav_mic": str(self.wav_mic_path),
        }
