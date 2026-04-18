import asyncio
import uuid
from typing import Dict, Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    id: uuid.UUID
    name: str
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    current_step: str = ""
    result: Any = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskQueue:
    """简单的内存任务队列"""

    def __init__(self):
        self._tasks: Dict[uuid.UUID, Task] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._workers: list = []

    def create_task(self, name: str) -> uuid.UUID:
        task_id = uuid.uuid4()
        task = Task(id=task_id, name=name)
        self._tasks[task_id] = task
        self._queue.put_nowait(task_id)
        return task_id

    def get_task(self, task_id: uuid.UUID) -> Optional[Task]:
        return self._tasks.get(task_id)

    def update_task(
        self,
        task_id: uuid.UUID,
        status: TaskStatus = None,
        progress: int = None,
        current_step: str = None,
        result: Any = None,
        error: str = None
    ) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return

        if status is not None:
            task.status = status
            if status == TaskStatus.RUNNING:
                task.started_at = datetime.now(timezone.utc)()
            elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                task.completed_at = datetime.now(timezone.utc)()

        if progress is not None:
            task.progress = progress
        if current_step is not None:
            task.current_step = current_step
        if result is not None:
            task.result = result
        if error is not None:
            task.error = error

    async def process_task(self, task_id: uuid.UUID, handler: Callable) -> Any:
        task = self._tasks.get(task_id)
        if not task:
            return None

        try:
            self.update_task(task_id, status=TaskStatus.RUNNING)
            result = await handler(task_id)
            self.update_task(task_id, status=TaskStatus.COMPLETED, progress=100, result=result)
            return result
        except Exception as e:
            self.update_task(task_id, status=TaskStatus.FAILED, error=str(e))
            raise


# 全局任务队列实例
task_queue = TaskQueue()