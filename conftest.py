"""pytest 配置与共享 fixture。

把项目根目录加入 sys.path（保证 `import meetvoice` 可用），并提供基于临时目录的
`cfg` fixture（关闭 LLM、缩短窗口，便于纯逻辑/无硬件测试）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture
def cfg(tmp_path):
    from meetvoice.config import Config

    c = Config()
    c.notes_dir = str(tmp_path / "notes")
    c.recording_dir = str(tmp_path / "recordings")
    c.recordings_dir = str(tmp_path / "recordings")
    c.logs_dir = str(tmp_path / "logs")
    c.llm.enabled = False  # 纯逻辑测试不联网
    c.window_sec = 3
    c.capture.silence_sec = 0.1
    c.capture.sample_rate = 24000
    c.capture.target_sample_rate = 24000
    c.ensure_dirs()
    return c
