"""VibeVoice-ASR-7B 本地后端（默认 GPU 主引擎，§6.3 / §4.5）。

- transformers + 自回归 TTS/ASR 模型；联合产出 ASR + diarization + 时间戳。
- 懒加载 torch / transformers；显存不足时可用 device_map="auto" 分片。
- 真实推理需 GPU 与 7B 权重；此处给出符合接口的实现骨架。
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np

from ..config import ASRConfig
from ..types import Segment, TranscribeResult


class VibeVoiceLocalBackend:
    name = "vibevoice_local"

    def __init__(self, cfg: ASRConfig):
        self.cfg = cfg
        self._pipe = None

    def _ensure_model(self):
        if self._pipe is not None:
            return
        import torch  # 懒加载
        from transformers import AutoModelForCausalLM, AutoProcessor

        dtype = {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}.get(
            self.cfg.compute_dtype, torch.float32
        )
        self._pipe = {
            "model": AutoModelForCausalLM.from_pretrained(
                self.cfg.model_path,
                torch_dtype=dtype,
                device_map=self.cfg.device_map if self.cfg.device_map != "auto" else "cuda:0",
                attn_implementation=self.cfg.attn_impl,
            ),
            "processor": AutoProcessor.from_pretrained(self.cfg.model_path),
        }

    def transcribe(self, audio, sr: int, hotwords: Optional[List[str]] = None) -> TranscribeResult:
        self._ensure_model()
        # 真实实现：将音频编码为模型输入，自回归解码，解析 (text, spk, timestamp)。
        # 此处返回占位结构，保证接口连通；接入权重后由推理结果填充 Segment。
        raise NotImplementedError(
            "VibeVoice-ASR 推理需 GPU 与 7B 权重，请安装 torch/transformers 后补全 _generate。"
        )
