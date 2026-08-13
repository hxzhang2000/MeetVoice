"""Markdown 写入测试：live 追加（线程安全）/ final 排序 / summary / format_plain / 时间戳格式。"""

from __future__ import annotations

from pathlib import Path

from meetvoice.types import Segment
from meetvoice.writer.markdown import MarkdownWriter, _fmt_ts


def test_fmt_ts():
    assert _fmt_ts(0) == "00:00"
    assert _fmt_ts(5) == "00:05"
    assert _fmt_ts(75 * 60 + 30) == "75:30"


def test_live_append_and_final(tmp_path):
    w = MarkdownWriter(tmp_path, "M1")
    w.open_live()
    segs = [
        Segment(0.0, 5.0, "大家好", "0"),
        Segment(5.0, 12.0, "开始会议", "1"),
    ]
    w.append_live(segs)
    w.append_live([Segment(2.0, 3.0, "插一句", "0")])  # 乱序，final 应排序
    live = Path(tmp_path / "M1_live.md").read_text(encoding="utf-8")
    assert "大家好" in live and "开始会议" in live

    fp = w.write_final(segs + [Segment(2.0, 3.0, "插一句", "0")])
    final = Path(fp).read_text(encoding="utf-8")
    # 时间戳格式 [MM:SS]–[MM:SS]
    assert "[00:00]–[00:05]" in final
    # 乱序段被排序到正确位置（start=2s 的「插一句」应排在 start=5s 的「开始会议」之前）
    assert "插一句" in final and "开始会议" in final
    assert final.index("插一句") < final.index("开始会议")


def test_speaker_map_and_summary(tmp_path):
    w = MarkdownWriter(tmp_path, "M2")
    w.speaker_map = {"0": "张三"}
    fp = w.write_final([Segment(0.0, 5.0, "hi", "0")])
    final = Path(fp).read_text(encoding="utf-8")
    assert "张三" in final
    sp = w.write_summary("# 摘要\n内容")
    assert Path(sp).exists()
    assert "摘要" in Path(sp).read_text(encoding="utf-8")


def test_format_plain(tmp_path):
    w = MarkdownWriter(tmp_path, "M3")
    txt = w.format_plain([Segment(0.0, 5.0, "a", "0"), Segment(5.0, 9.0, "b", "1")])
    assert "a" in txt and "b" in txt
    assert "[[" not in txt  # 纯文本无 Markdown 时间戳
