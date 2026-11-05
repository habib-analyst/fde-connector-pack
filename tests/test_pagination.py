from conftest import make_gw, make_hs, make_sf, make_slack
from fde_connector_pack.engine import StoreDestination, SyncEngine


def drain(conn):
    records, cursor, pages = [], None, 0
    while True:
        page = conn.fetch(cursor)
        pages += 1
        records.extend(page.records)
        cursor = page.next_cursor
        if page.done:
            return records, pages


def test_salesforce_pagination_to_completion():
    records, pages = drain(make_sf())
    assert len(records) == 12 and pages == 3  # 5 + 5 + 2
    assert records[0].external_id == "SF-001" and records[-1].external_id == "SF-012"


def test_hubspot_pagination_to_completion():
    records, pages = drain(make_hs())
    assert len(records) == 11 and pages == 3  # 4 + 4 + 3


def test_google_pagination_to_completion():
    records, pages = drain(make_gw())
    assert len(records) == 10 and pages == 3  # 4 + 4 + 2
    assert records[0].primary_email == "user1@fixture.example"


def test_slack_pagination_to_completion():
    records, pages = drain(make_slack())
    assert len(records) == 9 and pages == 3  # 4 + 4 + 1
    assert records[0].text == "Fixture message 1"


def test_engine_sync_pages_all_connectors(store):
    for make, total in [(make_sf, 12), (make_hs, 11), (make_gw, 10), (make_slack, 9)]:
        s = store.__class__(":memory:")
        src = make()
        dest = StoreDestination(s, src.name)
        report = SyncEngine(s).sync(src, dest)
        # Salesforce carries one bad record only when a validating delegate is
        # attached; plain store sync accepts all fetched records.
        assert report.fetched == total and report.created == total
        assert s.destination_count() == total
