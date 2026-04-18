from langchain_openai import ChatOpenAI
from app.config import settings


def get_llm(temperature: float | None = None) -> ChatOpenAI:
    """Get LLM instance based on config"""
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=temperature or settings.llm_temperature,
    )
