"""模型管理面板（§6.6 设置页内嵌）：列出 catalog、一键下载（落到 §4.5.2 目录）、删除、启用（互斥）。

依赖 PySide6（懒加载）与 ModelManager。未安装 PySide6 不影响包导入。
"""

from __future__ import annotations

from typing import Optional

from .._log import log
from ..config import Config
from ..models import ModelManager


def open_models_window(cfg: Config, manager: Optional[ModelManager] = None) -> None:
    """打开模型管理面板（PySide6 懒加载）。"""
    from PySide6.QtWidgets import (
        QApplication,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    app = QApplication.instance() or QApplication([])
    mgr = manager or ModelManager(cfg)

    w = QWidget()
    w.setWindowTitle("MeetVoice · 模型管理")
    layout = QVBoxLayout(w)
    lst = QListWidget()
    layout.addWidget(lst)
    status = QLabel("")
    layout.addWidget(status)

    btn_dl = QPushButton("下载")
    btn_del = QPushButton("删除")
    btn_enable = QPushButton("启用")
    btn_refresh = QPushButton("刷新")
    row = QHBoxLayout()
    for b in (btn_dl, btn_del, btn_enable, btn_refresh):
        row.addWidget(b)
    layout.addLayout(row)

    def refresh():
        lst.clear()
        for st in mgr.list_status():
            item = QListWidgetItem(
                f"{st['name']}  [{st['backend']}]  "
                f"{'已下载' if st['downloaded'] else '未下载'}  "
                f"{'●启用' if st['active'] else ''}"
            )
            item.setData(1, st["id"])
            lst.addItem(item)

    def selected_id():
        it = lst.currentItem()
        return it.data(1) if it else None

    def on_download():
        mid = selected_id()
        if not mid:
            return
        status.setText(f"下载中：{mid} …")
        try:
            mgr.download(mid)
            status.setText(f"下载完成：{mid}")
        except Exception as e:
            status.setText(f"下载失败：{e}")
            log.warning("下载失败 {}：{}", mid, e)
        refresh()

    def on_delete():
        mid = selected_id()
        if not mid:
            return
        mgr.delete(mid)
        refresh()

    def on_enable():
        mid = selected_id()
        if not mid:
            return
        try:
            mgr.enable(mid)
            status.setText(f"已启用：{mid}（需重启应用后生效）")
        except Exception as e:
            status.setText(f"启用失败：{e}")
        refresh()

    btn_dl.clicked.connect(on_download)
    btn_del.clicked.connect(on_delete)
    btn_enable.clicked.connect(on_enable)
    btn_refresh.clicked.connect(refresh)

    refresh()
    w.show()
    if not QApplication.instance():
        app.exec()
