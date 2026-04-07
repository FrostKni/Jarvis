import asyncio
import json
import websockets
from backend.voice.wake_word import WakeWordDetector
from backend.voice.vad import VoiceActivityDetector
from backend.voice.stt import StreamingSTT
from backend.voice.tts import StreamingTTS


class VoicePipeline:
    """End-to-end voice pipeline orchestrator."""

    def __init__(
        self,
        session_id: str,
        on_response: callable,
        backend_url: str = "ws://localhost:8000/ws/voice",
        timeout_seconds: int = 30,
    ):
        self.session_id = session_id
        self.on_response = on_response
        self.backend_url = f"{backend_url}/{session_id}"
        self.timeout_seconds = timeout_seconds

        self.wake_word = WakeWordDetector(on_detected=self._on_wake_word_sync)
        self.vad = VoiceActivityDetector()
        self.stt = None
        self.tts = StreamingTTS()
        self.ws = None

        self.is_listening = False
        self.last_activity = None
        self._running = False
        self._loop = None

    def start(self):
        """Start the voice pipeline."""
        self._running = True
        self._loop = asyncio.get_event_loop()
        self.wake_word.start()
        asyncio.create_task(self._connect_backend())
        asyncio.create_task(self._monitor_timeout())

    def stop(self):
        """Stop the voice pipeline."""
        self._running = False
        self.wake_word.stop()
        if self.stt:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.stt.stop())
            except RuntimeError:
                pass

    def _on_wake_word_sync(self):
        """Thread-safe wake word handler (called from WakeWordDetector thread)."""
        if self.is_listening or not self._loop:
            return
        asyncio.run_coroutine_threadsafe(self.on_wake_word(), self._loop)

    async def on_wake_word(self):
        """Handle wake word detection."""
        if self.is_listening:
            return

        print("[Jarvis] Listening...")
        self.is_listening = True
        self.last_activity = asyncio.get_event_loop().time()

        self.stt = StreamingSTT(
            on_transcript=self.on_partial_transcript,
            on_final=self.on_final_transcript,
        )
        await self.stt.start()

    async def on_partial_transcript(self, text: str):
        """Handle partial transcript."""
        print(f"\r[...] {text}", end="", flush=True)
        self.last_activity = asyncio.get_event_loop().time()

    async def on_final_transcript(self, text: str):
        """Handle final transcript."""
        if not text.strip():
            self.is_listening = False
            return

        print(f"\n[You] {text}")

        if self.ws:
            await self.ws.send(json.dumps({"type": "transcript", "text": text}))

        self.is_listening = False
        if self.stt:
            await self.stt.stop()

    async def _connect_backend(self):
        """Connect to backend WebSocket."""
        async with websockets.connect(self.backend_url) as ws:
            self.ws = ws
            async for raw in ws:
                msg = json.loads(raw)
                await self._handle_backend_message(msg)

    async def _handle_backend_message(self, msg: dict):
        """Handle messages from backend."""
        if msg["type"] == "done":
            response = msg["text"]
            print(f"[Jarvis] {response}")
            await self.on_response(response)
            await self.tts.speak(response)
        elif msg["type"] == "thinking":
            print("[Jarvis] Thinking...", end="", flush=True)

    async def _monitor_timeout(self):
        """Monitor for inactivity timeout."""
        while self._running:
            if self.is_listening and self.last_activity:
                elapsed = asyncio.get_event_loop().time() - self.last_activity
                if elapsed > self.timeout_seconds:
                    print("\n[Jarvis] Timeout. Say 'Hey Jarvis' to activate.")
                    self.is_listening = False
                    if self.stt:
                        await self.stt.stop()

            await asyncio.sleep(1)
