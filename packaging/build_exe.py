"""构建 MeetVoice 单文件 exe（Windows）。

用法（在项目根目录执行）：
    python packaging/build_exe.py

前置：
    pip install pyinstaller pystray PySide6 requests openai
    （重型 ML 依赖 torch/transformers/funasr/sounddevice/librosa 不打包——
     真实 GPU/CPU 转写需另行安装，且本测试版不依赖它们即可验证 CLI 与桌面壳。）

产物：dist/meetvoice.exe（单文件，自包含）。

说明：
    - 默认 --console（测试时可见日志）。正式发布可把 --console 改为 --windowed。
    - PySide6 用 --collect-all 完整打包 Qt 插件（平台/图像格式等），确保 GUI 可渲染。
    - models_catalog.toml / config.example.toml / CHANGELOG.md / README.md 以 --add-data
      放到包根，运行时由 `sys._MEIPASS` 解析，与设计文档中相对路径定位一致。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # 项目根
LAUNCHER = ROOT / "packaging" / "launcher.py"

DATA_FILES = [
    "models_catalog.toml",
    "config.example.toml",
    "CHANGELOG.md",
    "README.md",
]


def build() -> int:
    if not LAUNCHER.exists():
        print(f"[build] 找不到启动器: {LAUNCHER}", file=sys.stderr)
        return 2

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--name",
        "meetvoice",
        "--paths",
        str(ROOT),  # 让分析阶段能 import meetvoice 包
        "--console",  # 测试期保留控制台；发布改为 --windowed
        "--collect-all",
        "PySide6",
        "--collect-submodules",
        "pystray",
        "--collect-submodules",
        "meetvoice",
        "--hidden-import",
        "openai",
        "--hidden-import",
        "requests",
    ]
    for f in DATA_FILES:
        p = ROOT / f
        if p.exists():
            cmd += ["--add-data", f"{p};."]
        else:
            print(f"[build] 警告：未找到数据文件 {p}，跳过", file=sys.stderr)
    cmd.append(str(LAUNCHER))

    print("[build] 执行：", " ".join(cmd[:8]), "... (参数略)")
    rc = subprocess.call(cmd)
    if rc == 0:
        exe = ROOT / "dist" / "meetvoice.exe"
        print(f"[build] 完成 -> {exe}  ({exe.stat().st_size / 1024 / 1024:.1f} MB)" if exe.exists() else "[build] 完成，但未找到产物")
    else:
        print(f"[build] PyInstaller 失败，rc={rc}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(build())
