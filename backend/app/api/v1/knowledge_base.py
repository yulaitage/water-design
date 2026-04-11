import uuid
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.knowledge_base import (
    SpecificationIngestRequest,
    CaseIngestRequest,
    RetrievalResult
)

router = APIRouter(prefix="/knowledge-base", tags=["knowledge_base"])


@router.post("/specifications")
async def ingest_specification(
    request: SpecificationIngestRequest,
    db: AsyncSession = Depends(get_db)
):
    """导入规范条文"""
    from app.models.specification import Specification

    spec = Specification(
        name=request.name,
        code=request.code,
        chapter=request.chapter,
        section=request.section,
        content=request.content,
        project_types=request.project_types
    )
    db.add(spec)
    await db.commit()
    await db.refresh(spec)

    return {"id": str(spec.id), "status": "created"}


@router.post("/cases")
async def ingest_case(
    request: CaseIngestRequest,
    db: AsyncSession = Depends(get_db)
):
    """导入历史案例"""
    from app.models.case import Case

    case = Case(
        name=request.name,
        project_type=request.project_type,
        location=request.location,
        owner=request.owner,
        report_content=request.report_content,
        design_params=request.design_params
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)

    return {"id": str(case.id), "status": "created"}


@router.get("/specifications", response_model=list[RetrievalResult])
async def list_specifications(
    db: AsyncSession = Depends(get_db)
):
    """列出所有规范条文"""
    from app.models.specification import Specification
    from sqlalchemy import select

    stmt = select(Specification)
    result = await db.execute(stmt)
    specs = result.scalars().all()

    return [
        RetrievalResult(
            source="specification",
            title=f"{spec.code} {spec.name}",
            content=spec.content[:500],
            relevance_score=1.0,
            metadata={"chapter": spec.chapter, "section": spec.section}
        )
        for spec in specs
    ]


@router.get("/cases", response_model=list[RetrievalResult])
async def list_cases(
    db: AsyncSession = Depends(get_db)
):
    """列出所有历史案例"""
    from app.models.case import Case
    from sqlalchemy import select

    stmt = select(Case)
    result = await db.execute(stmt)
    cases = result.scalars().all()

    return [
        RetrievalResult(
            source="case",
            title=case.name,
            content=case.summary or "",
            relevance_score=1.0,
            metadata={"project_type": case.project_type, "location": case.location}
        )
        for case in cases
    ]