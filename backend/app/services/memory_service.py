import uuid
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


class MemoryService:
    """三层对话记忆系统：短期（滑动窗口）+ 项目上下文 + 语义检索"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_recent_messages(
        self, project_id: uuid.UUID, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取项目最近对话消息（短期记忆）"""
        from app.models.conversation import Conversation

        stmt = (
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        conversation = result.scalar_one_or_none()

        if not conversation or not conversation.messages:
            return []

        messages = conversation.messages[-limit:] if conversation.messages else []
        return [
            {
                "role": m.get("role", "user"),
                "content": m.get("content", ""),
            }
            for m in messages
            if m.get("role") in ("user", "assistant")
        ]

    async def get_project_context(self, project_id: uuid.UUID) -> Dict[str, Any]:
        """获取项目上下文信息（项目记忆）"""
        from app.models.cost_estimate import CostEstimate

        context = {}

        try:
            stmt = (
                select(CostEstimate)
                .where(CostEstimate.project_id == project_id)
                .order_by(CostEstimate.version.desc())
                .limit(1)
            )
            result = await self.db.execute(stmt)
            estimate = result.scalar_one_or_none()

            if estimate:
                context["cost_estimate"] = {
                    "project_type": estimate.project_type,
                    "total_cost": float(estimate.total_cost),
                    "cost_per_km": float(estimate.cost_per_km) if estimate.cost_per_km else None,
                    "design_params": estimate.design_params,
                }
        except Exception as e:
            logger.warning("Failed to load project context: %s", e)

        return context

    async def search_semantic_memory(
        self, query: str, top_k: int = 3
    ) -> str:
        """语义检索相关记忆（语义记忆）"""
        try:
            from app.core.vector_store import VectorStoreService

            vs = VectorStoreService(self.db)
            specs = await vs.search_similar_specifications(query=query, top_k=top_k)

            if not specs:
                return ""

            lines = []
            for s in specs:
                lines.append(
                    f"[{s['code']}] {s['name']}: {s['content'][:200]}"
                )
            return "相关规范参考：\n" + "\n".join(lines)
        except Exception as e:
            logger.warning("Semantic memory search failed: %s", e)
            return ""

    async def build_context_block(
        self, project_id: uuid.UUID, current_message: str
    ) -> str:
        """构建完整的上下文块，注入到 agent 对话中"""
        blocks = []

        project_ctx = await self.get_project_context(project_id)
        if project_ctx:
            cost = project_ctx.get("cost_estimate")
            if cost:
                blocks.append(
                    f"项目已有估算：类型={cost['project_type']}，"
                    f"总造价={cost['total_cost']:.2f}万元"
                )

        semantic = await self.search_semantic_memory(current_message)
        if semantic:
            blocks.append(semantic)

        return "\n\n".join(blocks)

    async def append_conversation(
        self,
        project_id: uuid.UUID,
        user_message: str,
        assistant_message: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> uuid.UUID:
        """追加消息到对话历史"""
        from app.models.conversation import Conversation

        stmt = (
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        conversation = result.scalar_one_or_none()

        now = datetime.now(timezone.utc).isoformat()

        if not conversation:
            conversation = Conversation(
                project_id=project_id,
                messages=[],
                context={},
            )
            self.db.add(conversation)
            await self.db.flush()

        conversation.messages.append(
            {
                "role": "user",
                "content": user_message,
                "timestamp": now,
                "tool_calls": [],
            }
        )
        conversation.messages.append(
            {
                "role": "assistant",
                "content": assistant_message,
                "timestamp": now,
                "tool_calls": tool_calls or [],
            }
        )
        conversation.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation.id
