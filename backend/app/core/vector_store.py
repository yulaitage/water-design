import uuid
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.specification import Specification
from app.models.case import Case

logger = logging.getLogger(__name__)


class VectorStoreService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def embed_text(self, text: str) -> List[float]:
        from app.core.embeddings import get_embeddings
        embeddings = get_embeddings()
        result = await embeddings.aembed_query(text)
        return result[0] if result and len(result) > 0 else []

    async def store_specification_embedding(self, spec_id: uuid.UUID) -> None:
        stmt = select(Specification).where(Specification.id == spec_id)
        result = await self.db.execute(stmt)
        spec = result.scalar_one_or_none()
        if not spec or not spec.content:
            return

        embedding = await self.embed_text(spec.content)
        if embedding:
            spec.content_embedding = embedding
            await self.db.commit()

    async def store_case_embedding(self, case_id: uuid.UUID) -> None:
        stmt = select(Case).where(Case.id == case_id)
        result = await self.db.execute(stmt)
        case = result.scalar_one_or_none()
        if not case or not case.summary:
            return

        embedding = await self.embed_text(case.summary)
        if embedding:
            case.summary_embedding = embedding
            await self.db.commit()

    async def batch_store_specification_embeddings(self) -> int:
        stmt = select(Specification).where(Specification.content_embedding.is_(None))
        result = await self.db.execute(stmt)
        specs = result.scalars().all()

        count = 0
        for spec in specs:
            if spec.content:
                embedding = await self.embed_text(spec.content)
                if embedding:
                    spec.content_embedding = embedding
                    count += 1

        if count > 0:
            await self.db.commit()
        return count

    async def batch_store_case_embeddings(self) -> int:
        stmt = select(Case).where(Case.summary_embedding.is_(None))
        result = await self.db.execute(stmt)
        cases = result.scalars().all()

        count = 0
        for case in cases:
            if case.summary:
                embedding = await self.embed_text(case.summary)
                if embedding:
                    case.summary_embedding = embedding
                    count += 1

        if count > 0:
            await self.db.commit()
        return count

    async def search_similar_specifications(
        self, query: str, top_k: int = 5, project_type: Optional[str] = None
    ) -> List[dict]:
        query_embedding = await self.embed_text(query)
        if not query_embedding:
            return []

        conditions = ["content_embedding IS NOT NULL"]
        params: dict = {"query_embedding": str(query_embedding), "limit": top_k}

        if project_type:
            conditions.append("project_types @> ARRAY[:project_type]::varchar[]")
            params["project_type"] = project_type

        where_clause = " AND ".join(conditions)

        sql = text(f"""
            SELECT id, name, code, chapter, section, content, project_types,
                   1 - (content_embedding <=> :query_embedding::vector) as similarity
            FROM specifications
            WHERE {where_clause}
            ORDER BY content_embedding <=> :query_embedding::vector
            LIMIT :limit
        """)

        result = await self.db.execute(sql, params)
        rows = result.fetchall()

        return [
            {
                "id": str(row.id),
                "name": row.name,
                "code": row.code,
                "chapter": row.chapter,
                "section": row.section,
                "content": row.content,
                "project_types": row.project_types,
                "similarity": float(row.similarity),
                "source": "specification",
            }
            for row in rows
        ]

    async def search_similar_cases(
        self, query: str, top_k: int = 5, project_type: Optional[str] = None
    ) -> List[dict]:
        query_embedding = await self.embed_text(query)
        if not query_embedding:
            return []

        conditions = ["summary_embedding IS NOT NULL"]
        params: dict = {"query_embedding": str(query_embedding), "limit": top_k}

        if project_type:
            conditions.append("project_type = :project_type")
            params["project_type"] = project_type

        where_clause = " AND ".join(conditions)

        sql = text(f"""
            SELECT id, name, project_type, location, owner, summary, design_params,
                   1 - (summary_embedding <=> :query_embedding::vector) as similarity
            FROM cases
            WHERE {where_clause}
            ORDER BY summary_embedding <=> :query_embedding::vector
            LIMIT :limit
        """)

        result = await self.db.execute(sql, params)
        rows = result.fetchall()

        return [
            {
                "id": str(row.id),
                "name": row.name,
                "project_type": row.project_type,
                "location": row.location,
                "owner": row.owner,
                "summary": row.summary,
                "design_params": row.design_params,
                "similarity": float(row.similarity),
                "source": "case",
            }
            for row in rows
        ]
