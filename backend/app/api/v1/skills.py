import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.skill_execution_service import SkillManager
from app.services.skill_learning_service import SkillLearningService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills", tags=["skills"])


class SkillResponse(BaseModel):
    id: str
    name: str
    description: str
    trigger_patterns: List[str]
    parameters: List[dict]
    solution_steps: List[dict]
    success_rate: float
    usage_count: int
    is_verified: bool
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class SkillExecutionLogResponse(BaseModel):
    id: str
    query: str
    matched_pattern: Optional[str]
    execution_result: Optional[str]
    success: bool
    feedback: Optional[str]
    execution_time_ms: int
    created_at: Optional[str] = None


class VerifySkillRequest(BaseModel):
    verified: bool


@router.get("/", response_model=List[SkillResponse])
async def list_skills(
    verified_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取所有已学习的技能"""
    manager = SkillManager(db)
    skills = await manager.get_all_skills(verified_only=verified_only)
    return [
        SkillResponse(
            id=str(s.id),
            name=s.name,
            description=s.description,
            trigger_patterns=s.trigger_patterns or [],
            parameters=s.parameters or [],
            solution_steps=s.solution_steps or [],
            success_rate=s.success_rate,
            usage_count=s.usage_count,
            is_verified=s.is_verified,
            created_at=s.created_at.isoformat() if s.created_at else None,
        )
        for s in skills[skip:skip+limit]
    ]


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取单个技能详情"""
    from app.models.skill import Skill
    from sqlalchemy import select

    stmt = select(Skill).where(Skill.id == skill_id)
    result = await db.execute(stmt)
    skill = result.scalar_one_or_none()

    if not skill:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Skill not found")

    return SkillResponse(
        id=str(skill.id),
        name=skill.name,
        description=skill.description,
        trigger_patterns=skill.trigger_patterns or [],
        parameters=skill.parameters or [],
        solution_steps=skill.solution_steps or [],
        success_rate=skill.success_rate,
        usage_count=skill.usage_count,
        is_verified=skill.is_verified,
        created_at=skill.created_at.isoformat() if skill.created_at else None,
    )


@router.post("/{skill_id}/verify")
async def verify_skill(
    skill_id: UUID,
    request: VerifySkillRequest,
    db: AsyncSession = Depends(get_db),
):
    """验证/取消验证技能"""
    from app.models.skill import Skill
    from sqlalchemy import select

    stmt = select(Skill).where(Skill.id == skill_id)
    result = await db.execute(stmt)
    skill = result.scalar_one_or_none()

    if not skill:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Skill not found")

    skill.is_verified = request.verified
    await db.commit()

    return {"status": "success", "verified": skill.is_verified}


@router.get("/{skill_id}/logs", response_model=List[SkillExecutionLogResponse])
async def get_skill_execution_logs(
    skill_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取技能执行历史"""
    from app.models.skill import SkillExecutionLog
    from sqlalchemy import select

    stmt = (
        select(SkillExecutionLog)
        .where(SkillExecutionLog.skill_id == skill_id)
        .order_by(SkillExecutionLog.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    logs = result.scalars().all()

    return [
        SkillExecutionLogResponse(
            id=str(log.id),
            query=log.query,
            matched_pattern=log.matched_pattern,
            execution_result=log.execution_result,
            success=log.success,
            feedback=log.feedback,
            execution_time_ms=log.execution_time_ms,
            created_at=log.created_at.isoformat() if log.created_at else None,
        )
        for log in logs
    ]


@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """删除技能"""
    from app.models.skill import Skill, SkillExecutionLog
    from sqlalchemy import select, delete

    # 删除执行日志
    stmt = delete(SkillExecutionLog).where(SkillExecutionLog.skill_id == skill_id)
    await db.execute(stmt)

    # 删除技能
    stmt = delete(Skill).where(Skill.id == skill_id)
    result = await db.execute(stmt)

    if result.rowcount == 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Skill not found")

    await db.commit()
    return {"status": "success"}