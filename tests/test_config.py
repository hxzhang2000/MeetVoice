"""配置层测试：TOML 加载、环境变量覆盖、overrides 叠加、路径解析、目录创建。"""

from __future__ import annotations

from pathlib import Path

import pytest

from meetvoice.config import Config


def test_from_toml_and_env(tmp_path, monkeypatch):
    p = tmp_path / "config.toml"
    p.write_text(
        '[paths]\nnotes_dir = "my_notes"\n'
        '[asr]\nbackend = "moss_local"\n'
        '[llm]\nenabled = true\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("MEETVOICE_LLM_API_KEY", "sk-test-123")
    monkeypatch.setenv("MEETVOICE_ASR_BACKEND", "funasr_local")
    cfg = Config.from_toml(p)
    assert cfg.notes_dir == "my_notes"
    assert cfg.asr.backend == "funasr_local"  # 环境变量优先级最高
    assert cfg.llm.api_key == "sk-test-123"


def test_overrides_merge(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('[asr]\nbackend = "vibevoice_local"\n', encoding="utf-8")
    cfg = Config.from_toml(p, overrides={"asr": {"backend": "moss_local"}})
    assert cfg.asr.backend == "moss_local"


def test_resolve_makes_absolute(tmp_path):
    cfg = Config()
    cfg.notes_dir = "notes"
    cfg.resolve(tmp_path)
    assert Path(cfg.notes_dir).is_absolute()
    assert str(Path(cfg.notes_dir)) == str(tmp_path / "notes")


def test_ensure_dirs(tmp_path):
    cfg = Config()
    cfg.notes_dir = str(tmp_path / "a")
    cfg.recording_dir = str(tmp_path / "b")
    cfg.recordings_dir = str(tmp_path / "c")
    cfg.logs_dir = str(tmp_path / "d")
    cfg.ensure_dirs()
    for d in (cfg.notes_dir, cfg.recording_dir, cfg.recordings_dir, cfg.logs_dir):
        assert Path(d).is_dir()
