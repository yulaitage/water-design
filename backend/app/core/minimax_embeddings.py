"""MiniMax Embeddings wrapper — MiniMax uses a non-OpenAI-compatible embeddings API.

The API expects: {"model": "...", "texts": [...], "type": "query"|"document"}
Response: {"vectors": [[...]], ...}

This wrapper adapts it to the langchain embeddings interface.
"""
from typing import List, Optional
import logging

import requests
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)


class MiniMaxEmbeddings(Embeddings):
    """Langchain-compatible embeddings wrapper for MiniMax API."""

    def __init__(
        self,
        model: str = "embo-01",
        api_key: Optional[str] = None,
        base_url: str = "https://api.minimaxi.com/v1",
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._call_api(texts, "document")

    def embed_query(self, text: str) -> List[float]:
        vectors = self._call_api([text], "query")
        return vectors[0] if vectors else []

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> List[float]:
        return self.embed_query(text)

    def _call_api(self, texts: List[str], emb_type: str) -> List[List[float]]:
        url = f"{self.base_url}/embeddings"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "texts": texts,
            "type": emb_type,
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            data = resp.json()

            # Check for MiniMax error
            base_resp = data.get("base_resp", {})
            if base_resp.get("status_code") != 0:
                logger.error(
                    "MiniMax embeddings error: %s (code=%s)",
                    base_resp.get("status_msg", "unknown"),
                    base_resp.get("status_code"),
                )
                return []

            vectors = data.get("vectors")
            if vectors is None:
                logger.warning("MiniMax embeddings returned no vectors: %s", data)
                return []

            return vectors
        except Exception as e:
            logger.error("MiniMax embeddings request failed: %s", e)
            return []
