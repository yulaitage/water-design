from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.vector_store import VectorStoreService


class RetrievalService:
    """RAG 检索服务 - 基于 pgvector 语义搜索"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.vector_store = VectorStoreService(db)

    async def retrieve_specifications(
        self,
        query: str,
        project_type: str,
        top_k: int = 10
    ) -> List[dict]:
        """检索规范条文 - 使用 pgvector 语义搜索"""
        return await self.vector_store.search_similar_specifications(
            query=query,
            top_k=top_k,
            project_type=project_type
        )

    async def retrieve_cases(
        self,
        query: str,
        project_type: str,
        location: Optional[str] = None,
        top_k: int = 5
    ) -> List[dict]:
        """检索历史案例 - 使用 pgvector 语义搜索"""
        results = await self.vector_store.search_similar_cases(
            query=query,
            top_k=top_k,
            project_type=project_type
        )

        if location:
            results = [
                r for r in results
                if location in r.get("location", "")
            ]

        return results

    async def retrieve_for_chapter(
        self,
        chapter: str,
        project_type: str,
        location: Optional[str] = None
    ) -> Tuple[List[dict], List[dict]]:
        """按章节检索对应的规范和案例"""
        specs = await self.retrieve_specifications(
            query=chapter,
            project_type=project_type,
            top_k=5
        )

        cases = await self.retrieve_cases(
            query=chapter,
            project_type=project_type,
            location=location,
            top_k=3
        )

        return specs, cases
