# Changelog

MeetVoice 更新日志。格式参考 [Keep a Changelog](https://keepachangelog.com/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)（**软件包版本**，独立于
`docs/开发方案.md` 的设计文档版本，后者领先于实现）。

## [0.2.0] - 2026-08-13

### Added
- **版本控制**：包与 `pyproject.toml` 统一版本号 `0.2.0`；`meetvoice/__init__.py`
  新增元数据（`__app_name__`/`__version__`/`__github_url__` 等）作为单一事实源，
  并提供 `about_text()` 与 `changelog_path()` 纯函数。
- **更新日志**：新增本 `CHANGELOG.md`，按版本记录变更。
- **软件显示版本号**：
  - CLI：`meetvoice version` / `--version` 以及 `meetvoice config` 顶部均显示版本；
    新增 `meetvoice about`、`meetvoice changelog` 命令。
  - 桌面端：托盘悬浮标题显示 `MeetVoice v0.2.0`；设置窗口底部显示版本与 GitHub 链接；
    新增「关于」对话框。
- **GitHub Star 推荐**：关于对话框与托盘菜单提供「⭐ 在 GitHub 上 Star」入口，
  并附仓库链接。

## [0.1.0] - 2026-08-13

### Added
- 初始软件骨架（按 `docs/开发方案.md` §8 结构树实现），全部重型依赖懒加载、纯逻辑可单测。
- 配置层、会议管理（JSON 单一事实源 + 回收站）、Markdown 滚动出稿、静音边界滚动窗口、
  双路音频采集（真实 WASAPI loopback + 测试替身）。
- ASR 适配器（vibevoice / moss / funasr / vibeasr_cpp / vibeasr_vllm + MockBackend）；
  LiveSession 单一状态源编排；LLM 会议总结。
- 模型管理、桌面托盘壳（懒加载）、CLI。
- LLM 接入 Ollama 本地大模型（零配置、全本地零外传）。
- 34+ 单测通过，无硬件端到端冒烟（`meetvoice demo`）通过。
