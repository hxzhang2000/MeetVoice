"""FunASR 本地后端（CPU 中文兜底，§6.3 / §4.5）。

- 2026-05 起 FunASR 原生支持 diarization（自动说话人分离），无需 CAM++。
- 懒加载 funasr / modelscope / torch；首次调用构造时导入。
- `transcribe` 将 FunASR 输出映射为 Segment 列表（含 spk_id）。
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np

from ..config import ASRConfig
from ..types import Segment, TranscribeResult


class FunASRLocalBackend:
    name = "funasr_local"

    def __init__(self, cfg: ASRConfig):
        self.cfg = cfg
        self._model = None

    def _ensure_model(self):
        if self._model is not None:
            return
        from funasr import AutoModel  # 懒加载

        self._model = AutoModel(
            model=cfg_model(self.cfg),
            vad_model=self.cfg.funasr_vad,
            punc_model=self.cfg.funasr_punc,
            spk_model=self.cfg.funasr_spk,  # auto = 原生 diarization
            disable_update=True,
        )

    def transcribe(self, audio, sr: int, hotwords: Optional[List[str]] = None) -> TranscribeResult:
        self._ensure_model()
        audio = np.asarray(audio, dtype=np.float32).ravel()
        # FunASR 接受 (samples, sr) 或音频路径；此处传 (signal, fs)
        res = self._model.generate(
            input=(audio, sr),
            batch_size_s=300,
            hotword=" ".join(hotwords) if hotwords else None,
            return_spk_res=True,
        )
        segments = []
        for item in res:
            text = item.get("text", "")
            spk = item.get("spk", "0")
            ts = item.get("timestamp", None)
            if ts:
                for (start_ms, end_ms), piece in zip(ts, text.split()):
                    segments.append(
                        Segment(start_ms / 1000.0, end_ms / 1000.0, piece, str(spk))
                    )
            else:
                segments.append(Segment(0.0, len(audio) / sr, text, str(spk)))
        return TranscribeResult(segments=segments, text=text)


def cfg_model(cfg: ASRConfig) -> str:
    # model_path 已是 HF id 或本地路径（目录）
    return cfg.model_path or cfg.funasr_model
