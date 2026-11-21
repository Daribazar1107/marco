from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.routes import assistant, google
from app.voice import speech_to_text, text_to_speech

app = FastAPI(title=f"{settings.app_name} API")
app.include_router(assistant.router)
app.include_router(google.router)

STATIC = Path(__file__).parent / "static"


# ---------------------------------------------------------------- Pages


@app.get("/", include_in_schema=False)
def page():
    """Marco: login, chat, microphone."""
    return FileResponse(STATIC / "index.html")


@app.get("/tools", include_in_schema=False)
def tools_page():
    """The earlier test page: speech -> text and text -> speech."""
    return FileResponse(STATIC / "tools.html")


@app.get("/api/config")
def public_config():
    """Settings the browser needs. Only public values here (anon key is public)."""
    return {
        "supabase_url": settings.supabase_url,
        "supabase_anon_key": settings.supabase_anon_key,
        "stt_provider": settings.stt_provider,
        "llm_model": settings.ollama_model,
    }


# ---------------------------------------------------------------- Checks


@app.get("/hello/{name}")
def say_hello(name: str):
    return {"message": f"Сайн уу, {name}! Би Марко."}


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT now() AS db_time, version() AS pg_version")
            ).one()
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Database error: {error}")

    return {
        "status": "ok",
        "database": "connected",
        "db_time": row.db_time,
        "postgres": row.pg_version,
    }


# ---------------------------------------------------------------- Voice test tools


@app.post("/stt")
async def stt(audio: UploadFile):
    """Upload a recording, get the text back."""
    try:
        user_text = await speech_to_text(await audio.read())
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Яриа таних алдаа: {error}")
    return {"text": user_text}


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice: Literal["mn-MN-YesuiNeural", "mn-MN-BataaNeural"] = "mn-MN-BataaNeural"
    rate: int = Field(default=0, ge=-50, le=50)


@app.post("/tts")
async def tts(request: TTSRequest):
    """Send text, get speech back."""
    try:
        audio, audio_type = await text_to_speech(request.text, request.voice, request.rate)
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Дуу үүсгэх алдаа: {error}")
    return Response(content=audio, media_type=audio_type)
