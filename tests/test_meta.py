"""版本元数据 / CHANGELOG 相关测试（task #49）。"""

import re

import meetvoice


def test_version_format():
    assert re.match(r"^\d+\.\d+\.\d+$", meetvoice.__version__), meetvoice.__version__
    assert meetvoice.__version_info__ == tuple(
        int(x) for x in meetvoice.__version__.split(".")
    )


def test_meta_constants():
    assert meetvoice.__app_name__ == "MeetVoice"
    assert meetvoice.__github_url__.startswith("https://github.com/")
    assert "hxzhang2000/MeetVoice" in meetvoice.__github_url__
    assert meetvoice.__description__


def test_about_text_includes_version_and_repo():
    txt = meetvoice.about_text()
    assert meetvoice.__version__ in txt
    assert meetvoice.__github_url__ in txt
    assert "Star" in txt


def test_changelog_exists_and_mentions_version():
    p = meetvoice.changelog_path()
    assert p is not None, "CHANGELOG.md 未找到"
    content = p.read_text(encoding="utf-8")
    assert "Changelog" in content
    assert meetvoice.__version__ in content
