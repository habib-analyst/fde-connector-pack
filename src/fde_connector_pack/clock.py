from __future__ import annotations
import random
import time
from dataclasses import dataclass, field


class SystemClock:
    def __init__(self):
        self.sleeps: list[float] = []
    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        if seconds > 0:
            time.sleep(min(seconds, 0.01))  # tests never use this; kept tiny
    def now(self) -> float:
        return time.time()


class FakeClock:
    """Deterministic clock: sleep() records the delay and advances virtual time."""
    def __init__(self, start: float = 1000.0):
        self._now = start
        self.sleeps: list[float] = []
    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self._now += seconds
    def now(self) -> float:
        return self._now


@dataclass
class RetryPolicy:
    max_attempts: int = 4          # total attempts including the first
    base_delay: float = 1.0
    multiplier: float = 2.0
    max_delay: float = 30.0
    jitter_seed: int = 42

    def delays(self):
        """Yield the deterministic delay schedule (one per retry)."""
        rng = random.Random(self.jitter_seed)
        for attempt in range(self.max_attempts - 1):
            raw = self.base_delay * (self.multiplier ** attempt)
            jitter = rng.uniform(0, 0.5)
            yield min(self.max_delay, raw + jitter)

    def delay_for(self, attempt: int, rng: random.Random,
                  retry_after: float | None = None) -> float:
        if retry_after is not None:
            return float(retry_after)
        raw = self.base_delay * (self.multiplier ** attempt)
        jitter = rng.uniform(0, 0.5)
        return min(self.max_delay, raw + jitter)
