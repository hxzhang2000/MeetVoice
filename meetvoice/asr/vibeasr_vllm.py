"""VibeASR 经 vLLM 服务化后端（HTTP，§6.3 / §4.5）。

- 后端为已启动的 vLLM OpenAI 兼容服务（/v1/audio/transcriptions）。
- 懒加载 requests；将音频 POST 到 vLLM 端点，解析返回。
"""

from __future__ import annotations

import tempfile
import wave
from pathlib import Path
from typing import List, Optional

import numpy as np

from ..config import ASRConfig
from ..types import Segment, TranscribeResult


class VibeASRVllmBackend:
    name = "vibeasr_vllm"

    def __init__(self, cfg: ASRConfig):
        self.cfg = cfg

    def transcribe(self, audio, sr: int, hotwords: Optional[List[str]] = None) -> TranscribeResult:
        import requests  # 懒加载

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            arr = np.clip(np.asarray(audio, dtype=np.float32).ravel(), -1, 1)
            wf.writeframes((arr * 32767).astype("<i2").tobytes())

        with open(wav_path, "rb") as f:
            resp = requests.post(
                f"{self.cfg.vllm_base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.cfg.vllm_api_key or 'EMPTY'}"},
                files={"file": ("audio.wav", f, "audio/wav")},
                data={"model": self.cfg.vllm_model},
                timeout=self.cfg.max_new_tokens,
            )
        Path(wav_path).unlink(missing_ok=True)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("text", "")
        # vLLM 返回文本为主；说话人/时间戳需后端支持，否则整体为一段
        segments = [Segment(0.0, len(audio) / sr, text, "0")] if text else []
        return TranscribeResult(segments=segments, text=text)
