"""会议记录存储测试：create / mark_done / list / 级联删除（回收站/物理）/ export。"""

from __future__ import annotations

from pathlib import Path

from meetvoice.meeting.store import MeetingStore


def _store(tmp_path, recycle=True):
    return MeetingStore(
        tmp_path / "recordings",
        trash_dir=(tmp_path / "trash") if recycle else None,
    )


def test_create_and_list(tmp_path):
    s = _store(tmp_path)
    rec = s.create(sample_rate=24000, hotwords=["术语A"])
    assert rec.meeting_id
    assert rec.status == "recording"
    assert Path(tmp_path / "recordings" / f"{rec.meeting_id}.json").exists()
    listed = s.list()
    assert len(listed) == 1
    assert listed[0].meeting_id == rec.meeting_id


def test_mark_done_and_rename(tmp_path):
    s = _store(tmp_path)
    rec = s.create()
    s.mark_done(rec, duration_sec=120.0, artifacts={"final_md": "/x/final.md"})
    assert rec.status == "done"
    assert rec.duration_sec == 120.0
    s.rename_speaker(rec, "0", "张三")
    assert rec.speaker_map["0"] == "张三"


def test_delete_recycle(tmp_path):
    s = _store(tmp_path, recycle=True)
    rec = s.create()
    s.mark_done(rec, artifacts={"final_md": str(tmp_path / "recordings" / f"{rec.meeting_id}_final.md")})
    # 建一个关联文件
    Path(rec.artifacts["final_md"]).write_text("x", encoding="utf-8")
    info = s.delete(rec.meeting_id)
    assert info["recycled"] is True
    assert info["removed"] >= 1
    # 原文件已移入回收站
    trash = tmp_path / "trash" / rec.meeting_id
    assert trash.exists()
    assert not Path(rec.artifacts["final_md"]).exists()


def test_delete_physical(tmp_path):
    s = _store(tmp_path, recycle=False)
    rec = s.create()
    s.mark_done(rec, artifacts={"final_md": str(tmp_path / "recordings" / f"{rec.meeting_id}_final.md")})
    Path(rec.artifacts["final_md"]).write_text("x", encoding="utf-8")
    info = s.delete(rec.meeting_id)
    assert info["recycled"] is False
    assert not Path(tmp_path / "recordings" / f"{rec.meeting_id}.json").exists()


def test_export_zip(tmp_path):
    s = _store(tmp_path)
    rec = s.create()
    s.mark_done(rec, artifacts={"final_md": str(tmp_path / "recordings" / f"{rec.meeting_id}_final.md")})
    Path(rec.artifacts["final_md"]).write_text("内容", encoding="utf-8")
    zp = s.export(rec.meeting_id, tmp_path / "out.zip")
    assert zp.exists() and zp.suffix == ".zip"
