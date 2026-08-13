"""LLM 接入层（§6.7）：客户端工厂 + Ollama 本地模型管理。

设计要点：
- 总结模块只依赖 OpenAI 兼容接口；provider 决定端点来源（官方/第三方/本地 Ollama/vLLM）。
- `openai` / `requests` 均为可选依赖，仅在对应函数内懒加载；未安装不影响包导入与纯逻辑单测。
"""

from __future__ import annotations

from .client import build_llm_client
from .ollama import (
    ensure_ollama_model,
    is_ollama_running,
    list_ollama_models,
    pull_ollama_model,
)

__all__ = [
    "build_llm_client",
    "is_ollama_running",
    "list_ollama_models",
    "pull_ollama_model",
    "ensure_ollama_model",
]
