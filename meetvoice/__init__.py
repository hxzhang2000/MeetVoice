"""MeetVoice — 实时会议记录系统。

双路音频采集（系统声 WASAPI loopback + 本机麦克风），实时转写为文字并
保存为本地 Markdown；结束后可调用 OpenAI 兼容大模型生成会议总结，并提供
会议管理与模型管理。详见 docs/开发方案.md。
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
