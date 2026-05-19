from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import re

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.agent import invoke_agent
from app.services.memory_service import MemoryService
from app.services.skill_execution_service import SkillManager

# 新的 Agent 会话缓存
_agent_sessions: Dict[str, "ReportAgent"] = {}


class AgentOrchestrator:
    """Agent 编排器 — 基于 LangGraph ReAct Agent + Skill自学习"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.memory_service = MemoryService(db)
        self.skill_manager = SkillManager(db)

    def get_agent_session(
        self,
        project_id: str,
        embedding_config: dict = None,
        llm_config: dict = None
    ) -> "ReportAgent":
        """获取或创建 Agent 会话（复用）"""
        # 延迟导入避免循环
        from app.agents.report_agent import ReportAgent

        if project_id not in _agent_sessions:
            _agent_sessions[project_id] = ReportAgent(
                db=self.db,
                project_id=project_id,
                embedding_config=embedding_config,
                llm_config=llm_config
            )
        return _agent_sessions[project_id]

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
        # 注意：对于报告生成请求，跳过Skill匹配，交给Agent处理
        skip_skill = any(kw in request.message.lower() for kw in ['报告', '生成报告', '编制', '检索素材'])
        skill_result = None
        if not skip_skill:
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

            # 2. 构建增强消息 - 项目ID必须放在消息最开头
            project_uuid_str = str(project_id)
            full_message = f"""[系统信息] 当前项目UUID是：{project_uuid_str}
所有工具调用（generate_report、search_materials等）必须使用此UUID作为project_id参数。
项目名称：长兴岛前卫泵闸海域使用论证（如有需要可使用）

---用户消息---"""

            if context_block:
                full_message += f"\n\n[系统提供的项目上下文]\n{context_block}"

            full_message += f"\n\n{request.message}\n\n[重要] 调用工具时请使用 project_id={project_uuid_str}"""

            # 3. 调用 Agent（使用前端传来的AI配置）
            # 对于报告生成请求，优先使用新的 ReportAgent
            report_intent_keywords = ['生成报告', '编制报告', '开始报告', '写报告', '生成海域']
            is_report_request = any(kw in request.message for kw in report_intent_keywords)

            try:
                import logging
                logger = logging.getLogger(__name__)

                if is_report_request:
                    # 使用新的 ReportAgent
                    logger.warning(f"=== ORCHESTRATOR: Using ReportAgent for report generation ===")

                    embedding_config = {
                        "model": request.embedding_model,
                        "api_key": request.embedding_api_key,
                        "base_url": request.embedding_base_url,
                    }
                    llm_config = {
                        "model_name": request.model_name,
                        "api_key": request.api_key,
                        "base_url": request.base_url,
                    }

                    agent = self.get_agent_session(
                        project_id=str(project_id),
                        embedding_config=embedding_config,
                        llm_config=llm_config
                    )

                    # 构建历史消息格式
                    history_msgs = [
                        {"role": "user" if msg.role == "user" else "assistant", "content": msg.content}
                        for msg in history
                    ] if history else []

                    result = await agent.process(
                        user_message=request.message,
                        history=history_msgs,
                        report_id=None  # 新报告
                    )

                    reply_content = result.get("message", "")
                    intent = result.get("intent", "REPORT_GENERATE")
                    report_id = result.get("report_id")
                    report_content = result.get("report_content")

                    logger.warning(f"=== ORCHESTRATOR: ReportAgent returned, report_id={report_id}, content_len={len(report_content or '')} ===")
                else:
                    # 使用原有的 invoke_agent
                    logger.warning(f"=== ORCHESTRATOR: Calling invoke_agent ===")

                    reply_content = await invoke_agent(
                        db=self.db,
                        message=full_message,
                        history=history,
                        project_id=str(project_id),
                        model_name=request.model_name,
                        api_key=request.api_key,
                        base_url=request.base_url,
                        embedding_model=request.embedding_model,
                        embedding_api_key=request.embedding_api_key,
                        embedding_base_url=request.embedding_base_url,
                    )
                    logger.warning(f"=== ORCHESTRATOR: invoke_agent returned (len={len(reply_content)}) ===")

                    # 简化意图标签
                    intent = self._detect_intent_tag(reply_content)

                    # 检测报告生成并提取 report_id
                    report_id = None
                    report_content = None
                    import re
                    match = re.search(r'\[REPORT_ID:([^\]]+)\]', reply_content)
                    if match:
                        report_id = match.group(1)
                    else:
                        match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', reply_content)
                        if match:
                            potential_uuid = match.group(1)
                            try:
                                from sqlalchemy import text
                                verify_result = await self.db.execute(
                                    text("SELECT id FROM report_tasks WHERE id = :id"),
                                    {"id": potential_uuid}
                                )
                                if verify_result.fetchone():
                                    report_id = potential_uuid
                            except Exception:
                                pass

                    if report_id:
                        intent = "REPORT_GENERATE"
                        try:
                            from app.services.report_service import ReportService
                            service = ReportService(self.db)
                            import uuid as uuid_module
                            report_content = await service.get_report_content(uuid_module.UUID(report_id))
                        except Exception as e:
                            logger.warning(f"=== ORCHESTRATOR: get_report_content failed: {e} ===")
                            report_content = None
            except Exception as e:
                logger = __import__("logging").getLogger(__name__)
                logger.warning("Agent invocation failed: %s", e)
                reply_content = f"抱歉，AI 引擎处理出现异常：{str(e)}"
                intent = "GENERAL_CHAT"
                report_id = None
                report_content = None

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
            report_id=report_id,
            report_content=report_content,
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
