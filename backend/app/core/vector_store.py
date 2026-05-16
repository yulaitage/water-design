import uuid
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.specification import Specification
from app.models.case import Case
from app.models.wiki import WikiItem
from app.models.document import Document, DocumentChunk

logger = logging.getLogger(__name__)


class VectorStoreService:
    def __init__(
        self,
        db: AsyncSession,
        embedding_model: Optional[str] = None,
        embedding_api_key: Optional[str] = None,
        embedding_base_url: Optional[str] = None,
    ):
        self.db = db
        self.embedding_model = embedding_model
        self.embedding_api_key = embedding_api_key
        self.embedding_base_url = embedding_base_url
        self._embeddings = None

    def _get_embeddings(self):
        if self._embeddings is None:
            from app.core.embeddings import get_embeddings
            self._embeddings = get_embeddings(
                model=self.embedding_model,
                api_key=self.embedding_api_key,
                base_url=self.embedding_base_url,
            )
        return self._embeddings

    async def embed_text(self, text: str) -> List[float]:
        try:
            embeddings = self._get_embeddings()
            truncated = text[:5000] if len(text) > 5000 else text
            result = await embeddings.aembed_query(truncated)
            return result if result else []
        except Exception as e:
            logger.warning("Embedding failed: %s", e)
            return []

    async def embed_texts_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch embed multiple texts, splitting into max 64 per API call."""
        BATCH_SIZE = 64
        results: List[List[float]] = []
        try:
            embeddings = self._get_embeddings()
            for i in range(0, len(texts), BATCH_SIZE):
                batch = texts[i:i + BATCH_SIZE]
                truncated = [t[:5000] if len(t) > 5000 else t for t in batch]
                batch_results = await embeddings.aembed_documents(truncated)
                results.extend(batch_results)
            return results
        except Exception as e:
            logger.warning("Batch embedding failed: %s", e)
            return [[] for _ in texts]

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

        items = [(spec, spec.content) for spec in specs if spec.content]
        if not items:
            return 0

        texts = [content for _, content in items]
        all_embeddings = await self.embed_texts_batch(texts)

        count = 0
        for (spec, _), emb in zip(items, all_embeddings):
            if emb:
                spec.content_embedding = emb
                count += 1

        if count > 0:
            await self.db.commit()
        return count

    async def batch_store_case_embeddings(self) -> int:
        stmt = select(Case).where(Case.summary_embedding.is_(None))
        result = await self.db.execute(stmt)
        cases = result.scalars().all()

        items = [(case, case.summary) for case in cases if case.summary]
        if not items:
            return 0

        texts = [summary for _, summary in items]
        all_embeddings = await self.embed_texts_batch(texts)

        count = 0
        for (case, _), emb in zip(items, all_embeddings):
            if emb:
                case.summary_embedding = emb
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

        try:
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
        except Exception as e:
            logger.warning("Vector specification search failed: %s", e)
            try:
                await self.db.rollback()
            except Exception:
                pass
            return []

    async def search_similar_cases(
        self, query: str, top_k: int = 5, project_type: Optional[str] = None
    ) -> List[dict]:
        query_embedding = await self.embed_text(query)
        if not query_embedding:
            return []

        try:
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
        except Exception as e:
            logger.warning("Vector case search failed: %s", e)
            try:
                await self.db.rollback()
            except Exception:
                pass
            return []

    async def store_wiki_item_embedding(self, wiki_id: uuid.UUID) -> None:
        stmt = select(WikiItem).where(WikiItem.id == wiki_id)
        result = await self.db.execute(stmt)
        item = result.scalar_one_or_none()
        if not item or not item.content:
            return

        embedding = await self.embed_text(item.content)
        if embedding:
            item.content_embedding = embedding
            await self.db.commit()

    async def search_wiki_items(
        self, query: str, top_k: int = 10, project_type: Optional[str] = None
    ) -> List[dict]:
        query_embedding = await self.embed_text(query)
        if not query_embedding:
            return []

        try:
            conditions = ["content_embedding IS NOT NULL"]
            params: dict = {"query_embedding": str(query_embedding), "limit": top_k}

            if project_type:
                conditions.append("project_types @> ARRAY[:project_type]::varchar[]")
                params["project_type"] = project_type

            where_clause = " AND ".join(conditions)

            sql = text(f"""
                SELECT id, title, category, content, source_chapter, tags, project_types,
                       1 - (content_embedding <=> :query_embedding::vector) as similarity
                FROM wiki_items
                WHERE {where_clause}
                ORDER BY content_embedding <=> :query_embedding::vector
                LIMIT :limit
            """)

            result = await self.db.execute(sql, params)
            rows = result.fetchall()

            return [
                {
                    "id": str(row.id),
                    "title": row.title,
                    "category": row.category,
                    "content": row.content,
                    "source_chapter": row.source_chapter,
                    "tags": row.tags,
                    "project_types": row.project_types,
                    "similarity": float(row.similarity),
                    "wiki_item_id": str(row.id),
                }
                for row in rows
            ]
        except Exception as e:
            logger.warning("Vector wiki search failed: %s", e)
            try:
                await self.db.rollback()
            except Exception:
                pass
            return []

    async def store_document_embedding(self, doc_id: uuid.UUID) -> None:
        stmt = select(Document).where(Document.id == doc_id)
        result = await self.db.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc or not doc.full_text:
            return

        embedding = await self.embed_text(doc.full_text[:5000])
        if embedding:
            doc.text_embedding = embedding
            await self.db.commit()

    async def store_chunk_embeddings(self, document_id: uuid.UUID) -> int:
        """Store embeddings for all chunks of a document using batch API (flush only, caller handles commit)"""
        stmt = select(DocumentChunk).where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.embedding.is_(None)
        )
        result = await self.db.execute(stmt)
        chunks = result.scalars().all()

        embeddable = [(c, c.text) for c in chunks if c.text]
        if not embeddable:
            return 0

        texts = [t for _, t in embeddable]
        all_embeddings = await self.embed_texts_batch(texts)

        count = 0
        for (chunk, _), emb in zip(embeddable, all_embeddings):
            if emb:
                chunk.embedding = emb
                count += 1

        if count > 0:
            await self.db.flush()
        return count

    async def search_documents(
        self, query: str, top_k: int = 5, project_type: Optional[str] = None, category: Optional[str] = None
    ) -> List[dict]:
        params: dict = {"query": f"%{query}%", "limit": top_k}

        conditions = []
        if category is not None:
            conditions.append("category = :category")
            params["category"] = category

        if project_type:
            conditions.append("project_type = :project_type")
            params["project_type"] = project_type

        text_conditions = conditions.copy() if conditions else []
        text_conditions.append("(filename ILIKE :query OR title ILIKE :query OR full_text ILIKE :query)")
        text_where = " AND ".join(text_conditions)

        check_sql = text("SELECT COUNT(*) FROM documents WHERE text_embedding IS NOT NULL")
        result = await self.db.execute(check_sql)
        has_embeddings = result.scalar() > 0

        if has_embeddings:
            try:
                query_embedding = await self.embed_text(query)
                if query_embedding:
                    vector_conditions = ["text_embedding IS NOT NULL"] + conditions
                    vector_where = " AND ".join(vector_conditions)
                    params["query_embedding"] = str(query_embedding)

                    sql = text(f"""
                        SELECT id, filename, title, category, project_type, full_text,
                               1 - (text_embedding <=> :query_embedding::vector) as similarity
                        FROM documents
                        WHERE {vector_where}
                        ORDER BY text_embedding <=> :query_embedding::vector
                        LIMIT :limit
                    """)

                    result = await self.db.execute(sql, params)
                    rows = result.fetchall()

                    if rows:
                        return [
                            {
                                "id": str(row.id),
                                "filename": row.filename,
                                "title": row.title,
                                "category": row.category,
                                "project_type": row.project_type,
                                "content": row.full_text,
                                "similarity": float(row.similarity),
                                "source": "document",
                            }
                            for row in rows
                        ]
            except Exception as e:
                logger.warning("Vector search failed, falling back to text search: %s", e)
                try:
                    await self.db.rollback()
                except Exception:
                    pass

        sql = text(f"""
            SELECT id, filename, title, category, project_type, full_text,
                   0.5 as similarity
            FROM documents
            WHERE {text_where}
            ORDER BY created_at DESC
            LIMIT :limit
        """)

        result = await self.db.execute(sql, params)
        rows = result.fetchall()

        return [
            {
                "id": str(row.id),
                "filename": row.filename,
                "title": row.title,
                "category": row.category,
                "project_type": row.project_type,
                "content": row.full_text,
                "similarity": float(row.similarity),
                "source": "document",
            }
            for row in rows
        ]

    async def search_document_chunks(
        self, query: str, document_id: Optional[uuid.UUID] = None, top_k: int = 10
    ) -> List[dict]:
        params: dict = {"query": f"%{query}%", "limit": top_k}

        if document_id:
            params["document_id"] = str(document_id)

        conditions = ["d.category = :category"] if not document_id else ["dc.document_id = :document_id"]
        params["category"] = "case"

        query_embedding = await self.embed_text(query)
        if query_embedding:
            try:
                vector_conditions = ["dc.embedding IS NOT NULL"] + conditions
                params["query_embedding"] = str(query_embedding)
                where_clause = " AND ".join(vector_conditions)

                sql = text(f"""
                    SELECT dc.id, dc.document_id, dc.chunk_index, dc.text, dc.page, dc.chunk_type,
                           dc.image_path, dc.image_description,
                           d.filename, d.title as doc_title,
                           1 - (dc.embedding <=> :query_embedding::vector) as similarity
                    FROM document_chunks dc
                    JOIN documents d ON dc.document_id = d.id
                    WHERE {where_clause}
                    ORDER BY dc.embedding <=> :query_embedding::vector
                    LIMIT :limit
                """)

                result = await self.db.execute(sql, params)
                rows = result.fetchall()

                if rows:
                    return [
                        {
                            "id": str(row.id),
                            "document_id": str(row.document_id),
                            "chunk_index": row.chunk_index,
                            "text": row.text,
                            "page": row.page,
                            "chunk_type": row.chunk_type,
                            "image_path": row.image_path,
                            "image_description": row.image_description,
                            "filename": row.filename,
                            "doc_title": row.doc_title,
                            "similarity": float(row.similarity),
                            "source": "document_chunk",
                        }
                        for row in rows
                    ]
            except Exception as e:
                logger.warning("Vector chunk search failed, falling back to text: %s", e)
                try:
                    await self.db.rollback()
                except Exception:
                    pass

        text_conditions = ["d.category = :category"] if not document_id else ["dc.document_id = :document_id"]
        text_conditions.append("(dc.text ILIKE :query OR d.title ILIKE :query OR d.filename ILIKE :query)")
        where_clause = " AND ".join(text_conditions)

        sql = text(f"""
            SELECT dc.id, dc.document_id, dc.chunk_index, dc.text, dc.page, dc.chunk_type,
                   dc.image_path, dc.image_description,
                   d.filename, d.title as doc_title,
                   0.5 as similarity
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE {where_clause}
            ORDER BY dc.chunk_index
            LIMIT :limit
        """)

        result = await self.db.execute(sql, params)
        rows = result.fetchall()

        return [
            {
                "id": str(row.id),
                "document_id": str(row.document_id),
                "chunk_index": row.chunk_index,
                "text": row.text,
                "page": row.page,
                "chunk_type": row.chunk_type,
                "image_path": row.image_path,
                "image_description": row.image_description,
                "filename": row.filename,
                "doc_title": row.doc_title,
                "similarity": float(row.similarity),
                "source": "document_chunk",
            }
            for row in rows
        ]
