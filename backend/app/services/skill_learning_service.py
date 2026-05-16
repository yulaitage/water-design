import logging
import uuid
import re
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.skill import Skill, SkillExecutionLog
from app.models.conversation import Conversation
from app.core.vector_store import VectorStoreService

logger = logging.getLogger(__name__)


class SkillLearningService:
    """Skill自动学习服务 - 从成功的对话中提取技能"""

    # 触发技能生成的对话模式
    SUCCESS_PATTERNS = [
        # 用户明确表示满意或问题解决
        r"谢谢", r"明白了", r"解决了", r"好[的嘛]?",
        r"对的", r"正确", r"可以", r"没问题",
        # Agent成功调用工具并给出正确结果
        r"造价.*万元", r"总造价.*估算", r"计算完成",
        r"规范.*检索到", r"已找到.*规范",
    ]

    # 从对话中提取的工具调用模式
    TOOL_PATTERNS = {
        "estimate_cost": r"(?:调用|使用).*?(?:造价|估算|计算).*?工具",
        "search_specifications": r"(?:调用|使用).*?(?:规范|标准|检索).*?工具",
        "generate_report": r"(?:调用|使用).*?报告.*?工具",
        "analyze_terrain": r"(?:调用|使用).*?地形.*?工具",
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_and_learn_from_conversation(
        self,
        conversation_id: uuid.UUID,
        user_message: str,
        assistant_response: str
    ) -> Optional[Skill]:
        """分析对话，学习是否能形成Skill

        Returns:
            新创建的Skill或None（如果没有学习价值）
        """
        # 检查是否值得学习
        if not self._is_successful_interaction(assistant_response):
            return None

        # 提取技能候选
        skill_candidate = await self._extract_skill_candidate(
            user_message, assistant_response
        )

        if not skill_candidate:
            return None

        # 检查是否已存在相似Skill
        existing = await self._find_similar_skill(skill_candidate["name"])
        if existing:
            # 更新已有Skill的使用计数
            existing.usage_count += 1
            await self.db.commit()
            return existing

        # 创建新Skill
        skill = Skill(
            name=skill_candidate["name"],
            description=skill_candidate["description"],
            trigger_patterns=skill_candidate["trigger_patterns"],
            parameters=skill_candidate.get("parameters", []),
            solution_steps=skill_candidate.get("solution_steps", []),
            examples=[{
                "query": user_message[:200],
                "solution": assistant_response[:500]
            }],
            success_rate=0.8,  # 新技能初始成功率
            usage_count=1,
        )
        self.db.add(skill)

        try:
            await self.db.commit()
            await self.db.refresh(skill)
            logger.info(f"Learned new skill: {skill.name}")
            return skill
        except Exception as e:
            logger.warning(f"Failed to create skill: {e}")
            await self.db.rollback()
            return None

    def _is_successful_interaction(self, response: str) -> bool:
        """判断交互是否成功（可用于学习）"""
        for pattern in self.SUCCESS_PATTERNS:
            if re.search(pattern, response):
                return True

        # 检查是否有具体的数值结果（说明工具成功执行）
        has_numbers = re.search(r'\d+\.?\d*\s*(?:万元|米|km|公里|立方|元)', response)
        has_tool_result = any(p in response.lower() for p in ["完成", "结果", "如下", "计算"])

        return has_numbers and has_tool_result

    async def _extract_skill_candidate(
        self,
        user_message: str,
        assistant_response: str
    ) -> Optional[Dict[str, Any]]:
        """从对话中提取技能候选"""
        # 从用户消息中提取意图
        intent = self._extract_intent(user_message)
        if not intent:
            return None

        # 生成技能名称
        name = self._generate_skill_name(intent, user_message)

        # 提取触发模式
        trigger_patterns = self._extract_trigger_patterns(user_message)

        # 推断参数
        parameters = self._infer_parameters(intent, user_message)

        # 推断解决步骤
        solution_steps = self._infer_solution_steps(intent, assistant_response)

        return {
            "name": name,
            "description": f"用于{intent}的技能，从实际对话中学习",
            "trigger_patterns": trigger_patterns,
            "parameters": parameters,
            "solution_steps": solution_steps,
        }

    def _extract_intent(self, message: str) -> Optional[str]:
        """提取用户意图"""
        # 去除标点，转小写
        msg = re.sub(r'[，。！？、]', '', message.lower())

        intents = [
            ("造价估算", [r'造价', r'估算', r'费用', r'多少钱']),
            ("规范检索", [r'规范', r'标准', r'条文', r'要求']),
            ("报告生成", [r'报告', r'生成', r'编写']),
            ("地形分析", [r'地形', r'断面', r'分析']),
            ("工程设计", [r'设计', r'参数', r'方案']),
        ]

        for intent_name, keywords in intents:
            for kw in keywords:
                if kw in msg:
                    return intent_name

        return None

    def _generate_skill_name(self, intent: str, message: str) -> str:
        """生成技能名称"""
        # 尝试从消息中提取具体对象
        object_match = re.search(r'([^\s，的]+(?:工程|项目|堤防|河道|水库))', message)
        obj = object_match.group(1) if object_match else ""

        intent_map = {
            "造价估算": "造价估算",
            "规范检索": "规范查询",
            "报告生成": "报告生成",
            "地形分析": "地形分析",
            "工程设计": "设计参数",
        }

        return f"{obj}{intent_map.get(intent, intent)}" if obj else f"{intent_map.get(intent, intent)}技能"

    def _extract_trigger_patterns(self, message: str) -> List[str]:
        """提取触发模式"""
        patterns = []

        # 保留关键词作为模式
        keywords = re.findall(r'[\w]+', message)
        for kw in keywords:
            if len(kw) >= 2 and kw not in ['请问', '我想', '帮我', '这个', '什么']:
                patterns.append(kw)

        # 保留完整问句作为模式
        if len(message) < 50:
            patterns.append(message)

        return patterns[:10]  # 最多10个模式

    def _infer_parameters(self, intent: str, message: str) -> List[dict]:
        """推断所需参数"""
        params = []

        if intent == "造价估算":
            params = [
                {"name": "project_type", "type": "string", "required": True,
                 "description": "工程类型，如堤防/河道/水库"},
                {"name": "design_params", "type": "object", "required": True,
                 "description": "设计参数，包含尺度、长度等"},
            ]
        elif intent == "规范检索":
            params = [
                {"name": "query", "type": "string", "required": True,
                 "description": "检索关键词"},
                {"name": "project_type", "type": "string", "required": False,
                 "description": "工程类型过滤"},
            ]

        return params

    def _infer_solution_steps(self, intent: str, response: str) -> List[dict]:
        """推断解决步骤"""
        steps = []

        if intent == "造价估算":
            steps = [
                {"step": 1, "action": "search_specifications",
                 "params": {"query": "${project_type} 设计标准", "top_k": 3}},
                {"step": 2, "action": "estimate_cost",
                 "params": {"project_type": "${project_type}",
                            "design_params": "${design_params}"}},
            ]
        elif intent == "规范检索":
            steps = [
                {"step": 1, "action": "search_specifications",
                 "params": {"query": "${query}", "project_type": "${project_type}"}},
            ]
        elif intent == "报告生成":
            steps = [
                {"step": 1, "action": "search_specifications",
                 "params": {"query": "${project_name} ${report_type}", "top_k": 5}},
                {"step": 2, "action": "generate_report",
                 "params": {"report_type": "${report_type}"}},
            ]

        return steps

    async def _find_similar_skill(self, name: str) -> Optional[Skill]:
        """查找是否已存在相似技能"""
        stmt = select(Skill).where(Skill.name.like(f"%{name[:10]}%"))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def find_matching_skill(self, query: str) -> Optional[Skill]:
        """根据查询找到匹配的Skill"""
        from app.core.vector_store import VectorStoreService

        # 先用关键词匹配
        stmt = select(Skill).where(
            Skill.trigger_patterns.any(query[:50])
        ).limit(5)
        result = await self.db.execute(stmt)
        candidates = result.scalars().all()

        # 如果有候选，计算相似度排序
        if candidates:
            try:
                vs = VectorStoreService(self.db)
                query_embedding = await vs.embed_text(query)
            except Exception as e:
                logger.warning(f"Embedding failed: {e}")
                query_embedding = None

            if query_embedding:
                scored = []
                for skill in candidates:
                    if skill.embedding:
                        similarity = self._cosine_similarity(
                            query_embedding,
                            [float(x) for x in skill.embedding]
                        )
                        scored.append((skill, similarity))
                if scored:
                    scored.sort(key=lambda x: x[1], reverse=True)
                    return scored[0][0]

        # 尝试语义搜索
        try:
            vs = VectorStoreService(self.db)
            # 直接用名称和描述搜索
            results = await self._search_skills_by_text(vs, query)
            return results[0] if results else None
        except Exception as e:
            logger.warning(f"Skill semantic search failed: {e}")
            return None

    async def _search_skills_by_text(
        self,
        vs: VectorStoreService,
        query: str
    ) -> List[Skill]:
        """通过文本搜索Skill"""
        stmt = select(Skill).where(Skill.is_verified == True).limit(10)
        result = await self.db.execute(stmt)
        skills = result.scalars().all()

        # 简单的文本匹配排序
        query_lower = query.lower()
        scored = []
        for skill in skills:
            score = 0
            if query_lower in skill.name.lower():
                score += 10
            if query_lower in skill.description.lower():
                score += 5
            for pattern in skill.trigger_patterns:
                if pattern.lower() in query_lower:
                    score += 3
            if score > 0:
                scored.append((skill, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in scored[:3]]

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        if len(a) != len(b) or len(a) == 0:
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)

    async def record_execution(
        self,
        skill_id: uuid.UUID,
        query: str,
        matched_pattern: str,
        success: bool,
        result: str = "",
        execution_time_ms: int = 0
    ) -> SkillExecutionLog:
        """记录技能执行日志"""
        log = SkillExecutionLog(
            skill_id=skill_id,
            query=query,
            matched_pattern=matched_pattern,
            execution_result=result,
            success=success,
            execution_time_ms=execution_time_ms,
        )
        self.db.add(log)

        # 更新Skill的成功率和使用计数
        skill = await self._get_skill(skill_id)
        if skill:
            # 简单移动平均更新成功率
            skill.usage_count += 1
            if success:
                skill.success_rate = (skill.success_rate * (skill.usage_count - 1) + 1.0) / skill.usage_count
            else:
                skill.success_rate = (skill.success_rate * (skill.usage_count - 1)) / skill.usage_count

        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def _get_skill(self, skill_id: uuid.UUID) -> Optional[Skill]:
        stmt = select(Skill).where(Skill.id == skill_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_skills(self, verified_only: bool = False) -> List[Skill]:
        """获取所有技能"""
        stmt = select(Skill)
        if verified_only:
            stmt = stmt.where(Skill.is_verified == True)
        stmt = stmt.order_by(Skill.usage_count.desc())
        result = await self.db.execute(stmt)
        return result.scalars().all()