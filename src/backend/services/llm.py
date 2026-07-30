"""Khởi tạo LLM dùng chung cho agent."""

from functools import lru_cache

from langchain_openai import ChatOpenAI

from ..config import get_settings


@lru_cache
def get_llm() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.model_name,
        temperature=settings.llm_temperature,
        api_key=settings.openai_api_key or "sk-missing",
        timeout=45,
        max_retries=2,
    )
