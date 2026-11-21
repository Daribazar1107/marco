from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The backend folder (the one that holds the .env file)
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "Marco"
    database_url: str
    supabase_url: str
    # Supabase -> Settings -> API -> "anon public" key. Safe to show in the browser.
    supabase_anon_key: str = ""

    # Where this server is reachable (used for the Google redirect URL)
    public_url: str = "http://localhost:8000"
    timezone: str = "Asia/Ulaanbaatar"

    # ---- Speech to text ----
    # "buzzasr" = local Whisper (works now), "chimege" = Chimege API (needs a token)
    stt_provider: str = "buzzasr"
    whisper_model: str = "BuzzASR/mongolian"
    whisper_device: str = "auto"  # auto, mps or cpu
    whisper_beams: int = 5  # 1 = fastest, 5 = more accurate
    chimege_token: str = ""
    chimege_stt_url: str = "https://api.chimege.com/v1.2/transcribe"
    chimege_token_header: str = "Token"

    # ---- Text to speech (edge-tts) ----
    tts_voice: str = "mn-MN-BataaNeural"

    # ---- AI brain (Ollama) ----
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "gemma4:26b"
    agent_max_steps: int = 6  # tool calls in one request, protects from endless loops

    # ---- Google ----
    google_client_file: str = "credentials.json"  # inside the backend folder

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
