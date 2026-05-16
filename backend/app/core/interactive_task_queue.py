import asyncio
import uuid
import json
from typing import Dict, List, Optional, Any, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.report_state import ReportPhase, ChapterState, InputRequestType


@dataclass
class InputRequest:
    """用户输入请求"""
    info_type: InputRequestType
    description: str
    examples: List[str] = field(default_factory=list)
    provided: bool = False
    provided_content: Optional[str] = None


@dataclass
class ChapterContext:
    """章节上下文"""
    name: str
    index: int
    status: ChapterState = ChapterState.PENDING
    content: str = ""
    revision_count: int = 0
    confirmed: bool = False
    pending_inputs: List[InputRequest] = field(default_factory=list)
    revision_note: Optional[str] = None


@dataclass
class InteractiveReportTask:
    """交互式报告生成任务"""
    task_id: uuid.UUID
    project_id: uuid.UUID
    phase: ReportPhase = ReportPhase.IDLE
    current_chapter_index: int = 0
    chapters: Dict[str, ChapterContext] = field(default_factory=dict)
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

    # 事件用于暂停/继续
    pause_event: asyncio.Event = field(default_factory=asyncio.Event)
    continue_event: asyncio.Event = field(default_factory=asyncio.Event)
    input_event: asyncio.Event = field(default_factory=asyncio.Event)
    confirm_event: asyncio.Event = field(default_factory=asyncio.Event)

    # 当前生成的异步生成器
    current_generator: Optional[AsyncGenerator] = None

    # 知识库检索结果
    retrieved_specs: List[dict] = field(default_factory=list)
    retrieved_cases: List[dict] = field(default_factory=list)

    def get_current_chapter(self) -> Optional[ChapterContext]:
        if 0 <= self.current_chapter_index < len(self.chapters):
            return list(self.chapters.values())[self.current_chapter_index]
        return None

    def is_paused(self) -> bool:
        return self.pause_event.is_set() or self.input_event.is_set() or self.confirm_event.is_set()


class InteractiveTaskQueue:
    """交互式报告任务队列"""

    def __init__(self):
        self._tasks: Dict[uuid.UUID, InteractiveReportTask] = {}

    def create_task(self, project_id: uuid.UUID, chapter_names: List[str]) -> uuid.UUID:
        task_id = uuid.uuid4()
        chapters = {
            name: ChapterContext(name=name, index=i)
            for i, name in enumerate(chapter_names)
        }
        task = InteractiveReportTask(
            task_id=task_id,
            project_id=project_id,
            chapters=chapters
        )
        self._tasks[task_id] = task
        return task_id

    def get_task(self, task_id: uuid.UUID) -> Optional[InteractiveReportTask]:
        return self._tasks.get(task_id)

    def get_chapter_context(self, task_id: uuid.UUID, chapter_name: str) -> Optional[ChapterContext]:
        task = self._tasks.get(task_id)
        if task:
            return task.chapters.get(chapter_name)
        return None

    def update_phase(self, task_id: uuid.UUID, phase: ReportPhase):
        task = self._tasks.get(task_id)
        if task:
            task.phase = phase

    def update_chapter_status(
        self,
        task_id: uuid.UUID,
        chapter_name: str,
        status: ChapterState,
        content: Optional[str] = None
    ):
        task = self._tasks.get(task_id)
        if task and chapter_name in task.chapters:
            task.chapters[chapter_name].status = status
            if content is not None:
                task.chapters[chapter_name].content += content

    def append_chapter_content(self, task_id: uuid.UUID, chapter_name: str, content: str):
        task = self._tasks.get(task_id)
        if task and chapter_name in task.chapters:
            task.chapters[chapter_name].content += content

    def set_chapter_generating(self, task_id: uuid.UUID, chapter_index: int):
        task = self._tasks.get(task_id)
        if task:
            task.current_chapter_index = chapter_index
            task.phase = ReportPhase.CHAPTER_GENERATING
            chapters = list(task.chapters.values())
            if chapter_index < len(chapters):
                chapters[chapter_index].status = ChapterState.GENERATING

    async def wait_for_user_input(self, task_id: uuid.UUID) -> InputRequest:
        """等待用户提供输入"""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        task.phase = ReportPhase.NEEDS_INPUT
        chapter = task.get_current_chapter()
        if chapter and chapter.pending_inputs:
            input_req = chapter.pending_inputs[-1]
            await self.input_event.wait()
            self.input_event.clear()
            return input_req
        return InputRequest(info_type=InputRequestType.OTHER, description="等待用户输入")

    def provide_input(self, task_id: uuid.UUID, info_type: InputRequestType, content: str):
        """用户提供输入后继续"""
        task = self._tasks.get(task_id)
        if task:
            chapter = task.get_current_chapter()
            if chapter and chapter.pending_inputs:
                chapter.pending_inputs[-1].provided = True
                chapter.pending_inputs[-1].provided_content = content
            task.input_event.set()
            task.phase = ReportPhase.CHAPTER_GENERATING

    async def wait_for_confirmation(self, task_id: uuid.UUID) -> tuple[bool, Optional[str]]:
        """等待用户确认章节

        Returns:
            (confirmed, revision_note) - confirmed为True表示确认，为False表示需要修改
        """
        task = self._tasks.get(task_id)
        if not task:
            return False, "Task not found"

        task.phase = ReportPhase.AWAITING_CONFIRM
        chapter = task.get_current_chapter()
        if chapter:
            chapter.status = ChapterState.WAITING_CONFIRM

        await self.confirm_event.wait()
        self.confirm_event.clear()

        if chapter:
            return chapter.confirmed, chapter.revision_note
        return False, None

    def confirm_chapter(self, task_id: uuid.UUID, revision_note: Optional[str] = None):
        """用户确认章节"""
        task = self._tasks.get(task_id)
        if task:
            chapter = task.get_current_chapter()
            if chapter:
                chapter.confirmed = True
                chapter.status = ChapterState.COMPLETE
                chapter.revision_note = revision_note
            task.phase = ReportPhase.CHAPTER_GENERATING
            self.confirm_event.set()

    def request_revision(self, task_id: uuid.UUID, revision_note: str):
        """用户要求修改章节"""
        task = self._tasks.get(task_id)
        if task:
            chapter = task.get_current_chapter()
            if chapter:
                chapter.confirmed = False
                chapter.status = ChapterState.REVISION
                chapter.revision_note = revision_note
                chapter.revision_count += 1
                # 清空内容重新生成
                chapter.content = ""
            task.phase = ReportPhase.CHAPTER_GENERATING
            self.confirm_event.set()

    def add_pending_input(
        self,
        task_id: uuid.UUID,
        chapter_name: str,
        info_type: InputRequestType,
        description: str,
        examples: Optional[List[str]] = None
    ):
        """添加待处理的用户输入请求"""
        task = self._tasks.get(task_id)
        if task:
            chapter = task.chapters.get(chapter_name)
            if chapter:
                chapter.pending_inputs.append(InputRequest(
                    info_type=info_type,
                    description=description,
                    examples=examples or []
                ))

    def pause_for_input(self, task_id: uuid.UUID):
        """暂停等待用户输入"""
        task = self._tasks.get(task_id)
        if task:
            task.phase = ReportPhase.NEEDS_INPUT

    def resume(self, task_id: uuid.UUID):
        """继续生成"""
        task = self._tasks.get(task_id)
        if task:
            task.pause_event.set()

    def set_error(self, task_id: uuid.UUID, error: str):
        task = self._tasks.get(task_id)
        if task:
            task.phase = ReportPhase.FAILED
            task.error = error

    def set_completed(self, task_id: uuid.UUID):
        task = self._tasks.get(task_id)
        if task:
            task.phase = ReportPhase.COMPLETED

    def get_status(self, task_id: uuid.UUID) -> dict:
        """获取任务状态"""
        task = self._tasks.get(task_id)
        if not task:
            return {"status": "not_found"}

        chapters_status = {}
        for name, ctx in task.chapters.items():
            chapters_status[name] = {
                "status": ctx.status.value,
                "index": ctx.index,
                "confirmed": ctx.confirmed,
                "revision_count": ctx.revision_count,
                "pending_inputs": [
                    {"type": inp.info_type.value, "description": inp.description, "provided": inp.provided}
                    for inp in ctx.pending_inputs
                ]
            }

        current_chapter = task.get_current_chapter()

        return {
            "task_id": str(task.task_id),
            "project_id": str(task.project_id),
            "phase": task.phase.value,
            "current_chapter_index": task.current_chapter_index,
            "current_chapter": current_chapter.name if current_chapter else None,
            "chapters": chapters_status,
            "error": task.error,
        }


# 全局交互式任务队列
interactive_task_queue = InteractiveTaskQueue()
