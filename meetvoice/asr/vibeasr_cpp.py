"""VibeASR.cpp 后端（仅英文，量化 GGUF 子进程，§6.3 / §4.5）。

- 通过子进程调用 asr_infer 可执行文件（传入 vae/lm GGUF）。
- 懒加载 subprocess；输出解析为 Segment。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List, Optional

import numpy as np

from ..config import ASRConfig
from ..types import Segment, TranscribeResult


class VibeASRCppBackend:
    name = "vibeasr_cpp"

    def __init__(self, cfg: ASRConfig):
        self.cfg = cfg

    def transcribe(self, audio, sr: int, hotwords: Optional[List[str]] = None) -> TranscribeResult:
        # 写出临时 wav 供子进程读取
        import tempfile
        import wave

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            arr = np.clip(np.asarray(audio, dtype=np.float32).ravel(), -1, 1)
            wf.writeframes((arr * 32767).astype("<i2").tobytes())

        cmd = [
            self.cfg.asr_cpp_bin,
            "--vae", self.cfg.asr_cpp_vae,
            "--lm", self.cfg.asr_cpp_lm,
            "--input", wav_path,
            "--threads", str(self.cfg.asr_cpp_threads),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        segments = []
        if proc.returncode == 0:
            try:
                data = json.loads(proc.stdout)
                for seg in data.get("segments", []):
                    segments.append(
                        Segment(seg["start"], seg["end"], seg["text"], str(seg.get("speaker", "0")))
                    )
            except (json.JSONDecodeError, KeyError):
                pass
        Path(wav_path).unlink(missing_ok=True)
        return TranscribeResult(segments=segments, text=" ".join(s.text for s in segments))
