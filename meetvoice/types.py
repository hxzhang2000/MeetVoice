"""跨模块共享数据类型（避免循环依赖）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Segment:
    """一段转写结果。

    start/end 单位为秒（相对会议开始）；speaker 为模型产出的说话人 ID
    （如 "0" / "spk_0"），未提供说话人时为 ""。
    """

    start: float
    end: float
    text: str
    speaker: str = ""


@dataclass
class TranscribeResult:
    segments: List[Segment] = field(default_factory=list)
    text: str = ""
    language: Optional[str] = None
    raw: Optional[object] = None  # 后端原始输出，便于调试
