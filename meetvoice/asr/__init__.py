"""ASR 适配器（§6.3）。

统一接口 `ASRBackend.transcribe(audio, sr, hotwords) -> TranscribeResult`。
各后端为懒加载实现：未安装对应重型依赖（torch / funasr / vllm 等）时不影响
包导入与纯逻辑单测；`build_backend(cfg)` 按 `cfg.asr.backend` 分派构造。
"""

from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable

from ..types import Segment, TranscribeResult


@runtime_checkable
class ASRBackend(Protocol):
    name: str

    def transcribe(
        self, audio, sr: int, hotwords: Optional[List[str]] = None
    ) -> TranscribeResult:
        ...


class MockBackend:
    """测试 / headless 用的占位后端：返回预置或合成的 Segment。

    可用于在无 GPU / 无模型环境下端到端验证编排层与写入层。
    """

    name = "mock"

    def __init__(self, segments: Optional[List[Segment]] = None, delay: float = 0.0):
        self._segments = segments or [
            Segment(0.0, 5.0, "大家好，我们开始今天的会议。", "0"),
            Segment(5.0, 12.0, "先过一下 VibeVoice 的接入方案。", "1"),
        ]
        self.delay = delay

    def transcribe(self, audio, sr: int, hotwords=None) -> TranscribeResult:
        if self.delay:
            import time

            time.sleep(self.delay)
        return TranscribeResult(segments=list(self._segments), text=" ".join(s.text for s in self._segments))
