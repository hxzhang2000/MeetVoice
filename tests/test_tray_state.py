"""单一状态源测试：LiveSession 状态广播（IDLE→RECORDING→PROCESSING→IDLE）、
暂停/继续、stop_and_finalize 的 on_done 回调。
"""

from __future__ import annotations

import time

import numpy as np

from meetvoice.asr import MockBackend
from meetvoice.audio.capture import IterableCapture
from meetvoice.orchestrator import LiveSession, SessionState


def _make_session(cfg, n_chunks=30, loop=False):
    sr = cfg.capture.sample_rate
    chunk = np.zeros(int(sr * 0.2), dtype=np.float32)
    cap = IterableCapture([(chunk, chunk)] * n_chunks, loop=loop, sample_rate=sr)
    return LiveSession(cfg, capture=cap, asr=MockBackend())


def test_state_transitions_natural_end(cfg):
    session = _make_session(cfg, n_chunks=30, loop=False)
    states = []
    session.on_state_change = states.append
    session.start()
    session.join(timeout=30)
    assert states[0] == "recording"
    assert "processing" in states
    assert states[-1] == "idle"
    assert session.state == SessionState.IDLE
    assert session.meeting.status == "done"


def test_pause_resume(cfg):
    session = _make_session(cfg, n_chunks=200, loop=True)
    states = []
    session.on_state_change = states.append
    session.start()
    time.sleep(0.3)
    session.pause()
    assert session.state == SessionState.PAUSED
    assert "paused" in states
    session.resume()
    assert session.state == SessionState.RECORDING
    session.stop_and_finalize()
    session.join(timeout=30)
    assert session.state == SessionState.IDLE


def test_stop_and_finalize_calls_on_done(cfg):
    session = _make_session(cfg, n_chunks=200, loop=True)
    called = []
    session.start()
    time.sleep(0.2)
    session.stop_and_finalize(on_done=lambda: called.append(True))
    session.join(timeout=30)
    assert called == [True]
    assert session.state == SessionState.IDLE


def test_artifacts_written(cfg):
    session = _make_session(cfg, n_chunks=30, loop=False)
    session.start()
    session.join(timeout=30)
    from pathlib import Path

    mid = session.meeting.meeting_id
    assert Path(cfg.notes_dir, f"{mid}_live.md").exists()
    assert Path(cfg.notes_dir, f"{mid}_final.md").exists()
    assert Path(cfg.recordings_dir, f"{mid}_sys.wav").exists()
    assert Path(cfg.recordings_dir, f"{mid}_mic.wav").exists()
