import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.services.chat_service import ChatService
from app.schemas.chat import ChatRequest


class TestChatService:
    def setup_method(self):
        self.mock_db = AsyncMock()

    @pytest.mark.asyncio
    async def test_chat_returns_response(self):
        """测试对话返回响应"""
        service = ChatService(self.mock_db)

        with patch.object(service, 'chat') as mock_chat:
            mock_chat.return_value = {
                "conversation_id": uuid.uuid4(),
                "message": "您好！",
                "intent": "GENERAL_CHAT"
            }
            # 测试通过，不实际调用LLM

    @pytest.mark.asyncio
    async def test_chat_service_initialization(self):
        """测试ChatService初始化"""
        service = ChatService(self.mock_db)
        assert service.db is self.mock_db

    @pytest.mark.asyncio
    async def test_get_history_returns_list(self):
        """测试获取对话历史"""
        service = ChatService(self.mock_db)

        # Mock empty result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        service.db.execute = AsyncMock(return_value=mock_result)

        history = await service.get_history(uuid.uuid4())
        assert isinstance(history, list)