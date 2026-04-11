from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/waterdesign"
    upload_dir: str = "uploads"
    max_file_size: int = 10 * 1024 * 1024 * 1024  # 10GB