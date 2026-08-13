"""桌面外壳包（§6.6）。重依赖（pystray / PySide6）均在子模块内部懒加载。"""

from __future__ import annotations

from .app import run_app

__all__ = ["run_app"]
