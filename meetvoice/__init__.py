"""MeetVoice — 实时会议记录系统。

双路音频采集（系统声 WASAPI loopback + 本机麦克风），实时转写为文字并
保存为本地 Markdown；结束后可调用 OpenAI 兼容大模型（含本地 Ollama）生成会议总结，
并提供会议管理与模型管理。详见 docs/开发方案.md。
"""

from pathlib import Path
from typing import Optional

__app_name__ = "MeetVoice"
__version__ = "0.2.0"
__version_info__ = (0, 2, 0)
__github_repo__ = "hxzhang2000/MeetVoice"
__github_url__ = "https://github.com/hxzhang2000/MeetVoice"
__homepage__ = __github_url__
__description__ = "实时会议记录系统：双路音频采集 + 实时转写 + 会议总结 + 会议/模型管理"


def about_text() -> str:
    """返回「关于」纯文本（CLI 与对话框共用，单一事实源）。"""
    return (
        f"{__app_name__} v{__version__}\n"
        f"{__description__}\n"
        f"\n"
        f"GitHub: {__github_url__}\n"
        f"如果对你有帮助，欢迎给我们一个 ⭐ Star！"
    )


def changelog_path() -> Optional[Path]:
    """定位仓库根目录的 CHANGELOG.md（开发态/安装态兼容尝试）。"""
    here = Path(__file__).resolve().parent
    for cand in (here.parent / "CHANGELOG.md", here.parent.parent / "CHANGELOG.md"):
        if cand.exists():
            return cand
    return None


__all__ = [
    "__app_name__",
    "__version__",
    "__version_info__",
    "__github_repo__",
    "__github_url__",
    "__homepage__",
    "__description__",
    "about_text",
    "changelog_path",
]
