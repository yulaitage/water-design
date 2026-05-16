from typing import Optional, Tuple

from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings
from app.config import settings

_embeddings_cache: dict[Tuple, Embeddings] = {}


def get_embeddings(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Embeddings:
    effective_base_url = base_url or settings.embedding_base_url or settings.llm_base_url or ""
    effective_api_key = api_key or settings.embedding_api_key or settings.llm_api_key or ""
    model_name = model or settings.embedding_model

    cache_key = (model_name, effective_api_key, effective_base_url)
    if cache_key in _embeddings_cache:
        return _embeddings_cache[cache_key]

    if "minimax" in effective_base_url.lower():
        from app.core.minimax_embeddings import MiniMaxEmbeddings
        instance = MiniMaxEmbeddings(
            model=model_name,
            api_key=effective_api_key,
            base_url=effective_base_url,
        )
    else:
        instance = OpenAIEmbeddings(
            model=model_name,
            api_key=effective_api_key,
            base_url=effective_base_url,
            check_embedding_ctx_length=False,
            request_timeout=30,
        )

    _embeddings_cache[cache_key] = instance
    return instance
