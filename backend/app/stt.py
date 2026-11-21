from functools import lru_cache

from faster_whisper import WhisperModel

# Sizes: "small" (fast, weaker), "medium", "large-v3" (best for Mongolian, slower)
MODEL_SIZE = "medium"


@lru_cache(maxsize=1)
def get_model() -> WhisperModel:
    # Loaded once, the first time it's needed
    return WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")


def transcribe(audio_path: str) -> dict:
    model = get_model()
    segments, info = model.transcribe(
        audio_path,
        language="mn",
        beam_size=5,
        vad_filter=True,  # skips silence
    )
    text = " ".join(segment.text.strip() for segment in segments)
    return {
        "text": text,
        "language": info.language,
        "duration": round(info.duration, 2),
    }