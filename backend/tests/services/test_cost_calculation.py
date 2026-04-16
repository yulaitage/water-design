import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.calculation_engine import CalculationEngine, CalculationContext


class TestCalculationEngine:
    def test_simple_formula(self):
        engine = CalculationEngine()
        context = CalculationContext(
            design_params={"length": 1000, "height": 5, "slope_ratio": 2.0},
            constants={"coefficient": 1.05}
        )

        result = engine.evaluate("length * height * slope_ratio", context)
        assert result == 1000 * 5 * 2.0

    def test_formula_with_constant(self):
        engine = CalculationEngine()
        context = CalculationContext(
            design_params={"length": 1000, "height": 5},
            constants={"coefficient": 1.05}
        )

        result = engine.evaluate("length * height * coefficient", context)
        assert result == 1000 * 5 * 1.05

    def test_invalid_formula_returns_none(self):
        engine = CalculationEngine()
        context = CalculationContext(design_params={}, constants={})

        result = engine.evaluate("invalid +++ formula", context)
        assert result is None

    def test_missing_param_returns_none(self):
        engine = CalculationEngine()
        context = CalculationContext(
            design_params={"length": 1000},
            constants={}
        )

        result = engine.evaluate("length * missing_param", context)
        assert result is None

    def test_calculate_earthwork_volume(self):
        """测试土方工程量计算"""
        # V = H × (B + m×H) × L
        # H=5m, B=10m, m=2, L=1000m
        # V = 5 * (10 + 2*5) * 1000 = 5 * 20 * 1000 = 100000 m³
        context = CalculationContext(
            design_params={"height": 5, "topwidth": 10, "slope_ratio": 2, "length": 1000},
            constants={}
        )
        engine = CalculationEngine()
        result = engine.evaluate("height * (topwidth + slope_ratio * height) * length", context)
        assert result == 100000