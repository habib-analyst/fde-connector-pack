"""Demo: sync Salesforce fixture contacts into a local SQLite store.

Run: PYTHONPATH=src python3 -m fde_connector_pack.demo
No network: the fixture server runs in-process via FastAPI TestClient.
"""
from __future__ import annotations
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from .connectors.salesforce import SalesforceConnector
from .connectors.hubspot import HubSpotConnector
from .engine import StoreDestination, SyncEngine
from .fixtures import FaultPlan
from .fixtures.hubspot import create_hubspot_app
from .fixtures.salesforce import create_salesforce_app
from .store import SyncStore


def main() -> None:
    db = Path(tempfile.mkdtemp()) / "demo-sync.db"
    store = SyncStore(db)
    plan = FaultPlan(fail_cursor_times={"sf-5": 2})
    sf = SalesforceConnector(TestClient(create_salesforce_app(plan)))
    hs = HubSpotConnector(TestClient(create_hubspot_app()))
    dest = StoreDestination(store, "salesforce", delegate=hs)
    engine = SyncEngine(store)
    try:
        engine.sync(sf, dest, crash_after_pages=1)
    except Exception as exc:
        print(f"simulated crash: {exc}")
    report = engine.sync(sf, dest)
    print(f"pages={report.pages} fetched={report.fetched} created={report.created} "
          f"duplicates={report.duplicates} dead_lettered={report.dead_lettered}")
    print(f"destination rows={store.destination_count()} "
          f"dead letters={len(store.dead_letters())} db={db}")


if __name__ == "__main__":
    main()
