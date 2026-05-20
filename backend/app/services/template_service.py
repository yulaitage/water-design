from pathlib import Path
from typing import Dict, Any
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches
from jinja2 import Template
import re


class TemplateService:
    """Word文档模板渲染服务"""

    def __init__(self, template_dir: str = "templates/reports"):
        self.template_dir = Path(template_dir)
        self.template_dir.mkdir(parents=True, exist_ok=True)

    def get_chapter_template(self, report_type: str) -> Dict[str, str]:
        """获取报告章节模板"""
        templates = {
            "feasibility": {
                "1": "## {{ chapter_num }}. 项目概述\n\n### {{ chapter }}.1 项目背景\n{{ content }}",
                "2": "## {{ chapter_num }}. 工程建设的必要性\n\n### {{ chapter }}.1 项目由来\n{{ content }}",
                "3": "## {{ chapter_num }}. 工程任务与规模\n\n### {{ chapter }}.1 防洪标准\n{{ content }}",
            }
        }
        return templates.get(report_type, {})

    def render_chapter(
        self,
        template: str,
        chapter_num: str,
        content: str,
        context: Dict[str, Any]
    ) -> str:
        """渲染单个章节"""
        t = Template(template, autoescape=True)
        return t.render(
            chapter_num=chapter_num,
            chapter=chapter_num,
            content=content,
            **context
        )

    def _insert_images(self, doc: Document, content: str, base_path: str = ".") -> str:
        """将Markdown中的图片插入到Word文档，返回剩余文本内容"""
        pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        remaining = content

        for match in re.finditer(pattern, content):
            alt_text = match.group(1)
            img_path = match.group(2)
            full_match = match.group(0)

            # 尝试插入图片
            try:
                img_file = Path(base_path) / img_path
                if not img_file.exists():
                    img_file = Path(img_path)
                if img_file.exists():
                    # 找到图片在文本中的位置，在其前面插入
                    idx = remaining.find(full_match)
                    if idx >= 0:
                        before = remaining[:idx]
                        after = remaining[idx + len(full_match):]
                        # 在before末尾插入段落和图片
                        if before.strip():
                            doc.add_paragraph(before.strip())
                        doc.add_picture(str(img_file), width=Inches(5.5))
                        remaining = after
                        continue
            except Exception:
                pass

            # 如果图片处理失败，保留原文
            remaining = remaining.replace(full_match, f"[插图: {alt_text}]", 1)

        # 处理剩余文本
        if remaining.strip():
            doc.add_paragraph(remaining.strip())
        return remaining

    def create_word_document(
        self,
        chapters: Dict[str, str],
        output_path: str,
        title: str
    ) -> str:
        """创建Word文档，支持Markdown图片格式"""
        doc = Document()

        # 设置标题
        heading = doc.add_heading(title, 0)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 添加章节
        for chapter_title, chapter_content in chapters.items():
            doc.add_heading(chapter_title, level=1)

            # 处理图片插入
            pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
            parts = re.split(pattern, chapter_content)

            if len(parts) > 1:
                # 有图片的情况
                i = 0
                while i < len(parts):
                    if i % 3 == 0:
                        # 文本部分
                        text = parts[i].strip()
                        if text:
                            doc.add_paragraph(text)
                    elif i % 3 == 1:
                        # alt text
                        alt_text = parts[i]
                    elif i % 3 == 2:
                        # 图片路径
                        img_path = parts[i].strip()
                        try:
                            img_file = Path(img_path)
                            if img_file.exists():
                                last_para = doc.paragraphs[-1] if doc.paragraphs else None
                                doc.add_picture(str(img_file), width=Inches(5.5))
                        except Exception:
                            doc.add_paragraph(f"[插图: {parts[i-1]}]")
                    i += 1
            else:
                # 无图片，直接添加段落
                doc.add_paragraph(chapter_content)

        # 保存
        doc.save(output_path)
        return output_path

    def template_exists(self, report_type: str) -> bool:
        """检查模板是否存在"""
        template_path = self.template_dir / f"{report_type}_template.md"
        return template_path.exists()