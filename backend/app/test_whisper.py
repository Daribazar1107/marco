import sys
import time

import torch
from transformers import WhisperForConditionalGeneration, WhisperProcessor

from app.config import settings
from app.voice import load_audio

samples = load_audio(open(sys.argv[1], "rb").read())
print(f"Recording: {len(samples) / 16000:.1f} s, loudest point: {abs(samples).max():.2f} (good: 0.1 to 1.0)")

processor = WhisperProcessor.from_pretrained(settings.whisper_model)
for device, dtype in [("cpu", torch.float32), ("mps", torch.float16)]:
    if device == "mps" and not torch.backends.mps.is_available():
        continue
    model = WhisperForConditionalGeneration.from_pretrained(
        settings.whisper_model, torch_dtype=dtype
    ).to(device).eval()
    features = processor.feature_extractor(
        samples, sampling_rate=16000, return_tensors="pt"
    ).input_features.to(device, dtype)
    start = time.time()
    with torch.inference_mode():
        ids = model.generate(
            features, num_beams=1, no_repeat_ngram_size=3, repetition_penalty=1.2
        )
    text = processor.batch_decode(ids, skip_special_tokens=True)[0]
    print(f"{device}: {time.time() - start:.1f} s -> {text}")
    del model