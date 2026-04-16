import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.services.intent_detection import IntentDetectionService, Intent
from app.schemas.chat import ChatRequest, ChatResponse


class AgentOrchestrator:
    """Agent编排器"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.intent_service = IntentDetectionService()

    async def process(self, request: ChatRequest) -> ChatResponse:
        """
        处理用户对话

        流程:
        1. 检索相关记忆
        2. 识别意图
        3. 调用工具
        4. 存储对话
        5. 生成回复
        """
        # 1. 获取对话历史
        conversation = await self._get_or_create_conversation(request.project_id)

        # 2. 识别意图
        intent = self.intent_service.detect(request.message)
        params = self.intent_service.extract_params(request.message, intent)

        # 3. 构建上下文
        context = {
            "intent": intent,
            "params": params,
            "conversation_id": conversation.id,
            "history": conversation.messages[-5:] if conversation.messages else []
        }

        # 4. 调用对应工具
        tool_calls = []
        reply_content = ""

        if intent == Intent.COST_ESTIMATE:
            result = await self._handle_cost_estimate(context)
            reply_content = result.get("reply", "已完成费用估算")
            if result.get("tool_call"):
                tool_calls.append(result["tool_call"])
        elif intent == Intent.REPORT_GENERATE:
            result = await self._handle_report_generate(context)
            reply_content = result.get("reply", "正在生成报告")
            if result.get("tool_call"):
                tool_calls.append(result["tool_call"])
        elif intent == Intent.TERRAIN_UPLOAD:
            reply_content = "请上传地形文件，我会帮您解析并提取地形特征。"
        elif intent == Intent.PROJECT_CREATE:
            reply_content = "我将为您创建一个新项目，请提供项目名称和类型。"
        elif intent == Intent.CAD_GENERATE:
            reply_content = "正在为您生成CAD图纸，请稍候..."
        elif intent == Intent.GENERAL_CHAT:
            reply_content = await self._handle_general_chat(request.message, context)

        # 5. 更新对话历史
        await self._append_message(conversation, request.message, reply_content, tool_calls)

        return ChatResponse(
            conversation_id=conversation.id,
            message=reply_content,
            intent=intent.value,
            tool_calls=tool_calls if tool_calls else None,
            context=context
        )

    async def _get_or_create_conversation(self, project_id: uuid.UUID) -> Conversation:
        """获取或创建对话"""
        from sqlalchemy import select
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            conversation = Conversation(
                project_id=project_id,
                messages=[],
                context={"project_type": None}
            )
            self.db.add(conversation)
            await self.db.commit()
            await self.db.refresh(conversation)

        return conversation

    async def _append_message(
        self,
        conversation: Conversation,
        user_message: str,
        assistant_message: str,
        tool_calls: List[Dict[str, Any]]
    ) -> None:
        """追加消息到对话历史"""
        conversation.messages.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_calls": []
        })
        conversation.messages.append({
            "role": "assistant",
            "content": assistant_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_calls": tool_calls
        })
        await self.db.commit()

    async def _handle_cost_estimate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理费用估算请求"""
        return {
            "reply": "请提供设计参数，我将为您计算工程量并估算费用。例如：长度1000米，堤高5米，边坡系数1:2。",
            "tool_call": None
        }

    async def _handle_report_generate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理报告生成请求"""
        return {
            "reply": "正在为您生成设计报告，请稍候...",
            "tool_call": {
                "tool": "report_generation",
                "params": {"project_id": context.get("params", {}).get("project_id")}
            }
        }

    async def _handle_general_chat(self, message: str, context: Dict[str, Any]) -> str:
        """处理通用对话"""
        greetings = ["你好", "您好", "hi", "hello"]
        if any(g in message.lower() for g in greetings):
            return "您好！我是水利工程AI助理，可以帮您进行工程量估算、设计报告生成等工作。请问有什么可以帮您？"

        return "我理解您的需求。请告诉我更多细节，我会尽力帮助您完成水利工程设计和估算工作。"

    async def get_conversation_history(self, project_id: uuid.UUID) -> List[Conversation]:
        """获取项目对话历史"""
        from sqlalchemy import select
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.created_at.desc())
        )
        return list(result.scalars().all())