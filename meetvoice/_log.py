"""共享日志入口：优先 loguru（{} 风格），未安装时降级为兼容 {} 风格的 stdlib 封装。

关键点：所有模块统一用 `log.info("msg {}", arg)` 的 `{}` 占位写法（与 loguru 一致）。
若 loguru 缺失，降级封装会把 `{}` 用 str.format 处理，保证同一套调用在两种后端下都不报错。
"""

from __future__ import annotations

import logging


class _FmtLogger:
    """将 `{}` 风格的 `log.info("x {}", a)` 适配到 stdlib logging。"""

    def __init__(self, name: str = "meetvoice", level=logging.INFO):
        self._l = logging.getLogger(name)
        if not self._l.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
            self._l.addHandler(h)
        self._l.setLevel(level)

    @staticmethod
    def _fmt(msg, args):
        if not args:
            return msg
        try:
            return msg.format(*args)
        except Exception:
            return msg

    def info(self, msg, *args, **kw):
        self._l.info(self._fmt(msg, args))

    def warning(self, msg, *args, **kw):
        self._l.warning(self._fmt(msg, args))

    def error(self, msg, *args, **kw):
        self._l.error(self._fmt(msg, args))

    def debug(self, msg, *args, **kw):
        self._l.debug(self._fmt(msg, args))

    def exception(self, msg, *args, **kw):
        self._l.exception(self._fmt(msg, args))


try:
    from loguru import logger as log
except ImportError:  # pragma: no cover - 仅在未安装 loguru 的测试/精简环境
    log = _FmtLogger()
