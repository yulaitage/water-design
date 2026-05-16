from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class UserProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=200)
    avatar_initial: Optional[str] = Field(None, max_length=1)


class UserProfileResponse(BaseModel):
    id: UUID
    name: str
    email: str
    avatar_initial: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
