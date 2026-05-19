"""
RAG 检索服务 - 统一的检索入口
支持意图感知的检索策略
"""
import uuid
import logging
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class RAGService:
    """RAG 检索服务 - 根据意图动态调整检索策略

    意图类型：
    - generate: 首次生成报告，需要全面检索
    - revise: 修订章节，检索特定章节相关素材
    - supplement: 补充内容，检索缺失数据相关素材
    - general: 一般性对话
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_config: dict = None
    ):
        self.db = db
        self.embedding_config = embedding_config or {}
        self._vector_store = None

    @property
    def vector_store(self):
        """懒加载 VectorStoreService"""
        if self._vector_store is None:
            from app.core.vector_store import VectorStoreService
            self._vector_store = VectorStoreService(
                self.db,
                embedding_model=self.embedding_config.get("model"),
                embedding_api_key=self.embedding_config.get("api_key"),
                embedding_base_url=self.embedding_config.get("base_url")
            )
        return self._vector_store

    async def retrieve_for_report(
        self,
        query: str,
        project_id: str,
        intent: str,  # "generate" | "revise" | "supplement" | "general"
        top_k: int = 10
    ) -> Dict[str, List[dict]]:
        """根据意图检索相关素材

        Args:
            query: 检索查询
            project_id: 项目UUID
            intent: 意图类型
            top_k: 检索数量

        Returns:
            {
                "cases": 检索到的案例,
                "specs": 检索到的规范,
                "materials": 检索到的素材,
                "chunks": 检索到的文档块
            }
        """
        results = {
            "cases": [],
            "specs": [],
            "materials": [],
            "chunks": []
        }

        project_uuid = uuid.UUID(project_id) if project_id else None

        if intent == "general":
            # 一般性对话，只做简单检索
            results["cases"] = await self.vector_store.search_similar_cases(
                query=query, top_k=5, project_type="河道整治"
            )
            results["specs"] = await self.vector_store.search_similar_specifications(
                query=query, top_k=5
            )
            return results

        if intent == "generate":
            # 首次生成：全面检索
            results["cases"] = await self.vector_store.search_similar_cases(
                query=f"{query} 水利工程 泵闸 海域使用", top_k=top_k, project_type="河道整治"
            )
            results["specs"] = await self.vector_store.search_similar_specifications(
                query=f"{query} 工程设计 规范 标准", top_k=top_k
            )
            results["materials"] = await self.vector_store.search_project_materials(
                query=query, project_id=project_uuid, top_k=top_k
            )
            results["chunks"] = await self.vector_store.search_all_chunks(
                query=query, project_id=project_uuid, top_k=top_k * 2
            )

        elif intent == "revise":
            # 修订章节：检索特定章节相关素材
            results["chunks"] = await self.vector_store.search_all_chunks(
                query=query, project_id=project_uuid, top_k=top_k
            )
            results["specs"] = await self.vector_store.search_similar_specifications(
                query=query, top_k=5
            )

        elif intent == "supplement":
            # 补充内容：检索缺失数据相关素材
            results["materials"] = await self.vector_store.search_project_materials(
                query=query, project_id=project_uuid, top_k=top_k
            )
            results["chunks"] = await self.vector_store.search_all_chunks(
                query=query, project_id=project_uuid, top_k=top_k
            )
            results["specs"] = await self.vector_store.search_similar_specifications(
                query=query, top_k=5
            )

        logger.info(f"=== RAG Retrieved: cases={len(results['cases'])}, specs={len(results['specs'])}, materials={len(results['materials'])}, chunks={len(results['chunks'])} ===")

        return results

    async def retrieve_cases_for_chapter(
        self,
        chapter: str,
        project_id: str,
        top_k: int = 5
    ) -> List[dict]:
        """根据章节检索相关案例

        Args:
            chapter: 章节名称
            project_id: 项目UUID
            top_k: 检索数量

        Returns:
            相关案例列表
        """
        chapter_queries = {
            "第1章 项目概述": ["项目背景 长兴岛 水利设施", "区域水系 防洪排涝"],
            "第2章 工程建设的必要性": ["防洪排涝 现状 需求分析", "水环境 改善"],
            "第3章 工程任务与规模": ["设计流量 装机容量", "排涝标准 防洪标准"],
            "第4章 工程总体布置": ["场址选择 总体布置", "进水渠 泵房 出水渠"],
            "第5章 工程设计": ["建筑物结构 钢筋混凝土", "水泵 电机 机电设备"],
            "第6章 施工组织设计": ["施工条件 场地 交通", "施工方法 工期"],
            "第7章 投资估算": ["工程投资 造价", "编制依据 单价 定额"],
            "第8章 经济评价": ["经济效益 费用 收益", "内部收益率 净现值"],
            "第9章 环境影响评价": ["环境现状 空气质量 地表水", "环境影响 保护措施"],
            "第10章 结论与建议": ["结论 建议 技术可行", "项目建设 世界级生态岛"]
        }

        queries = chapter_queries.get(chapter, [chapter])
        all_cases = []

        for q in queries:
            cases = await self.vector_store.search_similar_cases(
                query=q, top_k=top_k, project_type="河道整治"
            )
            all_cases.extend(cases)

        # 去重
        seen_ids = set()
        unique_cases = []
        for case in all_cases:
            if case["id"] not in seen_ids:
                seen_ids.add(case["id"])
                unique_cases.append(case)

        return unique_cases[:top_k]

    async def retrieve_materials_for_chapter(
        self,
        chapter: str,
        project_id: str,
        top_k: int = 10
    ) -> List[dict]:
        """根据章节检索相关素材

        Args:
            chapter: 章节名称
            project_id: 项目UUID
            top_k: 检索数量

        Returns:
            相关素材列表
        """
        chapter_queries = {
            "第1章 项目概述": ["项目背景 长兴岛", "区域水系 地形地貌"],
            "第2章 工程建设的必要性": ["防洪排涝现状", "水环境问题"],
            "第3章 工程任务与规模": ["设计流量 装机", "排涝标准"],
            "第4章 工程总体布置": ["场址 布置", "建筑物结构"],
            "第5章 工程设计": ["结构设计 钢筋", "机电设备"],
            "第6章 施工组织设计": ["施工条件", "施工进度"],
            "第7章 投资估算": ["工程造价", "单价定额"],
            "第8章 经济评价": ["经济效益", "评价指标"],
            "第9章 环境影响评价": ["环境现状", "保护措施"],
            "第10章 结论与建议": ["结论 建议"]
        }

        queries = chapter_queries.get(chapter, [chapter])
        all_materials = []

        for q in queries:
            # 检索项目素材
            materials = await self.vector_store.search_project_materials(
                query=q, project_id=uuid.UUID(project_id), top_k=top_k
            )
            all_materials.extend(materials)

            # 检索文档块
            chunks = await self.vector_store.search_all_chunks(
                query=q, project_id=uuid.UUID(project_id), top_k=top_k
            )
            for chunk in chunks:
                chunk["source"] = f"{chunk.get('category', 'material')}_chunk"
                all_materials.append(chunk)

        # 去重
        seen_content = set()
        unique_materials = []
        for mat in all_materials:
            content_key = mat.get("content", mat.get("text", ""))[:100]
            if content_key and content_key not in seen_content:
                seen_content.add(content_key)
                unique_materials.append(mat)

        return unique_materials[:top_k]

    async def build_context_for_chapter(
        self,
        chapter: str,
        project_id: str,
        project_name: str = "",
        top_k: int = 10
    ) -> str:
        """为特定章节构建素材上下文

        Args:
            chapter: 章节名称
            project_id: 项目UUID
            project_name: 项目名称
            top_k: 检索数量

        Returns:
            格式化的上下文字符串
        """
        cases = await self.retrieve_cases_for_chapter(chapter, project_id, top_k)
        materials = await self.retrieve_materials_for_chapter(chapter, project_id, top_k)

        context = f"【{chapter}相关素材】\n\n"

        if cases:
            context += "=== 参考案例 ===\n"
            for i, case in enumerate(cases, 1):
                context += f"""
### 案例{i}：{case.get('name', '未知')}
- 位置：{case.get('location', '未知')}
- 类型：{case.get('project_type', '未知')}
- 摘要：{case.get('summary', case.get('description', ''))[:500]}
"""
            context += "\n"

        if materials:
            context += "=== 项目素材 ===\n"
            for mat in materials[:10]:
                source = mat.get('source', 'material')
                filename = mat.get('filename', mat.get('title', '素材'))
                content = mat.get('content', mat.get('text', ''))
                page = mat.get('page', '')

                if source in ['material_chunk', 'case_chunk']:
                    context += f"""【{filename} 第{page}页】
{content}

"""
                else:
                    context += f"""【{filename}】
{content[:800] if content else '无内容'}...

"""

        return context if context != f"【{chapter}相关素材】\n\n" else ""