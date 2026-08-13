"""Markdown 写入（§6.4）：live.md / final.md / summary.md。

设计要点：
- live.md 在录制中持续增量追加（线程安全锁保护）。
- final.md 终稿时整体重写（按时间排序）。
- summary.md 由会议总结模块写入（§6.7）。
- 时间戳统一用 `[MM:SS]–[MM:SS]` 格式，与 §6.8 回放按 `[MM:SS]` 解析一致
  （v1.12 修正：旧模板 `00:00–02:18` 与解析不符）。
- speaker_map 用于把模型产出的说话人 ID 映射为昵称（人工重指派）。
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union


def _fmt_ts(sec: float) -> str:
    """秒 -> MM:SS（分钟可超过 59，如 1h15m30s -> 75:30）。"""
    sec = int(round(sec or 0))
    m, s = divmod(sec, 60)
    return f"{m:02d}:{s:02d}"


def _speaker_label(speaker: str, speaker_map: Dict[str, str]) -> str:
    if speaker and speaker in speaker_map:
        return speaker_map[speaker]
    if speaker:
        return f"说话人{speaker}"
    return "说话人?"


def _seg_attrs(seg) -> dict:
    """兼容 Segment 对象与 dict。"""
    if isinstance(seg, dict):
        return {
            "start": float(seg.get("start", 0.0)),
            "end": float(seg.get("end", 0.0)),
            "text": str(seg.get("text", "")),
            "speaker": str(seg.get("speaker", "")),
        }
    return {
        "start": float(getattr(seg, "start", 0.0)),
        "end": float(getattr(seg, "end", 0.0)),
        "text": str(getattr(seg, "text", "")),
        "speaker": str(getattr(seg, "speaker", "")),
    }


class MarkdownWriter:
    def __init__(self, notes_dir: str | Path, meeting_id: str):
        self.notes_dir = Path(notes_dir)
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.meeting_id = meeting_id
        self.live_path = self.notes_dir / f"{meeting_id}_live.md"
        self.final_path = self.notes_dir / f"{meeting_id}_final.md"
        self.summary_path = self.notes_dir / f"{meeting_id}_summary.md"
        self.speaker_map: Dict[str, str] = {}
        self._lock = threading.Lock()

    # ---- live -------------------------------------------------------- #
    def open_live(self) -> None:
        header = (
            f"# 实时转写（进行中）· {self.meeting_id}\n\n"
            f"> 生成时间：{datetime.now().isoformat(timespec='seconds')}\n\n"
        )
        self.live_path.write_text(header, encoding="utf-8")

    def append_live(self, segments: Sequence) -> None:
        """增量追加若干段（线程安全）。"""
        if not segments:
            return
        blocks = []
        for seg in segments:
            a = _seg_attrs(seg)
            ts = f"[{_fmt_ts(a['start'])}]–[{_fmt_ts(a['end'])}]"
            label = _speaker_label(a["speaker"], self.speaker_map)
            blocks.append(f"## {ts} {label}\n{a['text'].strip()}\n")
        text = "\n".join(blocks) + "\n"
        with self._lock:
            with self.live_path.open("a", encoding="utf-8") as f:
                f.write(text)

    # ---- final ------------------------------------------------------- #
    def write_final(self, segments: Sequence) -> Path:
        """终稿：整体重写，按时间排序、应用说话人映射。"""
        segs = sorted((_seg_attrs(s) for s in segments), key=lambda a: a["start"])
        lines = [
            f"# 会议转写终稿 · {self.meeting_id}",
            "",
            f"> 生成时间：{datetime.now().isoformat(timespec='seconds')}",
            "",
        ]
        for a in segs:
            ts = f"[{_fmt_ts(a['start'])}]–[{_fmt_ts(a['end'])}]"
            label = _speaker_label(a["speaker"], self.speaker_map)
            lines.append(f"## {ts} {label}")
            lines.append(a["text"].strip())
            lines.append("")
        self.final_path.write_text("\n".join(lines), encoding="utf-8")
        return self.final_path

    # ---- summary ----------------------------------------------------- #
    def write_summary(self, markdown: str) -> Path:
        self.summary_path.write_text(markdown, encoding="utf-8")
        return self.summary_path

    # ---- 纯文本（供 LLM 总结）--------------------------------------- #
    def format_plain(self, segments: Sequence) -> str:
        """去 Markdown 标记的纯文本转写，每行 `说话人X: 文本`。"""
        segs = sorted((_seg_attrs(s) for s in segments), key=lambda a: a["start"])
        out = []
        for a in segs:
            label = _speaker_label(a["speaker"], self.speaker_map)
            out.append(f"{label}：{a['text'].strip()}")
        return "\n".join(out)

    # ---- 产物路径 ---------------------------------------------------- #
    def artifact_paths(self, summary_path: Optional[str | Path] = None) -> Dict[str, str]:
        paths = {
            "live_md": str(self.live_path),
            "final_md": str(self.final_path),
        }
        if summary_path:
            paths["summary_md"] = str(summary_path)
        return paths
