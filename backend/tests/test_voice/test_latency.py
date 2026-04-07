import pytest
from backend.voice.latency_tracker import LatencyTracker


def test_latency_tracker_initialization():
    """Test LatencyTracker initializes with default target."""
    tracker = LatencyTracker()
    assert tracker.target_ms == 555
    assert tracker.records == {}
    assert tracker.start_time is not None


def test_latency_tracker_custom_target():
    """Test LatencyTracker with custom target."""
    tracker = LatencyTracker(target_ms=600)
    assert tracker.target_ms == 600


def test_latency_tracker_record():
    """Test recording latency for a stage."""
    tracker = LatencyTracker()
    tracker.record("stt", 150.5)
    assert tracker.records["stt"] == 150.5


def test_latency_tracker_multiple_records():
    """Test recording latency for multiple stages."""
    tracker = LatencyTracker()
    tracker.record("wake_word", 10.0)
    tracker.record("vad", 20.0)
    tracker.record("stt", 150.0)
    tracker.record("llm", 300.0)
    tracker.record("tts", 75.0)

    assert len(tracker.records) == 5
    assert tracker.records["wake_word"] == 10.0
    assert tracker.records["stt"] == 150.0


def test_latency_tracker_get_summary():
    """Test getting latency summary."""
    tracker = LatencyTracker()
    tracker.record("stt", 150.0)
    tracker.record("llm", 300.0)

    summary = tracker.get_summary()

    assert summary["stt"] == 150.0
    assert summary["llm"] == 300.0
    assert summary["total"] == 450.0
    assert summary["within_target"] is True
    assert summary["target"] == 555


def test_latency_tracker_within_target():
    """Test within_target flag when under target."""
    tracker = LatencyTracker(target_ms=500)
    tracker.record("stt", 200.0)
    tracker.record("llm", 200.0)

    summary = tracker.get_summary()

    assert summary["total"] == 400.0
    assert summary["within_target"] is True


def test_latency_tracker_exceeds_target():
    """Test within_target flag when exceeding target."""
    tracker = LatencyTracker(target_ms=500)
    tracker.record("stt", 300.0)
    tracker.record("llm", 400.0)

    summary = tracker.get_summary()

    assert summary["total"] == 700.0
    assert summary["within_target"] is False


def test_latency_tracker_reset():
    """Test resetting the tracker."""
    tracker = LatencyTracker()
    tracker.record("stt", 150.0)
    tracker.record("llm", 300.0)

    tracker.reset()

    assert tracker.records == {}
    assert tracker.start_time is not None


def test_latency_tracker_empty_summary():
    """Test summary with no records."""
    tracker = LatencyTracker()

    summary = tracker.get_summary()

    assert summary["total"] == 0
    assert summary["within_target"] is True


def test_latency_tracker_overwrite_stage():
    """Test that recording same stage overwrites previous value."""
    tracker = LatencyTracker()
    tracker.record("stt", 150.0)
    tracker.record("stt", 200.0)

    assert tracker.records["stt"] == 200.0


def test_latency_tracker_full_pipeline():
    """Test tracking a full voice pipeline interaction."""
    tracker = LatencyTracker(target_ms=555)

    tracker.record("wake_word", 10.0)
    tracker.record("vad", 20.0)
    tracker.record("stt", 150.0)
    tracker.record("context_fetch", 50.0)
    tracker.record("llm", 250.0)
    tracker.record("tts", 75.0)

    summary = tracker.get_summary()

    assert summary["total"] == 555.0
    assert summary["within_target"] is True
    assert len(tracker.records) == 6
