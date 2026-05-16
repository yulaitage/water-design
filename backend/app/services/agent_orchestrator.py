from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.agent import invoke_agent
from app.services.memory_service import MemoryService
from app.services.skill_execution_service import SkillManager


class AgentOrchestrator:
    """Agent 编排器 — 基于 LangGraph ReAct Agent + Skill自学习"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.memory_service = MemoryService(db)
        self.skill_manager = SkillManager(db)

    async def process(self, request: ChatRequest) -> ChatResponse:
        """处理用户对话：Skill匹配 → 记忆加载 → 调用 Agent → 学习新技能"""
        from app.models.project import Project
        from sqlalchemy import select

        # Defensive rollback to clear any stale aborted transaction
        try:
            await self.db.rollback()
        except Exception:
            pass

        # Handle both UUID and string project IDs
        project_id = request.project_id
        if project_id is None:
            if request.project_id_str:
                # Frontend sends string IDs like "1" - use a default project or create one
                stmt = select(Project).limit(1)
                result = await self.db.execute(stmt)
                project = result.scalar_one_or_none()
            else:
                # Neither project_id nor project_id_str provided - get or create default
                project = None

            if project is None:
                project_name = f"Project {request.project_id_str}" if request.project_id_str else "Default Project"
                project = Project(name=project_name, description="Default project")
                self.db.add(project)
                await self.db.commit()
                await self.db.refresh(project)

            project_id = project.id

        # 0. 尝试匹配Skill执行（快速路径）
        skill_result = await self.skill_manager.find_and_execute_skill(
            query=request.message,
            project_id=project_id
        )

        if skill_result:
            # Skill匹配成功，直接使用Skill结果
            reply_content = skill_result
            intent = self._detect_intent_tag(reply_content)
        else:
            # 1. 加载记忆
            history = await self.memory_service.get_recent_messages(project_id)
            context_block = await self.memory_service.build_context_block(
                project_id, request.message
            )

            # 2. 构建增强消息
            full_message = request.message
            if context_block:
                full_message = f"{request.message}\n\n[系统提供的项目上下文]\n{context_block}"

            # 3. 调用 Agent（使用前端传来的AI配置）
            try:
                reply_content = await invoke_agent(
                    db=self.db,
                    message=full_message,
                    history=history,
                    model_name=request.model_name,
                    api_key=request.api_key,
                    base_url=request.base_url,
                    embedding_model=request.embedding_model,
                    embedding_api_key=request.embedding_api_key,
                    embedding_base_url=request.embedding_base_url,
                )
            except Exception as e:
                logger = __import__("logging").getLogger(__name__)
                logger.warning("Agent invocation failed: %s", e)
                reply_content = f"抱歉，AI 引擎处理出现异常：{str(e)}"

            # 4. 简化意图标签
            intent = self._detect_intent_tag(reply_content)

        # 5. 存储对话
        conversation_id = await self.memory_service.append_conversation(
            project_id=project_id,
            user_message=request.message,
            assistant_message=reply_content,
        )

        # 6. 从成功对话中学习新Skill
        await self.skill_manager.learn_from_conversation(
            conversation_id=conversation_id,
            user_message=request.message,
            assistant_response=reply_content,
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
