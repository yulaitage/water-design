from langchain_openai import OpenAIEmbeddings
from app.config import settings


def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.embedding_api_key or settings.llm_api_key,
        base_url=settings.embedding_base_url or settings.llm_base_url,
    )
