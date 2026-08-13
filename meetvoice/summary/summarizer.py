"""会议总结模块（§6.7）：会后 LLM 结构化纪要。

设计要点：
- 仅会后调用一次，全程不上传音频，仅把转写纯文本送 OpenAI 兼容大模型。
- `openai` 为可选依赖，在 `MeetingSummarizer.__init__` 内懒加载；未安装时
  不影响包导入与纯逻辑单测（测试可注入 fake client）。
- 防幻觉纪律（见 SUMMARY_PROMPT）：未提及即标"未讨论"，不得补写转写外内容。
- 长会议 map-reduce：超 token 预算时切片逐块总结再二次合并（见 summarize）。
"""

from __future__ import annotations

import os
from typing import List, Optional

from ..config import Config

SUMMARY_PROMPT = """你是一名严谨的会议记录助手。请仅依据下方转写稿输出结构化纪要，
严守以下纪律：
1. 不得编造转写稿中未出现的人名、数据、决议或行动项；某类信息未讨论时，写明"未讨论"。
2. 关键决议 / 行动项尽量引用原文时间戳（如 [14:32]），便于回查。
3. 输出包含：一句话摘要、详细摘要、关键决议、待办事项（务必标注负责人与截止时间）、
   行动项、未决问题。

转写稿如下：
{transcript}"""


def _chunk_text(text: str, max_chars: int) -> List[str]:
    """按字符预算粗略切片（中文按字符计，约略对应 token）。"""
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]
    chunks: List[str] = []
    step = int(max_chars * 0.9)  # 留 10% 重叠，避免句子被切断
    for i in range(0, len(text), step):
        chunks.append(text[i : i + max_chars])
    return chunks


class MeetingSummarizer:
    def __init__(self, cfg: Config, client: Optional[object] = None):
        self.cfg = cfg.llm
        # client 可注入（测试用 fake）；否则懒加载 openai
        self._client = client
        self._client_loaded = client is not None

    @property
    def client(self):
        if self._client is None and not self._client_loaded:
            from openai import OpenAI  # 懒加载（可选依赖）

            key = self.cfg.api_key or os.getenv("MEETVOICE_LLM_API_KEY", "")
            self._client = OpenAI(base_url=self.cfg.base_url, api_key=key)
            self._client_loaded = True
        return self._client

    def summarize(self, transcript: str) -> str:
        """对转写纯文本生成结构化纪要 markdown。

        长文本走 map-reduce：先逐块总结，再合并做二次总结；仍超长则截断并注明。
        """
        if not transcript or not transcript.strip():
            return "# 会议总结\n\n（无转写内容，无法生成纪要。）"

        prompt_template = self.cfg.prompt_template or SUMMARY_PROMPT
        # 字符预算：max_tokens 的中文大致等价字符数（保守按 1 token≈1 中文字）
        budget = max(500, int(self.cfg.max_tokens / 2))
        chunks = _chunk_text(transcript, budget)

        if len(chunks) == 1:
            return self._call(prompt_template.replace("{transcript}", chunks[0]))

        # map-reduce：逐块总结
        partials: List[str] = []
        for ch in chunks:
            partials.append(self._call(prompt_template.replace("{transcript}", ch)))
        merged = "\n\n---\n\n".join(partials)
        # 二次合并总结
        final_prompt = (
            "以下是同一会议分块得到的若干摘要，请合并为一份完整结构化纪要，"
            "去重并保留所有关键决议、待办与未决问题：\n\n" + merged
        )
        return self._call(final_prompt)

    def _call(self, prompt: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.cfg.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
            timeout=self.cfg.timeout,
        )
        return (resp.choices[0].message.content or "").strip()
