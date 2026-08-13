"""命令行入口（§6.6 / §9）：meetvoice <command>。

命令：
- version            打印版本
- config [--path]    解析并打印当前配置
- list               列出历史会议
- models             列出模型目录及本地状态
- recover <id>       对中断会议基于已落盘 wav 重跑终稿+总结
- start [--config]   启动托盘桌面应用（需图形环境）
- demo [--seconds]   无硬件端到端冒烟测试（MockBackend + IterableCapture）

click 为依赖项；重型 ML/GUI 依赖仍仅在对应命令内部懒加载。
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

import click

from . import (
    __app_name__,
    __description__,
    __github_url__,
    __version__,
    about_text,
    changelog_path,
)
from ._log import log
from .config import Config


def _load_config(config_path: Optional[str]) -> Config:
    """加载 config.toml，并叠加 config.user.toml / config.models.toml 覆盖段。"""
    import tomllib

    base = Path(config_path) if config_path else Path("config.toml")
    overrides: dict = {}
    for name in ("config.user.toml", "config.models.toml"):
        p = base.parent / name if base.exists() else Path(name)
        if p.exists():
            overrides.update(tomllib.loads(p.read_text(encoding="utf-8")))
    return Config.from_toml(base, overrides=overrides or None)


@click.group()
@click.version_option(version=__version__, prog_name="MeetVoice")
def cli():
    """MeetVoice 实时会议记录命令行。"""


@cli.command()
def version():
    """打印版本号。"""
    click.echo(__version__)


@cli.command()
def about():
    """显示版本与 GitHub 仓库信息，并推荐 Star。"""
    click.echo(about_text())


@cli.command()
def changelog():
    """打印 CHANGELOG.md（若存在）。"""
    p = changelog_path()
    if p is None:
        click.echo("未找到 CHANGELOG.md（开发仓库根目录）。", err=True)
        raise SystemExit(1)
    click.echo(p.read_text(encoding="utf-8"))


@cli.command()
@click.option("--path", default=None, help="config.toml 路径（默认 ./config.toml）")
def config(path):
    """解析并打印当前配置。"""
    cfg = _load_config(path)
    click.echo(f"version        = {__version__}")
    click.echo(f"notes_dir      = {cfg.notes_dir}")
    click.echo(f"recording_dir  = {cfg.recording_dir}")
    click.echo(f"recordings_dir = {cfg.recordings_dir}")
    click.echo(f"logs_dir       = {cfg.logs_dir}")
    click.echo(f"window_sec     = {cfg.window_sec}")
    click.echo(f"asr.backend    = {cfg.asr.backend}")
    click.echo(f"asr.model_path = {cfg.asr.model_path}")
    click.echo(f"asr.device     = {cfg.asr.device}")
    click.echo(f"llm.enabled    = {cfg.llm.enabled}")
    click.echo(f"llm.provider   = {cfg.llm.provider}")
    if cfg.llm.provider == "ollama":
        click.echo(f"llm.ollama_host = {cfg.llm.ollama_host}")
    click.echo(f"models.active  = {cfg.models.active}")


@cli.command()
@click.option("--path", default=None, help="config.toml 路径")
def list(path):
    """列出历史会议（§6.8）。"""
    cfg = _load_config(path)
    from .meeting.store import MeetingStore

    store = MeetingStore(
        cfg.recordings_dir,
        trash_dir=cfg.meetings.trash_dir if cfg.meetings.recycle else None,
    )
    recs = store.list()
    if not recs:
        click.echo("（无会议记录）")
        return
    for r in recs:
        click.echo(f"{r.meeting_id}  [{r.status}]  {r.duration_str}  spk={r.speaker_count}")


@cli.command()
@click.option("--path", default=None, help="config.toml 路径")
def models(path):
    """列出模型目录及本地状态（§4.5 / §6.6）。"""
    cfg = _load_config(path)
    from .models import ModelManager

    mgr = ModelManager(cfg)
    for st in mgr.list_status():
        flag = "●" if st["active"] else " "
        dl = "已下载" if st["downloaded"] else "未下载"
        click.echo(f"[{flag}] {st['id']:<24} {st['backend']:<16} {dl}  {st['name']}")


@cli.group()
def llm():
    """LLM / Ollama 本地大模型相关命令。"""


@llm.command("check")
@click.option("--path", default=None, help="config.toml 路径")
def llm_check(path):
    """检查 LLM 配置与 Ollama 服务状态。"""
    cfg = _load_config(path)
    click.echo(f"provider  = {cfg.llm.provider}")
    click.echo(f"model     = {cfg.llm.model}")
    if cfg.llm.provider == "ollama":
        click.echo(f"ollama_host = {cfg.llm.ollama_host}")
        click.echo(f"endpoint    = {cfg.llm.resolved_base_url()}")
        from .llm.ollama import is_ollama_running, list_ollama_models

        running = is_ollama_running(cfg.llm.ollama_host)
        click.echo(f"ollama 运行 = {'是' if running else '否'}")
        if running:
            models = list_ollama_models(cfg.llm.ollama_host)
            click.echo(f"本地模型   = {', '.join(models) if models else '（无）'}")
            ready = cfg.llm.model in models
            click.echo(
                f"当前模型就绪 = {'是' if ready else f'否（可 `meetvoice llm pull {cfg.llm.model}`）'}"
            )
    else:
        click.echo(f"base_url = {cfg.llm.base_url}")


@llm.command("list")
@click.option("--path", default=None, help="config.toml 路径")
def llm_list(path):
    """列出 Ollama 本地已拉取的模型。"""
    cfg = _load_config(path)
    if cfg.llm.provider != "ollama":
        click.echo("provider 非 ollama，无需列出本地模型；可用 `meetvoice config` 查看端点。")
        return
    from .llm.ollama import is_ollama_running, list_ollama_models

    if not is_ollama_running(cfg.llm.ollama_host):
        click.echo(f"Ollama 未运行（{cfg.llm.ollama_host}）。", err=True)
        raise SystemExit(1)
    for m in list_ollama_models(cfg.llm.ollama_host):
        click.echo(m)


@llm.command("pull")
@click.argument("model")
@click.option("--path", default=None, help="config.toml 路径")
def llm_pull(model, path):
    """从 Ollama 拉取指定模型（如 `meetvoice llm pull qwen2.5:7b`）。"""
    cfg = _load_config(path)
    from .llm.ollama import is_ollama_running, pull_ollama_model

    if cfg.llm.provider != "ollama":
        click.echo("provider 非 ollama，跳过拉取。", err=True)
        raise SystemExit(1)
    if not is_ollama_running(cfg.llm.ollama_host):
        click.echo(f"Ollama 未运行（{cfg.llm.ollama_host}），无法拉取。", err=True)
        raise SystemExit(1)
    click.echo(f"正在从 Ollama 拉取 {model} …")
    try:
        pull_ollama_model(cfg.llm.ollama_host, model)
        click.echo(f"已拉取 {model}。请将其填入 [llm].model 后使用。")
    except Exception as e:
        click.echo(f"拉取失败：{e}", err=True)
        raise SystemExit(1)


@cli.command()
@click.argument("meeting_id")
@click.option("--path", default=None, help="config.toml 路径")
def recover(meeting_id, path):
    """对中断会议基于已落盘 wav 重跑终稿+总结（§6.5 崩溃恢复）。"""
    cfg = _load_config(path)
    from .orchestrator import recover_meeting

    try:
        rec = recover_meeting(cfg, meeting_id)
        click.echo(f"已恢复会议 {meeting_id}，状态：{rec.status}")
    except Exception as e:
        click.echo(f"恢复失败：{e}", err=True)
        raise SystemExit(1)


@cli.command()
@click.option("--config", "config_path", default=None, help="config.toml 路径")
def start(config_path):
    """启动托盘桌面应用（需图形环境）。"""
    cfg = _load_config(config_path)
    from .ui import run_app

    raise SystemExit(run_app(cfg, config_path=config_path))


@cli.command()
@click.option("--seconds", default=8, help="模拟会议时长（秒）")
@click.option("--path", default=None, help="config.toml 路径（可选，仅读默认值）")
def demo(seconds, path):
    """无硬件端到端冒烟测试：MockBackend + IterableCapture 跑通采集→ASR→出稿→终稿。"""
    import numpy as np

    from .asr import MockBackend
    from .audio.capture import IterableCapture
    from .orchestrator import LiveSession

    base = Path(tempfile.mkdtemp(prefix="meetvoice_demo_"))
    cfg = Config()
    cfg.notes_dir = str(base / "notes")
    cfg.recording_dir = str(base / "recordings")
    cfg.recordings_dir = str(base / "recordings")
    cfg.logs_dir = str(base / "logs")
    cfg.llm.enabled = False  # 冒烟不调用 LLM（避免联网）
    cfg.window_sec = 2
    cfg.capture.silence_sec = 0.1
    cfg.capture.sample_rate = 24000  # 演示直接用 24k，省去重采样路径差异
    cfg.capture.target_sample_rate = 24000
    cfg.ensure_dirs()

    sr = cfg.capture.sample_rate
    chunk = np.zeros(int(sr * 0.2), dtype=np.float32)
    n = max(1, int(seconds / 0.2))
    cap = IterableCapture([(chunk, chunk)] * n, loop=False, sample_rate=sr)
    backend = MockBackend()

    session = LiveSession(cfg, capture=cap, asr=backend)
    states: list[str] = []
    session.on_state_change = lambda s: states.append(s)
    session.start()
    session.join(timeout=30)

    rec = session.meeting
    final_md = base / "notes" / f"{rec.meeting_id}_final.md"
    live_md = base / "notes" / f"{rec.meeting_id}_live.md"
    click.echo(f"状态序列: {states}")
    click.echo(f"会议 ID : {rec.meeting_id}")
    click.echo(f"状态    : {rec.status}")
    click.echo(f"live.md : {live_md.exists()}")
    click.echo(f"final.md: {final_md.exists()}")
    if final_md.exists():
        click.echo("--- final.md 片段 ---")
        click.echo("\n".join(final_md.read_text(encoding="utf-8").splitlines()[:8]))
    click.echo(f"临时目录: {base}")


def main():
    cli()


if __name__ == "__main__":
    main()
