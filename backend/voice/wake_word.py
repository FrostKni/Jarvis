import asyncio
import struct
import threading
import pvporcupine
import pyaudio
from backend.config import get_settings

settings = get_settings()


class WakeWordDetector:
    def __init__(self, on_detected: callable):
        self.on_detected = on_detected
        self._running = False
        self._thread: threading.Thread | None = None
        self._porcupine = None
        self._audio = None
        self._stream = None

    def start(self):
        self._porcupine = pvporcupine.create(
            access_key=settings.picovoice_access_key,
            keywords=["jarvis"],
        )
        self._audio = pyaudio.PyAudio()
        self._stream = self._audio.open(
            rate=self._porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=self._porcupine.frame_length,
        )
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while self._running:
            pcm = self._stream.read(self._porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * self._porcupine.frame_length, pcm)
            if self._porcupine.process(pcm) >= 0:
                self.on_detected()

    def stop(self):
        self._running = False
        if self._stream:
            self._stream.close()
        if self._audio:
            self._audio.terminate()
        if self._porcupine:
            self._porcupine.delete()
