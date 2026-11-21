import asyncio
import io
import threading

import av
import edge_tts
import numpy as np

from app.config import settings

# Whisper is big (3 GB), so we load it once and keep it in memory.
# torch and transformers are imported only when Whisper is really used,
# so the server starts fast when STT_PROVIDER=chimege.
whisper_cache = {}
whisper_lock = threading.Lock()


def load_audio(audio: bytes) -> np.ndarray:
    """Any recording (webm, m4a, mp3, wav...) -> 16 kHz mono samples between -1 and 1."""
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    pcm = bytearray()
    with av.open(io.BytesIO(audio)) as container:
        for frame in container.decode(audio=0):
            for piece in resampler.resample(frame):
                pcm += bytes(piece.planes[0])[: piece.samples * 2]
    for piece in resampler.resample(None):  # flush the last bit
        pcm += bytes(piece.planes[0])[: piece.samples * 2]
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768


def get_whisper():
    """Load Whisper the first time it's needed, then reuse it."""
    import torch
    from transformers import WhisperForConditionalGeneration, WhisperProcessor

    with whisper_lock:
        if not whisper_cache:
            device = settings.whisper_device
            if device == "auto":
                device = "mps" if torch.backends.mps.is_available() else "cpu"
            dtype = torch.float16 if device == "mps" else torch.float32
            whisper_cache["processor"] = WhisperProcessor.from_pretrained(settings.whisper_model)
            whisper_cache["model"] = WhisperForConditionalGeneration.from_pretrained(
                settings.whisper_model, torch_dtype=dtype
            ).to(device).eval()
    return whisper_cache["model"], whisper_cache["processor"]


def trim_silence(samples: np.ndarray) -> np.ndarray:
    """Cut the quiet parts at the start and end, keep 0.2 s around the speech."""
    loud = np.flatnonzero(np.abs(samples) > 0.05 * np.abs(samples).max())
    start = max(loud[0] - 3200, 0)
    end = min(loud[-1] + 3200, len(samples))
    return samples[start:end]


def prepare(audio: bytes) -> np.ndarray | None:
    """Decode, cut silence, even out loudness. None = too short or silent."""
    samples = load_audio(audio)
    if len(samples) < 1600 or np.abs(samples).max() < 0.01:
        return None  # Whisper would invent words from silence
    samples = trim_silence(samples)
    return samples / np.abs(samples).max() * 0.9  # same loudness every time


def whisper_transcribe(samples: np.ndarray) -> str:
    import torch

    model, processor = get_whisper()
    features = processor.feature_extractor(
        samples, sampling_rate=16000, return_tensors="pt"
    ).input_features
    features = features.to(model.device, model.dtype)
    with torch.inference_mode():
        ids = model.generate(
            features,
            num_beams=settings.whisper_beams,
            no_repeat_ngram_size=3,
            repetition_penalty=1.2,
            max_new_tokens=200,
        )
    return processor.batch_decode(ids, skip_special_tokens=True)[0].strip()


def transcribe(audio: bytes) -> str:
    """Kept for test_whisper.py and older code: local Whisper only."""
    samples = prepare(audio)
    return "" if samples is None else whisper_transcribe(samples)


async def speech_to_text(audio: bytes) -> str:
    """Speech -> text with the provider chosen in .env (STT_PROVIDER)."""
    samples = await asyncio.to_thread(prepare, audio)
    if samples is None:
        return ""
    if settings.stt_provider == "chimege":
        from app import chimege

        return await chimege.transcribe(samples)
    # Whisper runs in a separate thread so the server stays responsive
    return await asyncio.to_thread(whisper_transcribe, samples)


async def text_to_speech(text: str, voice: str = "", rate: int = 0) -> tuple[bytes, str]:
    """Text -> speech with a free Microsoft Mongolian voice. Gives back (audio, type).
    rate: -50 (slower) ... 0 ... +50 (faster), in percent."""
    communicate = edge_tts.Communicate(text, voice or settings.tts_voice, rate=f"{rate:+d}%")
    audio = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    return bytes(audio), "audio/mpeg"
