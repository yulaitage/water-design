import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.core.vector_store import VectorStoreService


class TestVectorStoreService:
    def setup_method(self):
        self.mock_db = AsyncMock()

    @pytest.mark.asyncio
    async def test_embed_text(self):
        mock_embeddings = AsyncMock()
        mock_embeddings.aembed_query = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

        with patch("app.core.embeddings.get_embeddings", return_value=mock_embeddings):
            service = VectorStoreService(self.mock_db)
            result = await service.embed_text("测试文本")

        assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_embed_text_empty_result(self):
        mock_embeddings = AsyncMock()
        mock_embeddings.aembed_query = AsyncMock(return_value=[])

        with patch("app.core.embeddings.get_embeddings", return_value=mock_embeddings):
            service = VectorStoreService(self.mock_db)
            result = await service.embed_text("测试")

        assert result == []

    @pytest.mark.asyncio
    async def test_store_specification_embedding(self):
        mock_spec = MagicMock()
        mock_spec.content = "堤防工程设计规范条文..."

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_spec
        self.mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.object(VectorStoreService, "embed_text", new_callable=AsyncMock, return_value=[0.1] * 1536):
            service = VectorStoreService(self.mock_db)
            await service.store_specification_embedding(uuid.uuid4())

        assert mock_spec.content_embedding == [0.1] * 1536
        self.mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_similar_specifications(self):
        mock_row = MagicMock()
        mock_row.id = uuid.uuid4()
        mock_row.name = "堤防规范"
        mock_row.code = "GB 50286"
        mock_row.chapter = "3.1"
        mock_row.section = "3.1.2"
        mock_row.content = "条文内容"
        mock_row.project_types = ["堤防"]
        mock_row.similarity = 0.95

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [mock_row]
        self.mock_db.execute = AsyncMock(return_value=mock_result)

        with patch.object(VectorStoreService, "embed_text", new_callable=AsyncMock, return_value=[0.1] * 1536):
            service = VectorStoreService(self.mock_db)
            results = await service.search_similar_specifications("堤顶高程", top_k=5)

        assert len(results) == 1
        assert results[0]["code"] == "GB 50286"
        assert results[0]["similarity"] == 0.95

    @pytest.mark.asyncio
    async def test_search_similar_specifications_empty_embedding(self):
        with patch.object(VectorStoreService, "embed_text", new_callable=AsyncMock, return_value=[]):
            service = VectorStoreService(self.mock_db)
            results = await service.search_similar_specifications("测试")

        assert results == []
