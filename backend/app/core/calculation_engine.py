import ast
import math
import operator
from typing import Dict, Callable, Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class CalculationContext:
    design_params: Dict[str, float]
    constants: Dict[str, float]

    def get(self, key: str) -> Optional[float]:
        return self.design_params.get(key) or self.constants.get(key)


_SAFE_FUNCTIONS: Dict[str, Callable] = {
    "sqrt": lambda x: x ** 0.5 if x >= 0 else float("nan"),
    "abs": abs,
    "max": max,
    "min": min,
    "pow": pow,
}

_DEFAULT_CONSTANTS: Dict[str, float] = {
    "pi": 3.14159265359,
    "e": 2.71828182846,
    "g": 9.81,
    "soil_expansion_factor": 1.05,
    "compaction_factor": 0.95,
}

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_MAX_EXPRESSION_LENGTH = 500


class _SafeNodeVisitor(ast.NodeVisitor):
    """AST visitor that validates an expression contains only safe operations."""

    def __init__(self, allowed_names: set[str]):
        self.allowed_names = allowed_names
        self.errors: list[str] = []

    def visit_Expression(self, node: ast.Expression) -> None:
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if type(node.op) not in _BIN_OPS:
            self.errors.append(f"unsupported operator: {type(node.op).__name__}")
            return
        self.generic_visit(node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        if type(node.op) not in _UNARY_OPS:
            self.errors.append(f"unsupported unary operator: {type(node.op).__name__}")
            return
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_FUNCTIONS:
            func_name = node.func.id if isinstance(node.func, ast.Name) else "lambda"
            self.errors.append(f"forbidden function call: {func_name}")
            return
        for arg in node.args:
            self.visit(arg)
        for kw in node.keywords:
            self.visit(kw.value)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id not in self.allowed_names and node.id not in _SAFE_FUNCTIONS:
            self.errors.append(f"forbidden name: {node.id}")

    def visit_Constant(self, node: ast.Constant) -> None:
        if not isinstance(node.value, (int, float)):
            self.errors.append(f"unsupported constant type: {type(node.value).__name__}")

    def generic_visit(self, node: "ast.AST") -> None:
        allowed_types = (
            ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call,
            ast.Name, ast.Constant,
        )
        if type(node) not in allowed_types:
            self.errors.append(f"unsupported AST node: {type(node).__name__}")
            return
        # Only recurse into operand children, not operator objects
        if isinstance(node, ast.BinOp):
            self.visit(node.left)
            self.visit(node.right)
        elif isinstance(node, ast.UnaryOp):
            self.visit(node.operand)
        elif isinstance(node, ast.Call):
            for arg in node.args:
                self.visit(arg)
        elif isinstance(node, ast.Expression):
            self.visit(node.body)


def _safe_eval(expr_str: str, variables: Dict[str, float]) -> Optional[float]:
    try:
        tree = ast.parse(expr_str, mode="eval")
    except SyntaxError:
        return None

    allowed = set(variables.keys()) | set(_SAFE_FUNCTIONS.keys())
    visitor = _SafeNodeVisitor(allowed)
    visitor.visit(tree)
    if visitor.errors:
        return None

    def _eval_node(node: ast.AST) -> float:
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id in variables:
                return float(variables[node.id])
            raise NameError(node.id)
        if isinstance(node, ast.BinOp):
            op_fn = _BIN_OPS[type(node.op)]
            return op_fn(_eval_node(node.left), _eval_node(node.right))
        if isinstance(node, ast.UnaryOp):
            op_fn = _UNARY_OPS[type(node.op)]
            return op_fn(_eval_node(node.operand))
        if isinstance(node, ast.Call):
            func = _SAFE_FUNCTIONS[node.func.id]
            args = [_eval_node(a) for a in node.args]
            return float(func(*args))
        raise TypeError(f"cannot evaluate {type(node).__name__}")

    try:
        result = _eval_node(tree.body)
    except (NameError, TypeError, ZeroDivisionError, ValueError):
        return None

    if not isinstance(result, (int, float)) or not math.isfinite(result):
        return None
    return float(result)


class CalculationEngine:

    def __init__(self, custom_constants: Optional[Dict[str, float]] = None):
        self.constants = {**_DEFAULT_CONSTANTS, **(custom_constants or {})}

    def _substitute_variables(self, formula: str, context: CalculationContext) -> str:
        import re

        expr = formula
        all_keys = sorted(
            list(context.design_params.keys()) + list(self.constants.keys()) + list(context.constants.keys()),
            key=len,
            reverse=True,
        )
        for key in all_keys:
            if key in context.design_params:
                value = context.design_params[key]
            elif key in self.constants:
                value = self.constants[key]
            else:
                value = context.constants[key]
            expr = re.sub(rf"\b{key}\b", str(value), expr)
        return expr

    def evaluate(self, formula: str, context: CalculationContext) -> Optional[float]:
        if len(formula) > _MAX_EXPRESSION_LENGTH:
            return None
        try:
            expr = self._substitute_variables(formula, context)
            all_vars = {**self.constants, **context.constants, **context.design_params}
            return _safe_eval(expr, all_vars)
        except Exception:
            return None

    def evaluate_with_functions(self, formula: str, context: CalculationContext) -> Optional[float]:
        if len(formula) > _MAX_EXPRESSION_LENGTH:
            return None
        try:
            expr = self._substitute_variables(formula, context)
            all_vars = {**self.constants, **context.constants, **context.design_params}
            return _safe_eval(expr, all_vars)
        except Exception:
            return None
