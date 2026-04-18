import logging
import json
import uuid

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.chat_service import ChatService
from app.services.memory_service import MemoryService
from app.schemas.chat import ChatRequest, ChatResponse, ConversationHistoryResponse


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    stream: bool = Query(False, description="是否使用流式响应"),
):
    """发送对话消息，支持多轮对话和工具调用"""
    if stream:
        return StreamingResponse(
            _stream_chat(db, request),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    service = ChatService(db)
    return await service.chat(request)


async def _stream_chat(db: AsyncSession, request: ChatRequest):
    """SSE 流式对话"""
    from app.core.llm import get_llm
    from langchain_core.messages import HumanMessage, AIMessage

    memory_service = MemoryService(db)
    history = await memory_service.get_recent_messages(request.project_id)
    context_block = await memory_service.build_context_block(
        request.project_id, request.message
    )

    full_message = request.message
    if context_block:
        full_message = f"{request.message}\n\n[系统提供的项目上下文]\n{context_block}"

    llm = get_llm()
    messages = []
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=full_message))

    full_response = ""

    try:
        async for chunk in llm.astream(messages):
            if chunk.content:
                full_response += chunk.content
                yield f"data: {json.dumps({'content': chunk.content}, ensure_ascii=False)}\n\n"
    except Exception:
        logger.exception("SSE chat error")
        yield f"data: {json.dumps({'error': '处理请求时出现错误'}, ensure_ascii=False)}\n\n"

    await memory_service.append_conversation(
        project_id=request.project_id,
        user_message=request.message,
        assistant_message=full_response,
    )

    yield "data: [DONE]\n\n"


@router.get("/projects/{project_id}/conversations", response_model=list[ConversationHistoryResponse])
async def get_conversation_history(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """获取项目对话历史"""
    service = ChatService(db)
    return await service.get_history(project_id, limit=limit, offset=offset)
