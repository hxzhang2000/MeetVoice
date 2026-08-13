"""系统托盘应用（§6.6）：右键菜单控制录制，状态以 LiveSession 为唯一来源。

所有 pystray / PIL 依赖均懒加载；未安装时不影响包导入。
"""

from __future__ import annotations

from typing import Optional

from .._log import log
from .. import __github_url__, __version__
from ..config import Config
from ..orchestrator import LiveSession, SessionState


class TrayApp:
    def __init__(self, cfg: Config, config_path: Optional[str] = None, bridge=None):
        self.cfg = cfg
        self.config_path = config_path
        # bridge：跨线程信号桥（GuiBridge），把菜单动作派发回 Qt 主线程。
        # 无 bridge 时（测试/独立调用）直接本地打开，作为降级。
        self.bridge = bridge
        # 单一状态源：LiveSession 通过 on_state_change 广播状态
        self.session = LiveSession(cfg, on_state_change=self._on_state_change)
        self.icon = None
        self._build_icon()

    def _build_icon(self):
        from . import icons

        img = icons.icon_image("idle")
        import pystray
        from pystray import Menu, MenuItem

        menu = Menu(
            MenuItem("● 开始录音", self.on_start, default=True),
            MenuItem("⏸ 暂停 / 继续", self.on_pause_resume),
            MenuItem("■ 停止并生成纪要", self.on_stop),
            Menu.SEPARATOR,
            MenuItem("📋 会议记录…", self.show_meetings),
            MenuItem("⚙ 设置 / 模型", self.show_settings),
            MenuItem("★ 关于 MeetVoice", self.show_about),
            MenuItem("⭐ 在 GitHub 上 Star", self.open_github_star),
            Menu.SEPARATOR,
            MenuItem("退出", self.on_quit),
        )
        self.icon = pystray.Icon(
            "MeetVoice", img, f"MeetVoice v{__version__}", menu
        )

    # ---- 状态广播（单一状态源）-------------------------------------- #
    def _on_state_change(self, state: str) -> None:
        if self.icon is not None:
            try:
                from . import icons

                img = icons.icon_image(state)
                if img is not None:
                    self.icon.icon = img
                self.icon.title = f"MeetVoice v{__version__} · {state}"
            except Exception as e:
                log.debug("更新托盘图标失败：{}", e)

    # ---- 菜单回调 ---------------------------------------------------- #
    def on_start(self, icon=None, item=None):
        if self.session.state == SessionState.IDLE:
            self.session.start()

    def on_pause_resume(self, icon=None, item=None):
        if self.session.state == SessionState.RECORDING:
            self.session.pause()
        elif self.session.state == SessionState.PAUSED:
            self.session.resume()

    def on_stop(self, icon=None, item=None):
        if self.session.state in (SessionState.RECORDING, SessionState.PAUSED):
            # 终稿在后台线程生成；完成后经 LiveSession 回调回到 idle
            self.session.stop_and_finalize(on_done=self._on_finalized)

    def _on_finalized(self) -> None:
        self._on_state_change("idle")
        self._notify("会议已生成纪要", "可于「会议记录」查看 final.md / summary.md")

    def show_meetings(self, icon=None, item=None):
        if self.bridge is not None:
            self.bridge.sig_meetings.emit()
        else:
            from .meetings import open_meetings_window

            open_meetings_window(self.cfg)

    def show_settings(self, icon=None, item=None):
        if self.bridge is not None:
            self.bridge.sig_settings.emit()
        else:
            from .settings import open_settings_window

            open_settings_window(self.cfg, self.config_path)

    def show_about(self, icon=None, item=None):
        if self.bridge is not None:
            self.bridge.sig_about.emit()
        else:
            from .about import open_about_window

            open_about_window()

    def open_github_star(self, icon=None, item=None):
        import webbrowser

        webbrowser.open(__github_url__)

    def _notify(self, title: str, message: str) -> None:
        try:
            if self.icon is not None:
                self.icon.notify(message, title)
        except Exception:
            pass

    def on_quit(self, icon=None, item=None):
        # 通过 bridge 派发到 Qt 主线程统一退出（停止托盘 + 退出 Qt 循环）。
        if self.bridge is not None:
            self.bridge.sig_quit.emit()
            return
        try:
            self.session.stop_and_finalize()
        except Exception:
            pass
        if self.icon is not None:
            self.icon.stop()

    def request_stop(self) -> None:
        """由 Qt 主线程调用：停止录制会话并退出托盘事件循环。"""
        try:
            self.session.stop_and_finalize()
        except Exception:
            pass
        if self.icon is not None:
            self.icon.stop()

    def run(self) -> None:
        if self.icon is not None:
            self.icon.run()
