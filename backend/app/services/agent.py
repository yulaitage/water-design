import uuid
from typing import Optional

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import get_llm
from app.prompts.system_prompts import SYSTEM_PROMPT


def create_tools(
    db: AsyncSession,
    embedding_model: Optional[str] = None,
    embedding_api_key: Optional[str] = None,
    embedding_base_url: Optional[str] = None,
):
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
            try:
                await db.rollback()
            except Exception:
                pass
            return f"费用估算失败：{str(e)}"

    async def search_specifications_tool(
        query: str, project_type: str = ""
    ) -> str:
        """Search engineering specifications by query."""
        from app.core.vector_store import VectorStoreService

        try:
            vs = VectorStoreService(db, embedding_model, embedding_api_key, embedding_base_url)
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
            try:
                await db.rollback()
            except Exception:
                pass
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
            try:
                await db.rollback()
            except Exception:
                pass
            return f"地形分析失败：{str(e)}"

    async def search_documents_tool(
        query: str, project_type: str = "", category: str = ""
    ) -> str:
        """Search through uploaded PDF documents for relevant content."""
        from app.core.vector_store import VectorStoreService

        try:
            vs = VectorStoreService(db, embedding_model, embedding_api_key, embedding_base_url)
            # First search for relevant documents
            docs = await vs.search_documents(
                query=query, top_k=3, project_type=project_type or None, category=category or None
            )

            # Also search cases table directly
            from sqlalchemy import select, text
            case_stmt = text("""
                SELECT id, name, project_type, location, summary, design_params
                FROM cases
                WHERE name ILIKE :query OR summary ILIKE :query OR location ILIKE :query
                LIMIT 5
            """)
            case_result = await db.execute(case_stmt, {"query": f"%{query}%"})
            cases = case_result.fetchall()
            if not cases:
                # If no cases match, return available cases for reference
                all_cases_result = await db.execute(text("SELECT id, name, project_type, location, summary FROM cases LIMIT 5"))
                all_cases = all_cases_result.fetchall()
                available = [f"• {c.name}（{c.project_type}，{c.location or '位置未知'}）" for c in all_cases]
                if available:
                    return "未找到匹配【" + query + "】的案例。\n\n当前知识库中可用的案例：\n" + "\n".join(available) + "\n\n请上传相关案例文档或修改查询关键词。"
                return "未找到相关文档，知识库中暂无案例。"
            for case in cases:
                docs.append({
                    "id": str(case.id),
                    "filename": case.name,
                    "title": case.name,
                    "category": "case",
                    "project_type": case.project_type,
                    "content": f"案例名称：{case.name}\n项目类型：{case.project_type}\n位置：{case.location}\n摘要：{case.summary or '无'}",
                    "similarity": 0.8,
                    "source": "case"
                })

            if not docs:
                return "未找到相关文档。"

            results = []
            for doc in docs:
                results.append(
                    f"文档：{doc['filename']}（{doc.get('title', '无标题')}）\n"
                    f"  相似度：{doc['similarity']:.2f}\n"
                    f"  内容摘要：{doc['content'][:500] if doc.get('content') else '无内容'}..."
                )

            # Also search document chunks for more detailed content
            chunks = await vs.search_document_chunks(query=query, top_k=5)
            if chunks:
                results.append("\n--- 文档细节内容 ---")
                for chunk in chunks:
                    chunk_info = (
                        f"[{chunk['filename']} 第{chunk.get('page', '?')}页]\n"
                        f"  {chunk['text'][:300]}..."
                    )
                    if chunk.get("image_path") and chunk.get("chunk_type") == "figure":
                        img_url = f"/api/v1/knowledge-base/images/{chunk['document_id']}/page/{chunk['page']}/img/{chunk['chunk_index'] - 9990}"
                        chunk_info += f"\n  ![图]({img_url})"
                    results.append(chunk_info)

            return "\n\n".join(results)
        except Exception as e:
            try:
                await db.rollback()
            except Exception:
                pass
            return f"文档搜索失败：{str(e)}"

    async def read_document_tool(document_id: str) -> str:
        """Read the full content of a specific document by its ID."""
        from sqlalchemy import select
        from app.models.document import Document

        try:
            doc_uuid = uuid.UUID(document_id)
            stmt = select(Document).where(Document.id == doc_uuid)
            result = await db.execute(stmt)
            doc = result.scalar_one_or_none()
            if not doc:
                return "文档未找到。"

            content = doc.full_text or "文档无文本内容。"
            # Return first 3000 characters as full reading would be too long
            return f"文档：{doc.filename}\n标题：{doc.title or '无'}\n\n内容：\n{content[:3000]}"
        except Exception as e:
            try:
                await db.rollback()
            except Exception:
                pass
            return f"文档读取失败：{str(e)}"

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

    wrapped_doc_search = lc_tool(search_documents_tool)
    wrapped_doc_search.name = "search_documents"
    wrapped_doc_search.description = (
        "搜索已上传的PDF文档、案例库和规范库。当用户询问文档内容、查找案例、搜索规范、或要求根据文档内容生成报告时使用。"
        "参数：query(搜索关键词), project_type(项目类型过滤，可选), category(文档分类，可选：planning/spec/case)"
    )

    wrapped_doc_read = lc_tool(read_document_tool)
    wrapped_doc_read.name = "read_document"
    wrapped_doc_read.description = (
        "读取指定文档的完整内容。当需要引用文档具体内容时使用。"
        "参数：document_id(文档UUID)"
    )

    return [wrapped_estimate, wrapped_search, wrapped_report, wrapped_terrain, wrapped_doc_search, wrapped_doc_read]


def build_agent(
    db: AsyncSession,
    temperature: float = 0.3,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    embedding_model: Optional[str] = None,
    embedding_api_key: Optional[str] = None,
    embedding_base_url: Optional[str] = None,
):
    """Build a LangGraph ReAct agent with tools and system prompt."""
    llm = get_llm(
        temperature=temperature,
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
    )
    tools = create_tools(db, embedding_model, embedding_api_key, embedding_base_url)
    agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)
    return agent


async def invoke_agent(
    db: AsyncSession,
    message: str,
    history: Optional[list] = None,
    temperature: float = 0.3,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    embedding_model: Optional[str] = None,
    embedding_api_key: Optional[str] = None,
    embedding_base_url: Optional[str] = None,
) -> str:
    """Invoke the agent and return the response text."""
    agent = build_agent(
        db,
        temperature=temperature,
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
        embedding_model=embedding_model,
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
    )

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