"""桌面应用入口（§6.6）：组装 ModelManager + LiveSession(TrayApp) 并启动托盘事件循环。

pystray / PySide6 等重依赖在 TrayApp 内部懒加载，本模块导入不触发它们。
"""

from __future__ import annotations

from typing import Optional

from .._log import log
from ..config import Config
from ..models import ModelManager


def run_app(cfg: Config, config_path: Optional[str] = None) -> int:
    mgr = ModelManager(cfg)
    # 仅一个已下载模型时自动启用（§4.5 / §6.6 自动启用规则）
    enabled = mgr.auto_enable()
    if enabled:
        log.info("自动启用模型：{}", enabled)
    elif not mgr.cfg.models.active:
        log.info(
            "未检测到已启用模型，请在托盘菜单「⚙ 设置 / 模型」中下载并启用一个 ASR 模型。"
        )

    # ---- 单一 Qt 事件循环架构（修复 about 关不掉 / 设置打不开 / Ctrl+C 无效 / 卡顿）----
    # 主线程：QApplication.exec() 负责全部 Qt 窗口与事件分发。
    # 工作线程：pystray.Icon.run() 负责系统托盘。
    # 托盘菜单回调在本线程触发，经 GuiBridge 信号跨线程派发回 Qt 主线程执行，
    # 避免在非 Qt 线程直接操作 Qt 对象（此前导致窗口卡死/无法关闭）。
    import signal as _signal
    import threading

    from PySide6.QtCore import QObject, QTimer, Signal
    from PySide6.QtWidgets import QApplication

    from .about import open_about_window
    from .meetings import open_meetings_window
    from .settings import open_settings_window
    from .tray import TrayApp

    class _GuiBridge(QObject):
        sig_about = Signal()
        sig_settings = Signal()
        sig_meetings = Signal()
        sig_quit = Signal()

        def __init__(self, cfg, config_path, quit_cb):
            super().__init__()
            self._cfg = cfg
            self._config_path = config_path
            self._quit_cb = quit_cb
            self.sig_about.connect(self._on_about)
            self.sig_settings.connect(self._on_settings)
            self.sig_meetings.connect(self._on_meetings)
            self.sig_quit.connect(self._on_quit)

        def _on_about(self):
            open_about_window()

        def _on_settings(self):
            open_settings_window(self._cfg, self._config_path)

        def _on_meetings(self):
            open_meetings_window(self._cfg)

        def _on_quit(self):
            self._quit_cb()

    app = QApplication.instance() or QApplication([])

    def _request_quit():
        """停止托盘与录制会话，并退出 Qt 事件循环。"""
        try:
            tray.request_stop()
        except Exception:
            pass
        app.quit()

    bridge = _GuiBridge(cfg, config_path, _request_quit)
    tray = TrayApp(cfg, config_path=config_path, bridge=bridge)

    # Ctrl+C / SIGINT：干净退出（此前主线程被 pystray 阻塞，无法响应）。
    def _on_sigint(signo, frame):
        log.info("收到中断信号，正在退出…")
        _request_quit()

    _signal.signal(_signal.SIGINT, _on_sigint)
    # 周期性空转定时器，确保主线程频繁回到 Python，使 SIGINT 处理器能及时被触发。
    _keep = QTimer()
    _keep.timeout.connect(lambda: None)
    _keep.start(300)

    # 托盘放到守护线程，主线程交给 Qt 事件循环。
    _tray_thread = threading.Thread(target=tray.run, daemon=True)
    _tray_thread.start()

    return app.exec()
