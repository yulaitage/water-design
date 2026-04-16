import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.services.intent_detection import IntentDetectionService, Intent


class TestIntentDetection:
    def setup_method(self):
        self.service = IntentDetectionService()

    def test_detect_cost_estimate_intent(self):
        """测试费用估算意图识别"""
        result = self.service.detect("帮我估算一下这个项目的费用")
        assert result == Intent.COST_ESTIMATE

    def test_detect_cost_estimate_with_numbers(self):
        """测试带数字的费用估算"""
        result = self.service.detect("河道长度1000米，堤高5米，估算投资")
        assert result == Intent.COST_ESTIMATE

    def test_detect_report_generate_intent(self):
        """测试报告生成意图识别"""
        result = self.service.detect("帮我生成报告")
        assert result == Intent.REPORT_GENERATE

    def test_detect_terrain_upload_intent(self):
        """测试地形上传意图识别"""
        result = self.service.detect("上传地形文件")
        assert result == Intent.TERRAIN_UPLOAD

    def test_detect_general_chat_intent(self):
        """测试通用对话意图识别"""
        result = self.service.detect("今天天气不错")
        assert result == Intent.GENERAL_CHAT

    def test_extract_numbers(self):
        """测试数字提取"""
        params = self.service.extract_params("长度1000米，宽度50米", Intent.COST_ESTIMATE)
        assert "numbers" in params
        assert 1000.0 in params["numbers"]
        assert 50.0 in params["numbers"]