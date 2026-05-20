from pydantic import BaseModel, ConfigDict
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
    project_id: Optional[UUID] = None  # Optional for backward compatibility
    project_id_str: Optional[str] = None  # For frontend string IDs like "1"
    message: str
    context: Optional[Dict[str, Any]] = None
    # AI Model Config from frontend
    model_type: Optional[str] = None  # 'gemini', 'openai', 'local'
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    # Embedding Config from frontend
    embedding_model: Optional[str] = None
    embedding_api_key: Optional[str] = None
    embedding_base_url: Optional[str] = None
    # Vision Config from frontend
    vision_model: Optional[str] = None
    vision_api_key: Optional[str] = None
    vision_base_url: Optional[str] = None


class ChatResponse(BaseModel):
    """对话响应"""
    conversation_id: UUID
    message: str  # 对话消息（讨论内容，不含报告正文）
    intent: str    # 意图标签，如 "REPORT_GENERATE"
    tool_calls: Optional[List[Dict[str, Any]]] = None
    context: Optional[Dict[str, Any]] = None
    # 报告相关字段
    report_id: Optional[str] = None   # 报告任务ID
    report_content: Optional[str] = None  # 报告内容（Markdown）


class ConversationHistoryResponse(BaseModel):
    """对话历史响应"""
    id: UUID
    project_id: UUID
    messages: List[Message]
    context: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)