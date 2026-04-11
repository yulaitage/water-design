from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID
from datetime import datetime


class ProjectInfo(BaseModel):
    name: str
    location: str
    owner: str
    scale: str
    description: str


class ReportCreateRequest(BaseModel):
    report_type: Literal["feasibility", "preliminary_design"]
    project_info: ProjectInfo


class ReportTaskResponse(BaseModel):
    task_id: UUID
    status: str
    report_type: str
    version: int = 1


class ReportStatusResponse(BaseModel):
    task_id: UUID
    status: str
    progress: int = Field(ge=0, le=100)
    current_chapter: Optional[str] = None
    version: int
    error: Optional[str] = None


class FormRevisionInput(BaseModel):
    chapters: List[str]
    modification_type: Literal["补充", "修改", "删除"]
    description: str


class NaturalLanguageRevisionInput(BaseModel):
    content: str


class RevisionRequest(BaseModel):
    revision_type: Literal["form", "natural_language"]
    chapters: Optional[List[str]] = None
    modification_type: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None


class RevisionResponse(BaseModel):
    revision_id: UUID
    version: int
    status: str


class RevisionHistoryItem(BaseModel):
    version: int
    created_at: datetime
    revision_type: Optional[str] = None
    user_input: Optional[str] = None


class RevisionHistoryResponse(BaseModel):
    revisions: List[RevisionHistoryItem]