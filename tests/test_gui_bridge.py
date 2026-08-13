"""GUI 事件循环 / 信号桥接回归测试（需 PySide6，否则跳过）。

验证桌面端 4 个 bug 的根本修复：
- 设置/会议记录等非模态窗口能「在主线程事件循环内打开且不阻塞循环」
  （此前 bug：open_settings_window 末尾 `if not QApplication.instance(): app.exec()`
   因 instance 已存在而永远不执行，窗口 show() 后无事件循环 → 卡死/打不开）。
- 托盘线程（模拟 pystray 线程）发出的信号能被 Qt 主线程的槽接收，
  即菜单动作经 GuiBridge 跨线程派发回主线程执行窗口逻辑。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from meetvoice.config import Config
from meetvoice.ui.meetings import open_meetings_window
from meetvoice.ui.settings import open_settings_window

_GUI_OPENS = {"settings": False, "meetings": False}


class _Bridge(QObject):
    sig_settings = Signal()
    sig_meetings = Signal()


def test_bridge_dispatches_window_open_to_main_thread():
    app = QApplication.instance() or QApplication([])

    def on_settings():
        open_settings_window(Config(), None)  # 不应阻塞事件循环
        _GUI_OPENS["settings"] = True

    def on_meetings():
        open_meetings_window(Config())  # 不应阻塞事件循环
        _GUI_OPENS["meetings"] = True

    bridge = _Bridge()
    bridge.sig_settings.connect(on_settings)
    bridge.sig_meetings.connect(on_meetings)

    def emit_from_tray_thread():
        # 模拟 pystray 菜单回调在其自身线程触发
        bridge.sig_settings.emit()
        bridge.sig_meetings.emit()

    t = threading.Thread(target=emit_from_tray_thread)
    t.start()

    # 主线程事件循环跑一会儿，让排队的信号被处理，然后退出
    QTimer.singleShot(1000, app.quit)
    app.exec()

    assert _GUI_OPENS["settings"], "设置窗口未能在主线程打开（事件循环被阻塞？）"
    assert _GUI_OPENS["meetings"], "会议记录窗口未能在主线程打开（事件循环被阻塞？）"
