from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class FaultPlan:
    """Scripted fault injection shared by all fixture apps.

    rate_limit_first_n: first N requests (any route) return 429.
    fail_cursor_times: {cursor_value: times} — a fetch whose cursor matches
        fails that many times with 500 before succeeding.
    rate_limit_cursor_times: {cursor_value: times} — same, but 429.
    """
    rate_limit_first_n: int = 0
    fail_cursor_times: dict = field(default_factory=dict)
    rate_limit_cursor_times: dict = field(default_factory=dict)
    retry_after: str = "2"


@dataclass
class FixtureState:
    request_count: int = 0
    cursor_hits: dict = field(default_factory=dict)
    fail_hits: dict = field(default_factory=dict)
    rl_hits: dict = field(default_factory=dict)

    def check_rate_limit(self, plan: FaultPlan) -> bool:
        self.request_count += 1
        return self.request_count <= plan.rate_limit_first_n

    def cursor_fault(self, plan: FaultPlan, cursor) -> str | None:
        """Return '500', '429' or None for this cursor fetch."""
        key = cursor or ""
        self.cursor_hits[key] = self.cursor_hits.get(key, 0) + 1
        if key in plan.fail_cursor_times:
            self.fail_hits[key] = self.fail_hits.get(key, 0) + 1
            if self.fail_hits[key] <= plan.fail_cursor_times[key]:
                return "500"
            return None
        if key in plan.rate_limit_cursor_times:
            self.rl_hits[key] = self.rl_hits.get(key, 0) + 1
            if self.rl_hits[key] <= plan.rate_limit_cursor_times[key]:
                return "429"
            return None
        return None


def check_auth(authorization: str | None, vendor: str) -> bool:
    return bool(authorization) and authorization.startswith(f"Bearer fixture-{vendor}-token")
