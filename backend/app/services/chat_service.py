import uuid
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.conversation import Conversation
from app.services.agent_orchestrator import AgentOrchestrator
from app.schemas.chat import ChatRequest, ChatResponse, ConversationHistoryResponse


class ChatService:
    """对话服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """处理对话"""
        orchestrator = AgentOrchestrator(self.db)
        return await orchestrator.process(request)

    async def get_history(
        self,
        project_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0
    ) -> List[ConversationHistoryResponse]:
        """获取项目对话历史（带分页）"""
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        conversations = result.scalars().all()

        return [
            ConversationHistoryResponse(
                id=c.id,
                project_id=c.project_id,
                messages=c.messages,
                context=c.context,
                created_at=c.created_at,
                updated_at=c.updated_at
            )
            for c in conversations
        ]

    async def get_conversation(self, conversation_id: uuid.UUID) -> Optional[Conversation]:
        """获取单条对话"""
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()