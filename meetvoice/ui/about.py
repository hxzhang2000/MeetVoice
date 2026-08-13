"""关于对话框（§6.6）：展示版本号与 GitHub Star 推荐。PySide6 全部懒加载。

纯文本来源见 ``meetvoice.about_text()``（CLI 与对话框共用，单一事实源）。
"""

from __future__ import annotations

from typing import Optional

from .. import __app_name__, __description__, __github_url__, __version__


def open_about_window(parent: Optional[object] = None) -> None:
    """打开「关于」对话框（PySide6 懒加载）。parent 为可选 Qt 父控件。"""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import (
        QApplication,
        QDialog,
        QLabel,
        QPushButton,
        QVBoxLayout,
    )

    app = QApplication.instance() or QApplication([])
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"{__app_name__} · 关于")
    dlg.setMinimumWidth(440)
    layout = QVBoxLayout(dlg)

    layout.addWidget(QLabel(f"<h2>{__app_name__}</h2>"))
    layout.addWidget(QLabel(f"版本 <b>{__version__}</b>"))

    desc = QLabel(__description__)
    desc.setWordWrap(True)
    layout.addWidget(desc)

    star = QLabel(
        "如果 MeetVoice 对你有帮助，欢迎在 GitHub 上给我们一个 ⭐ <b>Star</b>！"
    )
    star.setWordWrap(True)
    layout.addWidget(star)

    btn_star = QPushButton("⭐ 在 GitHub 上 Star")
    btn_star.clicked.connect(
        lambda: QDesktopServices.openUrl(QUrl(__github_url__))
    )
    layout.addWidget(btn_star)

    link = QLabel(f'<a href="{__github_url__}">{__github_url__}</a>')
    link.setOpenExternalLinks(True)
    layout.addWidget(link)

    btn_ok = QPushButton("确定")
    btn_ok.clicked.connect(dlg.accept)
    layout.addWidget(btn_ok)

    dlg.exec()
    if not QApplication.instance():
        app.exec()
