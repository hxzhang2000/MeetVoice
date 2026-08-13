"""Ollama 本地服务辅助（§6.7）：探测 / 列出模型 / 拉取模型。

仅在接入 Ollama 本地大模型时需要，全部懒加载 ``requests``；未安装不影响包导入与纯逻辑单测。
使用的是 Ollama 原生 REST API（非 OpenAI 兼容路径）：

- ``GET  {host}/api/tags``   列出本地已拉取模型
- ``POST {host}/api/pull``   拉取模型（body: ``{"name": <model>, "stream": false}``）
"""

from __future__ import annotations

from typing import List


def _host(host: str) -> str:
    return host.rstrip("/")


def is_ollama_running(host: str) -> bool:
    """Ollama 服务是否可达（``/api/tags`` 返回 200）。"""
    try:
        import requests

        r = requests.get(f"{_host(host)}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def list_ollama_models(host: str) -> List[str]:
    """列出 Ollama 本地已拉取的模型名；服务不可达时返回空列表。"""
    try:
        import requests

        r = requests.get(f"{_host(host)}/api/tags", timeout=5)
        r.raise_for_status()
        data = r.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def pull_ollama_model(host: str, model: str) -> bool:
    """从 Ollama 拉取指定模型（非流式）。成功返回 True；失败抛 RuntimeError。"""
    try:
        import requests

        r = requests.post(
            f"{_host(host)}/api/pull",
            json={"name": model, "stream": False},
            timeout=600,
        )
        r.raise_for_status()
        return True
    except Exception as exc:  # pragma: no cover - 依赖/网络问题由调用方捕获提示
        raise RuntimeError(f"Ollama 拉取模型 {model} 失败：{exc}") from exc


def ensure_ollama_model(host: str, model: str) -> bool:
    """若本地已存在则直接返回 True；否则拉取。"""
    if model in list_ollama_models(host):
        return True
    return pull_ollama_model(host, model)
