from langchain_openai import ChatOpenAI
from app.config import settings
from typing import Optional


def get_llm(
    temperature: float | None = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> ChatOpenAI:
    """Get LLM instance based on config, optionally overridden by runtime params"""
    return ChatOpenAI(
        model=model_name or settings.llm_model,
        api_key=api_key or settings.llm_api_key,
        base_url=base_url or settings.llm_base_url,
        temperature=temperature or settings.llm_temperature,
    )