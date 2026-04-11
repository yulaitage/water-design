import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from app.services.template_service import TemplateService


class TestTemplateService:
    @pytest.fixture
    def service(self, tmp_path):
        return TemplateService(template_dir=str(tmp_path))

    def test_chapter_template_exists(self, service):
        templates = service.get_chapter_template("feasibility")
        assert "1" in templates
        assert "2" in templates

    def test_create_word_document(self, service, tmp_path):
        output_path = tmp_path / "test_report.docx"
        chapters = {
            "第1章 项目概述": "项目背景内容...",
            "第2章 工程必要性": "必要性内容..."
        }

        result = service.create_word_document(
            chapters=chapters,
            output_path=str(output_path),
            title="测试报告"
        )

        assert Path(result).exists()