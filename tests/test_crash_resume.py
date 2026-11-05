import pytest

from conftest import make_hs, make_sf
from fde_connector_pack.engine import StoreDestination, SyncEngine
from fde_connector_pack.errors import SimulatedCrash
from fde_connector_pack.store import SyncStore


def _setup(store):
    sf = make_sf()
    hs = make_hs()
    dest = StoreDestination(store, "salesforce", delegate=hs)
    return sf, dest, SyncEngine(store)


def test_crash_after_first_page_then_resume_no_duplicates(store):
    sf, dest, engine = _setup(store)
    with pytest.raises(SimulatedCrash):
        engine.sync(sf, dest, crash_after_pages=1)
    # Page 1 (5 contacts) is durable, checkpoint points at page 2.
    assert store.destination_count() == 5
    assert store.get_checkpoint("salesforce") == "sf-5"

    report = engine.sync(sf, dest)  # resume with a fresh engine pass
    assert report.resumed_from_cursor == "sf-5"
    assert report.fetched == 7  # pages 2+3 only
    assert report.created == 6  # 7 fetched minus the 1 bad record
    assert report.duplicates == 0
    assert store.destination_count() == 11
    assert len(set(store.destination_ids())) == 11


def test_full_rerun_is_idempotent(store):
    sf, dest, engine = _setup(store)
    first = engine.sync(sf, dest, resume=False)
    assert first.created == 11 and first.dead_lettered == 1
    # A dead-letter row exists from run 1; clear it to isolate run 2 dedup:
    store.conn.execute("DELETE FROM dead_letters"); store.conn.commit()
    second = engine.sync(sf, dest, resume=False)
    assert second.created == 0 and second.duplicates == 11
    assert store.destination_count() == 11


def test_checkpoint_is_durable_across_store_instances(tmp_path):
    path = tmp_path / "durable.db"
    s1 = SyncStore(path)
    sf = make_sf(); dest = StoreDestination(s1, "salesforce")
    with pytest.raises(SimulatedCrash):
        SyncEngine(s1).sync(sf, dest, crash_after_pages=2)
    s1.close()
    s2 = SyncStore(path)  # reopen: checkpoint survived the "crash"
    assert s2.get_checkpoint("salesforce") == "sf-10"
    assert s2.destination_count() == 10
    report = SyncEngine(s2).sync(make_sf(), StoreDestination(s2, "salesforce"))
    assert report.fetched == 2 and s2.destination_count() == 12
    s2.close()


def test_mid_page_crash_repush_is_deduped(store):
    # Simulate a crash mid-page: push 3 records of page 1 manually (no
    # checkpoint), then run the full sync. The 3 re-pushes must dedupe.
    sf, dest, engine = _setup(store)
    page = sf.fetch()
    for rec in page.records[:3]:
        dest.push(rec)
    assert store.destination_count() == 3
    report = engine.sync(sf, dest, resume=False)
    assert report.duplicates == 3
    assert report.created == 8  # 11 good total - 3 already present
    assert store.destination_count() == 11
