import uuid
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.chat_service import ChatService
from app.schemas.chat import ChatRequest, ChatResponse, ConversationHistoryResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    发送对话消息

    支持多轮对话，自动识别意图并调用对应工具
    """
    service = ChatService(db)
    return await service.chat(request)


@router.get("/projects/{project_id}/conversations", response_model=list[ConversationHistoryResponse])
async def get_conversation_history(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """获取项目对话历史"""
    service = ChatService(db)
    return await service.get_history(project_id, limit=limit, offset=offset)