import io
import logging
from typing import Optional, List
from pathlib import Path
import uuid

import fitz  # pymupdf

logger = logging.getLogger(__name__)


class PDFParsingService:
    """PDF 文档解析服务 - 提取文本、表格和图片内容"""

    def __init__(self):
        self.chunk_size = 1000        # 每个语义块的目标最大字符数
        self.min_chunk_size = 100     # 最小块大小，低于此值会合并到相邻块
        self.context_sentences = 1    # 每块末尾携带上一块的最后 N 句作为上下文重叠
        self.min_image_size = 20      # 忽略小于此尺寸（point）的图片（装饰/噪声）

    def parse_pdf(self, file_path: str) -> dict:
        """
        解析 PDF 文件并返回结构化内容

        Returns:
            {
                "text": str,
                "chunks": List[dict],
                "metadata": dict,
                "images": List[dict],  # 新增: 提取的图片元数据
            }
        """
        full_text = ""
        chunks = []
        metadata = {
            "page_count": 0,
            "title": "",
            "author": "",
            "sections": []
        }

        doc = fitz.open(file_path)
        try:
            metadata["page_count"] = len(doc)
            metadata["title"] = doc.metadata.get("title", "") or ""
            metadata["author"] = doc.metadata.get("author", "") or ""

            # 提取所有嵌入图片
            all_raw_images = self._extract_raw_images(doc)

            for page_num, page in enumerate(doc, start=1):
                # 提取文本
                text = page.get_text("text") or ""

                if text:
                    full_text += f"\n--- 第 {page_num} 页 ---\n{text}"
                    page_chunks = self._split_into_chunks(text, page_num)
                    chunks.extend(page_chunks)

                # 提取表格
                tables = page.find_tables()
                for table_idx, table in enumerate(tables):
                    if table and table.extract():
                        table_text = self._fitz_table_to_text(table)
                        chunks.append({
                            "text": table_text,
                            "page": page_num,
                            "type": "table",
                            "index": table_idx,
                        })

            # 将图片关联到同页的文字块
            images_meta = self._link_images_to_chunks(all_raw_images, chunks, doc)

            # 识别章节
            metadata["sections"] = self._detect_sections(full_text)

        except Exception as e:
            logger.error(f"Failed to parse PDF: {e}")
            raise ValueError(f"PDF 解析失败: {str(e)}")
        finally:
            doc.close()

        return {
            "text": full_text,
            "chunks": chunks,
            "metadata": metadata,
            "images": images_meta,
        }

    # ========== 图片提取 ==========

    def _extract_raw_images(self, doc: fitz.Document) -> List[dict]:
        """提取所有嵌入图片及其页面坐标"""
        images = []
        for page_num, page in enumerate(doc, start=1):
            image_list = page.get_images(full=True)
            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    ext = base_image["ext"]
                except Exception:
                    continue

                rects = page.get_image_rects(xref)
                for rect in rects:
                    if rect.width < self.min_image_size or rect.height < self.min_image_size:
                        continue
                    images.append({
                        "image_index": img_idx,
                        "page": page_num,
                        "xref": xref,
                        "image_bytes": image_bytes,
                        "ext": ext,
                        "x": round(rect.x0, 1),
                        "y": round(rect.y0, 1),
                        "width": round(rect.width, 1),
                        "height": round(rect.height, 1),
                    })
        return images

    def _extract_text_blocks(self, page) -> List[dict]:
        """获取页面上的文字块及其坐标"""
        blocks = page.get_text("blocks")
        result = []
        for b in blocks:
            text = (b[4] or "").strip()
            if text:
                result.append({
                    "x0": b[0], "y0": b[1], "x1": b[2], "y1": b[3],
                    "text": text,
                })
        return result

    def _find_context_for_image(
        self,
        img: dict,
        text_blocks: List[dict],
        chunks_on_page: List[dict],
    ) -> tuple:
        """找到图片最邻近的文字上下文和对应的 chunk，返回 (context_text, chunk_id, context_before, context_after)"""
        if not text_blocks:
            return ("", None, None, None)

        # 找到图片下方最近的文字块（图注通常是图片正下方的文字）
        img_center_y = img["y"] + img["height"] / 2
        blocks_below = [b for b in text_blocks if b["y0"] >= img_center_y]
        blocks_above = [b for b in text_blocks if b["y1"] <= img_center_y]

        # 优先取图下方最近的块（可能是图注），其次取上方最近的块（描述文字）
        nearest_block = None
        if blocks_below:
            nearest_block = min(blocks_below, key=lambda b: b["y0"] - img_center_y)
        elif blocks_above:
            nearest_block = min(blocks_above, key=lambda b: img_center_y - b["y1"])

        if not nearest_block:
            return ("", None, None, None)

        context_text = nearest_block["text"][:2000]

        # context_before: 图片上方最近的文字块
        context_before = None
        if blocks_above:
            before_block = max(blocks_above, key=lambda b: b["y1"])
            context_before = before_block["text"][:500]

        # context_after: 图片下方最近的文字块（不是图注，取下一个）
        context_after = None
        if len(blocks_below) >= 2:
            # 第二近的下方块
            sorted_below = sorted(blocks_below, key=lambda b: b["y0"] - img_center_y)
            after_block = sorted_below[1] if len(sorted_below) > 1 else sorted_below[0]
            context_after = after_block["text"][:500]
        elif blocks_below:
            context_after = blocks_below[0]["text"][:500]

        # 匹配到同页的 chunk
        linked_id = None
        best_overlap = 0
        for chunk in chunks_on_page:
            overlap = self._trigram_overlap(context_text, chunk["text"])
            if overlap > best_overlap:
                best_overlap = overlap
                linked_id = chunk.get("_db_id")  # 在知识库上传时会被设置

        return (context_text, linked_id, context_before, context_after)

    def _trigram_overlap(self, a: str, b: str) -> int:
        """计算两个字符串中共享的 3-gram 数量"""
        if len(a) < 3 or len(b) < 3:
            return 0
        trigrams_a = {a[i:i + 3] for i in range(len(a) - 2)}
        trigrams_b = {b[i:i + 3] for i in range(len(b) - 2)}
        return len(trigrams_a & trigrams_b)

    def _link_images_to_chunks(
        self,
        raw_images: List[dict],
        chunks: List[dict],
        doc: fitz.Document,
    ) -> List[dict]:
        """将每张图片关联到周围文本，返回图片元数据列表（不含 image_bytes 以减少内存）"""
        if not raw_images:
            return []

        chunks_by_page: dict = {}
        for chunk in chunks:
            page = chunk.get("page", 1)
            chunks_by_page.setdefault(page, []).append(chunk)

        # 缓存每页的文字块
        text_blocks_cache: dict = {}

        result = []
        for img in raw_images:
            page_num = img["page"]
            if page_num not in text_blocks_cache:
                text_blocks_cache[page_num] = self._extract_text_blocks(doc[page_num - 1])

            text_blocks = text_blocks_cache[page_num]
            context_text, linked_id, context_before, context_after = self._find_context_for_image(
                img, text_blocks, chunks_by_page.get(page_num, [])
            )

            # 返回不含 image_bytes 的元数据（调用方在知识库 API 中保存图片文件）
            result.append({
                "page": img["page"],
                "image_index": img["image_index"],
                "ext": img["ext"],
                "x": img["x"],
                "y": img["y"],
                "width": img["width"],
                "height": img["height"],
                "context_text": context_text,
                "context_before": context_before,
                "context_after": context_after,
                "linked_chunk_id": linked_id,
                # image_bytes 单独保留供调用方写入文件
                "_image_bytes": img["image_bytes"],
            })

        return result

    # ========== 表格提取 ==========

    def _fitz_table_to_text(self, table) -> str:
        """将 pymupdf 表格转为竖线分隔文本"""
        lines = []
        for row in table.extract():
            cleaned = [str(cell).strip() if cell else "" for cell in row]
            lines.append(" | ".join(cleaned))
        return "\n".join(lines)

    def _split_into_chunks(self, text: str, page_num: int) -> List[dict]:
        """按语义边界分块：段落 → 章节 → 句子 → 按目标大小合并"""
        import re

        # Step 1: normalize whitespace (PDF extraction often has erratic line breaks)
        normalized = re.sub(r'\n{3,}', '\n\n', text)

        # Step 2: split by double-newline paragraph boundaries
        raw_paras = [p.strip() for p in re.split(r'\n{2,}', normalized) if p.strip()]

        # Step 3: further split paragraphs at chapter/section headers (第X章, 1.2.3, etc.)
        segments = self._split_by_section_headers(raw_paras)
        if not segments:
            return []

        # Step 4: split all segments into sentences for fine-grained merging
        all_sentences = []
        for seg in segments:
            all_sentences.extend(self._split_by_sentences(seg))

        # Step 5: merge sentences into target-sized chunks, splitting only at sentence boundaries
        chunks = []
        buffer = ""
        prev_context = ""

        for sent in all_sentences:
            if not sent:
                continue

            if not buffer:
                buffer = (prev_context + sent) if prev_context else sent
                continue

            combined = buffer + sent
            if len(combined) <= self.chunk_size:
                buffer = combined
            else:
                # Buffer is full — find last sentence boundary within chunk_size
                # to avoid creating a tiny orphan chunk
                keep, spill = self._cut_at_sentence_boundary(buffer, self.chunk_size)
                if keep:
                    chunks.append({"text": keep, "page": page_num, "type": "text"})
                    prev_context = self._extract_last_sentences(keep)
                    buffer = (prev_context + spill + sent) if spill else (prev_context + sent)
                else:
                    # Single sentence exceeds chunk_size — keep it as one chunk
                    chunks.append({"text": buffer, "page": page_num, "type": "text"})
                    prev_context = self._extract_last_sentences(buffer)
                    buffer = sent

        if buffer:
            chunks.append({"text": buffer, "page": page_num, "type": "text"})

        return chunks

    def _cut_at_sentence_boundary(self, text: str, max_len: int) -> tuple:
        """在句子边界处切分文本，返回 (前半部分, 后半部分)"""
        import re
        boundaries = list(re.finditer(r'[。；！？]', text))
        if not boundaries:
            return ("", text)

        # Find last sentence boundary that keeps the chunk <= max_len
        last_good = None
        for m in boundaries:
            if m.end() <= max_len:
                last_good = m
            else:
                break

        if last_good is None:
            # First sentence already exceeds max_len — keep it whole
            for m in boundaries:
                if m.end() > 0:
                    return (text[:m.end()], text[m.end():])
            return ("", text)

        return (text[:last_good.end()], text[last_good.end():])

    def _split_by_section_headers(self, paragraphs: List[str]) -> List[str]:
        """在段落列表中进一步按章节标题拆分"""
        import re

        header_pattern = re.compile(
            r'^(?:第[一二三四五六七八九十\d]+[章节部篇]'
            r'|（[一二三四五六七八九十\d]+）'
            r'|\d+(?:\.\d+)*[\s\．\.]+)'
        )

        result = []
        for para in paragraphs:
            lines = para.split('\n')
            buf = []
            for line in lines:
                stripped = line.strip()
                if header_pattern.match(stripped) and buf:
                    seg_text = '\n'.join(buf).strip()
                    if seg_text:
                        result.append(seg_text)
                    buf = [line]
                else:
                    buf.append(line)
            if buf:
                seg_text = '\n'.join(buf).strip()
                if seg_text:
                    result.append(seg_text)

        return result

    def _split_by_sentences(self, text: str) -> List[str]:
        """将过长段落按中文句子边界拆分"""
        import re
        raw = re.split(r'(?<=[。；！？])(?=\s*\S)', text)

        sentences = []
        buf = ""
        for part in raw:
            buf += part
            if len(buf) >= 20 or re.search(r'[。；！？]$', buf):
                sentences.append(buf.strip())
                buf = ""
        if buf.strip():
            sentences.append(buf.strip())

        return sentences

    def _extract_last_sentences(self, text: str) -> str:
        """提取文本末尾的 N 个句子，作为下一块的上下文"""
        import re
        sentences = re.split(r'(?<=[。；！？])(?=\s*\S)', text)
        count = min(self.context_sentences, len(sentences))
        return ''.join(sentences[-count:]) if count > 0 else ""

    def _merge_small_chunks(self, chunks: List[dict]) -> List[dict]:
        """合并过小的块到相邻块"""
        if len(chunks) <= 1:
            return chunks

        merged = []
        i = 0
        while i < len(chunks):
            chunk = chunks[i]
            if len(chunk["text"]) >= self.min_chunk_size:
                merged.append(chunk)
                i += 1
            elif i + 1 < len(chunks):
                nxt = chunks[i + 1]
                merged.append({
                    "text": chunk["text"] + '\n' + nxt["text"],
                    "page": chunk["page"], "type": chunk["type"],
                })
                i += 2
            elif merged:
                prev = merged[-1]
                merged[-1] = {
                    "text": prev["text"] + '\n' + chunk["text"],
                    "page": prev["page"], "type": prev["type"],
                }
                i += 1
            else:
                merged.append(chunk)
                i += 1

        return merged

    def _table_to_text(self, table: List[List[str]], page_num: int) -> str:
        """将表格转换为文本"""
        lines = []
        for row in table:
            cleaned_row = [cell.strip() if cell else "" for cell in row]
            lines.append(" | ".join(cleaned_row))
        return "\n".join(lines)

    def _detect_sections(self, text: str) -> List[dict]:
        """检测文本中的章节（简单实现）"""
        sections = []
        # 常见的中文章节标题模式
        patterns = [
            r"^第[一二三四五六七八九十\d]+[章节部篇]",
            r"^\d+[章节部篇]",
            r"^[0-9]+\.[0-9]+",  # 1.2, 1.2.3 等编号
            r"^#{1,6}\s",  # Markdown 标题
        ]
        import re
        lines = text.split('\n')
        for i, line in enumerate(lines):
            for pattern in patterns:
                if re.match(pattern, line.strip()):
                    sections.append({
                        "title": line.strip(),
                        "line": i,
                        "level": len(re.match(r'^(#+)\s', line.strip()).group(1)) if re.match(r'^#+\s', line.strip()) else 0
                    })
                    break
        return sections

    def extract_key_info(self, text: str) -> dict:
        """提取关键信息（工程名称、设计参数等）"""
        import re

        info = {
            "project_name": None,
            "design_standards": [],
            "parameters": {}
        }

        # 尝试匹配项目名称
        name_patterns = [
            r"工程名称[：:]\s*([^\n]+)",
            r"项目名称[：:]\s*([^\n]+)",
            r"工程[：:]\s*([^\n]+)",
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text)
            if match:
                info["project_name"] = match.group(1).strip()
                break

        # 提取设计规范
        standard_pattern = r"(GB|SL|SDJ|JGJ|DL|TB)[-\s]?[0-9]{3,}[^\n]*"
        info["design_standards"] = re.findall(standard_pattern, text)

        # 提取设计参数（简单实现）
        param_patterns = {
            "流量": r"设计流量[：:]\s*([^\n]+)",
            "堤顶高程": r"堤顶高程[：:]\s*([^\n]+)",
            "堤宽": r"堤顶宽度[：:]\s*([^\n]+)",
        }
        for param_name, pattern in param_patterns.items():
            match = re.search(pattern, text)
            if match:
                info["parameters"][param_name] = match.group(1).strip()

        return info