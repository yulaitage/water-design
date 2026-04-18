import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.services.retrieval_service import RetrievalService


class TestRetrievalService:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_retrieve_specifications_delegates_to_vector_store(self, mock_db):
        mock_vs = AsyncMock()
        mock_vs.search_similar_specifications = AsyncMock(return_value=[
            {
                "id": str(uuid.uuid4()),
                "name": "堤防工程设计规范",
                "code": "GB 50286",
                "chapter": "3.1",
                "section": "3.1.2",
                "content": "堤防工程设计标准...",
                "project_types": ["堤防"],
                "similarity": 0.95,
                "source": "specification",
            }
        ])

        with patch("app.services.retrieval_service.VectorStoreService", return_value=mock_vs):
            service = RetrievalService(mock_db)
            results = await service.retrieve_specifications("堤顶高程", "堤防")

        assert len(results) == 1
        assert results[0]["code"] == "GB 50286"
        mock_vs.search_similar_specifications.assert_called_once_with(
            query="堤顶高程", top_k=10, project_type="堤防"
        )

    @pytest.mark.asyncio
    async def test_retrieve_cases_filters_by_location(self, mock_db):
        mock_vs = AsyncMock()
        mock_vs.search_similar_cases = AsyncMock(return_value=[
            {
                "id": str(uuid.uuid4()),
                "name": "XX河道整治",
                "project_type": "河道整治",
                "location": "浙江省杭州市",
                "similarity": 0.88,
                "source": "case",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "YY河道治理",
                "project_type": "河道整治",
                "location": "浙江省宁波市",
                "similarity": 0.82,
                "source": "case",
            },
        ])

        with patch("app.services.retrieval_service.VectorStoreService", return_value=mock_vs):
            service = RetrievalService(mock_db)
            results = await service.retrieve_cases("河道整治", "河道整治", location="杭州")

        assert len(results) == 1
        assert "杭州" in results[0]["location"]

    @pytest.mark.asyncio
    async def test_retrieve_for_chapter(self, mock_db):
        mock_vs = AsyncMock()
        mock_vs.search_similar_specifications = AsyncMock(return_value=[])
        mock_vs.search_similar_cases = AsyncMock(return_value=[])

        with patch("app.services.retrieval_service.VectorStoreService", return_value=mock_vs):
            service = RetrievalService(mock_db)
            specs, cases = await service.retrieve_for_chapter("工程设计", "堤防", "浙江")

        assert specs == []
        assert cases == []
        mock_vs.search_similar_specifications.assert_called_once_with(
            query="工程设计", top_k=5, project_type="堤防"
        )
