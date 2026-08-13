"""会议记录窗口（§6.6 / §6.8）：历史会议列表、回放（打开产物）、删除（二次确认）、导出 zip。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .._log import log
from ..config import Config
from ..meeting.store import MeetingStore


def open_meetings_window(cfg: Config, parent=None) -> None:
    """打开会议记录窗口（PySide6 懒加载）。"""
    from PySide6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QListWidget,
        QListWidgetItem,
        QMessageBox,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    app = QApplication.instance() or QApplication([])
    store = MeetingStore(
        cfg.recordings_dir,
        trash_dir=cfg.meetings.trash_dir if cfg.meetings.recycle else None,
    )

    w = QWidget()
    w.setWindowTitle("MeetVoice · 会议记录")
    layout = QVBoxLayout(w)
    lst = QListWidget()
    layout.addWidget(lst)

    def refresh():
        lst.clear()
        for rec in store.list():
            item = QListWidgetItem(
                f"{rec.meeting_id}  [{rec.status}]  {rec.duration_str}"
            )
            item.setData(1, rec.meeting_id)
            lst.addItem(item)

    btn_open = QPushButton("打开目录")
    btn_replay = QPushButton("回放录音")
    btn_export = QPushButton("导出 zip")
    btn_delete = QPushButton("删除")
    row = QHBoxLayout()
    for b in (btn_open, btn_replay, btn_export, btn_delete):
        row.addWidget(b)
    layout.addLayout(row)

    def selected_id():
        it = lst.currentItem()
        return it.data(1) if it else None

    def on_open():
        mid = selected_id()
        if not mid:
            return
        rec = store.get(mid)
        if rec and rec.artifacts.get("final_md"):
            _open_file(rec.artifacts["final_md"])

    def on_replay():
        mid = selected_id()
        if not mid:
            return
        rec = store.get(mid)
        if rec and rec.artifacts.get("wav_sys"):
            _open_file(rec.artifacts["wav_sys"])

    def on_export():
        mid = selected_id()
        if not mid:
            return
        dest = Path(cfg.recordings_dir) / f"{mid}.zip"
        store.export(mid, dest)
        log.info("已导出会议 {} -> {}", mid, dest)

    def on_delete():
        mid = selected_id()
        if not mid:
            return
        r = QMessageBox.question(
            w,
            "确认删除",
            f"确定删除会议 {mid} 及其全部关联文件？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r == QMessageBox.StandardButton.Yes:
            info = store.delete(mid)
            log.info("删除会议 {}：{}", mid, info)
            refresh()

    btn_open.clicked.connect(on_open)
    btn_replay.clicked.connect(on_replay)
    btn_export.clicked.connect(on_export)
    btn_delete.clicked.connect(on_delete)

    refresh()
    w.show()


def _open_file(path: str) -> None:
    import os
    import sys

    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception as e:
        log.warning("打开文件失败：{}", e)
