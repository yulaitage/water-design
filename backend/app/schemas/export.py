from pydantic import BaseModel
from typing import List, Optional, Any


class ParameterItem(BaseModel):
    id: str
    label: str
    value: Any
    unit: Optional[str] = None
    description: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ExportReportRequest(BaseModel):
    projectName: Optional[str] = None
    params: List[ParameterItem] = []
    messages: List[ChatMessage] = []


class ExportAnalysisRequest(BaseModel):
    params: List[ParameterItem] = []


class CalculationRequest(BaseModel):
    params: List[ParameterItem] = []
    category: Optional[str] = None


class CalculationResponse(BaseModel):
    status: str
    notices: List[str] = []
    warnings: List[str] = []