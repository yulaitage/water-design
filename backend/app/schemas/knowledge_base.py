from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class SpecificationIngestRequest(BaseModel):
    name: str
    code: str
    chapter: str
    section: Optional[str] = None
    content: str
    project_types: List[str] = []


class CaseIngestRequest(BaseModel):
    name: str
    project_type: str
    location: str
    owner: str
    summary: str
    design_params: dict = {}


class SpecificationResponse(BaseModel):
    id: UUID
    name: str
    code: str
    chapter: str
    section: Optional[str] = None
    content: str
    project_types: List[str] = []
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CaseResponse(BaseModel):
    id: UUID
    name: str
    project_type: str
    location: str
    owner: str
    summary: str
    design_params: dict = {}
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RetrievalResult(BaseModel):
    source: str
    title: str
    content: str
    relevance_score: float
    metadata: dict
