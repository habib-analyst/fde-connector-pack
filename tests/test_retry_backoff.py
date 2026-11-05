import random

import pytest

from conftest import make_hs, make_sf, make_slack
from fde_connector_pack.clock import FakeClock, RetryPolicy
from fde_connector_pack.errors import RetryExhaustedError
from fde_connector_pack.fixtures import FaultPlan


def expected_delays(seed=42, base=1.0, mult=2.0, n=2):
    rng = random.Random(seed)
    return [min(30.0, base * (mult ** i) + rng.uniform(0, 0.5)) for i in range(n)]


def test_429_retry_after_is_honoured_exactly():
    clock = FakeClock()
    sf = make_sf(FaultPlan(rate_limit_first_n=2), clock=clock)
    page = sf.fetch()
    assert len(page.records) == 5
    assert sf.retry_count == 2
    # Retry-After: 2 from the fixture overrides the backoff schedule.
    assert sf.retry_delays == [2.0, 2.0]
    assert clock.sleeps == [2.0, 2.0]


def test_page_fails_twice_then_succeeds_with_seeded_backoff():
    clock = FakeClock()
    sf = make_sf(FaultPlan(fail_cursor_times={"sf-5": 2}), clock=clock)
    first = sf.fetch()
    assert first.next_cursor == "sf-5"
    page = sf.fetch("sf-5")
    assert len(page.records) == 5
    assert sf.retry_count == 2
    assert sf.retry_delays == pytest.approx(expected_delays(n=2))
    assert clock.sleeps == sf.retry_delays


def test_retry_budget_is_bounded_and_exhaustion_raises():
    clock = FakeClock()
    sf = make_sf(FaultPlan(rate_limit_first_n=99), clock=clock,
                 retry_policy=RetryPolicy(max_attempts=3))
    with pytest.raises(RetryExhaustedError) as ei:
        sf.fetch()
    assert ei.value.attempts == 3
    assert sf.request_count == 3  # bounded: exactly max_attempts tries
    assert sf.retry_count == 2


def test_slack_rate_limit_headers_retry():
    clock = FakeClock()
    slack = make_slack(FaultPlan(rate_limit_first_n=1), clock=clock)
    page = slack.fetch()
    assert len(page.records) == 4
    assert slack.retry_delays == [2.0]


def test_backoff_schedule_is_deterministic_for_same_seed():
    a = list(RetryPolicy(jitter_seed=7).delays())
    b = list(RetryPolicy(jitter_seed=7).delays())
    assert a == b and len(a) == 3
    assert all(x < y for x, y in zip(a, a[1:]))  # exponential growth dominates jitter


def test_hubspot_cursor_429_then_success():
    clock = FakeClock()
    hs = make_hs(FaultPlan(rate_limit_cursor_times={"hs-4": 1}), clock=clock)
    hs.fetch()
    page = hs.fetch("hs-4")
    assert len(page.records) == 4
    assert hs.retry_delays == [2.0]
