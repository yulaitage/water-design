from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.agent import invoke_agent
from app.services.memory_service import MemoryService


class AgentOrchestrator:
    """Agent 编排器 — 基于 LangGraph ReAct Agent"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.memory_service = MemoryService(db)

    async def process(self, request: ChatRequest) -> ChatResponse:
        """处理用户对话：加载记忆 → 调用 Agent → 存储对话 → 返回响应"""
        project_id = request.project_id

        # 1. 加载记忆
        history = await self.memory_service.get_recent_messages(project_id)
        context_block = await self.memory_service.build_context_block(
            project_id, request.message
        )

        # 2. 构建增强消息
        full_message = request.message
        if context_block:
            full_message = f"{request.message}\n\n[系统提供的项目上下文]\n{context_block}"

        # 3. 调用 Agent
        reply_content = await invoke_agent(
            db=self.db,
            message=full_message,
            history=history,
        )

        # 4. 简化意图标签
        intent = self._detect_intent_tag(reply_content)

        # 5. 存储对话
        conversation_id = await self.memory_service.append_conversation(
            project_id=project_id,
            user_message=request.message,
            assistant_message=reply_content,
        )

        return ChatResponse(
            conversation_id=conversation_id,
            message=reply_content,
            intent=intent,
            context=request.context,
        )

    @staticmethod
    def _detect_intent_tag(reply: str) -> str:
        """从回复内容推断意图标签（简化版）"""
        lower = reply.lower()
        if any(kw in lower for kw in ["造价", "费用", "工程量", "估算"]):
            return "COST_ESTIMATE"
        if any(kw in lower for kw in ["报告", "可研", "初设"]):
            return "REPORT_GENERATE"
        if any(kw in lower for kw in ["规范", "标准", "条文"]):
            return "SPEC_SEARCH"
        if any(kw in lower for kw in ["地形", "断面", "高程"]):
            return "TERRAIN_ANALYSIS"
        return "GENERAL_CHAT"
