"""滚动窗口测试：静音边界切分、强制切分（超 2×size）、drain 重叠、flush、buffered_len。"""

from __future__ import annotations

import numpy as np

from meetvoice.orchestrator.window import RollingWindow


def _sine(sr, sec, freq=200.0):
    t = np.arange(int(sr * sec)) / sr
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _silence(sr, sec):
    return np.zeros(int(sr * sec), dtype=np.float32)


def test_feed_and_drain_silence_boundary():
    w = RollingWindow(size_sec=3, silence_sec=0.2, sr=24000)
    # 3.5s 有声 + 0.5s 静音 -> 静音边界应被识别为切分点
    audio = np.concatenate([_sine(24000, 3.5), _silence(24000, 0.5)])
    w.feed(audio)
    assert w.has_segment_ready()
    seg = w.drain()
    assert len(seg) > 0
    assert not w.has_segment_ready()


def test_forced_cut_when_no_silence():
    w = RollingWindow(size_sec=2, silence_sec=0.2, sr=24000)
    # 持续有声超过 2×size，应强制在 size 处切分
    audio = _sine(24000, 5.0)
    w.feed(audio)
    assert w.has_segment_ready()
    seg = w.drain()
    # 切分长度应约等于 size_sec 的样本数
    assert abs(len(seg) - 2 * 24000) < 24000


def test_drain_keeps_overlap_and_flush():
    w = RollingWindow(size_sec=2, silence_sec=0.2, sr=24000)
    # 3.5s 有声 + 0.5s 静音：静音边界 (~3.5s) 在 after_sec(2s) 之后，应被切出
    audio = np.concatenate([_sine(24000, 3.5), _silence(24000, 0.5)])
    w.feed(audio)
    seg = w.drain()
    assert len(seg) > 0
    assert w.buffered_len > 0  # 保留重叠尾部
    rest = w.flush()
    assert w.buffered_len == 0
    assert len(rest) > 0


def test_buffered_len_and_sec():
    w = RollingWindow(size_sec=2, sr=24000)
    w.feed(_sine(24000, 1.0))
    assert w.buffered_len == 24000
    assert abs(w.buffered_sec - 1.0) < 1e-6
