"""控制窗口（§6.6，PySide6）：实时转写预览 + 开始/暂停/停止按钮。

PySide6 为懒加载依赖；未安装时不影响包导入。
"""

from __future__ import annotations

from typing import Optional

from ..config import Config
from ..orchestrator import LiveSession, SessionState


class ControlWindow:
    def __init__(self, cfg: Config, session: Optional[LiveSession] = None):
        self.cfg = cfg
        self.session = session or LiveSession(cfg, on_state_change=self.on_state_change)
        self._app = None
        self._ui = {}  # name -> widget

    # ---- 状态广播（订阅 LiveSession）-------------------------------- #
    def on_state_change(self, state: str) -> None:
        w = self._ui.get("status")
        if w is not None:
            try:
                w.setText(f"状态：{state}")
            except Exception:
                pass

    # ---- 运行 -------------------------------------------------------- #
    def run(self) -> None:
        from PySide6.QtWidgets import (
            QApplication,
            QTextEdit,
            QLabel,
            QPushButton,
            QVBoxLayout,
            QWidget,
        )

        app = QApplication([])
        self._app = app
        w = QWidget()
        w.setWindowTitle("MeetVoice 会议记录")
        layout = QVBoxLayout(w)

        btn_start = QPushButton("开始")
        btn_pause = QPushButton("暂停 / 继续")
        btn_stop = QPushButton("停止并生成纪要")
        btn_start.clicked.connect(self._start)
        btn_pause.clicked.connect(self._pause)
        btn_stop.clicked.connect(self._stop)

        status = QLabel("状态：idle")
        live = QTextEdit()
        live.setReadOnly(True)

        self._ui = {"status": status, "live": live}
        for b in (btn_start, btn_pause, btn_stop):
            layout.addWidget(b)
        layout.addWidget(status)
        layout.addWidget(live)
        w.show()
        app.exec()

    # ---- 按钮 -------------------------------------------------------- #
    def _start(self):
        if self.session.state == SessionState.IDLE:
            self.session.start()

    def _pause(self):
        if self.session.state == SessionState.RECORDING:
            self.session.pause()
        elif self.session.state == SessionState.PAUSED:
            self.session.resume()

    def _stop(self):
        if self.session.state in (SessionState.RECORDING, SessionState.PAUSED):
            self.session.stop_and_finalize(on_done=lambda: self.on_state_change("idle"))
