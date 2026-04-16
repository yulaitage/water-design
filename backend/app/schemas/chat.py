from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID
from datetime import datetime


class Message(BaseModel):
    """对话消息"""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: Optional[datetime] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatRequest(BaseModel):
    """对话请求"""
    project_id: UUID
    message: str
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    """对话响应"""
    conversation_id: UUID
    message: str
    intent: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    context: Optional[Dict[str, Any]] = None


class ConversationHistoryResponse(BaseModel):
    """对话历史响应"""
    id: UUID
    project_id: UUID
    messages: List[Message]
    context: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True