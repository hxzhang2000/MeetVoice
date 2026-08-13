"""LLM / Ollama 接入层测试：验证 provider 解析与客户端工厂（无需真实 openai/requests）。"""

from __future__ import annotations

import sys
import types


def _install_fake_openai():
    """注入最小 openai 桩，使 build_llm_client 无需真实依赖即可单测。"""
    if "openai" in sys.modules:
        return sys.modules["openai"]

    m = types.ModuleType("openai")

    class OpenAI:
        def __init__(self, base_url=None, api_key=None):
            self.base_url = base_url
            self.api_key = api_key

    m.OpenAI = OpenAI
    sys.modules["openai"] = m
    return m


def test_llmconfig_resolved_openai():
    from meetvoice.config import Config

    cfg = Config()
    assert cfg.llm.provider == "openai"
    assert cfg.llm.resolved_base_url() == "https://api.openai.com/v1"
    assert cfg.llm.resolved_api_key() == ""


def test_llmconfig_resolved_ollama():
    from meetvoice.config import Config

    cfg = Config()
    cfg.llm.provider = "ollama"
    cfg.llm.ollama_host = "http://127.0.0.1:11434"
    assert cfg.llm.resolved_base_url() == "http://127.0.0.1:11434/v1"
    # 未设置 api_key 时回退占位（Ollama 不校验）
    assert cfg.llm.resolved_api_key() == "ollama"
    # 显式设置则保留
    cfg.llm.api_key = "x"
    assert cfg.llm.resolved_api_key() == "x"


def test_build_llm_client_openai():
    from meetvoice.config import Config
    from meetvoice.llm import build_llm_client

    _install_fake_openai()
    cfg = Config()
    cfg.llm.base_url = "https://api.deepseek.com/v1"
    cfg.llm.api_key = "sk-deep"
    client = build_llm_client(cfg.llm)
    assert client.base_url == "https://api.deepseek.com/v1"
    assert client.api_key == "sk-deep"


def test_build_llm_client_ollama():
    from meetvoice.config import Config
    from meetvoice.llm import build_llm_client

    _install_fake_openai()
    cfg = Config()
    cfg.llm.provider = "ollama"
    cfg.llm.ollama_host = "http://127.0.0.1:11434"
    client = build_llm_client(cfg.llm)
    assert client.base_url == "http://127.0.0.1:11434/v1"
    assert client.api_key == "ollama"


def test_ollama_helpers_graceful_without_server():
    from meetvoice.llm.ollama import is_ollama_running, list_ollama_models

    # 无 Ollama 服务（且本环境未装 requests）时应安全返回，不抛异常
    assert is_ollama_running("http://127.0.0.1:11434") is False
    assert list_ollama_models("http://127.0.0.1:11434") == []
