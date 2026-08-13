"""MOSS-Transcribe-Diarize 0.9B 本地后端（GPU 高性价比候选，§6.3 / §4.5）。

- 端到端 ASR + diarization + 时间戳，单 pass 90min；Apache-2.0，0.9B 全开源。
- 懒加载 torch / transformers；需 trust_remote_code=True 加载自定义代码。
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np

from ..config import ASRConfig
from ..types import Segment, TranscribeResult


class MossLocalBackend:
    name = "moss_local"

    def __init__(self, cfg: ASRConfig):
        self.cfg = cfg
        self._pipe = None

    def _ensure_model(self):
        if self._pipe is not None:
            return
        import torch  # 懒加载
        from transformers import pipeline

        self._pipe = pipeline(
            "automatic-speech-recognition",
            model=self.cfg.model_path,
            trust_remote_code=self.cfg.moss_trust_remote_code,
            torch_dtype="auto",
            device_map=self.cfg.device_map if self.cfg.device_map != "auto" else "cuda:0",
        )

    def transcribe(self, audio, sr: int, hotwords: Optional[List[str]] = None) -> TranscribeResult:
        self._ensure_model()
        out = self._pipe(
            {"array": np.asarray(audio, dtype=np.float32).ravel(), "sampling_rate": sr},
            max_audio_seconds=self.cfg.moss_max_audio_min * 60,
            return_timestamps=True,
            return_spk_tokens=True,
        )
        segments = []
        for chunk in out.get("chunks", []):
            ts = chunk.get("timestamp", (0, 0))
            spk = chunk.get("speaker", "0")
            segments.append(Segment(float(ts[0] or 0), float(ts[1] or 0), chunk.get("text", ""), str(spk)))
        return TranscribeResult(segments=segments, text=out.get("text", ""))
