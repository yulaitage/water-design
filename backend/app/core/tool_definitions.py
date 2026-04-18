import json

from langchain_core.tools import tool


@tool
async def estimate_cost(project_type: str, design_params: dict, project_id: str) -> str:
    """计算工程量并估算费用。当用户询问工程造价、费用估算、工程量统计时使用。

    Args:
        project_type: 工程类型，"堤防" 或 "河道整治"
        design_params: 设计参数JSON，包含 length(长度m), height(堤高m), slope_ratio(边坡系数) 等
        project_id: 项目UUID
    """
    return f"已触发费用估算：类型={project_type}，参数={json.dumps(design_params, ensure_ascii=False)}"


@tool
async def generate_report(project_id: str, report_type: str = "feasibility") -> str:
    """生成设计报告。当用户要求生成报告、编写报告时使用。

    Args:
        project_id: 项目UUID
        report_type: 报告类型，"feasibility"(可研报告) 或 "preliminary"(初设报告)
    """
    return f"已触发报告生成：项目={project_id}，类型={report_type}"


@tool
async def search_specifications(query: str, project_type: str = "") -> str:
    """检索水利规范条文。当用户询问设计规范、技术标准、设计要求时使用。

    Args:
        query: 检索查询，如 "堤顶高程计算" 或 "防洪标准"
        project_type: 工程类型过滤，可选
    """
    return f"已触发规范检索：查询={query}"


@tool
async def analyze_terrain(project_id: str) -> str:
    """分析地形数据。当用户要求查看地形特征、断面数据时使用。

    Args:
        project_id: 项目UUID
    """
    return f"已触发地形分析：项目={project_id}"


ALL_TOOLS = [estimate_cost, generate_report, search_specifications, analyze_terrain]
