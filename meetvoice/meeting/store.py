"""会议管理（§6.8）：会议记录 JSON 作为单一事实来源。

设计要点：
- 每个会议一个 JSON（`<recordings_dir>/<meeting_id>.json`），含元数据、说话人映射、产物路径。
- `MeetingStore` 提供 create → mark_done → list → delete(级联) → export 全链路。
- 删除支持级联清除全部关联文件（wav_sys/wav_mic/json/live_md/final_md/summary_md/log）。
- `recycle=true`（trash_dir 存在）时先整体移入回收站，支持误删恢复；否则直接物理删除。
"""

from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _fmt_duration(sec: float) -> str:
    sec = int(sec or 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


@dataclass
class MeetingRecord:
    meeting_id: str
    started_at: str
    ended_at: Optional[str] = None
    duration_sec: float = 0.0
    sample_rate: int = 24000
    hotwords: List[str] = field(default_factory=list)
    speaker_map: Dict[str, str] = field(default_factory=dict)  # {spk_id: 昵称}
    status: str = "recording"        # recording | done | failed
    artifacts: Dict[str, str] = field(default_factory=dict)     # wav_sys/wav_mic/live_md/final_md/summary_md/log

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MeetingRecord":
        return cls(
            meeting_id=d["meeting_id"],
            started_at=d.get("started_at", ""),
            ended_at=d.get("ended_at"),
            duration_sec=float(d.get("duration_sec", 0.0)),
            sample_rate=int(d.get("sample_rate", 24000)),
            hotwords=list(d.get("hotwords", [])),
            speaker_map=dict(d.get("speaker_map", {})),
            status=d.get("status", "recording"),
            artifacts=dict(d.get("artifacts", {})),
        )

    @property
    def duration_str(self) -> str:
        return _fmt_duration(self.duration_sec)

    @property
    def speaker_count(self) -> int:
        # 统计实际出现的说话人 ID 数（从 artifacts 之外的映射推断）
        return len(self.speaker_map) if self.speaker_map else 0


class MeetingStore:
    def __init__(self, recordings_dir: str | Path, trash_dir: str | Path | None = None):
        self.root = Path(recordings_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.trash = Path(trash_dir) if trash_dir else None

    # ---- 写 ----------------------------------------------------------- #
    def create(self, sample_rate: int = 24000, hotwords: Optional[List[str]] = None) -> MeetingRecord:
        """start() 时调用：生成 meeting_id=当前时间戳，写初始 JSON。"""
        mid = datetime.now().strftime("%Y%m%d_%H%M%S")
        rec = MeetingRecord(
            meeting_id=mid,
            started_at=_iso_now(),
            sample_rate=sample_rate,
            hotwords=list(hotwords or []),
        )
        self._save(rec)
        return rec

    def mark_done(self, rec: MeetingRecord, **fields) -> None:
        """终稿完成后回写路径/状态。"""
        for k, v in fields.items():
            setattr(rec, k, v)
        rec.status = "done"
        self._save(rec)

    def mark_failed(self, rec: MeetingRecord, error: str = "") -> None:
        rec.status = "failed"
        if error:
            rec.artifacts.setdefault("error", error)
        self._save(rec)

    def rename_speaker(self, rec: MeetingRecord, spk_id: str, name: str) -> None:
        """说话人人工重指派（§6.8 回放）。"""
        rec.speaker_map[spk_id] = name
        self._save(rec)

    def _save(self, rec: MeetingRecord) -> None:
        path = self.root / f"{rec.meeting_id}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rec.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)  # 原子写

    # ---- 读 ----------------------------------------------------------- #
    def list(self) -> List[MeetingRecord]:
        """枚举全部会议，按开始时间倒序。"""
        recs = []
        for p in self.root.glob("*.json"):
            try:
                recs.append(MeetingRecord.from_dict(json.loads(p.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, KeyError):
                continue
        recs.sort(key=lambda r: r.started_at, reverse=True)
        return recs

    def get(self, meeting_id: str) -> Optional[MeetingRecord]:
        p = self.root / f"{meeting_id}.json"
        if not p.exists():
            return None
        return MeetingRecord.from_dict(json.loads(p.read_text(encoding="utf-8")))

    # ---- 关联文件迭代 ------------------------------------------------ #
    def _iter_files(self, rec: MeetingRecord):
        """yield 该会议的全部关联文件路径（JSON + 各产物）。"""
        yield self.root / f"{rec.meeting_id}.json"
        for path in rec.artifacts.values():
            if path:
                yield Path(path)

    # ---- 删除（级联 + 回收站）-------------------------------------- #
    def delete(self, meeting_id: str) -> Dict[str, Any]:
        """级联删除：一并删除该会议的全部文件。
        recycle（trash_dir 存在）时先整体移入回收站，否则直接物理删除。
        返回 {removed: int, recycled: bool, trash_path: str|None}。
        """
        rec = self.get(meeting_id)
        if rec is None:
            raise FileNotFoundError(f"会议不存在：{meeting_id}")

        files = [p for p in self._iter_files(rec) if p.exists()]
        if self.trash:  # trash_dir 已存在（[meetings].recycle=true）即走回收站
            self.trash.mkdir(parents=True, exist_ok=True)
            dest = self.trash / meeting_id
            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir(parents=True, exist_ok=True)
            for f in files:
                try:
                    shutil.move(str(f), str(dest / f.name))
                except shutil.Error:
                    pass
            return {"removed": len(files), "recycled": True, "trash_path": str(dest)}
        # 直接物理删除
        removed = 0
        for f in files:
            try:
                if f.is_dir():
                    shutil.rmtree(f)
                else:
                    f.unlink()
                removed += 1
            except (FileNotFoundError, PermissionError):
                pass
        return {"removed": removed, "recycled": False, "trash_path": None}

    # ---- 导出 zip ---------------------------------------------------- #
    def export(self, meeting_id: str, dest_zip: str | Path) -> Path:
        """单会议打包 zip（含全部可见文件），返回 zip 路径。"""
        rec = self.get(meeting_id)
        if rec is None:
            raise FileNotFoundError(f"会议不存在：{meeting_id}")
        dest_zip = Path(dest_zip)
        if dest_zip.suffix != ".zip":
            dest_zip = dest_zip.with_suffix(".zip")
        with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in self._iter_files(rec):
                if f.exists() and f.is_file():
                    zf.write(f, arcname=f.name)
        return dest_zip
