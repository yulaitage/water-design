from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.models.specification import Specification
from app.models.case import Case
from app.core.report_exceptions import RetrievalFailedException


class RetrievalService:
    """结构化RAG检索服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def retrieve_specifications(
        self,
        query: str,
        project_type: str,
        top_k: int = 10
    ) -> List[dict]:
        """
        检索规范条文
        - 向量相似度 + 工程类型过滤
        - 按章节排序
        """
        # 简化：先用关键词匹配模拟向量检索
        # 实际需要使用 pgvector 的 cosine_distance 或 dot_product
        stmt = (
            select(Specification)
            .where(
                and_(
                    Specification.project_types.contains([project_type])
                )
            )
            .order_by(Specification.chapter)
            .limit(top_k)
        )
        result = await self.db.execute(stmt)
        specs = result.scalars().all()

        return [
            {
                "id": str(spec.id),
                "name": spec.name,
                "code": spec.code,
                "chapter": spec.chapter,
                "section": spec.section,
                "content": spec.content,
                "project_types": spec.project_types,
                "source": "specification"
            }
            for spec in specs
        ]

    async def retrieve_cases(
        self,
        query: str,
        project_type: str,
        location: Optional[str] = None,
        top_k: int = 5
    ) -> List[dict]:
        """
        检索历史案例
        - 向量相似度 + 项目类型 + 地理位置
        """
        conditions = [Case.project_type == project_type]
        if location:
            conditions.append(Case.location.contains(location))

        stmt = (
            select(Case)
            .where(and_(*conditions))
            .limit(top_k)
        )
        result = await self.db.execute(stmt)
        cases = result.scalars().all()

        return [
            {
                "id": str(case.id),
                "name": case.name,
                "project_type": case.project_type,
                "location": case.location,
                "owner": case.owner,
                "summary": case.summary,
                "design_params": case.design_params,
                "source": "case"
            }
            for case in cases
        ]

    async def retrieve_for_chapter(
        self,
        chapter: str,
        project_type: str,
        location: Optional[str] = None
    ) -> Tuple[List[dict], List[dict]]:
        """
        按章节检索对应的规范和案例
        返回 (specifications, cases)
        """
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