import time
from typing import Dict


class LatencyTracker:
    """Track latency across voice pipeline stages."""

    def __init__(self, target_ms: int = None):
        self.target_ms = target_ms or 555
        self.records: Dict[str, float] = {}
        self.start_time = time.time()

    def record(self, stage: str, latency_ms: float):
        """Record latency for a pipeline stage."""
        self.records[stage] = latency_ms

    def get_summary(self) -> dict:
        """Get latency summary."""
        total = sum(self.records.values())
        return {
            **self.records,
            "total": total,
            "within_target": total <= self.target_ms,
            "target": self.target_ms,
        }

    def reset(self):
        """Reset tracker for new interaction."""
        self.records.clear()
        self.start_time = time.time()
