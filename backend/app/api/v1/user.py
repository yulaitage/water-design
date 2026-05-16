from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.user import UserProfile
from app.schemas.user import UserProfileResponse, UserProfileUpdate

router = APIRouter(prefix="/user", tags=["user"])


async def _get_or_create_profile(db: AsyncSession) -> UserProfile:
    stmt = select(UserProfile).limit(1)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        profile = UserProfile(
            name="张工程师",
            email="yulaitage@gmail.com",
            avatar_initial="张",
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    return profile


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(db: AsyncSession = Depends(get_db)):
    profile = await _get_or_create_profile(db)
    return UserProfileResponse.model_validate(profile)


@router.put("/profile", response_model=UserProfileResponse)
async def update_profile(
    request: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_or_create_profile(db)

    if request.name is not None:
        profile.name = request.name
    if request.email is not None:
        profile.email = request.email
    if request.avatar_initial is not None:
        profile.avatar_initial = request.avatar_initial

    await db.commit()
    await db.refresh(profile)
    return UserProfileResponse.model_validate(profile)
