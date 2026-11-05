from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Any

from .auth import TokenProvider
from .clock import FakeClock, RetryPolicy
from .errors import (ConnectorError, PermanentError, RetryExhaustedError,
                     classify_status)


@dataclass
class Page:
    records: list
    next_cursor: str | None = None
    done: bool = True


@dataclass
class PushResult:
    external_id: str
    created: bool = True
    vendor_id: str = ""


class BaseConnector:
    """Common connector interface: fetch(cursor) / push(record) / health().

    HTTP is performed through an injected client (FastAPI TestClient in
    tests and demos), so no sockets or network are involved. Every call
    goes through request(), which applies:
      * fixture OAuth-style Authorization header,
      * 429 handling honouring Retry-After,
      * retry with exponential backoff + seeded jitter on retryable errors,
      * immediate PermanentError on permanent errors.
    Retry delays are taken from the injected clock, never wall time in tests.
    """
    name = "base"

    def __init__(self, client, clock=None, retry_policy: RetryPolicy | None = None,
                 token_ttl: float = 3600.0):
        self.client = client
        self.clock = clock or FakeClock()
        self.policy = retry_policy or RetryPolicy()
        self.tokens = TokenProvider(self.name, self.clock, ttl=token_ttl)
        self._rng = random.Random(self.policy.jitter_seed)
        self.retry_count = 0
        self.request_count = 0
        self.retry_delays: list[float] = []

    # -- resilient request ----------------------------------------------
    def request(self, method: str, url: str, **kwargs):
        headers = dict(kwargs.pop("headers", {}) or {})
        last_error: ConnectorError | None = None
        for attempt in range(self.policy.max_attempts):
            headers.update(self.tokens.headers())
            self.request_count += 1
            resp = self.client.request(method, url, headers=headers, **kwargs)
            if resp.status_code < 400:
                return resp
            error_class = classify_status(resp.status_code)
            code, message = self._error_detail(resp)
            if error_class == "permanent":
                raise PermanentError(message or f"HTTP {resp.status_code}",
                                     status=resp.status_code, code=code)
            last_error = ConnectorError(message or f"HTTP {resp.status_code}",
                                        status=resp.status_code, code=code,
                                        error_class="retryable")
            if attempt < self.policy.max_attempts - 1:
                retry_after = None
                ra = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
                if ra is not None:
                    try:
                        retry_after = float(ra)
                    except ValueError:
                        retry_after = None
                delay = self.policy.delay_for(attempt, self._rng, retry_after=retry_after)
                self.retry_delays.append(delay)
                self.retry_count += 1
                self.clock.sleep(delay)
        raise RetryExhaustedError(
            f"retry budget exhausted for {method} {url}: {last_error}",
            attempts=self.policy.max_attempts,
            status=last_error.status if last_error else None,
            code=last_error.code if last_error else "")

    def _error_detail(self, resp) -> tuple[str, str]:
        """Extract (code, message) from a vendor error body. Overridable."""
        try:
            body = resp.json()
        except Exception:
            return "", resp.text[:200] if hasattr(resp, "text") else ""
        if isinstance(body, dict):
            code = str(body.get("error") or body.get("errorCode") or
                       body.get("category") or "")
            msg = str(body.get("message") or body.get("error") or "")
            # nested shapes (Google / Salesforce list)
            err = body.get("error")
            if isinstance(err, dict):
                code = str(err.get("errors", [{}])[0].get("reason", "") if err.get("errors") else err.get("code", ""))
                msg = str(err.get("message", ""))
            return code, msg
        if isinstance(body, list) and body and isinstance(body[0], dict):
            return str(body[0].get("errorCode", "")), str(body[0].get("message", ""))
        return "", ""

    # -- interface --------------------------------------------------------
    def fetch(self, cursor: str | None = None) -> Page:
        raise NotImplementedError

    def push(self, record) -> PushResult:
        raise NotImplementedError

    def health(self) -> bool:
        raise NotImplementedError

    def idempotency_key(self, record) -> str:
        return f"{self.name}:{record.external_id}"
