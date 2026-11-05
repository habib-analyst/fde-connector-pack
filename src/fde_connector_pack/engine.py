from __future__ import annotations
from dataclasses import dataclass, field

from .base import BaseConnector
from .errors import ConnectorError, PermanentError, RetryExhaustedError, SimulatedCrash
from .store import SyncStore


@dataclass
class SyncReport:
    source: str
    destination: str
    pages: int = 0
    fetched: int = 0
    created: int = 0
    duplicates: int = 0
    dead_lettered: int = 0
    resumed_from_cursor: str | None = None


class StoreDestination(BaseConnector):
    """Destination adapter that writes into the SyncStore idempotently.

    Optionally delegates validation to a real vendor connector's push():
    when delegate is set, the vendor push runs first (permanent vendor
    rejections propagate), then the idempotent store write dedupes.
    """
    name = "store"

    def __init__(self, store: SyncStore, source_name: str, delegate: BaseConnector | None = None):
        # No HTTP client needed when there is no delegate.
        super().__init__(client=None)
        self.name = f"store:{source_name}"
        self.store = store
        self.source_name = source_name
        self.delegate = delegate

    def push(self, record):
        if self.delegate is not None:
            self.delegate.push(record)  # raises PermanentError for bad records
        key = f"{self.source_name}:{record.external_id}"
        payload = record.model_dump() if hasattr(record, "model_dump") else dict(record)
        created = self.store.put_destination(key, self.source_name, record.external_id, payload)
        from .base import PushResult
        return PushResult(external_id=record.external_id, created=created,
                          vendor_id=record.external_id)

    def fetch(self, cursor=None):
        raise NotImplementedError("StoreDestination is push-only")

    def health(self) -> bool:
        return True


class SyncEngine:
    """Pages a source connector into a destination, checkpointing durably.

    After each page is fully processed the next cursor is written to the
    checkpoint table (SQLite commit), so a crash between pages resumes
    from the last checkpoint. A crash mid-page re-fetches that page on
    resume; the destination's idempotency keys make the re-push a no-op
    for records already written, so no duplicates appear.
    """

    def __init__(self, store: SyncStore):
        self.store = store

    def sync(self, source: BaseConnector, destination: BaseConnector,
             *, resume: bool = True, crash_after_pages: int | None = None,
             max_pages: int = 100) -> SyncReport:
        report = SyncReport(source=source.name, destination=destination.name)
        cursor = self.store.get_checkpoint(source.name) if resume else None
        report.resumed_from_cursor = cursor
        pages_done_this_run = 0
        for _ in range(max_pages):
            page = source.fetch(cursor)
            report.pages += 1
            report.fetched += len(page.records)
            for record in page.records:
                try:
                    result = destination.push(record)
                    if result.created:
                        report.created += 1
                    else:
                        report.duplicates += 1
                except PermanentError as exc:
                    report.dead_lettered += 1
                    self.store.add_dead_letter(
                        source.name, record.external_id, "permanent",
                        exc.code, exc.message, 1,
                        record.model_dump() if hasattr(record, "model_dump") else {})
                except RetryExhaustedError as exc:
                    report.dead_lettered += 1
                    self.store.add_dead_letter(
                        source.name, record.external_id, "retryable_exhausted",
                        exc.code, exc.message, exc.attempts,
                        record.model_dump() if hasattr(record, "model_dump") else {})
                except ConnectorError as exc:
                    report.dead_lettered += 1
                    self.store.add_dead_letter(
                        source.name, record.external_id, exc.error_class,
                        exc.code, exc.message, 1,
                        record.model_dump() if hasattr(record, "model_dump") else {})
            # Durable checkpoint after the whole page is processed.
            self.store.save_checkpoint(source.name, page.next_cursor)
            pages_done_this_run += 1
            if crash_after_pages is not None and pages_done_this_run >= crash_after_pages and not page.done:
                raise SimulatedCrash(
                    f"simulated crash after {pages_done_this_run} page(s)")
            cursor = page.next_cursor
            if page.done:
                break
        return report
