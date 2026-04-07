import asyncio
import wave
import io
from pathlib import Path
import pytest
from backend.voice.vad import VoiceActivityDetector


FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"


@pytest.fixture
def vad():
    return VoiceActivityDetector()


class TestVADBasic:
    @pytest.mark.asyncio
    async def test_vad_invalid_threshold(self):
        with pytest.raises(ValueError, match="threshold must be between 0 and 1"):
            VoiceActivityDetector(threshold=1.5)

        with pytest.raises(ValueError, match="threshold must be between 0 and 1"):
            VoiceActivityDetector(threshold=-0.1)

    @pytest.mark.asyncio
    async def test_vad_invalid_sample_rate(self):
        with pytest.raises(ValueError, match="sample_rate must be 8000 or 16000"):
            VoiceActivityDetector(sample_rate=44100)

        with pytest.raises(ValueError, match="sample_rate must be 8000 or 16000"):
            VoiceActivityDetector(sample_rate=22050)

    @pytest.mark.asyncio
    async def test_vad_empty_audio_data(self, vad):
        with pytest.raises(ValueError, match="audio_data cannot be empty"):
            async for _ in vad.process_stream(b""):
                pass


@pytest.mark.asyncio
class TestVADModelLoading:
    async def test_vad_model_caching(self):
        vad = VoiceActivityDetector()

        await vad.load_model()
        model1 = vad.model

        await vad.load_model()
        model2 = vad.model

        assert model1 is model2, "Model should not be reloaded"

    async def test_vad_detects_speech(self):
        vad = VoiceActivityDetector()

        fixture_path = FIXTURES_DIR / "speech_sample.wav"
        with open(fixture_path, "rb") as f:
            audio_data = f.read()

        chunks_processed = 0
        speech_detected = False

        async for is_speech in vad.process_stream(audio_data):
            chunks_processed += 1
            if is_speech:
                speech_detected = True

        assert chunks_processed > 0, "No chunks processed"
        assert speech_detected, "VAD failed to detect speech"

    async def test_vad_silence_ignored(self):
        vad = VoiceActivityDetector()
        silence = b"\x00" * 32000

        speech_detected = False
        async for is_speech in vad.process_stream(silence):
            if is_speech:
                speech_detected = True

        assert not speech_detected, "VAD falsely detected speech in silence"

    async def test_vad_custom_threshold(self):
        vad = VoiceActivityDetector(threshold=0.9)
        silence = b"\x00" * 32000

        speech_detected = False
        async for is_speech in vad.process_stream(silence):
            if is_speech:
                speech_detected = True

        assert not speech_detected, (
            "VAD with high threshold should not detect speech in silence"
        )

    async def test_vad_handles_wav_header(self):
        vad = VoiceActivityDetector()

        raw_audio = b"\x00" * 32000

        with io.BytesIO() as buf:
            with wave.open(buf, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(raw_audio)
            wav_data = buf.getvalue()

        raw_result = list([x async for x in vad.process_stream(raw_audio)])
        wav_result = list([x async for x in vad.process_stream(wav_data)])

        assert raw_result == wav_result, "WAV header should be handled transparently"
