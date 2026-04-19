import pytest
from unittest.mock import patch, MagicMock

from app.core.llm import get_llm
from app.core.embeddings import get_embeddings


class TestLLMFactory:
    def test_get_llm_returns_chat_openai(self):
        with patch("app.core.llm.settings") as mock_settings:
            mock_settings.llm_model = "gpt-4o"
            mock_settings.llm_api_key = "test-key"
            mock_settings.llm_base_url = "https://api.openai.com/v1"
            mock_settings.llm_temperature = 0.3

            with patch("app.core.llm.ChatOpenAI") as MockChat:
                mock_instance = MagicMock()
                MockChat.return_value = mock_instance

                llm = get_llm()

                MockChat.assert_called_once_with(
                    model="gpt-4o",
                    api_key="test-key",
                    base_url="https://api.openai.com/v1",
                    temperature=0.3,
                )
                assert llm is mock_instance

    def test_get_llm_custom_temperature(self):
        with patch("app.core.llm.settings") as mock_settings:
            mock_settings.llm_model = "qwen-plus"
            mock_settings.llm_api_key = "key"
            mock_settings.llm_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            mock_settings.llm_temperature = 0.5

            with patch("app.core.llm.ChatOpenAI") as MockChat:
                get_llm(temperature=0.1)

                MockChat.assert_called_once()
                assert MockChat.call_args.kwargs["temperature"] == 0.1


class TestEmbeddingsFactory:
    def test_get_embeddings_with_fallback(self):
        with patch("app.core.embeddings.settings") as mock_settings:
            mock_settings.embedding_model = "text-embedding-3-small"
            mock_settings.embedding_api_key = ""
            mock_settings.llm_api_key = "openai-key"
            mock_settings.embedding_base_url = ""
            mock_settings.llm_base_url = "https://api.openai.com/v1"

            with patch("app.core.embeddings.OpenAIEmbeddings") as MockEmb:
                get_embeddings()

                MockEmb.assert_called_once()
                kwargs = MockEmb.call_args.kwargs
                assert kwargs["model"] == "text-embedding-3-small"
                assert kwargs["api_key"] == "openai-key"
                assert kwargs["base_url"] == "https://api.openai.com/v1"
