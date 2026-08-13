"""ASR 适配器测试：MockBackend 占位、build_backend 分派与异常（无需重型依赖）。"""

from __future__ import annotations

import numpy as np
import pytest

from meetvoice.asr import MockBackend
from meetvoice.asr.build_backend import build_backend
from meetvoice.config import Config
from meetvoice.types import Segment


def test_mock_backend():
    b = MockBackend()
    r = b.transcribe(np.zeros(100, dtype=np.float32), sr=24000)
    assert isinstance(r, object)
    assert len(r.segments) == 2
    assert "大家好" in r.text


def test_build_backend_unknown_raises():
    c = Config()
    c.asr.backend = "bogus_backend"
    with pytest.raises(ValueError):
        build_backend(c.asr)


def test_build_backend_future_milestone():
    c = Config()
    for backend in ("fireredasr_local", "qwen3asr_local"):
        c.asr.backend = backend
        with pytest.raises(NotImplementedError):
            build_backend(c.asr)


def test_live_session_uses_injected_asr_and_capture(cfg):
    """LiveSession 可在无重型依赖下注入 MockBackend + IterableCapture 跑通。"""
    from meetvoice.audio.capture import IterableCapture
    from meetvoice.orchestrator import LiveSession

    sr = cfg.capture.sample_rate
    chunk = np.zeros(int(sr * 0.2), dtype=np.float32)
    cap = IterableCapture([(chunk, chunk)] * 30, loop=False, sample_rate=sr)
    session = LiveSession(cfg, capture=cap, asr=MockBackend())
    states = []
    session.on_state_change = lambda s: states.append(s)
    session.start()
    session.join(timeout=30)
    assert "idle" in states
    assert session.meeting.status == "done"
    # 产物落盘
    from pathlib import Path

    assert Path(cfg.notes_dir, f"{session.meeting.meeting_id}_final.md").exists()
