from langchain_openai import ChatOpenAI
from app.config import settings
from typing import Optional


def get_llm(
    temperature: float | None = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: int = 300,  # 默认5分钟超时
) -> ChatOpenAI:
    """Get LLM instance based on config, optionally overridden by runtime params"""
    # If frontend passes model_name like "glm-4-flash", check if it's actually configured
    # Otherwise use the configured model
    actual_model = model_name or settings.llm_model
    actual_api_key = api_key or settings.llm_api_key
    actual_base_url = base_url or settings.llm_base_url

    # Map common model aliases to actual models
    model_mapping = {
        "glm-4-flash": "MiniMax-M2.7",
        "glm-4": "MiniMax-M2.7",
        "glm-4-plus": "MiniMax-M2.7",
        "gpt-4o": "MiniMax-M2.7",
        "gpt-4o-mini": "MiniMax-M2.7",
    }
    if actual_model in model_mapping:
        actual_model = model_mapping[actual_model]

    return ChatOpenAI(
        model=actual_model,
        api_key=actual_api_key,
        base_url=actual_base_url,
        temperature=temperature or settings.llm_temperature,
        timeout=timeout,
    )