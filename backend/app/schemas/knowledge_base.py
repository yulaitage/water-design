from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID


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
    report_content: str  # Markdown格式
    design_params: dict = {}


class RetrievalResult(BaseModel):
    source: str  # "specification" | "case"
    title: str
    content: str
    relevance_score: float
    metadata: dict