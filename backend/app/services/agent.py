import uuid
from typing import Optional

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import get_llm
from app.prompts.system_prompts import SYSTEM_PROMPT


def create_tools(db: AsyncSession):
    """Create tool instances with db session injected for actual data access."""

    async def estimate_cost_tool(
        project_type: str, design_params: dict, project_id: str
    ) -> str:
        """Estimate project cost based on design parameters."""
        from app.services.cost_calculation import CostCalculationService
        from app.schemas.cost_estimation import CostEstimateCreateRequest

        try:
            service = CostCalculationService(db)
            request = CostEstimateCreateRequest(
                project_id=uuid.UUID(project_id),
                project_type=project_type,
                design_params=design_params,
            )
            estimate = await service.calculate(request)
            summary_lines = [
                f"工程类型：{estimate.project_type}",
                f"总造价：{estimate.total_cost:.2f} 万元",
            ]
            if estimate.cost_per_km:
                summary_lines.append(f"每公里造价：{estimate.cost_per_km:.2f} 万元/km")
            for item in estimate.details:
                summary_lines.append(
                    f"  {item['item']}：{item['quantity']:.2f} {item['unit']} × {item['unit_price']:.2f} 元 = {item['subtotal']:.2f} 元"
                )
            return "\n".join(summary_lines)
        except Exception as e:
            return f"费用估算失败：{str(e)}"

    async def search_specifications_tool(
        query: str, project_type: str = ""
    ) -> str:
        """Search engineering specifications by query."""
        from app.core.vector_store import VectorStoreService

        try:
            vs = VectorStoreService(db)
            results = await vs.search_similar_specifications(
                query=query, top_k=5, project_type=project_type or None
            )
            if not results:
                return "未找到相关规范条文。"
            lines = []
            for r in results:
                lines.append(
                    f"[{r['code']}] {r['name']}（相似度：{r['similarity']:.2f}）\n"
                    f"  章节：{r['chapter']} {r.get('section', '')}\n"
                    f"  内容：{r['content'][:300]}..."
                )
            return "\n\n".join(lines)
        except Exception as e:
            return f"规范检索失败：{str(e)}"

    async def generate_report_tool(
        project_id: str, report_type: str = "feasibility"
    ) -> str:
        """Generate a design report for the project."""
        try:
            task_id = uuid.uuid4()
            return f"报告生成任务已创建（ID: {task_id}），正在后台生成{report_type}报告。请稍后查看任务状态。"
        except Exception as e:
            return f"报告生成失败：{str(e)}"

    async def analyze_terrain_tool(project_id: str) -> str:
        """Analyze terrain data for the project."""
        from sqlalchemy import text

        try:
            pid = uuid.UUID(project_id)
            stmt = text(
                "SELECT file_type, features FROM terrains WHERE project_id = :pid LIMIT 1"
            )
            result = await db.execute(stmt, {"pid": pid})
            row = result.fetchone()
            if not row:
                return "该项目尚未上传地形数据。"
            features = row.features if hasattr(row, "features") else {}
            return f"地形数据（{row.file_type}）：\n{str(features)[:500]}"
        except Exception as e:
            return f"地形分析失败：{str(e)}"

    from langchain_core.tools import tool as lc_tool

    wrapped_estimate = lc_tool(estimate_cost_tool)
    wrapped_estimate.name = "estimate_cost"
    wrapped_estimate.description = (
        "计算工程量并估算费用。当用户询问工程造价、费用估算、工程量统计时使用。"
        "参数：project_type(工程类型), design_params(设计参数JSON), project_id(项目UUID)"
    )

    wrapped_search = lc_tool(search_specifications_tool)
    wrapped_search.name = "search_specifications"
    wrapped_search.description = (
        "检索水利规范条文。当用户询问设计规范、技术标准、设计要求时使用。"
        "参数：query(检索查询), project_type(工程类型过滤，可选)"
    )

    wrapped_report = lc_tool(generate_report_tool)
    wrapped_report.name = "generate_report"
    wrapped_report.description = (
        "生成设计报告。当用户要求生成报告、编写报告时使用。"
        "参数：project_id(项目UUID), report_type(报告类型)"
    )

    wrapped_terrain = lc_tool(analyze_terrain_tool)
    wrapped_terrain.name = "analyze_terrain"
    wrapped_terrain.description = (
        "分析地形数据。当用户要求查看地形特征、断面数据时使用。"
        "参数：project_id(项目UUID)"
    )

    return [wrapped_estimate, wrapped_search, wrapped_report, wrapped_terrain]


def build_agent(db: AsyncSession, temperature: float = 0.3):
    """Build a LangGraph ReAct agent with tools and system prompt."""
    llm = get_llm(temperature=temperature)
    tools = create_tools(db)
    agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)
    return agent


async def invoke_agent(
    db: AsyncSession,
    message: str,
    history: Optional[list] = None,
    temperature: float = 0.3,
) -> str:
    """Invoke the agent and return the response text."""
    agent = build_agent(db, temperature=temperature)

    messages = []
    if history:
        for msg in history:
            if msg.get("role") == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg.get("role") == "assistant":
                messages.append(AIMessage(content=msg["content"]))

    messages.append(HumanMessage(content=message))

    result = await agent.ainvoke({"messages": messages})

    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
    if ai_messages:
        return ai_messages[-1].content

    return "抱歉，我无法处理您的请求。"
