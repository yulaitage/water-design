import re
from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass


@dataclass
class CalculationContext:
    """计算上下文，包含设计参数和常量"""
    design_params: Dict[str, float]
    constants: Dict[str, float]

    def get(self, key: str) -> Optional[float]:
        """获取参数值（设计参数优先，其次常量）"""
        return self.design_params.get(key) or self.constants.get(key)


class CalculationEngine:
    """公式计算引擎，支持表达式求值"""

    # 内置函数
    FUNCTIONS: Dict[str, Callable] = {
        "sqrt": lambda x: x ** 0.5 if x >= 0 else None,
        "abs": abs,
        "max": max,
        "min": min,
        "pow": pow,
    }

    # 默认常数
    DEFAULT_CONSTANTS: Dict[str, float] = {
        "pi": 3.14159265359,
        "e": 2.71828182846,
        "g": 9.81,  # 重力加速度
        "soil_expansion_factor": 1.05,  # 土方松散系数
        "compaction_factor": 0.95,  # 压实系数
    }

    def __init__(self, custom_constants: Optional[Dict[str, float]] = None):
        self.constants = {**self.DEFAULT_CONSTANTS, **(custom_constants or {})}

    def evaluate(self, formula: str, context: CalculationContext) -> Optional[float]:
        """
        计算公式值

        Args:
            formula: 公式字符串，如 "length * height * slope_ratio * 1.05"
            context: 计算上下文

        Returns:
            计算结果，失败返回None
        """
        try:
            # 替换变量名为值
            expr = formula
            for key in context.design_params:
                expr = re.sub(rf'\b{key}\b', str(context.design_params[key]), expr)

            for key, value in self.constants.items():
                expr = re.sub(rf'\b{key}\b', str(value), expr)

            # 安全评估（仅允许数字和运算符）
            if not re.match(r'^[\d\s+\-*/().sqrtabsilpmaxe]+$', expr.replace('_', '')):
                return None

            # 使用eval计算（仅含数字和运算符，无任何函数）
            result = eval(expr, {"__builtins__": {}}, {})
            return float(result)

        except (ValueError, SyntaxError, ZeroDivisionError, NameError):
            return None

    def evaluate_with_functions(self, formula: str, context: CalculationContext) -> Optional[float]:
        """
        计算带函数的公式

        Args:
            formula: 公式字符串，如 "sqrt(length**2 + height**2)"
            context: 计算上下文
        """
        try:
            expr = formula
            # 替换变量
            for key in context.design_params:
                expr = re.sub(rf'\b{key}\b', str(context.design_params[key]), expr)

            for key, value in self.constants.items():
                expr = re.sub(rf'\b{key}\b', str(value), expr)

            # 预处理函数
            for name, func in self.FUNCTIONS.items():
                if name in expr:
                    # 简单实现，实际可用ast解析
                    pass

            result = eval(expr, {"__builtins__": {}}, {**self.FUNCTIONS})
            return float(result)

        except Exception:
            return None