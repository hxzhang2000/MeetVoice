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

    from .tray import TrayApp

    TrayApp(cfg, config_path=config_path).run()
    return 0
