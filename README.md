# MeetVoice

实时会议记录系统：双路音频采集（系统声音 WASAPI 回环 + 本机麦克风），实时转写为文字并保存为本地 Markdown；会议结束后可调用 OpenAI 兼容大模型生成结构化会议总结，并提供会议管理与模型管理。

详见 [docs/开发方案.md](docs/开发方案.md)（当前 v1.15）。

如果 MeetVoice 对你有帮助，欢迎在 GitHub 上给我们一个 ⭐ [Star](https://github.com/hxzhang2000/MeetVoice)！

## 快速开始

```bash
# 1. 创建虚拟环境并安装
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e .[dev]         # 仅开发/单测
pip install -e .[full]        # 完整运行（含 GPU 后端）

# 2. 初始化配置
cp config.example.toml config.toml
# 按需编辑 config.toml（模型、LLM key、输出目录等）

# 3. 运行
meetvoice                    # 默认启动桌面外壳（托盘 + 控制窗口）
meetvoice --headless         # 无 UI 的命令行模式
meetvoice --help
```

## 项目结构

```
meetvoice/
├── audio/      # 双路采集、重采样、VAD
├── recorder/   # 双路 WAV 落盘
├── asr/        # ASR 适配器（vibevoice / moss / funasr / vibeasr_cpp / vibeasr_vllm）
├── writer/     # Markdown 写入（live / final / summary）
├── orchestrator/ # 滚动窗口 + LiveSession 编排
├── summary/    # 会议总结（OpenAI 兼容）
├── meeting/    # 会议管理（JSON 单一事实源、级联删除、回收站）
├── models/     # 模型管理（catalog / manager / download）
├── ui/         # 桌面外壳（托盘 / 控制窗口 / 设置 / 会议 / 模型面板）
└── cli.py      # 命令行入口
tests/          # 单元测试
```

## 设计约束

- 模型权重、录音、纪要、日志均为运行产物，已写入 `.gitignore`。
- 配置加载优先级：环境变量 > 运行时设置 > config.toml。
- 所有重型依赖（torch / funasr / pystray / PySide6 等）均为懒加载，未安装时不影响包导入与纯逻辑单测。
