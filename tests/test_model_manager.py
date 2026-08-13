"""模型管理测试：catalog 解析、下载落点、状态、启用（互斥+持久化）、删除、自动启用。

全部使用 fake downloader，不联网、不依赖重型依赖。
"""

from __future__ import annotations

from pathlib import Path

from meetvoice.config import Config
from meetvoice.models import ModelCatalog, ModelManager


def _fake_downloader(entry, dest, progress_cb=None, cancel_event=None):
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "weights.bin").write_text("x", encoding="utf-8")


def _mgr(tmp_path, catalog=None):
    c = Config()
    c.asr.model_root = str(tmp_path)
    cat = catalog or ModelCatalog.load()
    return ModelManager(
        c,
        catalog=cat,
        model_root=str(tmp_path),
        downloader=_fake_downloader,
        override_path=tmp_path / "config.models.toml",
    )


def test_catalog_load():
    cat = ModelCatalog.load()
    ids = [e.id for e in cat.list()]
    assert "vibevoice-7b" in ids
    assert "moss-0.9b" in ids
    e = cat.get("moss-0.9b")
    assert e.backend == "moss_local"
    assert e.target_dir == "moss"


def test_target_dir_and_status(tmp_path):
    mgr = _mgr(tmp_path)
    e = mgr.entry("moss-0.9b")
    assert mgr.model_dir(e) == tmp_path / "moss" / "moss-0.9b"
    assert mgr.is_downloaded("moss-0.9b") is False
    st = mgr.status("moss-0.9b")
    assert st["downloaded"] is False


def test_download_enable_disable_persist(tmp_path):
    mgr = _mgr(tmp_path)
    dest = mgr.download("moss-0.9b")
    assert dest.exists() and any(dest.iterdir())
    assert mgr.is_downloaded("moss-0.9b") is True

    mgr.enable("moss-0.9b")
    assert mgr.cfg.models.active == "moss-0.9b"
    assert mgr.cfg.asr.backend == "moss_local"
    assert mgr.cfg.asr.model_path == "OpenMOSS-Team/MOSS-Transcribe-Diarize"

    # 持久化覆盖文件可被重新加载
    ov = mgr.load_override()
    assert ov["models"]["active"] == "moss-0.9b"
    assert ov["asr"]["backend"] == "moss_local"

    mgr.disable()
    assert mgr.cfg.models.active == ""


def test_enable_requires_download(tmp_path):
    mgr = _mgr(tmp_path)
    try:
        mgr.enable("vibevoice-7b")  # 未下载
        assert False, "应抛 RuntimeError"
    except RuntimeError:
        pass


def test_delete(tmp_path):
    mgr = _mgr(tmp_path)
    mgr.download("moss-0.9b")
    assert mgr.is_downloaded("moss-0.9b")
    mgr.delete("moss-0.9b")
    assert not mgr.is_downloaded("moss-0.9b")


def test_auto_enable_single(tmp_path):
    mgr = _mgr(tmp_path)
    mgr.download("moss-0.9b")  # 仅一个已下载
    enabled = mgr.auto_enable()
    assert enabled == "moss-0.9b"
    assert mgr.cfg.models.active == "moss-0.9b"
