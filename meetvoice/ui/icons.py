"""托盘/窗口图标生成（懒加载 PIL）。无 PIL 时返回 None，由托盘用默认图标。"""

from __future__ import annotations

import io
from typing import Optional

_STATE_COLORS = {
    "idle": (128, 128, 128),
    "recording": (220, 50, 50),
    "paused": (230, 180, 60),
    "processing": (80, 140, 220),
    "error": (200, 40, 40),
}


def icon_image(state: str):
    """返回 PIL.Image（彩色圆点），无 PIL 时返回 None。"""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    size = 64
    color = _STATE_COLORS.get(state, (128, 128, 128))
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, size - 4, size - 4], fill=(*color, 255))
    return img


def icon_bytes(state: str) -> Optional[bytes]:
    img = icon_image(state)
    if img is None:
        return None
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
