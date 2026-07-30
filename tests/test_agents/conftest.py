"""LLM giả cho test node — không gọi mạng, không cần API key."""

import pytest

from src.backend.agents.shared.nodes.form_nodes import ExtractedDraft


class FakeStructuredLLM:
    """Trả về lần lượt các `ExtractedDraft` đã dựng sẵn."""

    def __init__(self, results: list[ExtractedDraft]):
        self.results = list(results)
        self.calls: list[object] = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        if self.results:
            return self.results.pop(0)
        return ExtractedDraft()


class FakeLLM:
    def __init__(self, results: list[ExtractedDraft]):
        self.structured = FakeStructuredLLM(results)

    def with_structured_output(self, schema):  # noqa: ARG002
        return self.structured


@pytest.fixture
def fake_llm(monkeypatch):
    """Nạp sẵn kết quả LLM: `fake_llm([draft1, draft2, ...])`."""

    def install(results: list[ExtractedDraft]) -> FakeLLM:
        llm = FakeLLM(results)
        monkeypatch.setattr(
            "src.backend.agents.shared.nodes.form_nodes.get_llm",
            lambda: llm,
        )
        return llm

    return install
