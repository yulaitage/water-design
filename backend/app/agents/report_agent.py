"""
基于 RAG 的智能报告编制 Agent - LangGraph StateGraph 实现
参考 GenericAgent 设计理念
"""
import uuid
import json
import logging
from typing import Optional, List, Dict, Any, TypedDict

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.core.llm import get_llm

logger = logging.getLogger(__name__)


class ReportAgentState(TypedDict):
    """Agent 状态"""
    messages: List[Dict[str, str]]  # 对话历史
    user_intent: Optional[str]  # 用户意图: generate | revise | supplement
    context: Dict[str, Any]  # RAG 检索上下文
    retrieved_cases: List[dict]  # 检索到的案例
    retrieved_specs: List[dict]  # 检索到的规范
    retrieved_materials: List[dict]  # 检索到的素材
    report_draft: Optional[str]  # 当前报告草稿
    report_id: Optional[str]  # 报告任务ID
    project_id: str  # 项目UUID
    pending_chapters: List[str]  # 待完善的章节
    iteration: int  # 迭代次数
    current_chapter: Optional[str]  # 当前正在处理的章节


class ReportAgent:
    """基于 RAG 的报告编制 Agent

    使用 LangGraph StateGraph 管理状态流转:
    understand → retrieve → generate → update_report → respond
    """

    def __init__(
        self,
        db: AsyncSession,
        project_id: str,
        embedding_config: dict = None,
        llm_config: dict = None
    ):
        self.db = db
        self.project_id = project_id
        self.embedding_config = embedding_config or {}
        self.llm_config = llm_config or {}
        self._graph = None
        self._llm = None

    def _get_llm(self, temperature: float = 0.3):
        """获取 LLM 实例（复用）"""
        if self._llm is None:
            self._llm = get_llm(
                temperature=temperature,
                model_name=self.llm_config.get("model_name"),
                api_key=self.llm_config.get("api_key"),
                base_url=self.llm_config.get("base_url"),
                timeout=300
            )
        return self._llm

    def _build_graph(self) -> StateGraph:
        """构建 LangGraph 状态图"""
        workflow = StateGraph(ReportAgentState)

        # 添加节点
        workflow.add_node("understand", self._understand_intent)
        workflow.add_node("retrieve", self._retrieve_knowledge)
        workflow.add_node("generate", self._generate_content)
        workflow.add_node("update_report", self._update_report)
        workflow.add_node("respond", self._generate_response)

        # 设置入口点
        workflow.set_entry_point("understand")

        # 添加边
        workflow.add_edge("understand", "retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", "update_report")
        workflow.add_edge("update_report", "respond")
        workflow.add_edge("respond", END)

        return workflow.compile()

    @property
    def graph(self):
        """懒加载图"""
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    async def _understand_intent(self, state: ReportAgentState) -> ReportAgentState:
        """理解用户意图：生成报告 / 修改章节 / 补充内容"""
        logger.info("=== ReportAgent: understanding intent ===")

        messages = state.get("messages", [])
        if not messages:
            return state

        last_message = messages[-1].get("content", "")

        # 使用 LLM 分类用户意图
        intent_prompt = f"""分析用户消息，判断其意图类型：

消息内容：
{last_message}

意图分类：
- generate: 用户要求生成全新报告（如"生成报告"、"编制报告"、"开始报告"）
- revise: 用户要求修改已有报告的某个章节（如"修改第3章"、"补充施工组织设计"）
- supplement: 用户要求补充报告中的某些内容（如"补充环境评价"、"加上经济分析"）
- general: 一般性对话，不涉及报告生成

请直接输出一个词：generate / revise / supplement / general

输出："""

        try:
            llm = self._get_llm(temperature=0.1)
            response = await llm.ainvoke(intent_prompt)
            intent = response.content.strip().lower()

            # 简单的意图验证
            if intent not in ["generate", "revise", "supplement", "general"]:
                intent = "general"

            logger.info(f"=== User intent: {intent} ===")

            # 更新状态
            state["user_intent"] = intent
            state["iteration"] = state.get("iteration", 0) + 1

        except Exception as e:
            logger.error(f"Intent understanding failed: {e}")
            state["user_intent"] = "general"

        return state

    async def _retrieve_knowledge(self, state: ReportAgentState) -> ReportAgentState:
        """RAG 检索：根据意图检索相关素材"""
        logger.info("=== ReportAgent: retrieving knowledge ===")

        intent = state.get("user_intent", "general")
        project_id = state.get("project_id", "")
        messages = state.get("messages", [])

        if not messages or intent == "general":
            return state

        last_message = messages[-1].get("content", "")

        try:
            from app.core.vector_store import VectorStoreService
            vs = VectorStoreService(
                self.db,
                embedding_model=self.embedding_config.get("model"),
                embedding_api_key=self.embedding_config.get("api_key"),
                embedding_base_url=self.embedding_config.get("base_url")
            )

            retrieved_cases = []
            retrieved_specs = []
            retrieved_materials = []

            # 根据意图决定检索策略
            if intent in ["generate", "revise", "supplement"]:
                # 检索案例（参考报告结构）
                cases_results = await vs.search_similar_cases(
                    query=f"水利工程 泵闸 海域使用论证 {last_message}",
                    top_k=5,
                    project_type="河道整治"
                )
                retrieved_cases = cases_results

                # 检索规范
                specs_results = await vs.search_similar_specifications(
                    query=f"水利工程设计 规范 标准 海域使用",
                    top_k=10
                )
                retrieved_specs = specs_results

                # 检索项目素材
                materials_results = await vs.search_project_materials(
                    query=last_message,
                    project_id=uuid.UUID(project_id),
                    top_k=20
                )
                retrieved_materials = materials_results

                # 同时检索所有相关文档块
                chunks_results = await vs.search_all_chunks(
                    query=last_message,
                    project_id=uuid.UUID(project_id),
                    top_k=30
                )

                logger.info(f"=== Retrieved: cases={len(retrieved_cases)}, specs={len(retrieved_specs)}, materials={len(retrieved_materials)}, chunks={len(chunks_results)} ===")

                # 将chunks也加入素材
                for chunk in chunks_results:
                    chunk["source"] = f"{chunk.get('category', 'material')}_chunk"
                    retrieved_materials.append(chunk)

            state["retrieved_cases"] = retrieved_cases
            state["retrieved_specs"] = retrieved_specs
            state["retrieved_materials"] = retrieved_materials

        except Exception as e:
            logger.error(f"Knowledge retrieval failed: {e}")
            state["retrieved_cases"] = []
            state["retrieved_specs"] = []
            state["retrieved_materials"] = []

        return state

    async def _generate_content(self, state: ReportAgentState) -> ReportAgentState:
        """生成报告内容：调用 LLM 生成/更新章节"""
        logger.info("=== ReportAgent: generating content ===")

        intent = state.get("user_intent", "general")
        messages = state.get("messages", [])
        retrieved_cases = state.get("retrieved_cases", [])
        retrieved_specs = state.get("retrieved_specs", [])
        retrieved_materials = state.get("retrieved_materials", [])

        if intent == "general" or not messages:
            return state

        last_message = messages[-1].get("content", "")

        try:
            # 获取项目信息
            project_info = await self._get_project_info(state["project_id"])

            # 构建案例文本
            cases_text = self._build_cases_context(retrieved_cases)

            # 构建规范文本
            specs_text = self._build_specs_context(retrieved_specs)

            # 构建素材文本
            materials_text = self._build_materials_context(retrieved_materials)

            # 根据意图选择生成策略
            if intent == "generate":
                report_content = await self._generate_full_report(
                    project_info, cases_text, specs_text, materials_text, last_message
                )
            elif intent == "revise":
                report_content = await self._revise_chapter(
                    state.get("report_draft", ""),
                    project_info, cases_text, specs_text, materials_text, last_message
                )
            elif intent == "supplement":
                report_content = await self._supplement_content(
                    state.get("report_draft", ""),
                    project_info, cases_text, specs_text, materials_text, last_message
                )
            else:
                report_content = state.get("report_draft", "")

            state["report_draft"] = report_content

        except Exception as e:
            logger.error(f"Content generation failed: {e}")

        return state

    async def _generate_full_report(
        self,
        project_info: dict,
        cases_text: str,
        specs_text: str,
        materials_text: str,
        user_message: str
    ) -> str:
        """生成完整报告"""
        project_name = project_info.get("name", "未命名项目")
        project_desc = project_info.get("description", "")

        prompt = f"""你是一位资深水利工程专家，负责编写一份详尽、完整的《海域使用论证报告》。

【项目基本信息】
- 项目名称：{project_name}
- 项目描述：{project_desc or '公益性水利工程'}
- 建设地点：上海市崇明区长兴岛
- 工程类型：泵闸工程（兼顾排涝与引水功能）

---

【参考案例报告的章节结构和详细程度】
{cases_text}

---

【相关规范条文】
{specs_text}

---

【项目素材】
{materials_text}

---

【用户要求】
{user_message}

---

【编写要求 - 必须遵守】
1. **报告必须详尽完整**，每个章节都要有大量实质性内容（每节至少300字）
2. **必须引用素材内容** - 从上方【项目素材】中提取相关段落，原文引用到报告中
3. 设计参数（流量、扬程、尺寸等）必须从素材中提取具体数值
4. 素材中没有的数据，用"[待根据勘察资料补充]"标注，但需写清楚需要什么数据
5. 使用Markdown格式，适当使用表格
6. **报告总长度目标：8000-20000字**

请生成完整的报告内容，包含所有10个章节：
## 第1章 项目概述
## 第2章 工程建设的必要性
## 第3章 工程任务与规模
## 第4章 工程总体布置
## 第5章 工程设计
## 第6章 施工组织设计
## 第7章 投资估算
## 第8章 经济评价
## 第9章 环境影响评价
## 第10章 结论与建议
"""

        llm = self._get_llm(temperature=0.3)
        response = await llm.ainvoke(prompt)

        report_content = response.content

        # 如果报告太短，尝试扩展
        if len(report_content) < 5000:
            expansion_prompt = f"""以下是一份海域使用论证报告的初稿，内容太简略。请将其扩展为详尽、专业的完整报告，**每章每节都要有大量实质性论述**：

{report_content}

---
【扩展要求】
1. 为每个章节添加详细的技术论述（每节至少500字）
2. 从以下角度扩展：
   - 项目背景：描述长兴岛区域水系、现有设施、存在问题
   - 建设必要性：从技术、社会、经济、环境多角度论证
   - 工程规模：明确设计参数、流量、容量等
   - 总体布置：详细描述各建筑物的结构和尺寸
   - 结论建议：给出明确结论和建设性意见
3. 使用Markdown格式，适当使用表格
4. **扩展后报告总长度应达到8000-20000字**

请直接在下方写出扩展后的完整报告（包含所有章节）：
"""
            try:
                expanded = await llm.ainvoke(expansion_prompt)
                if len(expanded.content) > len(report_content):
                    report_content = expanded.content
            except Exception as e:
                logger.warning(f"Report expansion failed: {e}")

        return report_content

    async def _revise_chapter(
        self,
        current_report: str,
        project_info: dict,
        cases_text: str,
        specs_text: str,
        materials_text: str,
        user_message: str
    ) -> str:
        """修订指定章节"""
        project_name = project_info.get("name", "未命名项目")

        prompt = f"""你是一位资深水利工程专家，负责修订报告中的特定章节。

【当前报告内容】
{current_report or "（暂无报告内容）"}

---

【用户修改要求】
{user_message}

---

【参考案例】
{cases_text}

---

【规范参考】
{specs_text}

---

【项目素材】
{materials_text}

---

【要求】
1. 根据用户要求修改报告中的指定章节
2. 新章节内容要详尽（每节至少300字）
3. 必须引用素材中的相关数据
4. 使用Markdown格式
5. 如果用户提到了具体章节（如"第3章"），请只修改该章节
6. 输出完整的修改后报告（或只输出修改的章节）

请生成修改后的报告内容：
"""

        llm = self._get_llm(temperature=0.3)
        response = await llm.ainvoke(prompt)
        return response.content

    async def _supplement_content(
        self,
        current_report: str,
        project_info: dict,
        cases_text: str,
        specs_text: str,
        materials_text: str,
        user_message: str
    ) -> str:
        """补充缺失内容"""
        project_name = project_info.get("name", "未命名项目")

        prompt = f"""你是一位资深水利工程专家，负责补充报告中的缺失内容。

【当前报告内容】
{current_report or "（暂无报告内容）"}

---

【用户补充要求】
{user_message}

---

【参考案例】
{cases_text}

---

【规范参考】
{specs_text}

---

【项目素材】
{materials_text}

---

【要求】
1. 根据用户要求，在现有报告基础上补充缺失内容
2. 补充内容要详尽（每节至少300字）
3. 必须引用素材中的相关数据
4. 使用Markdown格式
5. 输出完整的报告（含补充内容）

请生成补充后的完整报告内容：
"""

        llm = self._get_llm(temperature=0.3)
        response = await llm.ainvoke(prompt)
        return response.content

    async def _update_report(self, state: ReportAgentState) -> ReportAgentState:
        """更新报告：存储到数据库"""
        logger.info("=== ReportAgent: updating report ===")

        report_draft = state.get("report_draft")
        if not report_draft:
            return state

        report_id = state.get("report_id")

        try:
            # 解析报告内容，提取各章节
            chapters_content = self._parse_chapters(report_draft)

            # 如果有已有report_id，更新；否则创建新的
            if not report_id:
                report_id = str(uuid.uuid4())

            # 构建chapters JSON
            import json
            chapters_json = json.dumps(chapters_content, ensure_ascii=False)
            metadata_json = json.dumps({
                name: {"status": "complete", "confirmed": False, "revision_count": 0}
                for name in chapters_content.keys()
            })

            from datetime import datetime as dt
            now = dt.now()

            # 尝试更新或插入
            check_sql = text("SELECT id FROM report_tasks WHERE id = :id")
            result = await self.db.execute(check_sql, {"id": uuid.UUID(report_id)})
            exists = result.fetchone() is not None

            if exists:
                update_sql = text("""
                    UPDATE report_tasks
                    SET chapters = :chapters, chapters_metadata = :metadata,
                        status = 'completed', updated_at = :now
                    WHERE id = :id
                """)
                await self.db.execute(update_sql, {
                    "id": uuid.UUID(report_id),
                    "chapters": chapters_json,
                    "metadata": metadata_json,
                    "now": now
                })
            else:
                insert_sql = text("""
                    INSERT INTO report_tasks (id, project_id, report_type, status, version,
                        is_interactive, phase, current_chapter_index, chapters_metadata, chapters,
                        progress, created_at, updated_at)
                    VALUES (:id, :project_id, :report_type, :status, 1,
                        FALSE, 'idle', 1, :metadata, :chapters,
                        100, :now, :now)
                """)
                await self.db.execute(insert_sql, {
                    "id": uuid.UUID(report_id),
                    "project_id": state["project_id"],
                    "report_type": "feasibility",
                    "status": "completed",
                    "chapters": chapters_json,
                    "metadata": metadata_json,
                    "now": now
                })

            await self.db.commit()
            state["report_id"] = report_id
            logger.info(f"=== Report saved with ID: {report_id} ===")

        except Exception as e:
            logger.error(f"Report update failed: {e}")
            try:
                await self.db.rollback()
            except Exception:
                pass

        return state

    async def _generate_response(self, state: ReportAgentState) -> ReportAgentState:
        """生成回复：返回给用户的自然语言响应"""
        logger.info("=== ReportAgent: generating response ===")

        intent = state.get("user_intent", "general")
        report_id = state.get("report_id")
        report_draft = state.get("report_draft", "")
        messages = state.get("messages", [])

        if not messages:
            return state

        # 构建响应消息
        if intent == "generate":
            response_text = f"""✅ 报告已生成！

基于案例库中的相似工程经验和项目素材，完成了《海域使用论证报告》的编制。报告包含以下章节：

- 第1章 项目概述
- 第2章 工程建设的必要性
- 第3章 工程任务与规模
- 第4章 工程总体布置
- 第5章 工程设计
- 第6章 施工组织设计
- 第7章 投资估算
- 第8章 经济评价
- 第9章 环境影响评价
- 第10章 结论与建议

报告将显示在右侧预览区。您可以继续提出修改要求，如"修改第3章，增加施工组织设计内容"。
"""
        elif intent == "revise":
            response_text = f"""✅ 报告已根据您的要求修改！

报告ID: {report_id}

右侧预览区已更新，您可以查看修改后的报告内容。如需进一步调整，请继续告诉我。
"""
        elif intent == "supplement":
            response_text = f"""✅ 报告已补充缺失内容！

报告ID: {report_id}

右侧预览区已更新，新增内容已添加到报告中。如需继续补充其他内容，请告诉我。
"""
        else:
            response_text = f"""我已了解您的要求。如需生成或修改报告，请告诉我具体要求。
"""

        # 更新消息历史
        messages.append({"role": "assistant", "content": response_text})
        state["messages"] = messages

        return state

    async def _get_project_info(self, project_id: str) -> dict:
        """获取项目信息"""
        try:
            stmt = select(Project).where(Project.id == uuid.UUID(project_id))
            result = await self.db.execute(stmt)
            project = result.scalar_one_or_none()

            if project:
                return {
                    "name": project.name,
                    "description": project.description or ""
                }
        except Exception as e:
            logger.warning(f"Failed to get project info: {e}")

        return {"name": "未命名项目", "description": ""}

    def _build_cases_context(self, cases: List[dict]) -> str:
        """构建案例上下文"""
        if not cases:
            return "【参考案例报告】：暂无相似案例，使用标准结构。\n"

        text = "【参考案例报告的章节结构和详细程度】：\n\n"
        for i, case in enumerate(cases[:3], 1):
            case_summary = case.get('summary', case.get('description', ''))
            text += f"""### 参考案例{i}：{case.get('name', '未命名案例')}
- 位置：{case.get('location', '未知')}
- 类型：{case.get('project_type', '未知')}
- 内容摘要：
{case_summary}

"""
        return text

    def _build_specs_context(self, specs: List[dict]) -> str:
        """构建规范上下文"""
        if not specs:
            return "【相关规范】：未找到相关规范条文。\n"

        text = "【相关规范条文】：\n\n"
        for spec in specs[:10]:
            text += f"""【{spec.get('code', '规范')}】{spec.get('name', '规范名称')}
内容：{spec.get('content', '')}
---
"""
        return text

    def _build_materials_context(self, materials: List[dict]) -> str:
        """构建素材上下文"""
        if not materials:
            return "【项目素材】：暂无相关素材。\n"

        text = "【项目素材】：\n\n"
        for mat in materials[:20]:
            source = mat.get('source', 'material')
            filename = mat.get('filename', mat.get('title', '素材'))
            content = mat.get('content', mat.get('text', ''))
            page = mat.get('page', '')

            if source == 'material_chunk' or source == 'case_chunk':
                text += f"""【来源：{filename} 第{page}页】
{content}

"""
            else:
                text += f"""【来源：{filename}】
{content[:1000] if content else '无内容'}...

"""

        return text

    def _parse_chapters(self, report_content: str) -> Dict[str, str]:
        """解析报告内容，提取各章节"""
        import re
        chapters = {}

        # 按章节分割内容
        chapter_patterns = [
            (r'##\s*第1章[^\n]*.*?(?=##\s*第2章|$)', '第1章 项目概述'),
            (r'##\s*第2章[^\n]*.*?(?=##\s*第3章|$)', '第2章 工程建设的必要性'),
            (r'##\s*第3章[^\n]*.*?(?=##\s*第4章|$)', '第3章 工程任务与规模'),
            (r'##\s*第4章[^\n]*.*?(?=##\s*第[5-9]章|##\s*第10章|$)', '第4章 工程总体布置'),
            (r'##\s*第5章[^\n]*.*?(?=##\s*第[6-9]章|##\s*第10章|$)', '第5章 工程设计'),
            (r'##\s*第6章[^\n]*.*?(?=##\s*第[7-9]章|##\s*第10章|$)', '第6章 施工组织设计'),
            (r'##\s*第7章[^\n]*.*?(?=##\s*第[8-9]章|##\s*第10章|$)', '第7章 投资估算'),
            (r'##\s*第8章[^\n]*.*?(?=##\s*第9章|##\s*第10章|$)', '第8章 经济评价'),
            (r'##\s*第9章[^\n]*.*?(?=##\s*第10章|$)', '第9章 环境影响评价'),
            (r'##\s*第10章[^\n]*.*', '第10章 结论与建议'),
        ]

        for pattern, chapter_name in chapter_patterns:
            match = re.search(pattern, report_content, re.DOTALL)
            if match:
                chapters[chapter_name] = match.group(0).strip()

        # 如果章节解析失败，将整个内容作为第1章
        if not chapters:
            chapters = {"第1章 项目概述": report_content}

        return chapters

    async def process(self, user_message: str, history: List[Dict], report_id: str = None) -> Dict[str, Any]:
        """处理用户消息

        Args:
            user_message: 用户消息
            history: 对话历史
            report_id: 已有报告ID（用于修订/补充）

        Returns:
            {
                "message": 响应消息,
                "report_id": 报告ID,
                "report_content": 报告内容,
                "intent": 意图标签
            }
        """
        # 构建初始状态
        messages = history.copy() if history else []
        messages.append({"role": "user", "content": user_message})

        initial_state = ReportAgentState(
            messages=messages,
            user_intent=None,
            context={},
            retrieved_cases=[],
            retrieved_specs=[],
            retrieved_materials=[],
            report_draft=None,
            report_id=report_id,
            project_id=self.project_id,
            pending_chapters=[],
            iteration=0,
            current_chapter=None
        )

        # 执行图
        result_state = await self.graph.ainvoke(initial_state)

        # 获取最终消息
        final_messages = result_state.get("messages", [])
        response_message = ""
        for msg in reversed(final_messages):
            if msg.get("role") == "assistant":
                response_message = msg.get("content", "")
                break

        return {
            "message": response_message,
            "report_id": result_state.get("report_id"),
            "report_content": result_state.get("report_draft"),
            "intent": result_state.get("user_intent", "GENERAL_CHAT"),
        }


# 导入 Project 模型（避免循环导入）
from app.models.project import Project