import asyncio
import pytest
from backend.voice.vad import VoiceActivityDetector


@pytest.mark.asyncio
async def test_vad_detects_speech():
    """Test that VAD correctly identifies speech chunks."""
    vad = VoiceActivityDetector()

    with open("tests/fixtures/speech_sample.wav", "rb") as f:
        audio_data = f.read()

    chunks_processed = 0
    speech_detected = False

    async for is_speech in vad.process_stream(audio_data):
        chunks_processed += 1
        if is_speech:
            speech_detected = True

    assert chunks_processed > 0, "No chunks processed"
    assert speech_detected, "VAD failed to detect speech"


@pytest.mark.asyncio
async def test_vad_silence_ignored():
    """Test that VAD ignores silence."""
    vad = VoiceActivityDetector()
    silence = b"\x00" * 32000

    speech_detected = False
    async for is_speech in vad.process_stream(silence):
        if is_speech:
            speech_detected = True

    assert not speech_detected, "VAD falsely detected speech in silence"


@pytest.mark.asyncio
async def test_vad_model_caching():
    """Test that model is loaded only once."""
    vad = VoiceActivityDetector()

    await vad.load_model()
    model1 = vad.model

    await vad.load_model()
    model2 = vad.model

    assert model1 is model2, "Model should not be reloaded"


@pytest.mark.asyncio
async def test_vad_custom_threshold():
    """Test VAD with custom threshold."""
    vad = VoiceActivityDetector(threshold=0.9)
    silence = b"\x00" * 32000

    speech_detected = False
    async for is_speech in vad.process_stream(silence):
        if is_speech:
            speech_detected = True

    assert not speech_detected, (
        "VAD with high threshold should not detect speech in silence"
    )


@pytest.mark.asyncio
async def test_vad_handles_wav_header():
    """Test that VAD correctly extracts audio from WAV files."""
    import wave
    import io

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
