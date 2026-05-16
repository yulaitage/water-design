import logging
import uuid
import re
import time
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, SkillExecutionLog
from app.services.skill_learning_service import SkillLearningService

logger = logging.getLogger(__name__)


class SkillExecutionService:
    """Skill执行服务 - 执行匹配的技能"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_skill(
        self,
        skill: Skill,
        query: str,
        project_id: Optional[uuid.UUID] = None
    ) -> str:
        """执行技能并返回结果

        Args:
            skill: 要执行的技能
            query: 用户查询
            project_id: 项目ID（用于工具调用）

        Returns:
            执行结果字符串
        """
        start_time = time.time()

        try:
            # 根据solution_steps执行
            results = []
            for step in skill.solution_steps:
                action = step.get("action")
                params = self._render_params(step.get("params", {}), query, project_id)

                result = await self._execute_action(action, params, project_id)
                results.append(result)

            execution_time_ms = int((time.time() - start_time) * 1000)

            # 记录成功执行
            await self._record_execution(
                skill, query, True, "\n".join(results), execution_time_ms
            )

            return "\n\n".join(results)

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Skill execution failed: {e}")
            await self._record_execution(
                skill, query, False, str(e), execution_time_ms
            )
            raise

    async def _execute_action(
        self,
        action: str,
        params: Dict[str, Any],
        project_id: Optional[uuid.UUID]
    ) -> str:
        """执行单个动作"""
        if action == "search_specifications":
            return await self._search_specs(params)
        elif action == "estimate_cost":
            return await self._estimate_cost(params, project_id)
        elif action == "generate_report":
            return await self._generate_report(params, project_id)
        elif action == "analyze_terrain":
            return await self._analyze_terrain(params, project_id)
        else:
            return f"[未知动作: {action}]"

    async def _search_specs(self, params: Dict[str, Any]) -> str:
        """搜索规范"""
        from app.core.vector_store import VectorStoreService

        query = params.get("query", "")
        top_k = params.get("top_k", 5)
        project_type = params.get("project_type")

        vs = VectorStoreService(self.db)
        results = await vs.search_similar_specifications(
            query=query,
            top_k=top_k,
            project_type=project_type
        )

        if not results:
            return f"未找到与'{query}'相关的规范"

        lines = ["【规范检索结果】"]
        for r in results:
            lines.append(f"[{r['code']}] {r['name']}")
            lines.append(f"  {r['content'][:200]}...")
        return "\n".join(lines)

    async def _estimate_cost(
        self,
        params: Dict[str, Any],
        project_id: Optional[uuid.UUID]
    ) -> str:
        """估算造价"""
        from app.services.cost_calculation import CostCalculationService
        from app.schemas.cost_estimation import CostEstimateCreateRequest

        if not project_id:
            return "缺少项目ID，无法进行造价估算"

        project_type = params.get("project_type", "堤防")
        design_params = params.get("design_params", {})

        service = CostCalculationService(self.db)
        request = CostEstimateCreateRequest(
            project_id=project_id,
            project_type=project_type,
            design_params=design_params,
        )

        estimate = await service.calculate(request)

        lines = ["【造价估算结果】"]
        lines.append(f"工程类型：{estimate.project_type}")
        lines.append(f"总造价：{estimate.total_cost:.2f} 万元")
        if estimate.cost_per_km:
            lines.append(f"单公里造价：{estimate.cost_per_km:.2f} 万元/km")
        lines.append("\n明细：")
        for item in estimate.details:
            lines.append(f"  {item['item']}：{item['quantity']:.2f} {item['unit']} × {item['unit_price']:.2f}元 = {item['subtotal']:.2f}元")

        return "\n".join(lines)

    async def _generate_report(
        self,
        params: Dict[str, Any],
        project_id: Optional[uuid.UUID]
    ) -> str:
        """生成报告"""
        from app.services.report_service import ReportService
        from app.schemas.report import ReportCreateRequest, ProjectInfo

        if not project_id:
            return "缺少项目ID，无法生成报告"

        report_type = params.get("report_type", "feasibility")

        # 获取项目信息
        from app.models.project import Project
        stmt = select(Project).where(Project.id == project_id)
        result = await self.db.execute(stmt)
        project = result.scalar_one_or_none()

        if not project:
            return f"项目 {project_id} 不存在"

        service = ReportService(self.db)
        project_info = ProjectInfo(
            name=project.name,
            location=project.location or "",
            scale=project.description or "",
            description=project.description or "",
        )

        task = await service.create_report_task(project_id, ReportCreateRequest(report_type=report_type))

        # 异步生成，实际可通过SSE查询进度
        return f"报告生成任务已创建（ID: {task.id}），正在后台生成{report_type}报告"

    async def _analyze_terrain(
        self,
        params: Dict[str, Any],
        project_id: Optional[uuid.UUID]
    ) -> str:
        """分析地形"""
        from sqlalchemy import text

        if not project_id:
            return "缺少项目ID，无法分析地形"

        stmt = text("SELECT file_type, features FROM terrains WHERE project_id = :pid LIMIT 1")
        result = await self.db.execute(stmt, {"pid": project_id})
        row = result.fetchone()

        if not row:
            return "该项目尚未上传地形数据"

        return f"【地形分析】\n文件类型：{row.file_type}\n特征：{str(row.features)[:500]}"

    def _render_params(
        self,
        params: Dict[str, Any],
        query: str,
        project_id: Optional[uuid.UUID]
    ) -> Dict[str, Any]:
        """渲染参数，替换${变量}"""
        rendered = {}
        for key, value in params.items():
            if isinstance(value, str) and "${" in value:
                # 简单替换
                value = value.replace("${query}", query)
                value = value.replace("${project_id}", str(project_id) if project_id else "")
                # 可以进一步解析嵌套的参数
                if "project_type" not in params and any(kw in query for kw in ["堤防", "堤", "河道", "水库"]):
                    if "堤" in query:
                        rendered["project_type"] = "堤防"
                    elif "河道" in query:
                        rendered["project_type"] = "河道整治"
                    elif "水库" in query:
                        rendered["project_type"] = "水库"
            else:
                rendered[key] = value
        return rendered

    async def _record_execution(
        self,
        skill: Skill,
        query: str,
        success: bool,
        result: str,
        execution_time_ms: int
    ) -> None:
        """记录执行日志"""
        log = SkillExecutionLog(
            skill_id=skill.id,
            query=query[:500],
            matched_pattern=skill.trigger_patterns[0] if skill.trigger_patterns else "",
            execution_result=result[:1000] if result else "",
            success=success,
            execution_time_ms=execution_time_ms,
        )
        self.db.add(log)

        # 更新技能统计
        skill.usage_count += 1
        if success:
            skill.success_rate = (skill.success_rate * (skill.usage_count - 1) + 1.0) / skill.usage_count
        else:
            skill.success_rate = (skill.success_rate * (skill.usage_count - 1)) / skill.usage_count

        await self.db.commit()


class SkillManager:
    """Skill管理器 - 协调学习和执行"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.learning_service = SkillLearningService(db)
        self.execution_service = SkillExecutionService(db)

    async def find_and_execute_skill(
        self,
        query: str,
        project_id: Optional[uuid.UUID] = None
    ) -> Optional[str]:
        """查找并执行匹配的技能

        Returns:
            执行结果或None（没有匹配技能）
        """
        skill = await self.learning_service.find_matching_skill(query)
        if not skill:
            return None

        # 检查技能是否可用（成功率阈值）
        if skill.success_rate < 0.5 and not skill.is_verified:
            logger.info(f"Skill {skill.name} success_rate too low: {skill.success_rate}")
            return None

        try:
            result = await self.execution_service.execute_skill(skill, query, project_id)
            return result
        except Exception as e:
            logger.warning(f"Skill execution failed: {e}")
            await self.db.rollback()
            return None

    async def learn_from_conversation(
        self,
        conversation_id: uuid.UUID,
        user_message: str,
        assistant_response: str
    ) -> None:
        """从对话中学习新技能"""
        await self.learning_service.analyze_and_learn_from_conversation(
            conversation_id, user_message, assistant_response
        )

    async def get_all_skills(self, verified_only: bool = False) -> List[Skill]:
        """获取所有技能"""
        return await self.learning_service.get_skills(verified_only)

    async def verify_skill(self, skill_id: uuid.UUID) -> bool:
        """验证技能"""
        skill = await self.learning_service._get_skill(skill_id)
        if not skill:
            return False
        skill.is_verified = True
        await self.db.commit()
        return True