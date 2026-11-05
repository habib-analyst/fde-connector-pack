from __future__ import annotations

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
PERMANENT_STATUS = {400, 401, 403, 404, 409, 422}


def classify_status(status: int) -> str:
    """Return 'retryable' or 'permanent' for an HTTP status."""
    if status in RETRYABLE_STATUS:
        return "retryable"
    if status in PERMANENT_STATUS:
        return "permanent"
    if 500 <= status < 600:
        return "retryable"
    return "permanent"


class ConnectorError(Exception):
    def __init__(self, message: str, *, status: int | None = None,
                 code: str = "", error_class: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.error_class = error_class or (classify_status(status) if status else "permanent")
        self.message = message


class PermanentError(ConnectorError):
    def __init__(self, message: str, **kw):
        kw.setdefault("error_class", "permanent")
        super().__init__(message, **kw)


class RetryableError(ConnectorError):
    def __init__(self, message: str, **kw):
        kw.setdefault("error_class", "retryable")
        super().__init__(message, **kw)


class RetryExhaustedError(ConnectorError):
    def __init__(self, message: str, *, attempts: int = 0, **kw):
        kw.setdefault("error_class", "retryable_exhausted")
        super().__init__(message, **kw)
        self.attempts = attempts


class SimulatedCrash(Exception):
    """Raised by the sync engine's crash hook to simulate a process crash."""
