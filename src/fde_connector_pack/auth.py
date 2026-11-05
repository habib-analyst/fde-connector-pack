from __future__ import annotations


class TokenProvider:
    """OAuth-style token handling with fixture tokens.

    Holds a fixture access token with a virtual expiry (in clock seconds).
    When the injected clock passes the expiry, get_token() refreshes and
    returns the next fixture token. No real credentials anywhere.
    """
    def __init__(self, vendor: str, clock, ttl: float = 3600.0):
        self.vendor = vendor
        self.clock = clock
        self.ttl = ttl
        self.refresh_count = 0
        self._seq = 1
        self._issued_at = clock.now()
        self._token = f"fixture-{vendor}-token-1"

    def get_token(self) -> str:
        if self.clock.now() - self._issued_at >= self.ttl:
            self.refresh()
        return self._token

    def refresh(self) -> str:
        self.refresh_count += 1
        self._seq += 1
        self._token = f"fixture-{self.vendor}-token-{self._seq}"
        self._issued_at = self.clock.now()
        return self._token

    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.get_token()}"}
