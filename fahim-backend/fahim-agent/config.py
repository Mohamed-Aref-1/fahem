from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    PORT: int = 8080
    DB_SCHEMA: str = "public"
    AZURE_EMBEDDING_KEY: str
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_KEY: str = ""
    AZURE_OPENAI_DEPLOYMENT: str = "gpt-4.1"
    WEB_PORT: int = 3000

    class Config:
        env_file = (".env", "../.env")


@lru_cache
def get_settings() -> Settings:
    return Settings()