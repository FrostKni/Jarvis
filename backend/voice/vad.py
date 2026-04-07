import asyncio
import wave
import io
import torch
import numpy as np


class VoiceActivityDetector:
    """Silero VAD for speech detection."""

    def __init__(self, threshold: float = 0.5, sample_rate: int = 16000):
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.model = None
        self._loaded = False

    async def load_model(self):
        """Load Silero VAD model asynchronously."""
        if self._loaded:
            return

        def _load():
            model, _ = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            return model

        self.model = await asyncio.to_thread(_load)
        self._loaded = True

    def _extract_audio(self, audio_data: bytes) -> bytes:
        """Extract raw PCM from WAV or return raw bytes."""
        if audio_data[:4] == b"RIFF":
            with wave.open(io.BytesIO(audio_data), "rb") as wav:
                return wav.readframes(wav.getnframes())
        return audio_data

    async def process_stream(self, audio_data: bytes, chunk_size: int = 512):
        """Process audio stream and yield speech detection results."""
        await self.load_model()

        raw_audio = self._extract_audio(audio_data)
        audio_array = (
            np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32768.0
        )
        audio_tensor = torch.from_numpy(audio_array)

        for i in range(0, len(audio_tensor), chunk_size):
            chunk = audio_tensor[i : i + chunk_size]
            if len(chunk) < chunk_size:
                chunk = torch.nn.functional.pad(chunk, (0, chunk_size - len(chunk)))

            with torch.no_grad():
                speech_prob = self.model(chunk, self.sample_rate).item()

            yield speech_prob > self.threshold
