# 设计报告生成模块设计方案

> **模块**: 设计报告生成（Design Report Generation）
> **日期**: 2026-04-11
> **状态**: 已通过评审
> **下一步**: writing-plans

---

## 1. 模块定位

MVP第二阶段实现的模块。根据用户上传的项目资料，检索知识库（规范条文+历史案例），生成完整Word格式设计报告，支持修订版机制。

---

## 2. 架构概览

### 2.1 报告生成流程

```
用户上传项目资料
        ↓
项目创建（基本信息录入）
        ↓
选择报告类型（可行性报告/初步设计）
        ↓
结构化RAG检索
  ├─ 规范条文检索（按GB/T章节索引）
  └─ 历史案例检索（向量+元数据过滤）
        ↓
模板驱动章节生成
  ├─ 第1章 工程概况
  ├─ 第2章 工程必要性
  ├─ 第3章 工程任务与规模
  ├─ 第4章 工程布置
  ├─ 第5章 设计方案
  └─ ...
        ↓
Jinja2模板渲染 → Word文档
        ↓
异步任务状态查询
```

### 2.2 修订版流程

```
用户提交修改意见
  ├─ 表单：选择章节 + 修改类型 + 描述
  └─ 自然语言：自由描述修改需求
        ↓
AI解析修改意见 → 重新生成对应章节
        ↓
生成修订版V2，覆盖原章节
        ↓
保留完整修订历史（V1→V2→V3...）
```

---

## 3. 知识库设计

### 3.1 规范条文存储

```python
class Specification(Base):
    id: UUID
    name: str                    # 规范名称（如《堤防工程设计规范》）
    code: str                    # 规范编号（GB/T 502xx-2018）
    chapter: str                 # 章节（如"3.1 基本规定"）
    section: str                 # 条款编号（如"3.1.2"）
    content: str                 # Markdown格式条款内容
    content_embedding: Vector     # 向量（1536维，可配置）
    project_types: List[str]     # 适用工程类型

    created_at: datetime
```

### 3.2 历史案例存储

```python
class Case(Base):
    id: UUID
    name: str                    # 项目名称
    project_type: str            # 工程类型（河道整治/堤防/水库等）
    location: str                # 地理位置
    owner: str                   # 业主单位
    report_path: str             # 原始报告文件路径（Markdown）
    summary: str                  # AI提取的设计摘要
    summary_embedding: Vector     # 摘要向量
    design_params: JSONB          # 设计参数（流量、堤高、坡比等）

    created_at: datetime
```

### 3.3 检索策略

| 知识类型 | 检索方式 |
|----------|----------|
| 规范条文 | 向量相似度 + 工程类型过滤 + 章节排序 |
| 历史案例 | 向量相似度 + 项目类型 + 地理位置 |

---

## 4. 报告模板结构

### 4.1 可行性研究报告模板

```
1. 项目概述
   1.1 项目背景
   1.2 编制依据
   1.3 工程范围
2. 工程建设的必要性
   2.1 项目由来
   2.2 现状存在的主要问题
   2.3 项目建设的必要性
3. 工程任务与规模
   3.1 防洪标准
   3.2 工程规模
4. 工程总体布置
   4.1 防洪总体方案
   4.2 河道整治方案
5. 工程设计
   5.1 堤防设计
   5.2 护岸设计
   5.3 穿堤建筑物
6. 工程管理
7. 施工组织设计
8. 投资估算
9. 经济评价
10. 结论与建议
```

---

## 5. 数据结构

### 5.1 ReportTask 模型

```python
class ReportTask(Base):
    id: UUID
    project_id: UUID
    report_type: str             # "feasibility" | "preliminary_design"
    status: str                  # "pending" | "retrieving" | "generating" | "completed" | "failed"
    version: int                 # 修订版本号（从1开始）
    chapters: JSONB              # 各章节内容及来源追溯
    output_path: str             # Word文件路径
    error_message: str           # 失败原因
    progress: int                # 进度百分比
    current_chapter: str         # 当前生成章节

    created_at: datetime
    updated_at: datetime
```

### 5.2 ReportRevision 模型

```python
class ReportRevision(Base):
    id: UUID
    report_task_id: UUID
    version: int                  # 修订版本号
    revision_type: str           # "form" | "natural_language"
    user_input: str              # 原始修改意见
    modified_chapters: List[str]  # 被修改的章节列表
    ai_interpretation: str       # AI对修改意见的理解
    created_at: datetime
```

### 5.3 RevisionInput Schema

```python
# 表单输入
class FormRevisionInput(BaseModel):
    chapters: List[str]          # 要修改的章节
    modification_type: str        # "补充" | "修改" | "删除"
    description: str             # 修改描述

# 自然语言输入
class NaturalLanguageRevisionInput(BaseModel):
    content: str                 # 自然语言修改意见
```

---

## 6. API设计

### 6.1 创建报告任务

```
POST /api/v1/projects/{project_id}/reports
Content-Type: application/json

{
    "report_type": "feasibility" | "preliminary_design",
    "project_info": {
        "name": "XX河道整治工程",
        "location": "浙江省杭州市",
        "owner": "XX水务局",
        "scale": "河道长度20km，堤防加固15km",
        "description": "项目背景描述..."
    }
}

Response 202:
{
    "task_id": "uuid",
    "status": "pending",
    "report_type": "feasibility"
}
```

### 6.2 查询生成状态

```
GET /api/v1/reports/{task_id}/status
Response 200:
{
    "task_id": "uuid",
    "status": "generating",
    "progress": 65,
    "current_chapter": "第5章 工程设计",
    "version": 1,
    "error": null
}
```

### 6.3 下载报告

```
GET /api/v1/reports/{task_id}/download
Response 200: Word文件流 (application/vnd.openxmlformats-officedocument.wordprocessingml.document)
```

### 6.4 提交修订意见

```
POST /api/v1/reports/{task_id}/revisions

// 表单方式
{
    "revision_type": "form",
    "chapters": ["第3章 工程任务与规模"],
    "modification_type": "补充",
    "description": "需补充设计流量的计算过程"
}

// 自然语言方式
{
    "revision_type": "natural_language",
    "content": "请在第3章补充设计流量的计算过程，并增加水文分析依据"
}

Response 202:
{
    "revision_id": "uuid",
    "version": 2,
    "status": "pending"
}
```

### 6.5 查看修订历史

```
GET /api/v1/reports/{task_id}/revisions
Response 200:
{
    "revisions": [
        {
            "version": 1,
            "created_at": "2026-04-11T10:00:00Z",
            "revision_type": null,
            "user_input": null
        },
        {
            "version": 2,
            "created_at": "2026-04-11T11:00:00Z",
            "revision_type": "natural_language",
            "user_input": "请在第3章补充设计流量的计算过程"
        }
    ]
}
```

---

## 7. 错误处理

### 7.1 错误类型

| 错误码 | HTTP状态码 | 说明 |
|--------|------------|------|
| KNOWLEDGE_BASE_EMPTY | 422 | 知识库为空，需先导入规范和案例 |
| RETRIEVAL_FAILED | 200 | 检索失败，降级为无RAG生成 |
| TEMPLATE_NOT_FOUND | 500 | 报告模板不存在 |
| GENERATION_FAILED | 500 | 生成失败，返回具体章节错误 |
| INVALID_REVISION | 400 | 修订意见无效 |

### 7.2 错误响应格式

```json
{
    "error": {
        "code": "KNOWLEDGE_BASE_EMPTY",
        "message": "知识库为空，无法生成报告",
        "details": {},
        "suggestion": "请先导入规范条文和历史案例"
    }
}
```

---

## 8. 知识库摄入流程

```
多格式文档（PDF/Word/TXT）
        ↓
AI读取 + 格式转换 → Markdown
        ↓
结构化提取
├─ 规范条文：章节编号 + 条款内容 + 适用工程类型
└─ 历史案例：项目元数据 + 设计摘要 + 设计参数
        ↓
向量嵌入 + 存储PostgreSQL
```

---

## 9. 技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 向量模型 | text-embedding-3-small | 成本低，1536维可配置 |
| 规范存储 | 按GB/T章节结构 | 与水利行业标准对齐 |
| 案例过滤 | 类型+地理位置 | 行业最关注这两个维度 |
| 报告格式 | Jinja2+python-docx | 专业格式，支持目录生成 |
| 任务队列 | 内存队列+数据库持久化 | MVP阶段简化实现 |
| 修订机制 | V1→V2→V3版本链 | 保留完整修改历史 |

---

## 10. 依赖项

- **后端**: FastAPI, SQLAlchemy, pgvector, python-docx, Jinja2, LiteLLM
- **数据库**: PostgreSQL + pgvector
- **前端**: Ant Design Vue表单组件

---

## 11. TODO

- [ ] writing-plans - 拆解实现任务
- [ ] subagent-driven-development - 执行开发
