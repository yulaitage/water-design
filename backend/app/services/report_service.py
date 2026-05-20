import logging
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Optional, Dict, List, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.report import ReportTask, ReportRevision
from app.models.specification import Specification
from app.schemas.report import ReportCreateRequest, RevisionRequest, ProjectInfo
from app.services.retrieval_service import RetrievalService
from app.services.template_service import TemplateService
from app.core.task_queue import task_queue, TaskStatus
from app.core.report_exceptions import (
    KnowledgeBaseEmptyException,
    GenerationFailedException,
    InvalidRevisionException
)
from app.core.report_state import ReportPhase, ChapterState, InputRequestType
from app.core.interactive_task_queue import interactive_task_queue
from app.services.knowledge_mining_service import KnowledgeMiningService

_current_project_id: ContextVar[uuid.UUID] = ContextVar("_current_project_id")
_current_task_id: ContextVar[uuid.UUID] = ContextVar("_current_task_id")
logger = logging.getLogger(__name__)


class ReportService:
    """报告生成服务"""

    CHAPTER_ORDER = [
        "第1章 项目概述",
        "第2章 工程建设的必要性",
        "第3章 工程任务与规模",
        "第4章 工程总体布置",
        "第5章 工程设计",
        "第6章 工程管理",
        "第7章 施工组织设计",
        "第8章 投资估算",
        "第9章 经济评价",
        "第10章 结论与建议",
    ]

    def __init__(self, db: AsyncSession):
        self.db = db
        self.retrieval_service = RetrievalService(db)
        self.template_service = TemplateService()

    async def create_report_task(
        self,
        project_id: uuid.UUID,
        request: ReportCreateRequest
    ) -> ReportTask:
        """创建报告任务"""
        # 检查知识库是否为空
        spec_count = await self._count_specifications()
        if spec_count == 0:
            raise KnowledgeBaseEmptyException()

        # 创建任务
        task = ReportTask(
            project_id=project_id,
            report_type=request.report_type,
            status="pending",
            version=1
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        # 创建异步任务
        task_queue.create_task(f"report_{task.id}")

        return task

    async def _count_specifications(self) -> int:
        """统计规范数量"""
        from sqlalchemy import func
        stmt = select(func.count(Specification.id))
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def get_report_content(self, task_id: uuid.UUID) -> Optional[str]:
        """获取报告的 Markdown 内容"""
        task = await self._get_task(task_id)
        if not task or not task.chapters:
            return None
        # 合并各章节为完整报告
        # 优先使用CHAPTER_ORDER中存在的章节，保持原有顺序
        chapter_order = self.CHAPTER_ORDER
        parts = []
        for name in chapter_order:
            if name in task.chapters:
                parts.append(f"## {name}\n\n{task.chapters[name]}")
        # 如果没有找到任何章节（可能是旧格式数据），直接拼接所有chapters
        if not parts:
            for name, content in task.chapters.items():
                parts.append(f"## {name}\n\n{content}")
        return "\n\n".join(parts) if parts else None

    async def generate_report(
        self,
        task_id: uuid.UUID,
        project_info: ProjectInfo
    ) -> str:
        """生成报告（异步执行）"""
        # 获取任务
        task = await self._get_task(task_id)
        if not task:
            raise GenerationFailedException("未知", "任务不存在")

        try:
            # 更新进度：开始检索
            task_queue.update_task(
                task_id,
                status=TaskStatus.RUNNING,
                progress=10,
                current_step="检索知识库"
            )
            await self._update_task_status(task, status="retrieving", progress=10)

            # 检索规范、案例、项目素材
            specs, cases, materials = await self._retrieve_knowledge(
                project_info=project_info,
                project_id=task.project_id
            )

            # 更新进度：开始生成
            task_queue.update_task(
                task_id,
                progress=20,
                current_step="生成报告章节"
            )
            await self._update_task_status(task, progress=20, current_chapter="开始生成")

            # 设置当前项目ID供章节生成使用
            _current_project_id.set(task.project_id)

            # 按章节生成
            chapters = {}
            total_chapters = len(self.CHAPTER_ORDER)
            for i, chapter_name in enumerate(self.CHAPTER_ORDER):
                chapter_num = str(i + 1)

                # 计算进度
                progress = 20 + int((i / total_chapters) * 70)

                task_queue.update_task(
                    task_id,
                    progress=progress,
                    current_step=f"生成{chapter_name}"
                )
                await self._update_task_status(
                    task,
                    progress=progress,
                    current_chapter=chapter_name
                )

                # 生成章节内容
                content = await self._generate_chapter(
                    chapter_name=chapter_name,
                    chapter_num=chapter_num,
                    specs=specs,
                    cases=cases,
                    materials=materials,
                    project_info=project_info
                )
                chapters[chapter_name] = content

                # 挖掘知识并存储到Wiki
                try:
                    mining_service = KnowledgeMiningService(self.db)
                    project_info_dict = {
                        "name": project_info.name,
                        "description": project_info.description,
                        "scale": project_info.scale,
                        "location": project_info.location,
                    }
                    await mining_service.mine_knowledge_from_chapter(
                        chapter_name=chapter_name,
                        chapter_content=content,
                        project_info=project_info_dict,
                        report_id=task_id
                    )
                except Exception as e:
                    logger.warning(f"Knowledge mining failed for {chapter_name}: {e}")

            # 更新进度：渲染文档
            task_queue.update_task(
                task_id,
                progress=90,
                current_step="生成Word文档"
            )
            await self._update_task_status(task, progress=90, current_chapter="生成Word文档")

            # 渲染Word文档
            output_path = await self._render_document(
                task_id=task_id,
                chapters=chapters,
                project_info=project_info
            )

            # 完成
            task_queue.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                progress=100
            )
            await self._update_task_status(
                task,
                status="completed",
                progress=100,
                output_path=output_path
            )

            # 更新任务的 chapters 字段（存储 Markdown 内容供前端获取）
            task.chapters = chapters
            await self.db.commit()

            return output_path

        except Exception as e:
            task_queue.update_task(task_id, status=TaskStatus.FAILED, error=str(e))
            await self._update_task_status(task, status="failed", error_message=str(e))
            raise GenerationFailedException(chapter=task.current_chapter or "未知", reason=str(e))

    async def _retrieve_knowledge(self, project_info: ProjectInfo, project_id: uuid.UUID) -> tuple:
        """检索知识库（规范 -> 案例 -> 项目素材）"""
        specs, cases, materials = [], [], []

        try:
            specs, cases = await self.retrieval_service.retrieve_for_chapter(
                chapter="工程设计",
                project_type=self._infer_project_type(project_info),
                location=project_info.location
            )
        except Exception as e:
            logger.warning("Spec/case retrieval failed: %s", e)

        try:
            from app.core.vector_store import VectorStoreService
            vs = VectorStoreService(self.db)
            materials = await vs.search_project_materials(
                query=f"{project_info.description} {project_info.scale} 工程设计",
                project_id=project_id,
                top_k=10
            )
        except Exception as e:
            logger.warning("Material retrieval failed: %s", e)

        return specs, cases, materials

    def _infer_project_type(self, project_info: ProjectInfo) -> str:
        """从项目描述推断工程类型"""
        desc_lower = project_info.description.lower() + project_info.scale.lower()
        if "堤防" in desc_lower or "堤" in desc_lower:
            return "堤防"
        elif "河道" in desc_lower or "整治" in desc_lower:
            return "河道整治"
        elif "水库" in desc_lower:
            return "水库"
        return "河道整治"

    async def _generate_chapter(
        self,
        chapter_name: str,
        chapter_num: str,
        specs: List[dict],
        cases: List[dict],
        materials: List[dict],
        project_info: ProjectInfo
    ) -> str:
        """生成单个章节内容（使用 LLM）"""
        from app.core.llm import get_llm
        from app.prompts.report_prompts import CHAPTER_PROMPTS

        template = CHAPTER_PROMPTS.get(chapter_name)
        if not template:
            return f"{project_info.name}的{chapter_name}内容。\n参考案例：{cases[0]['name'] if cases else '无'}"

        specs_text = "\n".join([s["content"][:300] for s in specs[:3]]) if specs else "暂无参考规范"
        cases_text = "\n".join([c.get("summary", c.get("name", ""))[:200] for c in cases[:2]]) if cases else "暂无参考案例"
        materials_text = "\n".join([
            f"- [{m.get('filename', '素材')}] {m.get('content', '')[:300]}..."
            for m in materials[:3]
        ]) if materials else "暂无项目素材"

        # 提取素材中的图片信息用于插图
        figures_text = ""
        for m in materials[:3]:
            if m.get('source') == 'material_chunk' and m.get('image_path'):
                desc = m.get('image_description', '相关图片')
                img_rel = m['image_path'].replace("\\", "/")
                if img_rel.startswith("uploads/"):
                    img_rel = img_rel[len("uploads/"):]
                figures_text += f"\n- [{desc}]({img_rel})"

        for c in cases[:2]:
            if c.get('source') in ('case', 'document_chunk') and c.get('image_path'):
                desc = c.get('image_description', c.get('filename', '相关图片'))
                img_rel = c['image_path'].replace("\\", "/")
                if img_rel.startswith("uploads/"):
                    img_rel = img_rel[len("uploads/"):]
                figures_text += f"\n- [{desc}]({img_rel})"

        # 检索素材图片块
        try:
            from app.core.vector_store import VectorStoreService
            vs = VectorStoreService(self.db)
            proj_id = _current_project_id.get() if _current_project_id else None
            if proj_id:
                fig_chunks = await vs.search_material_chunks(
                    query=f"{project_info.description} 平面 断面 布置 图 设计",
                    project_id=proj_id, top_k=5
                )
                for fc in fig_chunks:
                    if fc.get('image_path') and fc.get('chunk_type') == 'figure':
                        desc = fc.get('image_description', '工程图片')
                        img_rel = fc['image_path'].replace("\\", "/")
                        if img_rel.startswith("uploads/"):
                            img_rel = img_rel[len("uploads/"):]
                        figures_text += f"\n- [{desc}]({img_rel})"
        except Exception:
            pass

        terrain_info = ""
        cost_data = ""

        try:
            from app.core.vector_store import VectorStoreService
            vs = VectorStoreService(self.db)
            terrain_results = await vs.search_similar_cases(query="地形特征 断面", top_k=1)
            if terrain_results:
                terrain_info = str(terrain_results[0].get("design_params", ""))
        except Exception:
            pass

        try:
            from sqlalchemy import select
            from app.models.cost_estimate import CostEstimate
            stmt = (
                select(CostEstimate)
                .where(CostEstimate.project_id == _current_project_id.get())
                .order_by(CostEstimate.version.desc())
                .limit(1)
            )
            result = await self.db.execute(stmt)
            estimate = result.scalar_one_or_none()
            if estimate:
                cost_data = f"总造价 {estimate.total_cost:.2f} 万元"
        except Exception:
            pass

        prompt = template.format(
            project_name=project_info.name,
            description=project_info.description,
            scale=project_info.scale,
            specs_text=specs_text,
            cases_text=cases_text,
            materials_text=materials_text,
            figures_text=figures_text or "暂无插图",
            terrain_info=terrain_info,
            cost_data=cost_data,
        )

        try:
            llm = get_llm(temperature=0.4)
            response = await llm.ainvoke(prompt)
            return response.content
        except Exception as e:
            return f"[LLM 生成失败: {str(e)}]\n\n{project_info.name}的{chapter_name}内容。"

    async def _render_document(
        self,
        task_id: uuid.UUID,
        chapters: Dict[str, str],
        project_info: ProjectInfo
    ) -> str:
        """渲染Word文档"""
        output_dir = Path("uploads/reports")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{task_id}.docx"

        self.template_service.create_word_document(
            chapters=chapters,
            output_path=str(output_path),
            title=project_info.name
        )

        return str(output_path)

    async def _get_task(self, task_id: uuid.UUID) -> Optional[ReportTask]:
        """获取任务"""
        stmt = select(ReportTask).where(ReportTask.id == task_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _update_task_status(
        self,
        task: ReportTask,
        status: str = None,
        progress: int = None,
        current_chapter: str = None,
        output_path: str = None,
        error_message: str = None
    ):
        """更新任务状态"""
        if status is not None:
            task.status = status
        if progress is not None:
            task.progress = progress
        if current_chapter is not None:
            task.current_chapter = current_chapter
        if output_path is not None:
            task.output_path = output_path
        if error_message is not None:
            task.error_message = error_message

        await self.db.commit()

    async def submit_revision(
        self,
        task_id: uuid.UUID,
        request: RevisionRequest
    ) -> ReportRevision:
        """提交修订意见"""
        task = await self._get_task(task_id)
        if not task:
            raise InvalidRevisionException("任务不存在")

        # 解析修订意见
        if request.revision_type == "form":
            user_input = f"修改章节：{','.join(request.chapters)}，类型：{request.modification_type}，描述：{request.description}"
            modified_chapters = request.chapters or []
        else:
            user_input = request.content
            modified_chapters = await self._parse_revision_chapters(request.content)

        # 创建修订记录
        revision = ReportRevision(
            report_task_id=task_id,
            version=task.version + 1,
            revision_type=request.revision_type,
            user_input=user_input,
            modified_chapters=modified_chapters
        )
        self.db.add(revision)

        # 更新任务版本
        task.version += 1
        task.status = "pending"

        await self.db.commit()
        await self.db.refresh(revision)

        return revision

    async def _parse_revision_chapters(self, content: str) -> List[str]:
        """从自然语言解析修订章节"""
        # 简化：实际需要调用LLM解析
        chapters = []
        for chapter in self.CHAPTER_ORDER:
            if chapter in content:
                chapters.append(chapter)
        return chapters if chapters else ["第5章 工程设计"]

    async def get_revision_history(self, task_id: uuid.UUID) -> List[ReportRevision]:
        """获取修订历史"""
        stmt = (
            select(ReportRevision)
            .where(ReportRevision.report_task_id == task_id)
            .order_by(ReportRevision.version)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    # ==================== 交互式报告生成方法 ====================

    async def start_interactive_report(
        self,
        project_id: uuid.UUID,
        report_type: str,
        project_info: ProjectInfo
    ) -> uuid.UUID:
        """启动交互式报告生成"""
        # 创建交互式任务
        task = ReportTask(
            project_id=project_id,
            report_type=report_type,
            status="pending",
            version=1,
            is_interactive=True,
            phase=ReportPhase.RETRIEVING.value,
            current_chapter_index=0,
            chapters_metadata={name: {"status": ChapterState.PENDING.value, "confirmed": False, "revision_count": 0}
                             for name in self.CHAPTER_ORDER}
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        # 创建交互式任务队列
        task_id = interactive_task_queue.create_task(project_id, self.CHAPTER_ORDER)
        _current_task_id.set(task_id)

        return task_id

    async def interactive_retrieve_knowledge(
        self,
        task_id: uuid.UUID,
        project_info: ProjectInfo,
        project_id: uuid.UUID
    ) -> tuple[List[dict], List[dict], List[dict]]:
        """交互式检索知识库（带进度）"""
        interactive_task_queue.update_phase(task_id, ReportPhase.RETRIEVING)

        # 检索规范
        yield {
            "type": "retrieving_progress",
            "progress": 20,
            "step": "正在检索相关规范条文..."
        }

        specs = []
        try:
            vs_service = self.retrieval_service.vector_store
            specs = await vs_service.search_similar_specifications(
                query=f"{project_info.description} {project_info.scale}",
                top_k=10,
                project_type=self._infer_project_type(project_info)
            )
        except Exception as e:
            logger.warning("Specification retrieval failed: %s", e)

        yield {
            "type": "retrieving_progress",
            "progress": 50,
            "step": f"检索到 {len(specs)} 条相关规范"
        }

        # 检索案例
        yield {
            "type": "retrieving_progress",
            "progress": 60,
            "step": "正在检索相似工程案例..."
        }

        cases = []
        try:
            cases = await vs_service.search_similar_cases(
                query=f"{project_info.description} {project_info.location}",
                top_k=5,
                project_type=self._infer_project_type(project_info)
            )
        except Exception as e:
            logger.warning("Case retrieval failed: %s", e)

        yield {
            "type": "retrieving_progress",
            "progress": 80,
            "step": f"检索到 {len(cases)} 个相似案例"
        }

        # 检索项目素材
        yield {
            "type": "retrieving_progress",
            "progress": 85,
            "step": "正在检索项目素材库..."
        }

        materials = []
        try:
            materials = await vs_service.search_project_materials(
                query=f"{project_info.description} {project_info.scale} 工程设计",
                project_id=project_id,
                top_k=10
            )
        except Exception as e:
            logger.warning("Material retrieval failed: %s", e)

        yield {
            "type": "retrieving_progress",
            "progress": 95,
            "step": f"检索到 {len(materials)} 份项目素材"
        }

        # 更新任务队列
        task = interactive_task_queue.get_task(task_id)
        if task:
            task.retrieved_specs = specs
            task.retrieved_cases = cases
            task.retrieved_materials = materials

        yield {
            "type": "retrieving_progress",
            "progress": 100,
            "step": "知识库检索完成，正在构建报告框架..."
        }

    async def interactive_generate_chapter_stream(
        self,
        task_id: uuid.UUID,
        chapter_index: int,
        specs: List[dict],
        cases: List[dict],
        materials: List[dict],
        project_info: ProjectInfo,
        revision_note: Optional[str] = None
    ) -> AsyncGenerator[dict, None]:
        """交互式流式生成章节内容

        Yields:
            dict - SSE事件数据
        """
        if chapter_index >= len(self.CHAPTER_ORDER):
            return

        chapter_name = self.CHAPTER_ORDER[chapter_index]
        _current_project_id.set(interactive_task_queue.get_task(task_id).project_id)

        # 更新任务状态
        interactive_task_queue.set_chapter_generating(task_id, chapter_index)

        yield {
            "type": "chapter_start",
            "chapter": chapter_name,
            "chapter_index": chapter_index,
            "total_chapters": len(self.CHAPTER_ORDER)
        }

        # 构建章节生成提示词
        prompt = await self._build_chapter_prompt(
            chapter_name=chapter_name,
            specs=specs,
            cases=cases,
            materials=materials,
            project_info=project_info,
            revision_note=revision_note
        )

        # 流式生成
        llm = None
        try:
            from app.core.llm import get_llm
            llm = get_llm(temperature=0.4)
        except Exception as e:
            logger.error("Failed to get LLM: %s", e)
            yield {"type": "error", "message": f"LLM初始化失败: {str(e)}"}
            return

        try:
            collected_content = []
            async for chunk in llm.astream(prompt):
                if chunk.content:
                    collected_content.append(chunk.content)
                    # 实时输出内容块
                    yield {
                        "type": "chunk",
                        "chapter": chapter_name,
                        "content": chunk.content
                    }

                    # 检测是否需要用户输入（通过关键词或内容分析）
                    detected_input = await self._detect_missing_info(
                        "".join(collected_content),
                        chapter_name
                    )
                    if detected_input:
                        yield {
                            "type": "need_input",
                            "chapter": chapter_name,
                            "info_type": detected_input["type"],
                            "description": detected_input["description"]
                        }
                        # 等待用户提供输入
                        await interactive_task_queue.wait_for_user_input(task_id)

            full_content = "".join(collected_content)

            # 更新章节内容到任务队列
            interactive_task_queue.update_chapter_status(
                task_id, chapter_name, ChapterState.WAITING_CONFIRM, full_content
            )

            yield {
                "type": "chapter_complete",
                "chapter": chapter_name,
                "chapter_index": chapter_index,
                "content": full_content,
                "revision_count": interactive_task_queue.get_chapter_context(task_id, chapter_name).revision_count
            }

            # 等待用户确认
            confirmed, revision_note = await interactive_task_queue.wait_for_confirmation(task_id)

            if not confirmed and revision_note:
                # 用户要求修改，重新生成本章
                async for event in self.interactive_generate_chapter_stream(
                    task_id, chapter_index, specs, cases, project_info, revision_note
                ):
                    yield event
            elif confirmed:
                # 确认完成，标记章节
                interactive_task_queue.update_chapter_status(
                    task_id, chapter_name, ChapterState.COMPLETE
                )

                # 挖掘本章知识到Wiki
                try:
                    mining_service = KnowledgeMiningService(self.db)
                    project_info_dict = {
                        "name": project_info.name,
                        "description": project_info.description,
                        "scale": project_info.scale,
                        "location": project_info.location,
                    }
                    await mining_service.mine_knowledge_from_chapter(
                        chapter_name=chapter_name,
                        chapter_content=full_content,
                        project_info=project_info_dict,
                        report_id=task_id
                    )
                except Exception as e:
                    logger.warning(f"Knowledge mining failed for {chapter_name}: {e}")

                if chapter_index < len(self.CHAPTER_ORDER) - 1:
                    # 还有下一章
                    yield {
                        "type": "awaiting_confirmation",
                        "chapter": chapter_name,
                        "confirmed": True,
                        "next_chapter": self.CHAPTER_ORDER[chapter_index + 1]
                    }
                else:
                    # 全部完成
                    yield {
                        "type": "all_chapters_complete",
                        "chapter": chapter_name
                    }

        except Exception as e:
            logger.exception("Chapter generation error")
            yield {"type": "error", "chapter": chapter_name, "message": str(e)}

    async def _build_chapter_prompt(
        self,
        chapter_name: str,
        specs: List[dict],
        cases: List[dict],
        materials: List[dict],
        project_info: ProjectInfo,
        revision_note: Optional[str] = None
    ) -> str:
        """构建章节生成提示词"""
        from app.prompts.report_prompts import CHAPTER_PROMPTS

        template = CHAPTER_PROMPTS.get(chapter_name, "")

        specs_text = "\n".join([
            f"- [{s.get('code', '规范')}] {s.get('name', '')}: {s.get('content', '')[:200]}..."
            for s in specs[:5]
        ]) if specs else "暂无相关规范"

        cases_text = "\n".join([
            f"- {c.get('name', '案例')}: {c.get('summary', c.get('description', ''))[:200]}..."
            for c in cases[:3]
        ]) if cases else "暂无相似案例"

        materials_text = "\n".join([
            f"- [{m.get('filename', '素材')}] {m.get('content', '')[:300]}..."
            for m in materials[:3]
        ]) if materials else "暂无项目素材"

        # 提取素材中的图片信息用于插图
        figures_text = ""
        for m in materials[:3]:
            if m.get('source') == 'material_chunk' and m.get('image_path'):
                desc = m.get('image_description', '相关图片')
                img_rel = m['image_path'].replace("\\", "/")
                if img_rel.startswith("uploads/"):
                    img_rel = img_rel[len("uploads/"):]
                figures_text += f"\n- [{desc}]({img_rel})"

        for c in cases[:2]:
            if c.get('source') in ('case', 'document_chunk') and c.get('image_path'):
                desc = c.get('image_description', c.get('filename', '相关图片'))
                img_rel = c['image_path'].replace("\\", "/")
                if img_rel.startswith("uploads/"):
                    img_rel = img_rel[len("uploads/"):]
                figures_text += f"\n- [{desc}]({img_rel})"

        # 检索素材图片块
        try:
            from app.core.vector_store import VectorStoreService
            vs = VectorStoreService(self.db)
            proj_id = _current_project_id.get() if _current_project_id else None
            if proj_id:
                fig_chunks = await vs.search_material_chunks(
                    query=f"{project_info.description} 平面 断面 布置 图 设计",
                    project_id=proj_id, top_k=5
                )
                for fc in fig_chunks:
                    if fc.get('image_path') and fc.get('chunk_type') == 'figure':
                        desc = fc.get('image_description', '工程图片')
                        img_rel = fc['image_path'].replace("\\", "/")
                        if img_rel.startswith("uploads/"):
                            img_rel = img_rel[len("uploads/"):]
                        figures_text += f"\n- [{desc}]({img_rel})"
        except Exception:
            pass

        terrain_info = ""
        cost_data = ""

        try:
            from app.core.vector_store import VectorStoreService
            vs = VectorStoreService(self.db)
            terrain_results = await vs.search_similar_cases(query="地形特征 断面", top_k=1)
            if terrain_results:
                terrain_info = str(terrain_results[0].get("design_params", ""))
        except Exception:
            pass

        try:
            from sqlalchemy import select
            from app.models.cost_estimate import CostEstimate
            stmt = (
                select(CostEstimate)
                .where(CostEstimate.project_id == _current_project_id.get())
                .order_by(CostEstimate.version.desc())
                .limit(1)
            )
            result = await self.db.execute(stmt)
            estimate = result.scalar_one_or_none()
            if estimate:
                cost_data = f"总造价 {estimate.total_cost:.2f} 万元"
        except Exception:
            pass

        revision_context = ""
        if revision_note:
            revision_context = f"\n\n【用户修改意见】：{revision_note}\n请根据修改意见重新生成内容。"

        prompt = f"""你是一位资深水利工程师，负责生成水利工程可行性研究报告的章节内容。

【项目信息】
- 项目名称：{project_info.name}
- 项目地点：{project_info.location}
- 工程规模：{project_info.scale}
- 项目描述：{project_info.description}

【参考规范】
{specs_text}

【相似案例】结构与篇幅参考：
{cases_text}

【项目素材】
{materials_text}

【可用插图】（在描述工程布置时使用 ![描述](图片路径) 插入图片）：
{figures_text or "暂无插图"}

【地形信息】
{terrain_info or "暂无地形数据"}

【造价信息】
{cost_data or "暂无造价数据"}

【章节要求】
{template or f"请生成{chapter_name}的完整内容，包括必要的背景介绍、技术分析和建议。在描述工程布置时，请在合适位置使用 ![图](图片路径) 格式插入相关工程图片。"}
{revision_context}

请生成专业的技术报告内容，使用Markdown格式，确保内容准确、完整、可操作。
"""
        return prompt

    async def _detect_missing_info(
        self,
        content: str,
        chapter_name: str
    ) -> Optional[dict]:
        """检测内容中是否缺少必要信息，需要用户补充

        Returns:
            dict: {"type": str, "description": str} 或 None
        """
        # 简单的关键词检测
        missing_patterns = [
            ("terrain_data", ["地形", "断面", "高程", "地质"], "请提供地形断面数据或地质勘察资料"),
            ("image", ["如图", "见附图", "示意图", "布置图"], "请提供相关工程图纸或示意图"),
            ("specification", ["根据规范", "按照标准", "按GB"], "请提供相关规范的具体条文"),
            ("case", ["参考案例", "类似工程", "工程实例"], "请提供一个相似的工程案例作为参考"),
            ("material", ["待补充", "数据待定", "详见附件", "需提供", "未获取"], "该章节内容存在待补充数据，请上传相关项目资料（如勘察报告、水文数据、设计图纸等）"),
        ]

        content_lower = content.lower()

        for info_type, keywords, description in missing_patterns:
            # 检查关键词是否在需要补充的上下文中
            for kw in keywords:
                if kw in content:
                    # 检查周围是否有具体数据
                    import re
                    # 简单检查是否有数字或具体描述
                    if not re.search(r'\d+', content.split(kw)[-1][:100] if kw in content else ""):
                        return {"type": info_type, "description": description}

        return None

    async def render_interactive_report(
        self,
        task_id: uuid.UUID,
        project_info: ProjectInfo
    ) -> str:
        """渲染交互式生成的报告为Word文档"""
        task = interactive_task_queue.get_task(task_id)
        if not task:
            raise GenerationFailedException("任务不存在", "未找到任务")

        chapters = {}
        for name, ctx in task.chapters.items():
            chapters[name] = ctx.content

        output_dir = Path("uploads/reports")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{task_id}.docx"

        self.template_service.create_word_document(
            chapters=chapters,
            output_path=str(output_path),
            title=project_info.name
        )

        # 更新任务状态
        interactive_task_queue.set_completed(task_id)

        # 更新数据库
        db_task = await self._get_task(task_id)
        if db_task:
            db_task.status = "completed"
            db_task.output_path = str(output_path)
            db_task.progress = 100
            await self.db.commit()

        return str(output_path)