# 地形数据导入模块设计方案

> **模块**: 地形数据导入（Terrain Import）
> **日期**: 2026-04-11
> **状态**: 已通过评审
> **下一步**: writing-plans

---

## 1. 模块定位

MVP第一个实现的模块。优先支持CSV和DXF格式，流式处理无大小限制，提取完整地形特征供后续AI校验使用。

---

## 2. 架构概览

```
用户上传文件 (CSV/DXF)
        ↓
    FastAPI 接收
        ↓
文件验证（大小/类型/魔数）
        ↓
流式解析（CSV流式读，DXF逐实体解析）
        ↓
提取地形特征
        ↓
存储PostGIS + 原始文件路径
        ↓
返回解析结果
```

---

## 3. 数据结构

### 3.1 Terrain 模型

```python
class Terrain(Base):
    id: UUID
    project_id: UUID
    file_path: str           # 原始文件路径
    file_type: str           # "CSV" | "DXF"
    status: str              # "pending" | "processing" | "completed" | "failed"
    error_message: str       # 解析失败原因

    # 解析后的特征（PostGIS存储）
    centerline: LineString   # 河道中心线
    cross_sections: JSONB    # 横断面数组
    elevation_range: JSONB   # [min, max, mean]
    slope_analysis: JSONB    # 坡度分析结果
    waterfront_line: LineString  # 规划岸线
    demolition_boundary: JSONB  # 动拆迁边界
    farmland_boundary: JSONB    # 基本农田图斑

    # 元数据
    bounds: Polygon          # 边界框
    feature_count: int       # 解析的特征点数量
    created_at: datetime
```

### 3.2 TerrainFeatures 数据结构

```python
class TerrainFeatures:
    centerline: Optional[GeoJSON]      # 河道中心线
    cross_sections: List[CrossSection] # 横断面
    elevation_range: List[float]       # [min, max, mean]
    slope_analysis: Dict               # 坡度统计
    waterfront_line: Optional[GeoJSON]  # 规划岸线
    demolition_boundary: Optional[Dict] # 动拆迁范围
    farmland_boundary: Optional[Dict]  # 基本农田图斑
```

### 3.3 支持的特征类型

| 特征 | 类型 | 说明 |
|------|------|------|
| centerline | GeoJSON LineString | 河道中心线 |
| cross_sections | Array | 横断面位置及形状 |
| elevation_range | [min, max, mean] | 高程范围 |
| slope_analysis | Dict | 坡度统计 |
| waterfront_line | GeoJSON LineString | 规划岸线 |
| demolition_boundary | Dict | 动拆迁边界 |
| farmland_boundary | Dict | 基本农田图斑 |

---

## 4. API设计

### 4.1 上传解析接口

```
POST /api/v1/projects/{project_id}/terrain
Content-Type: multipart/form-data

file: <文件>

Response 200:
{
    "id": "uuid",
    "project_id": "uuid",
    "file_type": "CSV" | "DXF",
    "status": "completed",
    "features": {
        "centerline": {...},
        "cross_sections_count": 25,
        "elevation_range": [100.5, 150.2, 125.3],
        "slope_analysis": {...},
        "waterfront_line": {...},
        "demolition_boundary": {...},
        "farmland_boundary": {...}
    },
    "bounds": {...},
    "feature_count": 15000
}
```

### 4.2 状态查询接口

```
GET /api/v1/projects/{project_id}/terrain
Response 200: { "terrain": {...} | null }

GET /api/v1/projects/{project_id}/terrain/status
Response 200: { "status": "completed", "progress": 100, "features": {...} }
```

### 4.3 重新解析接口

```
POST /api/v1/projects/{project_id}/terrain/reparse
```

---

## 5. 错误处理

### 5.1 错误类型

| 错误码 | HTTP状态码 | 说明 |
|--------|------------|------|
| FILE_TOO_LARGE | 413 | 文件超过处理能力 |
| INVALID_FILE_TYPE | 400 | 不支持的格式 |
| FILE_CORRUPTED | 400 | 文件损坏或格式错误 |
| NO_FEATURE_EXTRACTED | 422 | 无法提取有效地形特征 |
| PARTIAL_PARSING | 200 | 部分解析成功，返回警告 |

### 5.2 错误响应格式

```json
{
    "error": {
        "code": "NO_FEATURE_EXTRACTED",
        "message": "无法从文件中提取河道中心线",
        "details": {
            "detected_format": "DXF",
            "expected_content": "POLYLINE entities with elevation",
            "found_entities": ["LINE", "TEXT", "DIMENSION"]
        },
        "suggestion": "请检查DXF文件是否包含高程信息"
    }
}
```

### 5.3 部分解析成功

```json
{
    "status": "completed",
    "warning": {
        "code": "PARTIAL_PARSING",
        "message": "部分特征提取成功，以下特征缺失",
        "missing_features": ["centerline", "waterfront_line"],
        "extracted_features": ["elevation_range", "cross_sections"]
    },
    "features": {...}
}
```

---

## 6. 测试策略

### 6.1 单元测试

| 测试项 | 输入 | 预期结果 |
|--------|------|----------|
| CSV解析-有效 | 标准测量CSV | 正确提取坐标和高程 |
| CSV解析-空文件 | 空文件 | 返回NO_FEATURE_EXTRACTED |
| CSV解析-缺列 | 缺少高程列 | 返回PARTIAL_PARSING |
| DXF解析-有效 | 含POLYLINE的DXF | 正确提取中心线和断面 |
| DXF解析-无高程 | DXF无Z坐标 | 返回PARTIAL_PARSING |

### 6.2 集成测试

- 大文件流式处理（模拟1GB CSV）
- DXF复杂实体解析（含INSERT、BLOCK）
- 并发上传同一项目

### 6.3 测试数据

- `sample_river_survey.csv` - 标准河道测量数据
- `sample_terrain.dxf` - 标准地形CAD图
- `empty.csv` - 空文件（边界测试）
- `corrupted.dxf` - 损坏文件（边界测试）

---

## 7. 技术决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 格式支持 | CSV + DXF | 水利设计单位最常用 |
| 文件大小 | 无限制 | 后端流式处理 |
| 存储 | PostGIS + 原始路径 | 空间查询 + 重新解析 |
| 解析方式 | 流式 | 避免内存爆炸 |
| 特征完整度 | 全部7种 | 支持规划岸线、动拆迁、基本农田 |

---

## 8. 依赖项

- **后端**: FastAPI, SQLAlchemy, GeoAlchemy2, Pandas, ezdxf
- **数据库**: PostgreSQL + PostGIS
- **前端**: Ant Design Vue上传组件

---

## 9. TODO

- [ ] writing-plans - 拆解实现任务
- [ ] subagent-driven-development - 执行开发
