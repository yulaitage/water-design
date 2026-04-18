# 水利工程设计 AI 助手

Water Engineering Design AI Assistant — an intelligent co-pilot for levee, river regulation, and reservoir engineering projects.

## 功能特性

| 模块 | 功能 |
|------|------|
| **项目管理** | 河道整治、堤防等工程项目的全生命周期管理 |
| **地形数据解析** | CSV/DXF 格式地形文件上传，自动提取中心线、断面、高程范围、坡度分析 |
| **费用估算** | 基于计算规则的工程量自动统计，实时单价查询，分类汇总 |
| **AI 对话** | LangGraph ReAct Agent，多轮对话，工具调用（查规范、算费用、生报告） |
| **报告生成** | 基于知识库检索的 AI 辅助报告生成，Word 文档导出，支持修订历史 |
| **知识库** | 规范条文与历史案例管理，向量检索（pgvector），语义相似度匹配 |

## 技术栈

### 后端

| 层 | 技术 |
|---|------|
| 框架 | FastAPI + SQLAlchemy async |
| 数据库 | PostgreSQL 16 + pgvector (向量检索) |
| AI | LangChain + LangGraph, ChatOpenAI unified interface |
| 地理 | GeoAlchemy2 + PostGIS |
| 文档 | python-docx (Word), Jinja2 |

### 前端

| 层 | 技术 |
|---|------|
| 框架 | Vue 3 (Composition API + `<script setup>`) |
| 构建 | Vite 8 |
| 语言 | TypeScript |
| UI | Ant Design Vue 4 |
| 状态 | Pinia |
| HTTP | Axios + SSE 流式响应 |

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                     前端 (Vue 3)                     │
│  Projects │ Terrain │ Chat │ Cost │ Report │ KB   │
└────────────┬────────────────────────────────────────┘
             │ HTTP + SSE
┌────────────▼────────────────────────────────────────┐
│                   后端 (FastAPI)                    │
│  Projects │ Terrain │ Chat │ Cost │ Report │ KB  │
└────────────┬────────────────────────────────────────┘
             │
    ┌────────┼────────┐
    ▼        ▼        ▼
 ┌──────┐ ┌──────┐ ┌──────────┐
 │  DB  │ │ LLM  │ │ Embedding │
 │ pgvector │ │GPT-4o│ │ text-embedding │
 └──────┘ └──────┘ └──────────┘
```

## 项目结构

```
water-design/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API 路由
│   │   │   ├── projects.py   # 项目 CRUD
│   │   │   ├── terrain.py    # 地形上传解析
│   │   │   ├── chat.py       # AI 对话 (SSE)
│   │   │   ├── cost_estimation.py  # 费用估算
│   │   │   ├── reports.py    # 报告生成
│   │   │   ├── knowledge_base.py  # 知识库
│   │   │   └── unit_prices.py     # 单价管理
│   │   ├── core/
│   │   │   ├── calculation_engine.py  # 安全公式计算
│   │   │   ├── llm.py         # LLM 统一接口
│   │   │   ├── embeddings.py  # Embedding 接口
│   │   │   ├── vector_store.py # pgvector 检索
│   │   │   └── task_queue.py  # 异步任务队列
│   │   ├── models/            # SQLAlchemy 模型
│   │   ├── schemas/           # Pydantic 请求/响应模型
│   │   ├── services/          # 业务逻辑
│   │   └── prompts/          # AI 提示词模板
│   ├── alembic/               # 数据库迁移
│   └── tests/                 # 单元测试 (pytest)
├── frontend/
│   └── src/
│       ├── api/               # Axios API 客户端
│       ├── components/        # Vue 组件
│       ├── views/             # 页面
│       ├── stores/             # Pinia 状态
│       ├── composables/        # Vue composables
│       └── theme/             # Ant Design 主题
└── docker-compose.yml
```

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 16 + pgvector 扩展
- Docker Desktop（可选，用于完整容器化部署）

### 方式一：本地开发

**1. 克隆代码**
```bash
git clone https://github.com/yulaitage/water-design.git
cd water-design
```

**2. 配置环境变量**
```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入以下必填项：
#   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/waterdesign
#   LLM_API_KEY=sk-...       # OpenAI API Key
#   EMBEDDING_API_KEY=sk-... # Embedding API Key
#   API_KEY=your-secret-api-key  # 前端调用后端时使用
```

**3. 启动数据库**
```sql
-- 创建数据库
CREATE DATABASE waterdesign;

-- 启用 pgvector（需要先安装扩展）
CREATE EXTENSION IF NOT EXISTS vector;
```

**4. 运行后端**
```bash
cd backend
uv sync
uv run alembic upgrade head        # 执行数据库迁移
uv run uvicorn app.main:app --reload --port 8000
```

**5. 运行前端**
```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

### 方式二：Docker Compose（推荐）

**1. 配置环境变量**
```bash
cp backend/.env.example .env
# 必填项：
#   POSTGRES_PASSWORD=your-secure-password
#   LLM_API_KEY=sk-...
#   EMBEDDING_API_KEY=sk-...
#   API_KEY=your-secret-api-key
```

**2. 启动**
```bash
docker compose up --build
```

服务地址：
- 前端：http://localhost:80
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs

### 初始化知识库（可选）

系统启动后，通过 API 导入计算规则和单价数据：

```bash
# 导入计算规则
curl -X POST http://localhost:8000/api/v1/seed/rules \
  -H "X-API-Key: your-secret-api-key"

# 导入单价数据
curl -X POST http://localhost:8000/api/v1/seed/unit-prices \
  -H "X-API-Key: your-secret-api-key"
```

## 环境变量

### 后端

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `DATABASE_URL` | 是 | `postgresql+asyncpg://localhost/waterdesign` | 数据库连接串 |
| `LLM_API_KEY` | 是 | - | LLM API Key (OpenAI/Qwen/DeepSeek) |
| `LLM_BASE_URL` | 否 | `https://api.openai.com/v1` | LLM API Base URL |
| `LLM_MODEL` | 否 | `gpt-4o` | 模型名称 |
| `EMBEDDING_API_KEY` | 是 | - | Embedding API Key |
| `EMBEDDING_BASE_URL` | 否 | - | Embedding API Base URL |
| `EMBEDDING_MODEL` | 否 | `text-embedding-3-small` | Embedding 模型 |
| `API_KEY` | 是 | - | API 认证密钥（前端需在请求头中发送 `X-API-Key`） |
| `SQL_ECHO` | 否 | `false` | 是否打印 SQL 日志 |
| `POSTGRES_USER` | Docker | `waterdesign` | Docker 中的数据库用户名 |
| `POSTGRES_PASSWORD` | Docker | - | **必填**，数据库密码 |

### 前端

| 变量 | 说明 |
|------|------|
| `VITE_API_KEY` | 与后端 `API_KEY` 保持一致 |

## API 文档

启动后端后访问 http://localhost:8000/docs（Swagger UI）

所有 API 请求需要在 header 中携带：
```
X-API-Key: your-secret-api-key
```

### 核心端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/projects` | 项目列表 |
| `POST` | `/api/v1/projects` | 创建项目 |
| `POST` | `/api/v1/projects/{id}/terrain` | 上传地形文件 |
| `POST` | `/api/v1/projects/{id}/cost-estimates` | 创建费用估算 |
| `POST` | `/api/v1/chat?stream=true` | SSE 流式对话 |
| `POST` | `/api/v1/projects/{id}/reports` | 创建报告生成任务 |
| `GET` | `/api/v1/knowledge-base/specifications` | 规范列表 |
| `POST` | `/api/v1/knowledge-base/specifications` | 添加规范条文 |

## 测试

```bash
cd backend
uv run pytest tests/ -v
```

当前测试覆盖：46 个测试，全部通过。

## 许可证

MIT
