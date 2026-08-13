"""设置窗口（§6.6）：编辑 [capture]/[llm]/[ui]/[meetings]/[models] 并持久化为覆盖 toml。

保存策略：不覆盖主 config.toml，而是写入 `config.user.toml` 覆盖段，应用启动时由
`Config.from_toml(overrides=...)` 叠加生效。其中 backend/device/model_path 属「需重启」项，
窗口会提示用户重启后生效（§4.5.3 / §6.6 热更新边界）。
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from .._log import log
from .._tomlutil import dump_toml
from ..config import Config


def user_config_path(base_dir: str | Path) -> Path:
    return Path(base_dir) / "config.user.toml"


def build_override_sections(cfg: Config) -> dict:
    """把当前可编辑配置导出为覆盖段字典。"""
    return {
        "capture": {
            "sample_rate": cfg.capture.sample_rate,
            "target_sample_rate": cfg.capture.target_sample_rate,
            "silence_sec": cfg.capture.silence_sec,
            "mic_device": cfg.capture.mic_device or "",
            "loopback_device": cfg.capture.loopback_device or "",
        },
        "llm": {
            "enabled": cfg.llm.enabled,
            "provider": cfg.llm.provider,
            "base_url": cfg.llm.base_url,
            "api_key": cfg.llm.api_key,
            "ollama_host": cfg.llm.ollama_host,
            "model": cfg.llm.model,
            "temperature": cfg.llm.temperature,
            "max_tokens": cfg.llm.max_tokens,
            "timeout": cfg.llm.timeout,
        },
        "ui": {
            "autostart": cfg.ui.autostart,
            "minimize_to_tray_on_close": cfg.ui.minimize_to_tray_on_close,
        },
        "meetings": {
            "recycle": cfg.meetings.recycle,
            "trash_dir": cfg.meetings.trash_dir,
        },
        "models": {
            "active": cfg.models.active,
            "auto_enable": cfg.models.auto_enable,
        },
    }


def save_user_config(cfg: Config, base_dir: str | Path) -> Path:
    path = user_config_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_toml(build_override_sections(cfg)), encoding="utf-8")
    return path


def open_settings_window(cfg: Config, config_path: Optional[str] = None) -> None:
    """打开设置窗口（PySide6 懒加载）。config_path 用于定位 base_dir 以写覆盖文件。"""
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QComboBox,
        QFormLayout,
        QLineEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    app = QApplication.instance() or QApplication([])
    w = QWidget()
    w.setWindowTitle("MeetVoice · 设置")
    layout = QVBoxLayout(w)
    form = QFormLayout()

    # 构造可编辑控件并回填当前值
    ed = {}
    ed["mic_device"] = QLineEdit(cfg.capture.mic_device or "")
    ed["loopback_device"] = QLineEdit(cfg.capture.loopback_device or "")
    ed["silence_sec"] = QLineEdit(str(cfg.capture.silence_sec))
    ed["llm_enabled"] = QCheckBox(); ed["llm_enabled"].setChecked(cfg.llm.enabled)
    ed["llm_provider"] = QComboBox()
    ed["llm_provider"].addItems(["openai", "ollama"])
    ed["llm_provider"].setCurrentText(cfg.llm.provider)
    ed["llm_base_url"] = QLineEdit(cfg.llm.base_url)
    ed["llm_api_key"] = QLineEdit(cfg.llm.api_key)
    ed["llm_ollama_host"] = QLineEdit(cfg.llm.ollama_host)
    ed["llm_model"] = QLineEdit(cfg.llm.model)
    ed["ui_autostart"] = QCheckBox(); ed["ui_autostart"].setChecked(cfg.ui.autostart)
    ed["meetings_recycle"] = QCheckBox(); ed["meetings_recycle"].setChecked(cfg.meetings.recycle)
    ed["models_auto_enable"] = QCheckBox(); ed["models_auto_enable"].setChecked(cfg.models.auto_enable)

    def _sync_provider_visibility():
        is_ollama = ed["llm_provider"].currentText() == "ollama"
        # Ollama：端点由 ollama_host 推导，隐藏 base_url/api_key
        ed["llm_ollama_host"].setVisible(is_ollama)
        form.labelForField(ed["llm_ollama_host"]).setVisible(is_ollama)
        ed["llm_base_url"].setVisible(not is_ollama)
        form.labelForField(ed["llm_base_url"]).setVisible(not is_ollama)
        ed["llm_api_key"].setVisible(not is_ollama)
        form.labelForField(ed["llm_api_key"]).setVisible(not is_ollama)

    ed["llm_provider"].currentTextChanged.connect(_sync_provider_visibility)

    form.addRow("麦克风设备", ed["mic_device"])
    form.addRow("系统声回环设备", ed["loopback_device"])
    form.addRow("静音切分阈值(秒)", ed["silence_sec"])
    form.addRow("启用会议总结(LLM)", ed["llm_enabled"])
    form.addRow("LLM 接入方式", ed["llm_provider"])
    form.addRow("Ollama 服务地址", ed["llm_ollama_host"])
    form.addRow("LLM Base URL", ed["llm_base_url"])
    form.addRow("LLM API Key", ed["llm_api_key"])
    form.addRow("LLM 模型", ed["llm_model"])
    form.addRow("开机自启", ed["ui_autostart"])
    form.addRow("删除走回收站", ed["meetings_recycle"])
    form.addRow("模型自动启用", ed["models_auto_enable"])
    _sync_provider_visibility()
    layout.addLayout(form)

    btn_save = QPushButton("保存并提示重启")
    layout.addWidget(btn_save)

    def on_save():
        cfg.capture.mic_device = ed["mic_device"].text() or None
        cfg.capture.loopback_device = ed["loopback_device"].text() or None
        try:
            cfg.capture.silence_sec = float(ed["silence_sec"].text() or 0.6)
        except ValueError:
            pass
        cfg.llm.enabled = ed["llm_enabled"].isChecked()
        cfg.llm.provider = ed["llm_provider"].currentText()
        cfg.llm.model = ed["llm_model"].text()
        cfg.llm.ollama_host = ed["llm_ollama_host"].text()
        if cfg.llm.provider == "ollama":
            # 端点由 ollama_host 推导，api_key 用占位（Ollama 不校验）
            cfg.llm.base_url = cfg.llm.resolved_base_url()
            cfg.llm.api_key = "ollama"
        else:
            cfg.llm.base_url = ed["llm_base_url"].text()
            cfg.llm.api_key = ed["llm_api_key"].text()
        cfg.ui.autostart = ed["ui_autostart"].isChecked()
        cfg.meetings.recycle = ed["meetings_recycle"].isChecked()
        cfg.models.auto_enable = ed["models_auto_enable"].isChecked()
        base = Path(config_path).parent if config_path else Path(".")
        path = save_user_config(cfg, base)
        log.info("设置已保存到 {}（backend/device 等需重启生效）", path)

    btn_save.clicked.connect(on_save)
    w.show()
    if not QApplication.instance():
        app.exec()
