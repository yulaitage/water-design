from enum import Enum


class ReportPhase(str, Enum):
    """报告生成阶段"""
    IDLE = "idle"
    RETRIEVING = "retrieving"
    BUILDING_FRAMEWORK = "building_framework"
    CHAPTER_GENERATING = "chapter_generating"
    AWAITING_CONFIRM = "awaiting_confirm"
    NEEDS_INPUT = "needs_input"
    COMPLETED = "completed"
    FAILED = "failed"


class ChapterState(str, Enum):
    """章节状态"""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETE = "complete"
    REVISION = "revision"
    WAITING_CONFIRM = "waiting_confirm"
    NEEDS_DATA = "needs_data"


class InputRequestType(str, Enum):
    """用户输入请求类型"""
    TERRAIN_DATA = "terrain_data"
    IMAGE = "image"
    DOCUMENT = "document"
    SPECIFICATION = "specification"
    CASE = "case"
    OTHER = "other"
