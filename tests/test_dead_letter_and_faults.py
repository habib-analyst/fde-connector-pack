from conftest import make_hs, make_sf
from fde_connector_pack.engine import StoreDestination, SyncEngine
from fde_connector_pack.fixtures import FaultPlan


def test_dead_letter_contents_for_bad_record(store):
    sf, hs = make_sf(), make_hs()
    dest = StoreDestination(store, "salesforce", delegate=hs)
    report = SyncEngine(store).sync(sf, dest)
    assert report.dead_lettered == 1 and report.created == 11
    letters = store.dead_letters()
    assert len(letters) == 1
    letter = letters[0]
    assert letter["connector"] == "salesforce"
    assert letter["external_id"] == "SF-012"
    assert letter["error_class"] == "permanent"
    assert letter["error_code"] == "VALIDATION_ERROR"
    assert "bad-record-at-invalid.example" in letter["payload_json"]


def test_sync_completes_under_scripted_faults(store):
    # Page 2 fails twice with 500, page 3 is rate-limited once: the sync
    # must still complete, retrying within budget, dead-lettering only
    # the one permanently bad record.
    plan = FaultPlan(fail_cursor_times={"sf-5": 2},
                     rate_limit_cursor_times={"sf-10": 1})
    sf, hs = make_sf(plan), make_hs()
    dest = StoreDestination(store, "salesforce", delegate=hs)
    report = SyncEngine(store).sync(sf, dest)
    assert report.fetched == 12 and report.pages == 3
    assert report.created == 11 and report.dead_lettered == 1
    assert sf.retry_count == 3  # 2 transient 500s + 1 rate limit
    assert store.destination_count() == 11


def test_dead_letter_only_bad_record_others_succeed(store):
    sf, hs = make_sf(), make_hs()
    dest = StoreDestination(store, "salesforce", delegate=hs)
    SyncEngine(store).sync(sf, dest)
    ids = store.destination_ids()
    assert "SF-012" not in ids
    assert ids == [f"SF-{i:03d}" for i in range(1, 12)]
