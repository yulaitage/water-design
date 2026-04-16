# 工程量统计与费用估算模块 + AI对话助手设计方案

> **模块**: 工程量统计与费用估算 + AI对话助手
> **日期**: 2026-04-16
> **状态**: 已通过评审
> **下一步**: writing-plans

---

## 1. 模块定位

**工程量统计**：可行性研究阶段快速估算。根据设计参数+地形数据，自动统计工程量并估算费用。

**AI对话助手**：完整对话助手，多轮对话、记忆上下文、调用工具、生成回复。

两个模块协同工作：用户可通过对话触发各模块功能。

---

## 2. 架构概览

### 2.1 整体架构

```
用户对话
        ↓
意图识别（Intent Detection）
        ↓
Agent编排层
  ├─ 地形导入模块调用
  ├─ 设计报告生成调用
  ├─ 工程量统计与费用估算调用
  └─ CAD出图调用
        ↓
对话记忆存储（PostgreSQL + pgvector）
        ↓
结构化输出
  ├─ Excel/Word报告
  └─ 实时对话回复
```

### 2.2 对话Agent数据流

```
用户: "帮我分析这个河道整治项目，需要多少投资？"
        ↓
意图识别: PROJECT_ANALYSIS
        ↓
提取项目信息 → 调用工程量估算 → 生成报告
        ↓
记忆存储（对话历史 + 项目上下文）
        ↓
回复: "根据设计参数，初步估算投资约XXX万元..."
```

---

## 3. 工程量统计模块设计

### 3.1 数据结构

**计算规则模型**

```python
class CalculationRule(Base):
    id: UUID
    project_type: str       # "堤防" | "河道整治"
    item_category: str    # "土方工程" | "护岸工程"
    item_name: str        # "土方开挖" | "土方填筑"
    formula: str          # "length * height * slope_ratio * coefficient"
    unit: str             # "m³" | "m²"
    params: JSONB         # 参数定义
    created_at: datetime
```

**单价表模型**

```python
class UnitPrice(Base):
    id: UUID
    item_name: str        # "土方开挖"
    unit: str              # "m³"
    price: float           # 12.5 元/m³
    region: str            # "浙江省"
    year: int              # 2024
    source: str            # "user_import" | "knowledge_base"
    created_at: datetime
```

**工程量估算结果模型**

```python
class CostEstimate(Base):
    id: UUID
    project_id: UUID
    version: int
    status: str            # "draft" | "confirmed"

    # 设计参数
    design_params: JSONB

    # 分类汇总
    summary: JSONB         # {土方工程: 125000m³, 护岸工程: 8500m², ...}

    # 分项明细
    details: JSONB         # [{category, item, quantity, unit, unit_price, subtotal}, ...]

    # 总价
    total_cost: float
    cost_per_km: float    # 万元/km

    output_excel_path: str
    output_word_path: str

    created_at: datetime
```

### 3.2 API设计

```
POST   /api/v1/projects/{project_id}/cost-estimates
GET    /api/v1/projects/{project_id}/cost-estimates
GET    /api/v1/cost-estimates/{estimate_id}
POST   /api/v1/cost-estimates/{estimate_id}/recalculate
GET    /api/v1/cost-estimates/{estimate_id}/excel
POST   /api/v1/unit-prices/import
GET    /api/v1/unit-prices
```

### 3.3 核心计算规则

| 工程类别 | 计算项目 | 计算公式 |
|----------|----------|----------|
| 堤防工程 | 土方开挖 | V = H × (B + m×H) × L |
| 堤防工程 | 土方填筑 | V = H × (B + m×H) × L × 1.05 |
| 护岸工程 | 护坡砼 | S = L × √(H² + (m×H)²) |
| 护岸工程 | 垫层 | S = L × √(H² + (m×H)²) × 0.1 |
| 穿堤建筑物 | 防洪闸 | 单价 × 孔数 × 孔径系数 |

---

## 4. AI对话助手设计

### 4.1 数据结构

**Conversation模型**

```python
class Conversation(Base):
    id: UUID
    project_id: UUID
    messages: JSONB     # [{role, content, timestamp, tool_calls}]
    embedding: Vector  # 对话向量（用于检索相似对话）
    created_at: datetime
```

### 4.2 意图识别

```python
INTENTS = [
    "PROJECT_CREATE",      # 创建项目
    "TERRAIN_UPLOAD",     # 上传地形
    "REPORT_GENERATE",     # 生成报告
    "COST_ESTIMATE",     # 费用估算
    "CAD_GENERATE",       # CAD出图
    "GENERAL_CHAT"       # 一般对话
]
```

### 4.3 Agent Orchestrator

```python
class AgentOrchestrator:
    def __init__(self, llm, tools, memory_service):
        self.llm = llm
        self.tools = tools
        self.memory = memory_service

    async def process(self, user_input, project_id):
        # 1. 检索相关记忆
        # 2. 识别意图
        # 3. 调用工具
        # 4. 存储对话
        # 5. 生成回复
```

### 4.4 API设计

```
POST   /api/v1/chat                    # 发送对话
GET    /api/v1/projects/{project_id}/conversations  # 获取对话历史
GET    /api/v1/conversations/{id}     # 获取单次对话详情
```

---

## 5. 技术决策

### 5.1 工程量统计

| 决策 | 选择 | 理由 |
|------|------|------|
| 规则存储 | 数据库JSONB | 配置化，支持热更新 |
| 单价来源 | 用户导入 + 知识库检索 | 灵活，适应不同地区 |
| 输出格式 | Excel + Word双格式 | 便于调整 + 直接嵌入报告 |
| 计算触发 | 可独立使用或嵌入报告生成 | 两种场景都支持 |

### 5.2 AI对话助手

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent框架 | 自建（LiteLLM + 自建编排） | 无新依赖，代码可控 |
| 记忆存储 | PostgreSQL + pgvector | 项目已有，技术栈统一 |
| 意图识别 | 规则匹配 + LLM分类 | 简单场景规则足够 |
| 工具调用 | API调用 | 各模块已实现REST API |

---

## 6. 文件结构

```
backend/
├── app/
│   ├── api/v1/
│   │   ├── chat.py              # 对话API
│   │   ├── cost_estimation.py   # 工程量估算API
│   │   └── unit_prices.py       # 单价管理API
│   ├── models/
│   │   ├── conversation.py      # Conversation模型
│   │   ├── calculation_rule.py  # 计算规则模型
│   │   ├── unit_price.py        # 单价模型
│   │   └── cost_estimate.py    # 估算结果模型
│   ├── schemas/
│   │   ├── chat.py
│   │   ├── cost_estimation.py
│   │   └── unit_price.py
│   ├── services/
│   │   ├── agent_orchestrator.py  # Agent编排
│   │   ├── intent_detection.py     # 意图识别
│   │   ├── cost_calculation.py     # 工程量计算
│   │   └── chat_service.py         # 对话服务
│   └── core/
│       └── calculation_engine.py    # 计算引擎
├── templates/
│   └── reports/
│       └── cost_estimate_template.md  # 费用估算Word模板
└── tests/
```

---

## 7. TODO

- [ ] writing-plans - 拆解实现任务
- [ ] subagent-driven-development - 执行开发
