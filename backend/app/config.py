import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://localhost/waterdesign",
    )
    upload_dir: str = "uploads"
    max_file_size: int = 500 * 1024 * 1024  # 500MB (down from 10GB to prevent OOM)
    max_upload_size: int = 200 * 1024 * 1024  # 200MB - 大文件上传限制

    # LLM
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_temperature: float = 0.3
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    max_context_messages: int = 10

    # Vision (multimodal image description)
    vision_model: str = ""
    vision_api_key: str = ""
    vision_base_url: str = ""

    # Auth
    api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
