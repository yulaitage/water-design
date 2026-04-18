import logging
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Optional, Dict, List
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

_current_project_id: ContextVar[uuid.UUID] = ContextVar("_current_project_id")
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

            # 检索规范和案例
            specs, cases = await self._retrieve_knowledge(
                project_info=project_info
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
                    project_info=project_info
                )
                chapters[chapter_name] = content

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

            return output_path

        except Exception as e:
            task_queue.update_task(task_id, status=TaskStatus.FAILED, error=str(e))
            await self._update_task_status(task, status="failed", error_message=str(e))
            raise GenerationFailedException(chapter=task.current_chapter or "未知", reason=str(e))

    async def _retrieve_knowledge(self, project_info: ProjectInfo) -> tuple:
        """检索知识库"""
        specs, cases = [], []

        try:
            specs, cases = await self.retrieval_service.retrieve_for_chapter(
                chapter="工程设计",
                project_type=self._infer_project_type(project_info),
                location=project_info.location
            )
        except Exception as e:
            logger.warning("Knowledge retrieval failed, continuing with empty results: %s", e)

        return specs, cases

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