import asyncio
import wave
import io
from typing import AsyncGenerator
import torch
import numpy as np


class VoiceActivityDetector:
    """Silero VAD for speech detection."""

    def __init__(self, threshold: float = 0.5, sample_rate: int = 16000):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(f"threshold must be between 0 and 1, got {threshold}")
        if sample_rate not in (8000, 16000):
            raise ValueError(f"sample_rate must be 8000 or 16000, got {sample_rate}")
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.model = None
        self._loaded = False

    async def load_model(self):
        """Load Silero VAD model asynchronously."""
        if self._loaded:
            return

        def _load():
            result = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            if isinstance(result, tuple) and len(result) >= 1:
                return result[0]
            elif hasattr(result, "__call__"):
                return result
            else:
                torch.hub.clear_cache()
                result = torch.hub.load(
                    repo_or_dir="snakers4/silero-vad",
                    model="silero_vad",
                    force_reload=True,
                    trust_repo=True,
                )
                if isinstance(result, tuple) and len(result) >= 1:
                    return result[0]
                return result

        try:
            self.model = await asyncio.to_thread(_load)
            self._loaded = True
        except Exception as e:
            self._loaded = False
            raise RuntimeError(f"Failed to load Silero VAD model: {e}") from e

    def _extract_audio(self, audio_data: bytes) -> bytes:
        """Extract raw PCM from WAV or return raw bytes."""
        if audio_data[:4] == b"RIFF":
            with wave.open(io.BytesIO(audio_data), "rb") as wav:
                return wav.readframes(wav.getnframes())
        return audio_data

    async def process_stream(
        self, audio_data: bytes, chunk_size: int = 512
    ) -> AsyncGenerator[bool, None]:
        """Process audio stream and yield speech detection results.

        Args:
            audio_data: Raw audio bytes or WAV-formatted audio.
            chunk_size: Number of samples per processing chunk.

        Yields:
            True if speech detected in chunk, False otherwise.

        Raises:
            ValueError: If audio_data is empty.
            RuntimeError: If audio processing fails.
        """
        if not audio_data:
            raise ValueError("audio_data cannot be empty")

        await self.load_model()

        try:
            raw_audio = self._extract_audio(audio_data)
            if not raw_audio:
                raise ValueError("No audio data after extraction")

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
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Audio processing failed: {e}") from e
