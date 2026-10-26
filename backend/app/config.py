from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The backend folder (the one that holds the .env file)
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "Marco"
    database_url: str
    supabase_url: str

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings() 