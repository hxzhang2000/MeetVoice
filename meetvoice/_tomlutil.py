"""极简 TOML 序列化（仅覆盖本项目需要的扁平/列表结构），用于配置覆盖文件持久化。

不引入第三方 toml 写库：本项目只需写入 [section] = {key: scalar|list} 形式的覆盖段，
由 `Config.from_toml(overrides=...)` 在启动时叠加生效。
"""

from __future__ import annotations

from typing import Any


def _scalar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def dump_toml(sections: dict) -> str:
    """sections: {sec_name: {key: value}} 或 {key: scalar}。返回 TOML 文本。"""
    lines: list[str] = []
    for sec, kv in sections.items():
        if isinstance(kv, dict):
            lines.append(f"[{sec}]")
            for k, v in kv.items():
                if isinstance(v, (list, tuple)):
                    inner = ", ".join(_scalar(x) for x in v)
                    lines.append(f"{k} = [{inner}]")
                else:
                    lines.append(f"{k} = {_scalar(v)}")
            lines.append("")
        else:
            lines.append(f"{sec} = {_scalar(kv)}")
    return "\n".join(lines)
