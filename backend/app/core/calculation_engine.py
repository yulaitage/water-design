import re
import math
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
        "sqrt": lambda x: x ** 0.5 if x >= 0 else float('nan'),
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

    def _substitute_variables(self, formula: str, context: CalculationContext) -> str:
        """替换变量名为值，按长度降序排列避免子串冲突"""
        expr = formula
        # 按长度降序排列key，避免子串冲突（如 "ab" 不会被 "a" 先替换）
        all_keys = sorted(
            list(context.design_params.keys()) + list(self.constants.keys()) + list(context.constants.keys()),
            key=len,
            reverse=True
        )
        for key in all_keys:
            if key in context.design_params:
                value = context.design_params[key]
            elif key in self.constants:
                value = self.constants[key]
            else:
                value = context.constants[key]
            expr = re.sub(rf'\b{key}\b', str(value), expr)
        return expr

    def _validate_expression(self, expr: str) -> bool:
        """验证表达式仅包含允许的字符"""
        # 允许：数字、运算符、括号、点号、函数名字母
        allowed_pattern = r'^[\d\s+\-*/().sqrtabsilpmaxeSQRTABSMAXMINPOW]+$'
        if not re.match(allowed_pattern, expr.replace('_', '')):
            return False
        return True

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
            expr = self._substitute_variables(formula, context)

            if not self._validate_expression(expr):
                return None

            result = eval(expr, {"__builtins__": {}}, {})
            if isinstance(result, float) and not math.isfinite(result):
                return None
            return float(result)

        except (ValueError, SyntaxError, ZeroDivisionError, NameError, TypeError, AttributeError):
            return None

    def evaluate_with_functions(self, formula: str, context: CalculationContext) -> Optional[float]:
        """
        计算带函数的公式

        Args:
            formula: 公式字符串，如 "sqrt(length**2 + height**2)"
            context: 计算上下文

        Returns:
            计算结果，失败返回None
        """
        try:
            expr = self._substitute_variables(formula, context)

            if not self._validate_expression(expr):
                return None

            result = eval(expr, {"__builtins__": {}}, {**self.FUNCTIONS})
            if isinstance(result, float) and not math.isfinite(result):
                return None
            return float(result)

        except (ValueError, SyntaxError, ZeroDivisionError, NameError, TypeError, AttributeError):
            return None