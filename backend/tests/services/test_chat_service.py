import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.services.chat_service import ChatService
from app.schemas.chat import ChatRequest


class TestChatService:
    def setup_method(self):
        self.mock_db = AsyncMock()

    @pytest.mark.asyncio
    async def test_chat_service_initialization(self):
        service = ChatService(self.mock_db)
        assert service.db is self.mock_db

    @pytest.mark.asyncio
    async def test_chat_delegates_to_orchestrator(self):
        service = ChatService(self.mock_db)
        request = ChatRequest(project_id=uuid.uuid4(), message="你好")

        mock_response = MagicMock()
        mock_response.conversation_id = uuid.uuid4()
        mock_response.message = "您好！"
        mock_response.intent = "GENERAL_CHAT"

        with patch("app.services.chat_service.AgentOrchestrator") as MockOrch:
            mock_orch = MockOrch.return_value
            mock_orch.process = AsyncMock(return_value=mock_response)

            result = await service.chat(request)

        assert result.message == "您好！"
        assert result.intent == "GENERAL_CHAT"

    @pytest.mark.asyncio
    async def test_get_history_returns_list(self):
        service = ChatService(self.mock_db)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        self.mock_db.execute = AsyncMock(return_value=mock_result)

        history = await service.get_history(uuid.uuid4())
        assert isinstance(history, list)
