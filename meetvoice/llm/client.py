"""LLM 客户端工厂（§6.7）：按 provider 构造 OpenAI 兼容客户端。

- provider=openai：直接使用配置的 base_url / api_key（可指向官方 OpenAI、DeepSeek、
  阿里云百炼、本地 vLLM 等任意 OpenAI 兼容服务）。
- provider=ollama：端点由 ollama_host 推导为 ``http://host:port/v1``，api_key 回退占位，
  Ollama 的 OpenAI 兼容接口天然支持 ``chat.completions``，实现本地大模型零配置接入。

``openai`` 为可选依赖，在此处懒加载；未安装时抛出带安装提示的 ImportError。
"""

from __future__ import annotations

from typing import Any


def build_llm_client(cfg: Any) -> Any:
    """根据 ``LLMConfig`` 构造一个 OpenAI 兼容客户端。

    ``cfg`` 应提供 ``resolved_base_url()`` 与 ``resolved_api_key()`` 两个方法
    （见 ``meetvoice.config.LLMConfig``）。返回的客户端具有
    ``client.chat.completions.create(...)`` 接口，可直接被 ``MeetingSummarizer`` 使用。
    """
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - 依赖缺失时给出明确指引
        raise ImportError(
            "未安装 openai 依赖，无法创建 LLM 客户端。请运行 `pip install openai` "
            "（或 `pip install -e .[full]`）。"
        ) from exc

    return OpenAI(
        base_url=cfg.resolved_base_url(),
        api_key=cfg.resolved_api_key(),
    )
