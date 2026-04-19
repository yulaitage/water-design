import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.api.v1.projects import list_projects, create_project, get_project, delete_project


class TestListProjects:
    @pytest.mark.asyncio
    async def test_returns_project_list(self):
        mock_project = MagicMock()
        mock_project.id = uuid.uuid4()
        mock_project.name = "测试项目"
        mock_project.description = "描述"
        mock_project.created_at = MagicMock()

        mock_count = MagicMock()
        mock_count.scalar_one.return_value = 1

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_project]

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[mock_count, mock_result])

        response = await list_projects(skip=0, limit=20, db=mock_db)

        assert response.total == 1
        assert len(response.projects) == 1
        assert response.projects[0].name == "测试项目"


class TestCreateProject:
    @pytest.mark.asyncio
    async def test_creates_project(self):
        mock_db = AsyncMock()
        mock_db.refresh = AsyncMock()

        mock_project = MagicMock()
        mock_project.id = uuid.uuid4()
        mock_project.name = "新项目"
        mock_project.description = "描述"
        mock_project.created_at = MagicMock()

        with patch("app.api.v1.projects.Project") as MockProject:
            MockProject.return_value = mock_project
            mock_db.add = MagicMock()

            response = await create_project(
                request=MagicMock(name="新项目", description="描述"),
                db=mock_db,
            )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestGetProject:
    @pytest.mark.asyncio
    async def test_returns_existing_project(self):
        mock_project = MagicMock()
        mock_project.id = uuid.uuid4()
        mock_project.name = "项目A"
        mock_project.description = None
        mock_project.created_at = MagicMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_project

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        response = await get_project(uuid.uuid4(), db=mock_db)
        assert response.name == "项目A"

    @pytest.mark.asyncio
    async def test_raises_404_for_missing(self):
        from fastapi import HTTPException

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await get_project(uuid.uuid4(), db=mock_db)

        assert exc_info.value.status_code == 404


class TestDeleteProject:
    @pytest.mark.asyncio
    async def test_deletes_existing(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.delete = AsyncMock()
        mock_db.commit = AsyncMock()

        await delete_project(uuid.uuid4(), db=mock_db)
        mock_db.delete.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_404_for_missing(self):
        from fastapi import HTTPException

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await delete_project(uuid.uuid4(), db=mock_db)

        assert exc_info.value.status_code == 404
