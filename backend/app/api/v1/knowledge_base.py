import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.schemas.knowledge_base import (
    SpecificationIngestRequest,
    CaseIngestRequest,
    SpecificationResponse,
    CaseResponse,
    RetrievalResult,
)
from app.core.vector_store import VectorStoreService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-base", tags=["knowledge_base"])


@router.post("/specifications", response_model=SpecificationResponse, status_code=201)
async def ingest_specification(
    request: SpecificationIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.models.specification import Specification

    spec = Specification(
        name=request.name,
        code=request.code,
        chapter=request.chapter,
        section=request.section,
        content=request.content,
        project_types=request.project_types,
    )
    db.add(spec)
    await db.commit()
    await db.refresh(spec)

    try:
        vector_service = VectorStoreService(db)
        await vector_service.store_specification_embedding(spec.id)
    except Exception as e:
        logger.warning("Failed to generate specification embedding: %s", e)

    return SpecificationResponse.model_validate(spec)


@router.post("/cases", response_model=CaseResponse, status_code=201)
async def ingest_case(
    request: CaseIngestRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.models.case import Case

    case = Case(
        name=request.name,
        project_type=request.project_type,
        location=request.location,
        owner=request.owner,
        summary=request.summary,
        design_params=request.design_params,
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)

    try:
        vector_service = VectorStoreService(db)
        await vector_service.store_case_embedding(case.id)
    except Exception as e:
        logger.warning("Failed to generate case embedding: %s", e)

    return CaseResponse.model_validate(case)


@router.get("/specifications", response_model=List[SpecificationResponse])
async def list_specifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    from app.models.specification import Specification

    stmt = select(Specification).offset(skip).limit(limit).order_by(Specification.created_at.desc())
    result = await db.execute(stmt)
    specs = result.scalars().all()
    return [SpecificationResponse.model_validate(s) for s in specs]


@router.get("/cases", response_model=List[CaseResponse])
async def list_cases(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    from app.models.case import Case

    stmt = select(Case).offset(skip).limit(limit).order_by(Case.created_at.desc())
    result = await db.execute(stmt)
    cases = result.scalars().all()
    return [CaseResponse.model_validate(c) for c in cases]


@router.get("/search", response_model=List[RetrievalResult])
async def search_knowledge(
    query: str = Query(..., min_length=1),
    project_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    vector_service = VectorStoreService(db)
    specs = await vector_service.search_similar_specifications(
        query=query, top_k=5, project_type=project_type
    )
    cases = await vector_service.search_similar_cases(
        query=query, top_k=5, project_type=project_type
    )
    results = []
    for s in specs:
        results.append(RetrievalResult(
            source="specification",
            title=f"{s['code']} {s['name']}",
            content=s["content"][:500],
            relevance_score=s["similarity"],
            metadata={"chapter": s["chapter"], "section": s.get("section", "")},
        ))
    for c in cases:
        results.append(RetrievalResult(
            source="case",
            title=c["name"],
            content=c.get("summary", ""),
            relevance_score=c["similarity"],
            metadata={"project_type": c["project_type"], "location": c["location"]},
        ))
    results.sort(key=lambda r: r.relevance_score, reverse=True)
    return results
