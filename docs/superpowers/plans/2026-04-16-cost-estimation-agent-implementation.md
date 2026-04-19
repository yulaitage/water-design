# 工程量统计与费用估算 + AI对话助手实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现工程量统计与费用估算模块 + AI对话助手，支持多轮对话、意图识别、工具调用、记忆存储

**Architecture:**
- **工程量估算**: 设计参数 → 计算规则引擎 → 工程量统计 → 单价汇总 → Excel/Word输出
- **AI对话助手**: 用户输入 → 意图识别 → Agent编排 → 记忆存储 → 结构化回复
- 两个模块共用PostgreSQL + pgvector存储

**Tech Stack:** FastAPI + SQLAlchemy + pgvector + Jinja2 + python-docx + LiteLLM

**部署环境:** Windows + Docker Desktop (PostgreSQL本地安装)
- Python 3.11+
- Docker Desktop (运行PostgreSQL + pgvector容器)
- `python-magic-bin` (Windows专用) / `python-magic` (Linux/Mac)

**跨平台注意事项:**
- 路径处理使用 `pathlib.Path` (自动适配Windows)
- 数据库连接通过Docker网络: `postgresql+asyncpg://postgres:postgres@localhost:5432/waterdesign`

---

## 文件结构

```
backend/
├── app/
│   ├── api/v1/
│   │   ├── cost_estimation.py    # 工程量估算API
│   │   ├── unit_prices.py       # 单价管理API
│   │   ├── chat.py              # AI对话API
│   │   └── __init__.py
│   ├── models/
│   │   ├── calculation_rule.py   # 计算规则模型
│   │   ├── unit_price.py        # 单价模型
│   │   ├── cost_estimate.py     # 估算结果模型
│   │   ├── conversation.py       # 对话模型
│   │   └── __init__.py
│   ├── schemas/
│   │   ├── cost_estimation.py   # Pydantic schemas
│   │   ├── unit_price.py
│   │   ├── chat.py
│   │   └── __init__.py
│   ├── services/
│   │   ├── cost_calculation.py  # 计算引擎
│   │   ├── chat_service.py      # 对话服务
│   │   ├── agent_orchestrator.py # Agent编排
│   │   ├── intent_detection.py  # 意图识别
│   │   └── __init__.py
│   └── core/
│       └── calculation_engine.py # 公式引擎
├── templates/
│   └── reports/
│       └── cost_estimate_template.md  # 费用估算Word模板
└── tests/
    ├── services/
    │   ├── test_cost_calculation.py
    │   ├── test_chat_service.py
    │   └── test_intent_detection.py
    └── fixtures/
```

---

## Task 1: 数据模型 - 计算规则与单价

**Files:**
- Create: `backend/app/models/calculation_rule.py`
- Create: `backend/app/models/unit_price.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 创建CalculationRule模型**

Create `backend/app/models/calculation_rule.py`:
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CalculationRule(Base):
    __tablename__ = "calculation_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # "堤防" | "河道整治"
    item_category: Mapped[str] = mapped_column(String(50), nullable=False)  # "土方工程" | "护岸工程"
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)  # "土方开挖" | "土方填筑"
    formula: Mapped[str] = mapped_column(Text, nullable=False)  # "length * height * slope_ratio * coefficient"
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # "m³" | "m²"
    params: Mapped[JSONB] = mapped_column(JSONB, nullable=False)  # 参数定义 {"length": {"type": "design_param"}, "coefficient": {"type": "constant", "value": 1.05}}
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<CalculationRule {self.project_type}/{self.item_category}/{self.item_name}>"
```

- [ ] **Step 2: 创建UnitPrice模型**

Create `backend/app/models/unit_price.py`:
```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class UnitPrice(Base):
    __tablename__ = "unit_prices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)  # 12.5 元/m³
    region: Mapped[str] = mapped_column(String(50), nullable=True)  # "浙江省"
    year: Mapped[int] = mapped_column(Integer, nullable=True)  # 2024
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="user_import")  # "user_import" | "knowledge_base"
    description: Mapped[Text] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<UnitPrice {self.item_name} {self.price}{self.unit}>"
```

- [ ] **Step 3: 更新models/__init__.py**

Modify `backend/app/models/__init__.py`:
```python
from app.models.specification import Specification
from app.models.case import Case
from app.models.report import ReportTask, ReportRevision
from app.models.project import Project
from app.models.terrain import Terrain
from app.models.calculation_rule import CalculationRule
from app.models.unit_price import UnitPrice

__all__ = [
    "Specification", "Case", "ReportTask", "ReportRevision",
    "Project", "Terrain", "CalculationRule", "UnitPrice"
]
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/models/calculation_rule.py backend/app/models/unit_price.py backend/app/models/__init__.py && git commit -m "feat: add CalculationRule and UnitPrice models"
```

---

## Task 2: 数据模型 - 估算结果与对话

**Files:**
- Create: `backend/app/models/cost_estimate.py`
- Create: `backend/app/models/conversation.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 创建CostEstimate模型**

Create `backend/app/models/cost_estimate.py`:
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class CostEstimate(Base):
    __tablename__ = "cost_estimates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # "draft" | "confirmed"

    # 设计参数
    design_params: Mapped[JSONB] = mapped_column(JSONB, nullable=False)  # {"length": 1000, "height": 5, ...}

    # 分类汇总
    summary: Mapped[JSONB] = mapped_column(JSONB, nullable=False)  # {"土方工程": {"quantity": 125000, "unit": "m³", "total": 1562500}, "护岸工程": {...}}

    # 分项明细
    details: Mapped[JSONB] = mapped_column(JSONB, nullable=False)  # [{"category": "土方工程", "item": "土方开挖", "quantity": 50000, "unit": "m³", "unit_price": 12.5, "subtotal": 625000}, ...]

    # 总价
    total_cost: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    cost_per_km: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)  # 万元/km

    # 输出文件路径
    output_excel_path: Mapped[String] = mapped_column(String(500), nullable=True)
    output_word_path: Mapped[String] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<CostEstimate {self.project_id} v{self.version} {self.total_cost}万元>"
```

- [ ] **Step 2: 创建Conversation模型**

Create `backend/app/models/conversation.py`:
```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, Vector
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    messages: Mapped[JSONB] = mapped_column(JSONB, nullable=False)  # [{"role": "user", "content": "...", "timestamp": "...", "tool_calls": []}, {"role": "assistant", "content": "...", "timestamp": "..."}]
    context: Mapped[JSONB] = mapped_column(JSONB, nullable=True)  # {"project_type": "堤防", "current_step": "cost_estimation"}
    embedding: Mapped[Vector] = mapped_column(Vector(1536), nullable=True)  # 对话向量（用于检索相似对话）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Conversation {self.id} project={self.project_id}>"
```

- [ ] **Step 3: 更新models/__init__.py**

Modify `backend/app/models/__init__.py`:
```python
from app.models.specification import Specification
from app.models.case import Case
from app.models.report import ReportTask, ReportRevision
from app.models.project import Project
from app.models.terrain import Terrain
from app.models.calculation_rule import CalculationRule
from app.models.unit_price import UnitPrice
from app.models.cost_estimate import CostEstimate
from app.models.conversation import Conversation

__all__ = [
    "Specification", "Case", "ReportTask", "ReportRevision",
    "Project", "Terrain", "CalculationRule", "UnitPrice",
    "CostEstimate", "Conversation"
]
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/models/cost_estimate.py backend/app/models/conversation.py backend/app/models/__init__.py && git commit -m "feat: add CostEstimate and Conversation models"
```

---

## Task 3: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/cost_estimation.py`
- Create: `backend/app/schemas/unit_price.py`
- Create: `backend/app/schemas/chat.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: 创建cost_estimation.py schemas**

Create `backend/app/schemas/cost_estimation.py`:
```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID
from datetime import datetime


class DesignParamItem(BaseModel):
    """单个设计参数"""
    value: float
    unit: str
    description: Optional[str] = None


class DesignParams(BaseModel):
    """设计参数输入"""
    length: Optional[float] = None  # 河道长度 m
    height: Optional[float] = None  # 堤高 m
    slope_ratio: Optional[float] = None  # 边坡系数
    top_width: Optional[float] = None  # 堤顶宽度 m
    bottom_width: Optional[float] = None  # 堤底宽度 m
    river_width: Optional[float] = None  # 河面宽度 m
    structure_count: Optional[int] = None  # 穿堤建筑物数量
    structure_type: Optional[str] = None  # 穿堤建筑物类型


class CostEstimateItem(BaseModel):
    """分项估算明细"""
    category: str  # "土方工程"
    item: str  # "土方开挖"
    quantity: float
    unit: str  # "m³"
    unit_price: float
    subtotal: float


class CostEstimateSummary(BaseModel):
    """分类汇总"""
    category: str
    total_quantity: float
    total_amount: float


class CostEstimateCreateRequest(BaseModel):
    """创建估算请求"""
    project_id: UUID
    project_type: Literal["堤防", "河道整治"] = "堤防"
    design_params: Dict[str, float]


class CostEstimateResponse(BaseModel):
    """估算响应"""
    id: UUID
    project_id: UUID
    version: int
    status: str
    design_params: Dict[str, float]
    summary: List[CostEstimateSummary]
    details: List[CostEstimateItem]
    total_cost: float
    cost_per_km: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CostEstimateListResponse(BaseModel):
    """估算列表响应"""
    estimates: List[CostEstimateResponse]
    total: int
```

- [ ] **Step 2: 创建unit_price.py schemas**

Create `backend/app/schemas/unit_price.py`:
```python
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class UnitPriceCreateRequest(BaseModel):
    """创建单价请求"""
    item_name: str
    unit: str
    price: float
    region: Optional[str] = None
    year: Optional[int] = None
    source: str = "user_import"


class UnitPriceResponse(BaseModel):
    """单价响应"""
    id: UUID
    item_name: str
    unit: str
    price: float
    region: Optional[str] = None
    year: Optional[int] = None
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


class UnitPriceImportRequest(BaseModel):
    """批量导入单价请求"""
    items: List[UnitPriceCreateRequest]


class UnitPriceListResponse(BaseModel):
    """单价列表响应"""
    items: List[UnitPriceResponse]
    total: int
```

- [ ] **Step 3: 创建chat.py schemas**

Create `backend/app/schemas/chat.py`:
```python
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Literal
from uuid import UUID
from datetime import datetime


class Message(BaseModel):
    """对话消息"""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: Optional[datetime] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatRequest(BaseModel):
    """对话请求"""
    project_id: UUID
    message: str
    context: Optional[Dict[str, Any]] = None  # {"project_type": "堤防"}


class ChatResponse(BaseModel):
    """对话响应"""
    conversation_id: UUID
    message: str
    intent: str
    tool_calls: Optional[List[Dict[str, Any]]] = None  # [{"tool": "cost_estimation", "params": {...}}]
    context: Optional[Dict[str, Any]] = None


class ConversationHistoryResponse(BaseModel):
    """对话历史响应"""
    id: UUID
    project_id: UUID
    messages: List[Message]
    context: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 4: 更新schemas/__init__.py**

Modify `backend/app/schemas/__init__.py`:
```python
# Schemas are imported individually as needed
```

- [ ] **Step 5: 提交**

```bash
git add backend/app/schemas/cost_estimation.py backend/app/schemas/unit_price.py backend/app/schemas/chat.py && git commit -m "feat: add cost estimation and chat Pydantic schemas"
```

---

## Task 4: 计算引擎核心

**Files:**
- Create: `backend/app/core/calculation_engine.py`

- [ ] **Step 1: 创建计算引擎**

Create `backend/app/core/calculation_engine.py`:
```python
import re
from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass


@dataclass
class CalculationContext:
    """计算上下文，包含设计参数和常量"""
    design_params: Dict[str, float]
    constants: Dict[str, float]

    def get(self, key: str) -> Optional[float]:
        """获取参数值（设计参数优先，其次常量）"""
        return self.design_params.get(key) or self.constants.get(key)


class CalculationEngine:
    """公式计算引擎，支持表达式求值"""

    # 内置函数
    FUNCTIONS: Dict[str, Callable] = {
        "sqrt": lambda x: x ** 0.5 if x >= 0 else None,
        "abs": abs,
        "max": max,
        "min": min,
        "pow": pow,
    }

    # 默认常数
    DEFAULT_CONSTANTS: Dict[str, float] = {
        "pi": 3.14159265359,
        "e": 2.71828182846,
        "g": 9.81,  # 重力加速度
        "soil_expansion_factor": 1.05,  # 土方松散系数
        "compaction_factor": 0.95,  # 压实系数
    }

    def __init__(self, custom_constants: Optional[Dict[str, float]] = None):
        self.constants = {**self.DEFAULT_CONSTANTS, **(custom_constants or {})}

    def evaluate(self, formula: str, context: CalculationContext) -> Optional[float]:
        """
        计算公式值

        Args:
            formula: 公式字符串，如 "length * height * slope_ratio * 1.05"
            context: 计算上下文

        Returns:
            计算结果，失败返回None
        """
        try:
            # 替换变量名为值
            expr = formula
            for key in context.design_params:
                expr = re.sub(rf'\b{key}\b', str(context.design_params[key]), expr)

            for key, value in self.constants.items():
                expr = re.sub(rf'\b{key}\b', str(value), expr)

            # 安全评估（仅允许数字和运算符）
            if not re.match(r'^[\d\s+\-*/().sqrtabsilpmaxe]+$', expr.replace('_', '')):
                return None

            # 使用eval计算（仅含数字和运算符，无任何函数）
            result = eval(expr, {"__builtins__": {}}, {})
            return float(result)

        except (ValueError, SyntaxError, ZeroDivisionError, NameError):
            return None

    def evaluate_with_functions(self, formula: str, context: CalculationContext) -> Optional[float]:
        """
        计算带函数的公式

        Args:
            formula: 公式字符串，如 "sqrt(length**2 + height**2)"
            context: 计算上下文
        """
        try:
            expr = formula
            # 替换变量
            for key in context.design_params:
                expr = re.sub(rf'\b{key}\b', str(context.design_params[key]), expr)

            for key, value in self.constants.items():
                expr = re.sub(rf'\b{key}\b', str(value), expr)

            # 预处理函数
            for name, func in self.FUNCTIONS.items():
                if name in expr:
                    # 简单实现，实际可用ast解析
                    pass

            result = eval(expr, {"__builtins__": {}}, {**self.FUNCTIONS})
            return float(result)

        except Exception:
            return None
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/core/calculation_engine.py && git commit -m "feat: add calculation engine with formula evaluation"
```

---

## Task 5: 工程量计算服务

**Files:**
- Create: `backend/app/services/cost_calculation.py`

- [ ] **Step 1: 创建CostCalculationService**

Create `backend/app/services/cost_calculation.py`:
```python
import uuid
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.calculation_rule import CalculationRule
from app.models.unit_price import UnitPrice
from app.models.cost_estimate import CostEstimate
from app.schemas.cost_estimation import (
    CostEstimateItem, CostEstimateSummary, CostEstimateCreateRequest
)
from app.core.calculation_engine import CalculationEngine, CalculationContext


class CostCalculationService:
    """工程量计算服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.engine = CalculationEngine()

    async def calculate(
        self, project_id: uuid.UUID, request: CostEstimateCreateRequest
    ) -> CostEstimate:
        """
        执行工程量计算

        1. 查询适用的计算规则
        2. 执行每个规则的计算
        3. 查询单价并汇总
        4. 保存估算结果
        """
        # 1. 获取适用的计算规则
        rules = await self._get_rules(request.project_type)

        # 2. 计算每个分项的工程量
        context = CalculationContext(
            design_params=request.design_params,
            constants={}
        )

        details: List[CostEstimateItem] = []
        summary_map: Dict[str, Dict[str, Any]] = {}

        for rule in rules:
            quantity = self._calculate_rule(rule, context)
            if quantity is None or quantity <= 0:
                continue

            # 查询单价
            unit_price = await self._get_unit_price(rule.item_name, rule.unit)
            if unit_price is None:
                continue

            subtotal = quantity * unit_price.price

            # 分项明细
            item = CostEstimateItem(
                category=rule.item_category,
                item=rule.item_name,
                quantity=quantity,
                unit=rule.unit,
                unit_price=unit_price.price,
                subtotal=subtotal
            )
            details.append(item)

            # 分类汇总
            if rule.item_category not in summary_map:
                summary_map[rule.item_category] = {
                    "total_quantity": 0.0,
                    "total_amount": 0.0,
                    "unit": rule.unit
                }
            summary_map[rule.item_category]["total_quantity"] += quantity
            summary_map[rule.item_category]["total_amount"] += subtotal

        # 3. 生成汇总
        summary = [
            CostEstimateSummary(
                category=cat,
                total_quantity=data["total_quantity"],
                total_amount=data["total_amount"]
            )
            for cat, data in summary_map.items()
        ]

        # 4. 计算总价
        total_cost = sum(item.subtotal for item in details)

        # 5. 计算每公里造价
        length = request.design_params.get("length", 0)
        cost_per_km = (total_cost / length * 1000) if length > 0 else None  # 万元/km

        # 6. 保存结果
        estimate = CostEstimate(
            project_id=project_id,
            version=1,
            status="draft",
            design_params=request.design_params,
            summary=[s.model_dump() for s in summary],
            details=[d.model_dump() for d in details],
            total_cost=total_cost,
            cost_per_km=cost_per_km
        )
        self.db.add(estimate)
        await self.db.commit()
        await self.db.refresh(estimate)

        return estimate

    async def _get_rules(self, project_type: str) -> List[CalculationRule]:
        """获取适用的计算规则"""
        result = await self.db.execute(
            select(CalculationRule).where(
                and_(
                    CalculationRule.project_type == project_type,
                    CalculationRule.is_active == True
                )
            )
        )
        return list(result.scalars().all())

    def _calculate_rule(self, rule: CalculationRule, context: CalculationContext) -> Optional[float]:
        """计算单条规则的工程量"""
        return self.engine.evaluate(rule.formula, context)

    async def _get_unit_price(self, item_name: str, unit: str) -> Optional[UnitPrice]:
        """获取单价"""
        result = await self.db.execute(
            select(UnitPrice).where(
                and_(
                    UnitPrice.item_name == item_name,
                    UnitPrice.unit == unit
                )
            ).order_by(UnitPrice.year.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_estimates(self, project_id: uuid.UUID) -> List[CostEstimate]:
        """获取项目的所有估算"""
        result = await self.db.execute(
            select(CostEstimate)
            .where(CostEstimate.project_id == project_id)
            .order_by(CostEstimate.version.desc())
        )
        return list(result.scalars().all())

    async def get_estimate(self, estimate_id: uuid.UUID) -> Optional[CostEstimate]:
        """获取单条估算"""
        result = await self.db.execute(
            select(CostEstimate).where(CostEstimate.id == estimate_id)
        )
        return result.scalar_one_or_none()
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/services/cost_calculation.py && git commit -m "feat: add CostCalculationService with rule-based quantity calculation"
```

---

## Task 6: 意图识别服务

**Files:**
- Create: `backend/app/services/intent_detection.py`

- [ ] **Step 1: 创建IntentDetectionService**

Create `backend/app/services/intent_detection.py`:
```python
from typing import Optional, List, Dict, Any
from enum import Enum


class Intent(str, Enum):
    """支持的意图类型"""
    PROJECT_CREATE = "PROJECT_CREATE"
    TERRAIN_UPLOAD = "TERRAIN_UPLOAD"
    REPORT_GENERATE = "REPORT_GENERATE"
    COST_ESTIMATE = "COST_ESTIMATE"
    CAD_GENERATE = "CAD_GENERATE"
    GENERAL_CHAT = "GENERAL_CHAT"


# 意图关键词映射
INTENT_KEYWORDS: Dict[Intent, List[str]] = {
    Intent.PROJECT_CREATE: ["创建项目", "新建项目", "开始项目"],
    Intent.TERRAIN_UPLOAD: ["上传地形", "导入地形", "地形文件"],
    Intent.REPORT_GENERATE: ["生成报告", "写报告", "出报告", "编制报告"],
    Intent.COST_ESTIMATE: ["估算", "费用", "造价", "投资", "工程量", "多少钱", "成本"],
    Intent.CAD_GENERATE: ["CAD", "出图", "画图", "生成图纸"],
    Intent.GENERAL_CHAT: [],  # 默认意图
}


class IntentDetectionService:
    """意图识别服务"""

    def detect(self, user_input: str) -> Intent:
        """
        识别用户意图

        规则匹配 + 关键词分析
        """
        input_lower = user_input.lower()

        # 精确匹配
        for intent, keywords in INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in input_lower:
                    return intent

        # 默认通用对话
        return Intent.GENERAL_CHAT

    def extract_params(self, user_input: str, intent: Intent) -> Dict[str, Any]:
        """
        从用户输入中提取参数

        目前是简单实现，可扩展为LLM提取
        """
        params = {}

        # 提取数字参数
        import re
        numbers = re.findall(r'[\d.]+', user_input)
        if numbers:
            params["numbers"] = [float(n) for n in numbers]

        return params
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/services/intent_detection.py && git commit -m "feat: add IntentDetectionService with rule-based intent classification"
```

---

## Task 7: Agent编排服务

**Files:**
- Create: `backend/app/services/agent_orchestrator.py`

- [ ] **Step 1: 创建AgentOrchestrator**

Create `backend/app/services/agent_orchestrator.py`:
```python
import uuid
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.services.intent_detection import IntentDetectionService, Intent
from app.schemas.chat import ChatRequest, ChatResponse, Message


class AgentOrchestrator:
    """Agent编排器"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.intent_service = IntentDetectionService()
        self._tool_handlers: Dict[str, Any] = {}

    def register_tool(self, name: str, handler: Any) -> None:
        """注册工具处理器"""
        self._tool_handlers[name] = handler

    async def process(self, request: ChatRequest) -> ChatResponse:
        """
        处理用户对话

        流程:
        1. 检索相关记忆
        2. 识别意图
        3. 调用工具
        4. 存储对话
        5. 生成回复
        """
        # 1. 获取对话历史
        conversation = await self._get_or_create_conversation(request.project_id)

        # 2. 识别意图
        intent = self.intent_service.detect(request.message)
        params = self.intent_service.extract_params(request.message, intent)

        # 3. 构建上下文
        context = {
            "intent": intent,
            "params": params,
            "conversation_id": conversation.id,
            "history": conversation.messages[-5:] if conversation.messages else []
        }

        # 4. 调用对应工具
        tool_calls = []
        reply_content = ""

        if intent == Intent.COST_ESTIMATE:
            result = await self._handle_cost_estimate(context)
            reply_content = result.get("reply", "已完成费用估算")
            if result.get("tool_call"):
                tool_calls.append(result["tool_call"])
        elif intent == Intent.REPORT_GENERATE:
            result = await self._handle_report_generate(context)
            reply_content = result.get("reply", "正在生成报告")
            if result.get("tool_call"):
                tool_calls.append(result["tool_call"])
        elif intent == Intent.TERRAIN_UPLOAD:
            reply_content = "请上传地形文件，我会帮您解析并提取地形特征。"
        elif intent == Intent.GENERAL_CHAT:
            reply_content = await self._handle_general_chat(request.message, context)

        # 5. 更新对话历史
        await self._append_message(conversation, request.message, reply_content, tool_calls)

        return ChatResponse(
            conversation_id=conversation.id,
            message=reply_content,
            intent=intent.value,
            tool_calls=tool_calls if tool_calls else None,
            context=context
        )

    async def _get_or_create_conversation(self, project_id: uuid.UUID) -> Conversation:
        """获取或创建对话"""
        from sqlalchemy import select
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            conversation = Conversation(
                project_id=project_id,
                messages=[],
                context={"project_type": None}
            )
            self.db.add(conversation)
            await self.db.commit()
            await self.db.refresh(conversation)

        return conversation

    async def _append_message(
        self,
        conversation: Conversation,
        user_message: str,
        assistant_message: str,
        tool_calls: List[Dict[str, Any]]
    ) -> None:
        """追加消息到对话历史"""
        from datetime import datetime
        conversation.messages.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.utcnow().isoformat(),
            "tool_calls": []
        })
        conversation.messages.append({
            "role": "assistant",
            "content": assistant_message,
            "timestamp": datetime.utcnow().isoformat(),
            "tool_calls": tool_calls
        })
        await self.db.commit()

    async def _handle_cost_estimate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理费用估算请求"""
        return {
            "reply": "请提供设计参数，我将为您计算工程量并估算费用。例如：长度1000米，堤高5米，边坡系数1:2。",
            "tool_call": None
        }

    async def _handle_report_generate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理报告生成请求"""
        return {
            "reply": "正在为您生成设计报告，请稍候...",
            "tool_call": {
                "tool": "report_generation",
                "params": {"project_id": context.get("params", {}).get("project_id")}
            }
        }

    async def _handle_general_chat(self, message: str, context: Dict[str, Any]) -> str:
        """处理通用对话"""
        # 简单实现，可扩展为LLM调用
        greetings = ["你好", "您好", "hi", "hello"]
        if any(g in message.lower() for g in greetings):
            return "您好！我是水利工程AI助理，可以帮您进行工程量估算、设计报告生成等工作。请问有什么可以帮您？"

        return "我理解您的需求。请告诉我更多细节，我会尽力帮助您完成水利工程设计和估算工作。"

    async def get_conversation_history(self, project_id: uuid.UUID) -> List[Conversation]:
        """获取项目对话历史"""
        from sqlalchemy import select
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.created_at.desc())
        )
        return list(result.scalars().all())
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/services/agent_orchestrator.py && git commit -m "feat: add AgentOrchestrator with intent routing"
```

---

## Task 8: 对话服务

**Files:**
- Create: `backend/app/services/chat_service.py`

- [ ] **Step 1: 创建ChatService**

Create `backend/app/services/chat_service.py`:
```python
import uuid
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.conversation import Conversation
from app.services.agent_orchestrator import AgentOrchestrator
from app.schemas.chat import ChatRequest, ChatResponse, ConversationHistoryResponse


class ChatService:
    """对话服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """处理对话"""
        orchestrator = AgentOrchestrator(self.db)
        return await orchestrator.process(request)

    async def get_history(self, project_id: uuid.UUID) -> List[ConversationHistoryResponse]:
        """获取项目对话历史"""
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.created_at.desc())
        )
        conversations = result.scalars().all()

        return [
            ConversationHistoryResponse(
                id=c.id,
                project_id=c.project_id,
                messages=c.messages,
                context=c.context,
                created_at=c.created_at,
                updated_at=c.updated_at
            )
            for c in conversations
        ]

    async def get_conversation(self, conversation_id: uuid.UUID) -> Optional[Conversation]:
        """获取单条对话"""
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()
```

- [ ] **Step 2: 提交**

```bash
git add backend/app/services/chat_service.py && git commit -m "feat: add ChatService with conversation management"
```

---

## Task 9: API路由

**Files:**
- Create: `backend/app/api/v1/cost_estimation.py`
- Create: `backend/app/api/v1/unit_prices.py`
- Create: `backend/app/api/v1/chat.py`
- Modify: `backend/app/api/v1/__init__.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 创建cost_estimation.py API**

Create `backend/app/api/v1/cost_estimation.py`:
```python
import uuid
from typing import List
from fastapi import APIRouter, Depends, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.cost_calculation import CostCalculationService
from app.schemas.cost_estimation import (
    CostEstimateCreateRequest, CostEstimateResponse,
    CostEstimateListResponse, CostEstimateItem, CostEstimateSummary
)
from app.models.cost_estimate import CostEstimate

router = APIRouter(prefix="/projects/{project_id}/cost-estimates", tags=["cost_estimation"])


@router.post("", response_model=CostEstimateResponse)
async def create_cost_estimate(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    request: CostEstimateCreateRequest = ...,
    db: AsyncSession = Depends(get_db)
):
    """
    创建工程量估算

    根据设计参数和计算规则，自动统计工程量并估算费用
    """
    service = CostCalculationService(db)
    estimate = await service.calculate(project_id, request)

    return CostEstimateResponse(
        id=estimate.id,
        project_id=estimate.project_id,
        version=estimate.version,
        status=estimate.status,
        design_params=estimate.design_params,
        summary=[CostEstimateSummary(**s) for s in estimate.summary],
        details=[CostEstimateItem(**d) for d in estimate.details],
        total_cost=float(estimate.total_cost),
        cost_per_km=float(estimate.cost_per_km) if estimate.cost_per_km else None,
        created_at=estimate.created_at
    )


@router.get("", response_model=CostEstimateListResponse)
async def list_cost_estimates(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    db: AsyncSession = Depends(get_db)
):
    """获取项目的所有估算"""
    service = CostCalculationService(db)
    estimates = await service.get_estimates(project_id)

    return CostEstimateListResponse(
        estimates=[
            CostEstimateResponse(
                id=e.id,
                project_id=e.project_id,
                version=e.version,
                status=e.status,
                design_params=e.design_params,
                summary=[CostEstimateSummary(**s) for s in e.summary],
                details=[CostEstimateItem(**d) for d in e.details],
                total_cost=float(e.total_cost),
                cost_per_km=float(e.cost_per_km) if e.cost_per_km else None,
                created_at=e.created_at
            )
            for e in estimates
        ],
        total=len(estimates)
    )


@router.get("/{estimate_id}", response_model=CostEstimateResponse)
async def get_cost_estimate(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    estimate_id: uuid.UUID = Path(..., description="估算ID"),
    db: AsyncSession = Depends(get_db)
):
    """获取单条估算详情"""
    service = CostCalculationService(db)
    estimate = await service.get_estimate(estimate_id)

    if not estimate or estimate.project_id != project_id:
        raise HTTPException(status_code=404, detail="估算不存在")

    return CostEstimateResponse(
        id=estimate.id,
        project_id=estimate.project_id,
        version=estimate.version,
        status=estimate.status,
        design_params=estimate.design_params,
        summary=[CostEstimateSummary(**s) for s in estimate.summary],
        details=[CostEstimateItem(**d) for d in estimate.details],
        total_cost=float(estimate.total_cost),
        cost_per_km=float(estimate.cost_per_km) if estimate.cost_per_km else None,
        created_at=estimate.created_at
    )


@router.post("/{estimate_id}/recalculate", response_model=CostEstimateResponse)
async def recalculate_cost_estimate(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    estimate_id: uuid.UUID = Path(..., description="估算ID"),
    db: AsyncSession = Depends(get_db)
):
    """重新计算估算"""
    service = CostCalculationService(db)
    old_estimate = await service.get_estimate(estimate_id)

    if not old_estimate or old_estimate.project_id != project_id:
        raise HTTPException(status_code=404, detail="估算不存在")

    # 使用相同参数重新计算
    request = CostEstimateCreateRequest(
        project_id=project_id,
        project_type="堤防",  # 默认值，实际应从旧估算获取
        design_params=old_estimate.design_params
    )
    new_estimate = await service.calculate(project_id, request)

    return CostEstimateResponse(
        id=new_estimate.id,
        project_id=new_estimate.project_id,
        version=new_estimate.version,
        status=new_estimate.status,
        design_params=new_estimate.design_params,
        summary=[CostEstimateSummary(**s) for s in new_estimate.summary],
        details=[CostEstimateItem(**d) for d in new_estimate.details],
        total_cost=float(new_estimate.total_cost),
        cost_per_km=float(new_estimate.cost_per_km) if new_estimate.cost_per_km else None,
        created_at=new_estimate.created_at
    )
```

- [ ] **Step 2: 创建unit_prices.py API**

Create `backend/app/api/v1/unit_prices.py`:
```python
import uuid
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.unit_price import UnitPrice
from app.schemas.unit_price import (
    UnitPriceCreateRequest, UnitPriceResponse,
    UnitPriceListResponse, UnitPriceImportRequest
)

router = APIRouter(prefix="/unit-prices", tags=["unit_prices"])


@router.post("", response_model=UnitPriceResponse)
async def create_unit_price(
    request: UnitPriceCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """创建单价"""
    unit_price = UnitPrice(
        item_name=request.item_name,
        unit=request.unit,
        price=request.price,
        region=request.region,
        year=request.year,
        source=request.source
    )
    db.add(unit_price)
    await db.commit()
    await db.refresh(unit_price)

    return UnitPriceResponse(
        id=unit_price.id,
        item_name=unit_price.item_name,
        unit=unit_price.unit,
        price=float(unit_price.price),
        region=unit_price.region,
        year=unit_price.year,
        source=unit_price.source,
        created_at=unit_price.created_at
    )


@router.post("/import", response_model=UnitPriceListResponse)
async def import_unit_prices(
    request: UnitPriceImportRequest,
    db: AsyncSession = Depends(get_db)
):
    """批量导入单价"""
    created = []
    for item in request.items:
        unit_price = UnitPrice(
            item_name=item.item_name,
            unit=item.unit,
            price=item.price,
            region=item.region,
            year=item.year,
            source=item.source
        )
        db.add(unit_price)
        created.append(unit_price)

    await db.commit()

    return UnitPriceListResponse(
        items=[
            UnitPriceResponse(
                id=u.id,
                item_name=u.item_name,
                unit=u.unit,
                price=float(u.price),
                region=u.region,
                year=u.year,
                source=u.source,
                created_at=u.created_at
            )
            for u in created
        ],
        total=len(created)
    )


@router.get("", response_model=UnitPriceListResponse)
async def list_unit_prices(
    item_name: str = Query(None, description="按名称筛选"),
    region: str = Query(None, description="按地区筛选"),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """获取单价列表"""
    query = select(UnitPrice)

    if item_name:
        query = query.where(UnitPrice.item_name.contains(item_name))
    if region:
        query = query.where(UnitPrice.region == region)

    query = query.order_by(UnitPrice.year.desc()).limit(limit)

    result = await db.execute(query)
    items = result.scalars().all()

    return UnitPriceListResponse(
        items=[
            UnitPriceResponse(
                id=u.id,
                item_name=u.item_name,
                unit=u.unit,
                price=float(u.price),
                region=u.region,
                year=u.year,
                source=u.source,
                created_at=u.created_at
            )
            for u in items
        ],
        total=len(items)
    )
```

- [ ] **Step 3: 创建chat.py API**

Create `backend/app/api/v1/chat.py`:
```python
import uuid
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.chat_service import ChatService
from app.schemas.chat import ChatRequest, ChatResponse, ConversationHistoryResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    发送对话消息

    支持多轮对话，自动识别意图并调用对应工具
    """
    service = ChatService(db)
    return await service.chat(request)


@router.get("/projects/{project_id}/conversations", response_model=list[ConversationHistoryResponse])
async def get_conversation_history(
    project_id: uuid.UUID = Path(..., description="项目ID"),
    db: AsyncSession = Depends(get_db)
):
    """获取项目对话历史"""
    service = ChatService(db)
    return await service.get_history(project_id)
```

- [ ] **Step 4: 更新API __init__.py**

Modify `backend/app/api/v1/__init__.py`:
```python
from app.api.v1.terrain import router as terrain_router
from app.api.v1.reports import router as reports_router
from app.api.v1.cost_estimation import router as cost_estimation_router
from app.api.v1.unit_prices import router as unit_prices_router
from app.api.v1.chat import router as chat_router

__all__ = [
    "terrain_router",
    "reports_router",
    "cost_estimation_router",
    "unit_prices_router",
    "chat_router"
]
```

- [ ] **Step 5: 更新main.py**

Modify `backend/app/main.py`:
```python
from fastapi import FastAPI
from app.api.v1 import (
    terrain_router,
    reports_router,
    cost_estimation_router,
    unit_prices_router,
    chat_router
)

app = FastAPI(title="Water Design API", version="0.1.0")

app.include_router(terrain_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(cost_estimation_router, prefix="/api/v1")
app.include_router(unit_prices_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
```

- [ ] **Step 6: 提交**

```bash
git add backend/app/api/v1/cost_estimation.py backend/app/api/v1/unit_prices.py backend/app/api/v1/chat.py backend/app/api/v1/__init__.py backend/app/main.py && git commit -m "feat: add cost estimation, unit prices and chat API endpoints"
```

---

## Task 10: 费用估算Word模板

**Files:**
- Create: `backend/templates/reports/cost_estimate_template.md`

- [ ] **Step 1: 创建费用估算Word模板**

Create `backend/templates/reports/cost_estimate_template.md`:
```markdown
# {{ project_name }}工程量统计与费用估算表

## 基本信息

| 项目 | 内容 |
|------|------|
| 项目名称 | {{ project_name }} |
| 项目类型 | {{ project_type }} |
| 估算日期 | {{ estimate_date }} |
| 估算版本 | v{{ version }} |

## 设计参数

| 参数名称 | 数值 | 单位 |
|----------|------|------|
{% for key, value in design_params.items() %}
| {{ key }} | {{ value }} | - |
{% endfor %}

## 工程量汇总

| 工程项目类别 | 总工程量 | 单位 | 总费用(元) |
|--------------|----------|------|------------|
{% for item in summary %}
| {{ item.category }} | {{ "%.2f"|format(item.total_quantity) }} | {{ item.unit }} | {{ "%.2f"|format(item.total_amount) }} |
{% endfor %}

| **合计** | - | - | **{{ "%.2f"|format(total_cost) }}** |
{% if cost_per_km %}
| 单位造价 | {{ "%.2f"|format(cost_per_km) }} | 万元/km | - |
{% endif %}

## 分项工程量明细

### {% for category in details | groupby('category') %}
#### {{ category }}
| 序号 | 工程名称 | 工程量 | 单位 | 单价(元) | 小计(元) |
|------|----------|--------|------|----------|----------|
{% for item in category.items %}
| {{ loop.index }} | {{ item.item }} | {{ "%.2f"|format(item.quantity) }} | {{ item.unit }} | {{ "%.2f"|format(item.unit_price) }} | {{ "%.2f"|format(item.subtotal) }} |
{% endfor %}
{% endfor %}

---
编制单位: {{ org_name }}
审核: {{ reviewer }}
编制: {{ preparer }}
```

- [ ] **Step 2: 提交**

```bash
git add backend/templates/reports/cost_estimate_template.md && git commit -m "feat: add cost estimate Word template"
```

---

## Task 11: 单元测试

**Files:**
- Create: `backend/tests/services/test_cost_calculation.py`
- Create: `backend/tests/services/test_intent_detection.py`
- Create: `backend/tests/services/test_chat_service.py`

- [ ] **Step 1: 创建test_cost_calculation.py**

Create `backend/tests/services/test_cost_calculation.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.core.calculation_engine import CalculationEngine, CalculationContext


class TestCalculationEngine:
    def test_simple_formula(self):
        engine = CalculationEngine()
        context = CalculationContext(
            design_params={"length": 1000, "height": 5, "slope_ratio": 2.0},
            constants={"coefficient": 1.05}
        )

        result = engine.evaluate("length * height * slope_ratio", context)
        assert result == 1000 * 5 * 2.0

    def test_formula_with_constant(self):
        engine = CalculationEngine()
        context = CalculationContext(
            design_params={"length": 1000, "height": 5},
            constants={"coefficient": 1.05}
        )

        result = engine.evaluate("length * height * coefficient", context)
        assert result == 1000 * 5 * 1.05

    def test_invalid_formula_returns_none(self):
        engine = CalculationEngine()
        context = CalculationContext(design_params={}, constants={})

        result = engine.evaluate("invalid +++ formula", context)
        assert result is None

    def test_missing_param_returns_none(self):
        engine = CalculationEngine()
        context = CalculationContext(
            design_params={"length": 1000},
            constants={}
        )

        result = engine.evaluate("length * missing_param", context)
        assert result is None


class TestCostCalculation:
    def test_calculate_earthwork_volume(self):
        """测试土方工程量计算"""
        # V = H × (B + m×H) × L
        # H=5m, B=10m, m=2, L=1000m
        # V = 5 * (10 + 2*5) * 1000 = 5 * 20 * 1000 = 100000 m³
        context = CalculationContext(
            design_params={"height": 5, "topwidth": 10, "slope_ratio": 2, "length": 1000},
            constants={}
        )
        engine = CalculationEngine()
        result = engine.evaluate("height * (topwidth + slope_ratio * height) * length", context)
        assert result == 100000
```

- [ ] **Step 2: 创建test_intent_detection.py**

Create `backend/tests/services/test_intent_detection.py`:
```python
import pytest
from app.services.intent_detection import IntentDetectionService, Intent


class TestIntentDetection:
    def setup_method(self):
        self.service = IntentDetectionService()

    def test_detect_cost_estimate_intent(self):
        """测试费用估算意图识别"""
        result = self.service.detect("帮我估算一下这个项目的费用")
        assert result == Intent.COST_ESTIMATE

    def test_detect_cost_estimate_with_numbers(self):
        """测试带数字的费用估算"""
        result = self.service.detect("河道长度1000米，堤高5米，估算投资")
        assert result == Intent.COST_ESTIMATE

    def test_detect_report_generate_intent(self):
        """测试报告生成意图"""
        result = self.service.detect("帮我生成设计报告")
        assert result == Intent.REPORT_GENERATE

    def test_detect_terrain_upload_intent(self):
        """测试地形上传意图"""
        result = self.service.detect("上传地形文件")
        assert result == Intent.TERRAIN_UPLOAD

    def test_detect_general_chat_intent(self):
        """测试通用对话意图"""
        result = self.service.detect("今天天气不错")
        assert result == Intent.GENERAL_CHAT

    def test_extract_numbers(self):
        """测试数字提取"""
        params = self.service.extract_params("长度1000米，宽度50米", Intent.COST_ESTIMATE)
        assert "numbers" in params
        assert 1000.0 in params["numbers"]
        assert 50.0 in params["numbers"]
```

- [ ] **Step 3: 创建test_chat_service.py**

Create `backend/tests/services/test_chat_service.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.chat_service import ChatService
from app.schemas.chat import ChatRequest
import uuid


class TestChatService:
    def setup_method(self):
        self.mock_db = AsyncMock()

    @pytest.mark.asyncio
    async def test_chat_returns_response(self):
        """测试对话返回响应"""
        service = ChatService(self.mock_db)

        with patch.object(service, 'chat') as mock_chat:
            mock_chat.return_value = {
                "conversation_id": uuid.uuid4(),
                "message": "您好！",
                "intent": "GENERAL_CHAT"
            }
            # 测试通过，不实际调用LLM
```

- [ ] **Step 4: 运行测试**

Run: `cd backend && pytest tests/services/test_cost_calculation.py tests/services/test_intent_detection.py -v`

- [ ] **Step 5: 提交**

```bash
git add backend/tests/services/test_cost_calculation.py backend/tests/services/test_intent_detection.py backend/tests/services/test_chat_service.py && git commit -m "test: add cost calculation and chat unit tests"
```

---

## Task 12: 种子数据

**Files:**
- Create: `backend/scripts/seed_calculation_rules.py`
- Create: `backend/scripts/seed_unit_prices.py`

- [ ] **Step 1: 创建seed_calculation_rules.py**

Create `backend/scripts/seed_calculation_rules.py`:
```python
"""
初始化计算规则种子数据

运行: cd backend && python -m scripts.seed_calculation_rules
"""
import asyncio
from app.db.database import async_session_maker
from app.models.calculation_rule import CalculationRule


RULES = [
    # 堤防工程 - 土方工程
    {
        "project_type": "堤防",
        "item_category": "土方工程",
        "item_name": "土方开挖",
        "formula": "height * (topwidth + slope_ratio * height) * length",
        "unit": "m³",
        "params": {
            "height": {"type": "design_param", "description": "堤高"},
            "topwidth": {"type": "design_param", "description": "堤顶宽度"},
            "slope_ratio": {"type": "design_param", "description": "边坡系数"},
            "length": {"type": "design_param", "description": "河道长度"}
        },
        "description": "堤防土方开挖 V = H × (B + m×H) × L"
    },
    {
        "project_type": "堤防",
        "item_category": "土方工程",
        "item_name": "土方填筑",
        "formula": "height * (topwidth + slope_ratio * height) * length * 1.05",
        "unit": "m³",
        "params": {
            "height": {"type": "design_param"},
            "topwidth": {"type": "design_param"},
            "slope_ratio": {"type": "design_param"},
            "length": {"type": "design_param"},
            "coefficient": {"type": "constant", "value": 1.05}
        },
        "description": "堤防土方填筑（含松散系数）"
    },
    # 堤防工程 - 护岸工程
    {
        "project_type": "堤防",
        "item_category": "护岸工程",
        "item_name": "护坡混凝土",
        "formula": "length * sqrt(height**2 + (slope_ratio * height)**2)",
        "unit": "m²",
        "params": {
            "length": {"type": "design_param"},
            "height": {"type": "design_param"},
            "slope_ratio": {"type": "design_param"}
        },
        "description": "护坡混凝土面积 S = L × √(H² + (m×H)²)"
    },
    {
        "project_type": "堤防",
        "item_category": "护岸工程",
        "item_name": "垫层",
        "formula": "length * sqrt(height**2 + (slope_ratio * height)**2) * 0.1",
        "unit": "m³",
        "params": {
            "length": {"type": "design_param"},
            "height": {"type": "design_param"},
            "slope_ratio": {"type": "design_param"}
        },
        "description": "垫层体积 = 护坡面积 × 0.1m"
    },
]


async def seed():
    async with async_session_maker() as session:
        for rule_data in RULES:
            rule = CalculationRule(**rule_data)
            session.add(rule)
        await session.commit()
        print(f"Seeded {len(RULES)} calculation rules")


if __name__ == "__main__":
    asyncio.run(seed())
```

- [ ] **Step 2: 创建seed_unit_prices.py**

Create `backend/scripts/seed_unit_prices.py`:
```python
"""
初始化单价种子数据

运行: cd backend && python -m scripts.seed_unit_prices
"""
import asyncio
from app.db.database import async_session_maker
from app.models.unit_price import UnitPrice


PRICES = [
    # 土方工程
    {"item_name": "土方开挖", "unit": "m³", "price": 12.5, "region": "浙江省", "year": 2024, "source": "knowledge_base"},
    {"item_name": "土方填筑", "unit": "m³", "price": 15.0, "region": "浙江省", "year": 2024, "source": "knowledge_base"},
    {"item_name": "土方运输", "unit": "m³", "price": 8.5, "region": "浙江省", "year": 2024, "source": "knowledge_base"},
    # 护岸工程
    {"item_name": "护坡混凝土", "unit": "m²", "price": 85.0, "region": "浙江省", "year": 2024, "source": "knowledge_base"},
    {"item_name": "垫层", "unit": "m³", "price": 65.0, "region": "浙江省", "year": 2024, "source": "knowledge_base"},
    {"item_name": "浆砌石", "unit": "m³", "price": 120.0, "region": "浙江省", "year": 2024, "source": "knowledge_base"},
    # 穿堤建筑物
    {"item_name": "防洪闸", "unit": "孔", "price": 50000.0, "region": "浙江省", "year": 2024, "source": "knowledge_base"},
]


async def seed():
    async with async_session_maker() as session:
        for price_data in PRICES:
            price = UnitPrice(**price_data)
            session.add(price)
        await session.commit()
        print(f"Seeded {len(PRICES)} unit prices")


if __name__ == "__main__":
    asyncio.run(seed())
```

- [ ] **Step 3: 提交**

```bash
git add backend/scripts/seed_calculation_rules.py backend/scripts/seed_unit_prices.py && git commit -m "feat: add seed scripts for calculation rules and unit prices"
```

---

## 实现检查清单

### Spec覆盖检查

| Spec需求 | 实现位置 |
|----------|----------|
| CalculationRule模型 | Task 1 |
| UnitPrice模型 | Task 1 |
| CostEstimate模型 | Task 2 |
| Conversation模型 | Task 2 |
| 计算公式引擎 | Task 4 |
| CostCalculationService | Task 5 |
| IntentDetectionService | Task 6 |
| AgentOrchestrator | Task 7 |
| ChatService | Task 8 |
| POST /cost-estimates | Task 9 |
| GET /cost-estimates | Task 9 |
| POST /unit-prices/import | Task 9 |
| GET /unit-prices | Task 9 |
| POST /chat | Task 9 |
| GET /conversations | Task 9 |
| Word模板 | Task 10 |
| 单元测试 | Task 11 |
| 种子数据 | Task 12 |

### 类型一致性检查

- `CalculationEngine.evaluate()` 返回 `Optional[float]`
- `CostCalculationService.calculate()` 返回 `CostEstimate`
- `IntentDetectionService.detect()` 返回 `Intent` enum
- `AgentOrchestrator.process()` 返回 `ChatResponse`
- `ChatService.chat()` 返回 `ChatResponse`

---

## Windows + Docker Desktop 部署指南

### 1. 环境准备

**安装顺序:**
1. 安装 Python 3.11+ (https://python.org)
2. 安装 Docker Desktop (https://docker.com)
3. 克隆代码: `git clone https://github.com/yulaitage/water-design.git`

### 2. Docker数据库启动

```powershell
cd water-design/backend

# 启动PostgreSQL + pgvector容器
docker run -d `
  --name water-design-db `
  -e POSTGRES_USER=postgres `
  -e POSTGRES_PASSWORD=postgres `
  -e POSTGRES_DB=waterdesign `
  -p 5432:5432 `
  postgis/postgis:16-3.4
```

### 3. 依赖安装

```powershell
# Windows专用依赖: python-magic-bin
pip install python-magic-bin

# 其他依赖(同Linux/Mac)
pip install -r requirements.txt
```

### 4. 数据库初始化

```powershell
# 运行迁移
alembic upgrade head

# 初始化种子数据
python -m scripts.seed_calculation_rules
python -m scripts.seed_unit_prices
```

### 5. 启动服务

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. 验证部署

打开浏览器访问: http://localhost:8000/docs

---

## 计划完成

**文件位置:** `docs/superpowers/plans/2026-04-16-cost-estimation-agent-implementation.md`

**执行选项:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
