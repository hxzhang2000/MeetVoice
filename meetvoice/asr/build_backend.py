"""按配置分派构造 ASR 后端（§4.5 / §6.3）。

所有后端类均为懒加载：仅当真正使用该 backend 时才 import 对应重型依赖。
依赖缺失时抛出带安装提示的 RuntimeError，不影响其他后端与纯逻辑单测。
"""

from __future__ import annotations

from typing import Any

from ..config import ASRConfig


def build_backend(cfg: ASRConfig) -> Any:
    """根据 cfg.backend 构造对应后端实例。"""
    backend = cfg.backend
    try:
        if backend == "vibevoice_local":
            from .vibevoice_local import VibeVoiceLocalBackend

            return VibeVoiceLocalBackend(cfg)
        if backend == "moss_local":
            from .moss_local import MossLocalBackend

            return MossLocalBackend(cfg)
        if backend == "funasr_local":
            from .funasr_local import FunASRLocalBackend

            return FunASRLocalBackend(cfg)
        if backend == "vibeasr_cpp":
            from .vibeasr_cpp import VibeASRCppBackend

            return VibeASRCppBackend(cfg)
        if backend == "vibeasr_vllm":
            from .vibeasr_vllm import VibeASRVllmBackend

            return VibeASRVllmBackend(cfg)
        if backend in ("fireredasr_local", "qwen3asr_local"):
            raise NotImplementedError(
                f"后端 {backend} 为后续里程碑（M12/M14）实现的适配器，当前未提供。请参阅 models_catalog.toml。"
            )
    except ImportError as e:
        raise RuntimeError(
            f"后端 {backend} 所需依赖未安装：{e}。请 pip install -e .[full] 或单独安装对应依赖。"
        ) from e
    raise ValueError(f"未知 ASR 后端：{backend}")
