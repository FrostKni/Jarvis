import asyncio
import io
import sounddevice as sd
import numpy as np
from elevenlabs.client import AsyncElevenLabs
from elevenlabs import VoiceSettings
from backend.config import get_settings

settings = get_settings()

SAMPLE_RATE = 22050


class StreamingTTS:
    def __init__(self):
        self._client = AsyncElevenLabs(api_key=settings.elevenlabs_api_key)
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._playing = False

    async def speak(self, text: str):
        """Stream text to audio, sentence by sentence."""
        await self._queue.put(text)
        if not self._playing:
            asyncio.create_task(self._process_queue())

    async def _process_queue(self):
        self._playing = True
        while not self._queue.empty():
            text = await self._queue.get()
            await self._synthesize_and_play(text)
        self._playing = False

    async def _synthesize_and_play(self, text: str):
        audio_chunks = []
        async for chunk in await self._client.text_to_speech.convert_as_stream(
            voice_id=settings.elevenlabs_voice_id,
            text=text,
            model_id="eleven_flash_v2_5",
            voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.75),
        ):
            if chunk:
                audio_chunks.append(chunk)

        if audio_chunks:
            audio_bytes = b"".join(audio_chunks)
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            sd.play(audio_array, samplerate=SAMPLE_RATE, blocking=True)

    async def speak_stream(self, text_generator):
        """Accept an async generator of text chunks, split into sentences, stream to TTS."""
        buffer = ""
        async for token in text_generator:
            buffer += token
            sentences = _split_sentences(buffer)
            if len(sentences) > 1:
                for sentence in sentences[:-1]:
                    if sentence.strip():
                        await self.speak(sentence.strip())
                buffer = sentences[-1]
        if buffer.strip():
            await self.speak(buffer.strip())


def _split_sentences(text: str) -> list[str]:
    import re
    return re.split(r'(?<=[.!?])\s+', text)
