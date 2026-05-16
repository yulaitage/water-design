import base64
import httpx
import logging
from typing import Optional

from openai import AsyncOpenAI
from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位水利工程设计专家。请以专业、准确的语言描述这张工程设计图中的内容。
重点关注：
1. 图的类型（断面图、平面布置图、结构图、流程图等）
2. 图中标注的工程参数和尺寸
3. 图示的结构组成和空间关系
4. 图例和符号的含义
5. 如果是示意图，说明其表达的设计概念

描述应该详细但不过于冗长，控制在200字以内。以便后续通过语义搜索能匹配到相关工程需求。"""


class VisionService:
    """多模态视觉模型服务 — 为工程图片生成描述"""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.model_name = model_name or settings.vision_model or settings.llm_model
        self.api_key = api_key or settings.vision_api_key or settings.llm_api_key
        base_url = base_url or settings.vision_base_url or settings.llm_base_url or ""
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
        self.base_url = base_url
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=httpx.Timeout(20.0, connect=5.0),
        )

    async def describe_image(
        self,
        image_bytes: bytes,
        context_text: str = "",
    ) -> Optional[str]:
        """调用多模态模型生成图片描述

        Args:
            image_bytes: 图片原始字节（PNG/JPEG）
            context_text: PDF 中图片周围的文字，用于辅助理解

        Returns:
            AI 生成的图片描述，失败时返回 None
        """
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:image/png;base64,{image_b64}"

        user_text = "请描述这张工程设计图。"
        if context_text:
            user_text += f"\n\n图片在文档中的上下文文字如下，可供参考：\n{context_text[:500]}"

        try:
            client = self._client

            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": image_url}},
                            {"type": "text", "text": user_text},
                        ],
                    },
                ],
                max_tokens=400,
                temperature=0.3,
            )

            description = response.choices[0].message.content
            if description:
                logger.info("Vision description generated: %s...", description[:60])
                return description.strip()
            return None

        except Exception as e:
            logger.warning("Vision model call failed: %s", e)
            return None
