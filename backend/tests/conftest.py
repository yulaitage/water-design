import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.db.database import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def mock_llm():
    """Mock LLM that returns canned responses"""
    mock = AsyncMock()
    mock.ainvoke = AsyncMock(return_value=MagicMock(content="这是一个模拟的LLM响应。"))
    mock.astream = AsyncMock()
    async def _stream(*args, **kwargs):
        yield MagicMock(content="这")
        yield MagicMock(content="是")
        yield MagicMock(content="模拟")
        yield MagicMock(content="响应。")
    mock.astream.return_value = _stream()
    return mock


@pytest.fixture
def mock_embeddings():
    """Mock Embeddings that returns fixed vectors"""
    mock = AsyncMock()
    mock.aembed_query = AsyncMock(return_value=[[0.1] * 1536])
    return mock
