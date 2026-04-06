import asyncio
import pyaudio
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from backend.config import get_settings

settings = get_settings()

CHUNK = 1024
RATE = 16000
CHANNELS = 1


class StreamingSTT:
    def __init__(self, on_transcript: callable, on_final: callable):
        self.on_transcript = on_transcript  # partial results
        self.on_final = on_final            # final utterance
        self._client = DeepgramClient(settings.deepgram_api_key)
        self._connection = None
        self._audio = None
        self._stream = None
        self._running = False

    async def start(self):
        self._connection = self._client.listen.asyncwebsocket.v("1")

        self._connection.on(LiveTranscriptionEvents.Transcript, self._handle_transcript)
        self._connection.on(LiveTranscriptionEvents.SpeechStarted, lambda *_: None)

        options = LiveOptions(
            model="nova-3",
            language="en-US",
            smart_format=True,
            interim_results=True,
            utterance_end_ms="1000",
            vad_events=True,
            endpointing=300,
        )
        await self._connection.start(options)

        self._audio = pyaudio.PyAudio()
        self._stream = self._audio.open(
            format=pyaudio.paInt16,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )
        self._running = True
        asyncio.create_task(self._stream_audio())

    async def _stream_audio(self):
        while self._running:
            data = self._stream.read(CHUNK, exception_on_overflow=False)
            await self._connection.send(data)
            await asyncio.sleep(0)

    async def _handle_transcript(self, *args, **kwargs):
        result = kwargs.get("result") or (args[1] if len(args) > 1 else None)
        if not result:
            return
        alt = result.channel.alternatives[0]
        text = alt.transcript.strip()
        if not text:
            return
        if result.is_final:
            await self.on_final(text)
        else:
            await self.on_transcript(text)

    async def stop(self):
        self._running = False
        if self._connection:
            await self._connection.finish()
        if self._stream:
            self._stream.close()
        if self._audio:
            self._audio.terminate()
