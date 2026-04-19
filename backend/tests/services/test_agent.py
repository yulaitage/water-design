import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from app.services.agent_orchestrator import AgentOrchestrator
from app.schemas.chat import ChatRequest


class TestAgentOrchestrator:
    def setup_method(self):
        self.mock_db = AsyncMock()

    @pytest.mark.asyncio
    async def test_process_calls_agent_and_stores_conversation(self):
        with patch("app.services.agent_orchestrator.invoke_agent", new_callable=AsyncMock) as mock_invoke, \
             patch("app.services.agent_orchestrator.MemoryService") as MockMemory:

            mock_memory = MockMemory.return_value
            mock_memory.get_recent_messages = AsyncMock(return_value=[])
            mock_memory.build_context_block = AsyncMock(return_value="")
            mock_memory.append_conversation = AsyncMock(return_value=uuid.uuid4())

            mock_invoke.return_value = "工程量估算结果如下..."

            orchestrator = AgentOrchestrator(self.mock_db)
            request = ChatRequest(project_id=uuid.uuid4(), message="帮我估算费用")

            result = await orchestrator.process(request)

        assert "费用" in result.intent or result.intent == "COST_ESTIMATE"
        assert result.message == "工程量估算结果如下..."
        mock_memory.append_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_intent_tag_cost(self):
        assert AgentOrchestrator._detect_intent_tag("总造价 500 万元") == "COST_ESTIMATE"
        assert AgentOrchestrator._detect_intent_tag("工程量统计") == "COST_ESTIMATE"

    @pytest.mark.asyncio
    async def test_detect_intent_tag_report(self):
        assert AgentOrchestrator._detect_intent_tag("生成可研报告") == "REPORT_GENERATE"

    @pytest.mark.asyncio
    async def test_detect_intent_tag_spec(self):
        assert AgentOrchestrator._detect_intent_tag("GB 50286 规范要求") == "SPEC_SEARCH"

    @pytest.mark.asyncio
    async def test_detect_intent_tag_general(self):
        assert AgentOrchestrator._detect_intent_tag("你好") == "GENERAL_CHAT"


class TestAgentTools:
    def test_create_tools_returns_list(self):
        mock_db = AsyncMock()
        from app.services.agent import create_tools
        tools = create_tools(mock_db)
        assert len(tools) == 4
        names = {t.name for t in tools}
        assert "estimate_cost" in names
        assert "search_specifications" in names
        assert "generate_report" in names
        assert "analyze_terrain" in names
