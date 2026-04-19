import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.services.memory_service import MemoryService


class TestMemoryService:
    def setup_method(self):
        self.mock_db = AsyncMock()

    @pytest.mark.asyncio
    async def test_get_recent_messages_empty(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_db.execute = AsyncMock(return_value=mock_result)

        service = MemoryService(self.mock_db)
        messages = await service.get_recent_messages(uuid.uuid4())

        assert messages == []

    @pytest.mark.asyncio
    async def test_get_recent_messages_returns_last_n(self):
        mock_conversation = MagicMock()
        mock_conversation.messages = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "您好！"},
            {"role": "user", "content": "帮我估算"},
            {"role": "assistant", "content": "请提供参数"},
        ]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_conversation
        self.mock_db.execute = AsyncMock(return_value=mock_result)

        service = MemoryService(self.mock_db)
        messages = await service.get_recent_messages(uuid.uuid4(), limit=2)

        assert len(messages) == 2
        assert messages[0]["content"] == "帮我估算"

    @pytest.mark.asyncio
    async def test_append_conversation_creates_new(self):
        from app.models.conversation import Conversation

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        self.mock_db.execute = AsyncMock(return_value=mock_result)
        self.mock_db.add = MagicMock()
        self.mock_db.flush = AsyncMock()
        self.mock_db.commit = AsyncMock()
        self.mock_db.refresh = AsyncMock()

        service = MemoryService(self.mock_db)
        conv_id = await service.append_conversation(
            project_id=uuid.uuid4(),
            user_message="你好",
            assistant_message="您好！",
        )

        self.mock_db.add.assert_called_once()
        self.mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_semantic_memory_fallback(self):
        with patch("app.core.vector_store.VectorStoreService") as MockVS:
            mock_vs = MockVS.return_value
            mock_vs.search_similar_specifications = AsyncMock(return_value=[])

            service = MemoryService(self.mock_db)
            result = await service.search_semantic_memory("堤防设计")

        assert result == ""
