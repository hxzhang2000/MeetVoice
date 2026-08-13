"""会议总结测试：注入 fake OpenAI client（避免联网），验证调用与 map-reduce 分块。"""

from __future__ import annotations


class _Msg:
    def __init__(self, content):
        self.content = content


class _Ch:
    message = None

    def __init__(self, content):
        self.message = _Msg(content)


class _Resp:
    def __init__(self, content):
        self.choices = [_Ch(content)]


class FakeCompletions:
    def __init__(self, store):
        self._store = store

    def create(self, **kw):
        self._store["calls"] += 1
        prompt = kw.get("messages", [{}])[0].get("content", "")
        if "合并" in prompt:
            return _Resp("合并后的结构化纪要")
        return _Resp("分块摘要")


class FakeChat:
    def __init__(self, store):
        self.completions = FakeCompletions(store)


class FakeClient:
    def __init__(self, store):
        self.chat = FakeChat(store)
        self.store = store


def test_summarize_single_chunk():
    from meetvoice.config import Config
    from meetvoice.summary import MeetingSummarizer

    store = {"calls": 0}
    cfg = Config()
    cfg.llm.enabled = True
    s = MeetingSummarizer(cfg, client=FakeClient(store))
    out = s.summarize("今天讨论了项目排期。")
    assert out == "分块摘要"
    assert store["calls"] == 1


def test_summarize_map_reduce():
    from meetvoice.config import Config
    from meetvoice.summary import MeetingSummarizer

    store = {"calls": 0}
    cfg = Config()
    cfg.llm.enabled = True
    cfg.llm.max_tokens = 100  # 小预算触发切片
    s = MeetingSummarizer(cfg, client=FakeClient(store))
    # 构造超长文本
    long_text = "\n".join(f"第{i}条发言内容。" for i in range(200))
    out = s.summarize(long_text)
    assert "合并" in out  # 触发了二次合并
    assert store["calls"] >= 2  # 至少分块一次 + 合并一次


def test_summarize_empty():
    from meetvoice.config import Config
    from meetvoice.summary import MeetingSummarizer

    cfg = Config()
    s = MeetingSummarizer(cfg, client=FakeClient({"calls": 0}))
    out = s.summarize("")
    assert "无转写内容" in out
