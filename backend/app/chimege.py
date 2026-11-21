"""Chimege speech-to-text (cloud API, Mongolian company).

Turn it on in .env:
    STT_PROVIDER=chimege
    CHIMEGE_TOKEN=...            (console.chimege.com)

API manual: https://docs.api.chimege.com/v1.2/en/
    POST https://api.chimege.com/v1.2/transcribe
    headers: Token, Content-Type: application/octet-stream, Punctuate: true
    body: the audio file (we send 16 kHz mono WAV)
"""

import io
import wave

import httpx
import numpy as np

from app.config import settings


def to_wav(samples: np.ndarray, rate: int = 16000) -> bytes:
    """Float samples (-1..1) -> 16-bit mono WAV, the format most speech APIs accept."""
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes()
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm)
    return buffer.getvalue()


def _read_text(response: httpx.Response) -> str:
    """Chimege may answer with plain text or JSON; take the text either way."""
    if "json" in response.headers.get("content-type", ""):
        data = response.json()
        if isinstance(data, dict):
            for key in ("text", "transcription", "result", "data"):
                if isinstance(data.get(key), str):
                    return data[key]
        return str(data)
    return response.text


async def transcribe(samples: np.ndarray) -> str:
    if not settings.chimege_token:
        raise RuntimeError("CHIMEGE_TOKEN-ийг .env файлд тохируулна уу")

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            settings.chimege_stt_url,
            headers={
                settings.chimege_token_header: settings.chimege_token,
                "Content-Type": "application/octet-stream",
                "Punctuate": "true",  # adds commas and full stops
            },
            content=to_wav(samples),
        )
    if response.status_code != 200:
        raise RuntimeError(f"Chimege {response.status_code}: {response.text[:200]}")
    return _read_text(response).strip()
