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