"""配置层（pydantic 校验 + TOML 加载 + 环境变量覆盖）。

设计要点（详见 docs/开发方案.md §4.5 / §6.6）：
- 配置优先级：环境变量 > 运行时设置 > config.toml。
- 路径型字段（notes_dir / recording_dir / recordings_dir / logs_dir）为顶层扁平字段，
  与各子配置（capture / asr / llm / ui / meetings / models）共存，便于编排层直接引用。
- 重配置加载策略：asr.backend / model_path / device / capture.sample_rate 等属「需重启」项；
  paths 仅影响下次会议；具体热更新边界见 §6.6。
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field
except ImportError:  # pragma: no cover - 仅在未安装 pydantic 时降级
    BaseModel = object  # type: ignore

    class Field:  # type: ignore
        def __init__(self, default=None, **kwargs):
            self.default = default

        @classmethod
        def _(cls, *a, **k):
            return None


# --------------------------------------------------------------------------- #
# 子配置
# --------------------------------------------------------------------------- #
if BaseModel is not object:
    class CaptureConfig(BaseModel):
        sample_rate: int = 48000           # 采集采样率（浮点）
        target_sample_rate: int = 24000    # 送 ASR 的目标采样率
        channels: int = 1
        silence_sec: float = 0.6           # 滚动窗口切分静音阈值
        mic_device: Optional[str] = None   # 麦克风设备名/索引；None=默认
        loopback_device: Optional[str] = None  # 系统声回环设备；None=自动探测

    class ASRConfig(BaseModel):
        backend: str = "vibevoice_local"
        model_path: str = "microsoft/VibeVoice-ASR"
        device: str = "auto"
        model_root: str = "models"
        hotwords: List[str] = Field(default_factory=list)
        hf_cache_dir: str = ""
        ms_cache_dir: str = ""
        # vibevoice_local
        compute_dtype: str = "bf16"
        attn_impl: str = "flash_attention_2"
        device_map: str = "auto"
        max_new_tokens: int = 32768
        # funasr_local
        funasr_model: str = "paraformer-large"
        funasr_vad: str = "fsmn-vad"
        funasr_punc: str = "ct-punc"
        funasr_spk: str = "auto"
        # moss_local
        moss_trust_remote_code: bool = True
        moss_max_audio_min: int = 90
        # vibeasr_cpp
        asr_cpp_bin: str = "models/vibeasr/asr_infer.exe"
        asr_cpp_vae: str = "models/vibeasr/vibeasr-vae-encoder-i8_s.gguf"
        asr_cpp_lm: str = "models/vibeasr/vibeasr-lm-i2_s-embed-q6_k.gguf"
        asr_cpp_threads: int = 6
        # vibeasr_vllm
        vllm_base_url: str = "http://localhost:8000/v1"
        vllm_api_key: str = ""
        vllm_model: str = "microsoft/VibeVoice-ASR"

    class LLMConfig(BaseModel):
        enabled: bool = True
        provider: str = "openai"        # openai | ollama
        base_url: str = "https://api.openai.com/v1"
        api_key: str = ""
        ollama_host: str = "http://localhost:11434"  # provider=ollama 时的本地服务地址
        model: str = "gpt-4o-mini"
        temperature: float = 0.2
        max_tokens: int = 2048
        timeout: int = 60
        prompt_template: str = ""

        def resolved_base_url(self) -> str:
            """返回实际使用的 OpenAI 兼容端点。

            provider=ollama 时由 ollama_host 推导为 ``http://host:port/v1``，
            忽略 base_url，实现本地大模型零配置接入。
            """
            if self.provider == "ollama":
                return self.ollama_host.rstrip("/") + "/v1"
            return self.base_url

        def resolved_api_key(self) -> str:
            """Ollama 不校验密钥，留空时回退占位值（OpenAI SDK 要求 api_key 非空）。"""
            if self.provider == "ollama":
                return self.api_key or "ollama"
            return self.api_key

    class UIConfig(BaseModel):
        autostart: bool = False
        minimize_to_tray_on_close: bool = True

    class MeetingsConfig(BaseModel):
        recycle: bool = True
        trash_dir: str = "trash"

    class ModelsConfig(BaseModel):
        active: str = ""
        auto_enable: bool = True


# --------------------------------------------------------------------------- #
# 顶层 Config
# --------------------------------------------------------------------------- #
if BaseModel is not object:
    class Config(BaseModel):
        notes_dir: str = "notes"
        recording_dir: str = "recordings"
        recordings_dir: str = "recordings"
        logs_dir: str = "logs"
        window_sec: int = 45

        capture: CaptureConfig = Field(default_factory=CaptureConfig)
        asr: ASRConfig = Field(default_factory=ASRConfig)
        llm: LLMConfig = Field(default_factory=LLMConfig)
        ui: UIConfig = Field(default_factory=UIConfig)
        meetings: MeetingsConfig = Field(default_factory=MeetingsConfig)
        models: ModelsConfig = Field(default_factory=ModelsConfig)

        # ---- 加载 / 保存 ------------------------------------------------ #
        @classmethod
        def from_toml(cls, path: str | Path, overrides: Optional[Dict[str, Any]] = None) -> "Config":
            """加载 config.toml；`overrides` 为 {section: {key: val}} 形式的覆盖
            （如模型管理写入的 [models]/[asr] 覆盖段），用于「启用模型」后的热生效重载。
            """
            path = Path(path)
            data: Dict[str, Any] = {}
            if path.exists():
                with path.open("rb") as f:
                    data = tomllib.load(f)
            if overrides:
                for sec, kv in overrides.items():
                    if isinstance(kv, dict) and isinstance(data.get(sec), dict):
                        data[sec].update(kv)
                    else:
                        data[sec] = kv
            cfg = cls._from_dict(data)
            cfg._apply_env()
            return cfg

        @classmethod
        def _from_dict(cls, data: Dict[str, Any]) -> "Config":
            paths = data.get("paths", {})
            window = data.get("window", {})
            return cls(
                notes_dir=paths.get("notes_dir", "notes"),
                recording_dir=paths.get("recording_dir", "recordings"),
                recordings_dir=paths.get("recordings_dir", "recordings"),
                logs_dir=paths.get("logs_dir", "logs"),
                window_sec=window.get("window_sec", 45),
                capture=CaptureConfig(**data.get("capture", {})),
                asr=ASRConfig(**data.get("asr", {})),
                llm=LLMConfig(**data.get("llm", {})),
                ui=UIConfig(**data.get("ui", {})),
                meetings=MeetingsConfig(**data.get("meetings", {})),
                models=ModelsConfig(**data.get("models", {})),
            )

        def _apply_env(self) -> None:
            """环境变量覆盖（优先级最高）：MEETVOICE_LLM_API_KEY 等。"""
            env_map = {
                "MEETVOICE_LLM_API_KEY": ("llm", "api_key"),
                "MEETVOICE_LLM_BASE_URL": ("llm", "base_url"),
                "MEETVOICE_LLM_MODEL": ("llm", "model"),
                "MEETVOICE_LLM_PROVIDER": ("llm", "provider"),
                "MEETVOICE_LLM_OLLAMA_HOST": ("llm", "ollama_host"),
                "MEETVOICE_ASR_BACKEND": ("asr", "backend"),
                "MEETVOICE_ASR_DEVICE": ("asr", "device"),
            }
            for env_key, (section, attr) in env_map.items():
                val = os.environ.get(env_key)
                if val is not None:
                    setattr(getattr(self, section), attr, val)

        def resolve(self, base_dir: str | Path) -> "Config":
            """将相对路径（notes_dir 等 / model_root / trash_dir）解析为 base_dir 下绝对路径。"""
            base = Path(base_dir)
            self.notes_dir = str(_resolve(self.notes_dir, base))
            self.recording_dir = str(_resolve(self.recording_dir, base))
            self.recordings_dir = str(_resolve(self.recordings_dir, base))
            self.logs_dir = str(_resolve(self.logs_dir, base))
            self.asr.model_root = str(_resolve(self.asr.model_root, base))
            self.meetings.trash_dir = str(_resolve(self.meetings.trash_dir, base))
            return self

        def ensure_dirs(self) -> None:
            for d in (self.notes_dir, self.recording_dir, self.recordings_dir, self.logs_dir):
                Path(d).mkdir(parents=True, exist_ok=True)


def _resolve(p: str | Path, base: Path) -> Path:
    p = Path(p)
    return p if p.is_absolute() else (base / p)


# 供未安装 pydantic 时的降级占位（不应命中正常路径）
if BaseModel is object:  # pragma: no cover
    class Config:  # type: ignore
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
