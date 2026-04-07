import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys

sys.modules["pvporcupine"] = MagicMock()
sys.modules["pyaudio"] = MagicMock()
sys.modules["deepgram"] = MagicMock()
sys.modules["torch"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["sounddevice"] = MagicMock()
sys.modules["elevenlabs"] = MagicMock()
sys.modules["elevenlabs.client"] = MagicMock()

from backend.voice.pipeline import VoicePipeline


@pytest.fixture
def pipeline():
    """Create a VoicePipeline instance for testing."""
    on_response = AsyncMock()
    pipeline = VoicePipeline(
        session_id="test-session",
        on_response=on_response,
        backend_url="ws://test-server/ws/voice",
        timeout_seconds=5,
    )
    return pipeline


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    mock_ws = AsyncMock()
    mock_ws.send = AsyncMock()
    mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
    mock_ws.__aexit__ = AsyncMock(return_value=None)
    return mock_ws


def test_pipeline_initialization(pipeline):
    """Test VoicePipeline initializes correctly."""
    assert pipeline.session_id == "test-session"
    assert pipeline.timeout_seconds == 5
    assert pipeline.backend_url == "ws://test-server/ws/voice/test-session"
    assert pipeline.is_listening is False
    assert pipeline._running is False
    assert pipeline.wake_word is not None
    assert pipeline.vad is not None
    assert pipeline.tts is not None


def test_pipeline_custom_timeout():
    """Test VoicePipeline with custom timeout."""
    on_response = AsyncMock()
    pipeline = VoicePipeline(
        session_id="test",
        on_response=on_response,
        timeout_seconds=60,
    )
    assert pipeline.timeout_seconds == 60


def test_pipeline_custom_backend_url():
    """Test VoicePipeline with custom backend URL."""
    on_response = AsyncMock()
    pipeline = VoicePipeline(
        session_id="test",
        on_response=on_response,
        backend_url="ws://custom:9000/voice",
    )
    assert pipeline.backend_url == "ws://custom:9000/voice/test"


@pytest.mark.asyncio
async def test_pipeline_start(pipeline):
    """Test starting the pipeline."""
    with patch.object(pipeline.wake_word, "start") as mock_start:
        pipeline.start()

        assert pipeline._running is True
        assert pipeline._loop is not None
        mock_start.assert_called_once()


def test_pipeline_stop(pipeline):
    """Test stopping the pipeline."""
    pipeline._running = True
    pipeline.stt = MagicMock()
    pipeline.stt.stop = AsyncMock()

    with patch.object(pipeline.wake_word, "stop") as mock_stop:
        pipeline.stop()

        assert pipeline._running is False
        mock_stop.assert_called_once()


@pytest.mark.asyncio
async def test_on_wake_word_starts_stt(pipeline):
    """Test that wake word detection starts STT."""
    with patch("backend.voice.pipeline.StreamingSTT") as MockSTT:
        mock_stt = AsyncMock()
        MockSTT.return_value = mock_stt

        await pipeline.on_wake_word()

        assert pipeline.is_listening is True
        assert pipeline.last_activity is not None
        MockSTT.assert_called_once()
        mock_stt.start.assert_called_once()


@pytest.mark.asyncio
async def test_on_wake_word_ignores_when_listening(pipeline):
    """Test that wake word is ignored when already listening."""
    pipeline.is_listening = True

    with patch("backend.voice.pipeline.StreamingSTT") as MockSTT:
        await pipeline.on_wake_word()

        MockSTT.assert_not_called()


@pytest.mark.asyncio
async def test_on_partial_transcript(pipeline):
    """Test handling partial transcript."""
    pipeline.last_activity = None

    await pipeline.on_partial_transcript("hello world")

    assert pipeline.last_activity is not None


@pytest.mark.asyncio
async def test_on_final_transcript_sends_to_backend(pipeline):
    """Test that final transcript is sent to backend."""
    pipeline.ws = AsyncMock()
    pipeline.ws.send = AsyncMock()
    pipeline.stt = AsyncMock()
    pipeline.stt.stop = AsyncMock()

    await pipeline.on_final_transcript("hello jarvis")

    expected_msg = json.dumps({"type": "transcript", "text": "hello jarvis"})
    pipeline.ws.send.assert_called_once_with(expected_msg)
    pipeline.stt.stop.assert_called_once()
    assert pipeline.is_listening is False


@pytest.mark.asyncio
async def test_on_final_transcript_empty_text(pipeline):
    """Test that empty transcript is ignored."""
    pipeline.is_listening = True
    pipeline.ws = AsyncMock()

    await pipeline.on_final_transcript("   ")

    assert pipeline.is_listening is False
    pipeline.ws.send.assert_not_called()


@pytest.mark.asyncio
async def test_handle_backend_message_done(pipeline):
    """Test handling 'done' message from backend."""
    pipeline.tts = AsyncMock()
    pipeline.tts.speak = AsyncMock()

    msg = {"type": "done", "text": "Hello! How can I help?"}
    await pipeline._handle_backend_message(msg)

    pipeline.on_response.assert_called_once_with("Hello! How can I help?")
    pipeline.tts.speak.assert_called_once_with("Hello! How can I help?")


@pytest.mark.asyncio
async def test_handle_backend_message_thinking(pipeline):
    """Test handling 'thinking' message from backend."""
    msg = {"type": "thinking"}

    await pipeline._handle_backend_message(msg)


@pytest.mark.asyncio
async def test_monitor_timeout(pipeline):
    """Test timeout monitoring."""
    pipeline._running = True
    pipeline.is_listening = True
    pipeline.stt = AsyncMock()
    pipeline.stt.stop = AsyncMock()

    current_time = asyncio.get_event_loop().time()
    pipeline.last_activity = current_time - 6

    stop_event = asyncio.Event()

    async def stop_after_first_check():
        await asyncio.sleep(0.1)
        pipeline._running = False
        stop_event.set()

    asyncio.create_task(stop_after_first_check())

    await pipeline._monitor_timeout()

    assert pipeline.is_listening is False


@pytest.mark.asyncio
async def test_monitor_timeout_no_action_when_not_listening(pipeline):
    """Test timeout monitor doesn't act when not listening."""
    pipeline._running = True
    pipeline.is_listening = False
    pipeline.last_activity = None

    stop_event = asyncio.Event()

    async def stop_after_delay():
        await asyncio.sleep(0.1)
        pipeline._running = False
        stop_event.set()

    asyncio.create_task(stop_after_delay())

    await pipeline._monitor_timeout()

    assert pipeline.is_listening is False


@pytest.mark.asyncio
async def test_on_wake_word_sync_schedules_coroutine(pipeline):
    """Test that sync wake word handler schedules async coroutine."""
    pipeline._loop = asyncio.get_event_loop()
    pipeline.is_listening = False

    with patch("asyncio.run_coroutine_threadsafe") as mock_run:
        mock_run.return_value = MagicMock()
        pipeline._on_wake_word_sync()
        mock_run.assert_called_once()


def test_on_wake_word_sync_returns_none_when_listening(pipeline):
    """Test that sync wake word handler returns None when already listening."""
    pipeline._loop = asyncio.get_event_loop()
    pipeline.is_listening = True

    result = pipeline._on_wake_word_sync()

    assert result is None


def test_on_wake_word_sync_returns_none_when_no_loop(pipeline):
    """Test that sync wake word handler returns None when no event loop."""
    pipeline._loop = None
    pipeline.is_listening = False

    result = pipeline._on_wake_word_sync()

    assert result is None
