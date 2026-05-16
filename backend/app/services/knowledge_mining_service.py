import logging
import re
import uuid
from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.wiki import WikiItem

logger = logging.getLogger(__name__)


class KnowledgeMiningService:
    """知识挖掘服务 - 从报告生成过程中积累知识"""

    KNOWLEDGE_PATTERNS = {
        # 设计标准/参数
        "design_standard": [
            "设计标准", "设计参数", "设计流量", "设计水位", "堤顶高程",
            "边坡", "护坡", "防渗", "稳定", "沉降"
        ],
        # 计算规则
        "calculation_rule": [
            "计算方法", "计算公式", "复核", "验算", "依据",
            "流量计算", "水力计算", "结构计算"
        ],
        # 设计要点
        "design_tip": [
            "应采用", "宜采用", "推荐", "建议", "一般", "通常",
            "常用", "通常采用", "一般采用"
        ],
        # 案例总结
        "case_summary": [
            "类似工程", "工程实例", "案例", "已建", "参考",
            "已有", "国内", "国外", "经验"
        ],
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def mine_knowledge_from_chapter(
        self,
        chapter_name: str,
        chapter_content: str,
        project_info: Dict,
        report_id: Optional[uuid.UUID] = None
    ) -> List[WikiItem]:
        """从章节内容中挖掘知识并存储到Wiki

        Args:
            chapter_name: 章节名称
            chapter_content: 章节内容
            project_info: 项目信息 dict
            report_id: 来源报告ID

        Returns:
            新增的Wiki条目列表
        """
        extracted = []

        # 分类挖掘
        for category, keywords in self.KNOWLEDGE_PATTERNS.items():
            items = await self._extract_category_knowledge(
                category=category,
                keywords=keywords,
                chapter_name=chapter_name,
                content=chapter_content,
                project_info=project_info,
                report_id=report_id
            )
            extracted.extend(items)

        # 批量存储
        for item in extracted:
            self.db.add(item)

        if extracted:
            await self.db.commit()

        logger.info(f"Mined {len(extracted)} knowledge items from {chapter_name}")
        return extracted

    async def _extract_category_knowledge(
        self,
        category: str,
        keywords: List[str],
        chapter_name: str,
        content: str,
        project_info: Dict,
        report_id: Optional[uuid.UUID]
    ) -> List[WikiItem]:
        """提取特定类别的知识"""
        items = []

        for keyword in keywords:
            if keyword in content:
                # 找到包含关键词的段落
                segments = self._split_into_segments(content, keyword)
                for segment in segments:
                    if len(segment) > 50:  # 过滤太短的内容
                        wiki_item = await self._create_wiki_item(
                            category=category,
                            segment=segment,
                            chapter_name=chapter_name,
                            project_info=project_info,
                            report_id=report_id
                        )
                        if wiki_item:
                            items.append(wiki_item)

        # 去重：检查是否已存在相似知识
        unique_items = []
        for item in items:
            if not await self._is_duplicate(item):
                unique_items.append(item)

        return unique_items[:5]  # 每类最多5条

    def _split_into_segments(self, content: str, keyword: str) -> List[str]:
        """将内容按关键词拆分为段落"""
        # 按句子拆分
        sentences = re.split(r'[。\n]', content)
        segments = []
        current = []

        for sent in sentences:
            if keyword in sent:
                if current:
                    segments.append(''.join(current))
                    current = []
                segments.append(sent)
            else:
                current.append(sent)

        if current:
            segments.append(''.join(current))

        return [s.strip() for s in segments if s.strip()]

    async def _create_wiki_item(
        self,
        category: str,
        segment: str,
        chapter_name: str,
        project_info: Dict,
        report_id: Optional[uuid.UUID]
    ) -> Optional[WikiItem]:
        """从段落创建Wiki条目"""
        # 提取标题
        title = self._extract_title(segment, category)

        if not title or len(segment) < 30:
            return None

        # 确定适用工程类型
        project_types = []
        desc = project_info.get("description", "").lower()
        if "堤防" in desc:
            project_types.append("堤防")
        if "河道" in desc or "整治" in desc:
            project_types.append("河道整治")
        if "水库" in desc:
            project_types.append("水库")

        return WikiItem(
            title=title,
            category=category,
            content=segment,
            source_chapter=chapter_name,
            source_report_id=report_id,
            tags=self._extract_tags(segment),
            project_types=project_types or ["通用"]
        )

    def _extract_title(self, segment: str, category: str) -> str:
        """从段落提取标题"""
        # 尝试找数字编号开头的内容
        match = re.match(r'^(\d+\.\d+(?:\.\d+)?)\s*[．.]\s*(.+)', segment)
        if match:
            code = match.group(1)
            title = match.group(2)[:50]
            return f"{code} {title}"

        # 尝试找第一个完整句子
        first_sentence = segment.split('。')[0].strip()
        if len(first_sentence) > 5 and len(first_sentence) < 80:
            return first_sentence[:80]

        return f"{category}_{segment[:30]}"

    def _extract_tags(self, content: str) -> List[str]:
        """从内容中提取标签"""
        tags = []
        patterns = [
            r'设计[流量|水位|高程|标准|参数]',
            r'计算[方法|公式]',
            r'稳定[计算|验算]',
            r'防渗',
            r'护坡',
            r'堤顶',
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                tags.append(match.group(0))

        return tags[:5]  # 最多5个标签

    async def _is_duplicate(self, item: WikiItem) -> bool:
        """检查是否与已有知识重复"""
        stmt = select(WikiItem).where(
            WikiItem.title == item.title,
            WikiItem.category == item.category
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        return existing is not None

    async def get_wiki_items(
        self,
        category: Optional[str] = None,
        project_type: Optional[str] = None,
        limit: int = 20
    ) -> List[WikiItem]:
        """获取Wiki条目"""
        stmt = select(WikiItem)

        if category:
            stmt = stmt.where(WikiItem.category == category)
        if project_type:
            stmt = stmt.where(WikiItem.project_types.any(project_type))

        stmt = stmt.order_by(WikiItem.usage_count.desc(), WikiItem.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def search_wiki(
        self,
        query: str,
        top_k: int = 10
    ) -> List[Dict]:
        """搜索Wiki知识库"""
        from app.core.vector_store import VectorStoreService

        vs = VectorStoreService(self.db)
        results = await vs.search_wiki_items(query, top_k)

        # 更新使用计数
        for r in results:
            if r.get("wiki_item_id"):
                stmt = select(WikiItem).where(WikiItem.id == r["wiki_item_id"])
                result = await self.db.execute(stmt)
                item = result.scalar_one_or_none()
                if item:
                    item.usage_count += 1
        await self.db.commit()

        return results