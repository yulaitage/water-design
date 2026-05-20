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
        """Generate a design report for the project.
        IMPORTANT: The project_id must be taken from the message context [当前项目UUID：xxx].
        Example: project_id="a8aa9ed6-6af0-4106-af53-c1b091575460"
        Do NOT ask the user for project_id - it is provided in the message."""
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"=== generate_report_tool CALLED with project_id={project_id}, report_type={report_type} ===")

        from datetime import datetime as dt
        from sqlalchemy import select
        from app.models.project import Project

        try:
            # 先回滚清除可能损坏的事务
            await db.rollback()

            # 获取项目信息
            stmt = select(Project).where(Project.id == uuid.UUID(project_id))
            result = await db.execute(stmt)
            project = result.scalar_one_or_none()
            project_name = project.name if project else "未命名项目"
            project_desc = project.description if project and project.description else ""

            # 创建任务ID
            task_id = uuid.uuid4()
            now = dt.now()

            # 初始化VectorStore
            from app.core.vector_store import VectorStoreService
            vs = VectorStoreService(db, embedding_model, embedding_api_key, embedding_base_url)

            # 第一步：检索案例库 - 获取报告结构框架
            cases_results = await vs.search_similar_cases(
                query=f"{project_name} {project_desc} 水利工程 海域使用 泵闸",
                top_k=5,
                project_type="河道整治"
            )

            # 检索规范库
            specs_results = await vs.search_similar_specifications(
                query=f"{project_desc} 工程设计 海域使用 规范 标准 防洪",
                top_k=10
            )

            # 构建案例报告结构（作为章节参考）
            cases_text = ""
            if cases_results:
                cases_text = "【参考案例报告的章节结构和详细程度】：\n\n"
                for i, case in enumerate(cases_results[:3], 1):
                    case_summary = case.get('summary', case.get('description', ''))
                    case_text = f"""### 参考案例{i}：{case.get('name', '未命名案例')}
- 位置：{case.get('location', '未知')}
- 类型：{case.get('project_type', '未知')}
- 内容摘要：\n{case_summary}\n
"""
                    cases_text += case_text + "\n"
            else:
                cases_text = "【参考案例报告】：暂无相似案例，使用标准结构。\n"

            # 构建规范文本
            specs_text = ""
            if specs_results:
                specs_text = "【相关规范条文】：\n\n"
                for spec in specs_results[:10]:
                    specs_text += f"""【{spec.get('code', '规范') or '规范'}】{spec.get('name', '规范名称')}
内容：{spec.get('content', '')}
---
"""
            else:
                specs_text = "【相关规范】：未找到相关规范条文。\n"

            logger.warning(f"=== 初始检索完成: cases={len(cases_results)}, specs={len(specs_results)} ===")

            # 针对每个章节定义检索查询（智能检索的关键）
            chapter_queries = {
                "第1章 项目概述": [
                    f"{project_name} {project_desc} 项目背景 长兴岛 水利设施",
                    "区域水系 防洪排涝现状 问题分析",
                    "项目建设条件 地形地貌 气象水文"
                ],
                "第2章 工程建设的必要性": [
                    "防洪排涝 现状 缺口 需求分析",
                    "水环境 改善 区域发展",
                    "类似泵闸工程 建设经验 对比"
                ],
                "第3章 工程任务与规模": [
                    f"{project_desc} 设计流量 装机容量 规模",
                    "排涝标准 防洪标准 设计参数",
                    "水闸孔数 净宽 建筑物级别"
                ],
                "第4章 工程总体布置": [
                    f"{project_name} 场址选择 总体布置方案",
                    "进水渠 泵房 出水渠 布置",
                    "建筑物结构 设计尺寸 工程量"
                ],
                "第5章 工程设计": [
                    "建筑物结构 钢筋混凝土 灌注桩",
                    "水泵 电机 机电设备 选型",
                    "金属结构 闸门 启闭机"
                ],
                "第6章 施工组织设计": [
                    "施工条件 场地 交通 材料",
                    "施工方法 工期 施工进度",
                    "临时工程 施工布置"
                ],
                "第7章 投资估算": [
                    "工程投资 造价 估算 概算",
                    "编制依据 单价 定额",
                    "建筑工程 设备安装 独立费用"
                ],
                "第8章 经济评价": [
                    "经济效益 费用 收益 评价指标",
                    "内部收益率 净现值 效益费用比",
                    "国民经济 社会效益"
                ],
                "第9章 环境影响评价": [
                    "环境现状 空气质量 地表水",
                    "环境影响 施工期 运营期",
                    "环境保护 水土保持 措施"
                ],
                "第10章 结论与建议": [
                    "结论 建议 技术可行 经济合理",
                    "项目建设 世界级生态岛 发展规划"
                ]
            }

            # 为每个章节检索相关素材
            chapters_materials = {}
            for chapter_name, queries in chapter_queries.items():
                chapter_materials = []
                seen_content = set()
                for query in queries:
                    # 检索项目素材
                    try:
                        materials = await vs.search_project_materials(
                            query=query,
                            project_id=uuid.UUID(project_id),
                            top_k=10
                        )
                        for mat in materials:
                            content = mat.get('content', '')
                            if content and content not in seen_content:
                                seen_content.add(content)
                                chapter_materials.append({
                                    'filename': mat.get('filename', '素材'),
                                    'content': content,
                                    'source': 'material'
                                })
                    except Exception as e:
                        logger.warning(f"素材检索失败: {e}")

                    # 检索该项目下所有文档块（不限制category）
                    try:
                        chunks = await vs.search_all_chunks(
                            query=query,
                            project_id=uuid.UUID(project_id),
                            top_k=15  # 增大数量以获取更多素材
                        )
                        for chunk in chunks:
                            content = chunk.get('text', '')
                            if content and content not in seen_content:
                                seen_content.add(content)
                                page_info = f"第{chunk.get('page', '?')}页" if chunk.get('page') else ""
                                doc_category = chunk.get('category', '未知')
                                chapter_materials.append({
                                    'filename': f"{chunk.get('filename', '素材')}{page_info} [{doc_category}]",
                                    'content': content,
                                    'source': f'{doc_category}_chunk'
                                })
                    except Exception as e:
                        logger.warning(f"文档块检索失败: {e}")

                chapters_materials[chapter_name] = chapter_materials
                logger.warning(f"=== {chapter_name}: 检索到 {len(chapter_materials)} 条素材 ===")

            # 构建每个章节的素材文本
            def build_chapter_context(chapter_name: str) -> str:
                """为特定章节构建素材上下文"""
                mats = chapters_materials.get(chapter_name, [])
                if not mats:
                    return "（暂无相关素材）"

                context = f"【{chapter_name}相关素材】：\n\n"
                for mat in mats[:10]:  # 限制数量避免超出LLM上下文
                    context += f"""【来源：{mat['filename']}】
{mat['content']}

"""
                return context

            # 使用LLM生成报告
            from app.core.llm import get_llm
            llm = get_llm(temperature=0.3, timeout=300)

            # 构建每个章节的完整提示词
            # 为每个章节提供该章节专属的检索素材
            report_prompt = f"""你是一位资深水利工程专家，负责编写一份详尽、完整的《海域使用论证报告》。

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

【编写要求 - 必须遵守】
1. **报告必须详尽完整**，每个章节都要有大量实质性内容（每节至少300字）
2. **必须引用素材内容** - 从下方各章节的【相关素材】中提取相关段落，原文引用到报告中
3. 设计参数（流量、扬程、尺寸等）必须从素材中提取具体数值
4. 素材中没有的数据，用"[待根据勘察资料补充]"标注，但需写清楚需要什么数据
5. 使用Markdown格式，适当使用表格
6. **报告总长度目标：10000-20000字**

============================================================
【第1章 项目概述相关素材】
{build_chapter_context("第1章 项目概述")}
============================================================

## 第1章 项目概述

### 1.1 项目背景
详细描述长兴岛区域水系特点、现有水利设施情况、历史上的排涝问题。
**【必须从上方素材中引用相关描述】**

### 1.2 项目建设的必要性
从以下角度详细论证：
- 区域防洪排涝现状及缺口分析（引用素材数据）
- 改善水环境的需要
- 提升区域基础设施水平的需要
- 城区发展对水利设施的需求

### 1.3 项目目标与任务
明确项目建设目标，列出主要建设任务。

### 1.4 项目建设条件
- 地理位置及交通条件
- 地形地貌概况（引用素材地形数据）
- 气象水文条件（引用素材中所有相关数据）

============================================================
【第2章 工程建设的必要性相关素材】
{build_chapter_context("第2章 工程建设的必要性")}
============================================================

## 第2章 工程建设的必要性

### 2.1 区域水利现状分析
详细描述长兴岛现有水利工程体系，分析存在问题。
**【必须引用上方素材中关于现状分析的内容】**

### 2.2 项目建设必要性分析
从技术、社会、经济、环境多角度详细论证。
**【引用上方素材中的相关数据和案例】**

### 2.3 与类似工程的对比分析
**【引用上方素材】** 对比案例库中的类似泵闸工程。

============================================================
【第3章 工程任务与规模相关素材】
{build_chapter_context("第3章 工程任务与规模")}
============================================================

## 第3章 工程任务与规模

### 3.1 工程任务
明确排涝标准、设计流量等关键指标。

### 3.2 工程规模
**【必须从上方素材中提取具体数值填入下表】**
| 项目 | 数值 | 来源 |
|------|------|------|
| 泵站设计流量 | m³/s | [填入素材来源] |
| 泵站装机容量 | kW | [填入素材来源] |
| 水闸孔数 | 孔 | [填入素材来源] |
| 水闸单孔净宽 | m | [填入素材来源] |
| 防洪标准 | 年一遇 | [填入素材来源] |

### 3.3 主要建筑物级别
根据规范确定主要建筑物级别。

============================================================
【第4章 工程总体布置相关素材】
{build_chapter_context("第4章 工程总体布置")}
============================================================

## 第4章 工程总体布置

### 4.1 场址选择
说明泵闸位置选择的依据。
**【引用上方素材中相关选址依据】**

### 4.2 总体布置方案
**【引用上方素材中的图片】** 如有素材图片，插入 ![示意图](图片路径)
详细描述：
- 进水渠布置
- 泵房布置
- 出水渠布置
- 管理设施布置

### 4.3 主要建筑物设计
**【引用上方素材】** 描述进水闸、泵房、出水闸等建筑物的结构形式和主要尺寸。

### 4.4 工程量汇总
**【必须从上方素材中提取工程量数据】**
| 工程项目 | 单位 | 工程量 | 备注 |
|-----------|------|--------|------|
| 土方开挖 | 万m³ | [填入] | [来源] |
| 土方回填 | 万m³ | [填入] | [来源] |
| 混凝土 | m³ | [填入] | [来源] |
| 钢筋 | t | [填入] | [来源] |
| 砌石 | m³ | [填入] | [来源] |

============================================================
【第5章 工程设计相关素材】
{build_chapter_context("第5章 工程设计")}
============================================================

## 第5章 工程设计

### 5.1 建筑物结构设计
**【引用上方素材】** 描述建筑物结构形式、基础处理等。

### 5.2 机电设备选型
**【引用上方素材】** 描述水泵、电机等主要设备选型。

============================================================
【第6章 施工组织设计相关素材】
{build_chapter_context("第6章 施工组织设计")}
============================================================

## 第6章 施工组织设计

### 6.1 施工条件
**【引用上方素材】** 描述施工场地、交通、材料供应条件。

### 6.2 施工方法
**【引用上方素材】** 描述主要施工工艺和施工进度安排。

============================================================
【第7章 投资估算相关素材】
{build_chapter_context("第7章 投资估算")}
============================================================

## 第7章 投资估算

### 7.1 编制依据
### 7.2 工程投资估算
**【引用上方素材】** 估算总投资及各分项投资。

============================================================
【第8章 经济评价相关素材】
{build_chapter_context("第8章 经济评价")}
============================================================

## 第8章 经济评价

### 8.1 评价依据
### 8.2 经济效益分析
**【引用上方素材】** 计算经济内部收益率、净现值等指标。

============================================================
【第9章 环境影响评价相关素材】
{build_chapter_context("第9章 环境影响评价")}
============================================================

## 第9章 环境影响评价

### 9.1 环境现状
**【引用上方素材】** 描述工程区环境质量现状。

### 9.2 环境影响分析
**【引用上方素材】** 分析施工期和运营期环境影响，提出保护措施。

============================================================
【第10章 结论与建议相关素材】
{build_chapter_context("第10章 结论与建议")}
============================================================

## 第10章 结论与建议

### 10.1 结论
从技术可行性、经济社会效益、环境影响等方面给出明确结论。

### 10.2 建议
提出建设性意见。

---

【重要提醒】
- 每个章节的内容必须来自对应章节的【相关素材】，**禁止凭空编造**
- 如果素材中有数据，必须引用并填入表格
- 如果素材中没有数据，用"[待根据勘察资料补充]"标注
- **报告总长度目标：10000-20000字**

---
报告生成时间：{now.strftime('%Y年%m月%d日')}
"""

            try:
                llm_response = await llm.ainvoke(report_prompt)
                report_content = llm_response.content

                # 强制扩展内容：如果报告太短，添加更多内容
                if len(report_content) < 5000:
                    logger.warning(f"=== 报告内容过短({len(report_content)}字符)，尝试补充详细内容 ===")
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
                        expanded_response = await llm.ainvoke(expansion_prompt)
                        if len(expanded_response.content) > len(report_content):
                            report_content = expanded_response.content
                            logger.warning(f"=== 报告已扩展至 {len(report_content)} 字符 ===")
                    except Exception as expand_err:
                        logger.warning(f"=== 报告扩展失败: {expand_err} ===")

                logger.warning(f"=== LLM生成报告完成，长度: {len(report_content)} 字符 ===")
            except Exception as llm_err:
                logger.warning(f"=== LLM生成失败: {llm_err} ===")
                # 回退：构建一个基于章节素材的报告
                report_content = f"""# {project_name} 海域使用论证报告

报告生成过程中遇到错误，请检查素材库后重试。

以下是已检索到的素材摘要：

{cases_text}

{specs_text}

---
报告生成时间：{now.strftime('%Y年%m月%d日')}
"""

            # 解析生成的报告内容，提取各章节
            chapters_content = {}
            import re

            # 按章节分割内容（支持 ## 第X章 格式和 ## 第X章 章节名 格式）
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
                    chapters_content[chapter_name] = match.group(0).strip()

            # 如果章节解析失败（LLM可能用了不同格式），将整个内容作为第1章
            if not chapters_content:
                logger.warning(f"=== 章节解析失败，存储整个报告内容 ===")
                chapters_content = {
                    "第1章 项目概述": report_content,
                }

            logger.warning(f"=== Generated chapters: {list(chapters_content.keys())} ===")

            # 将dict转为JSON字符串传给数据库
            import json
            chapters_json = json.dumps(chapters_content, ensure_ascii=False)
            metadata_json = json.dumps({
                name: {"status": "complete", "confirmed": False, "revision_count": 0}
                for name in chapters_content.keys()
            })

            # 插入任务记录
            from sqlalchemy import text
            insert_sql = text("""
                INSERT INTO report_tasks (id, project_id, report_type, status, version,
                    is_interactive, phase, current_chapter_index, chapters_metadata, chapters,
                    progress, created_at, updated_at)
                VALUES (:id, :project_id, :report_type, :status, 1,
                    FALSE, 'idle', 1, :chapters_metadata, :chapters,
                    100, :now, :now)
            """)
            await db.execute(insert_sql, {
                "id": task_id,
                "project_id": project_id,
                "report_type": report_type,
                "status": "completed",
                "chapters_metadata": metadata_json,
                "chapters": chapters_json,
                "now": now
            })
            await db.commit()
            logger.warning(f"=== generate_report_tool SUCCESS: task_id={task_id} ===")

            # 返回包含 report_id 的消息，前端可以解析
            return f"✅ 报告已生成（ID: {task_id}）\n\n基于案例库中的相似工程经验生成了报告内容，报告将显示在右侧预览区。\n\n[REPORT_ID:{task_id}]"
        except Exception as e:
            import traceback
            logger.error(f"=== generate_report_tool FAILED: {e} ===")
            logger.error(f"Traceback: {traceback.format_exc()}")
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

    async def search_materials_tool(
        query: str, project_id: str
    ) -> str:
        """Search project-specific material documents (project material library).
        IMPORTANT: The project_id must be taken from the message context [当前项目UUID：xxx].
        Example: project_id="a8aa9ed6-6af0-4106-af53-c1b091575460"
        Do NOT ask the user for project_id - it is provided in the message."""
        from app.core.vector_store import VectorStoreService

        try:
            vs = VectorStoreService(db, embedding_model, embedding_api_key, embedding_base_url)
            results = await vs.search_project_materials(
                query=query, project_id=uuid.UUID(project_id), top_k=5
            )
            if not results:
                return "未找到项目素材库相关文档。请确认该项目已上传素材。"
            lines = []
            for r in results:
                lines.append(
                    f"[素材] {r['filename']}（相似度：{r['similarity']:.2f}）\n"
                    f"  内容：{r['content'][:500] if r.get('content') else '无内容'}..."
                )
            return "\n\n".join(lines) if lines else "未找到项目素材。"
        except Exception as e:
            try:
                await db.rollback()
            except Exception:
                pass
            return f"素材检索失败：{str(e)}"

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
        "生成设计报告。立即调用此工具生成报告。参数：project_id(项目UUID字符串), report_type(报告类型，feasibility或preliminary_design)"
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

    wrapped_materials = lc_tool(search_materials_tool)
    wrapped_materials.name = "search_materials"
    wrapped_materials.description = (
        "搜索项目专属素材库中的文档。当用户要求生成报告、引用项目资料、或检索项目特有文档时使用。"
        "参数：query(搜索关键词), project_id(项目UUID)"
    )

    return [wrapped_estimate, wrapped_search, wrapped_report, wrapped_terrain, wrapped_doc_search, wrapped_doc_read, wrapped_materials]


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
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Building agent with model: %s", model_name or "default")

    llm = get_llm(
        temperature=temperature,
        model_name=model_name,
        api_key=api_key,
        base_url=base_url,
    )
    logger.info("LLM created: %s", type(llm).__name__)
    tools = create_tools(db, embedding_model, embedding_api_key, embedding_base_url)
    logger.info("Tools created: %s", [t.name for t in tools])
    agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)
    return agent


async def invoke_agent(
    db: AsyncSession,
    message: str,
    history: Optional[list] = None,
    project_id: Optional[str] = None,
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

    # 注意：project_id 已经在 AgentOrchestrator 的 full_message 中注入
    # 这里不需要再添加，避免重复
    messages.append(HumanMessage(content=message))

    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"=== AGENT INVOKE START ===")
    logger.warning(f"Message: {message[:200]}...")

    result = await agent.ainvoke({"messages": messages})

    ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
    if ai_messages:
        final_msg = ai_messages[-1].content
        # Log tool calls if any
        import logging
        logger = logging.getLogger(__name__)
        for msg in result["messages"]:
            if hasattr(msg, 'type') and msg.type == 'tool':
                logger.info(f"TOOL CALL: {getattr(msg, 'name', 'unknown')} -> {str(getattr(msg, 'content', ''))[:100]}")
        return final_msg

    return "抱歉，我无法处理您的请求。"