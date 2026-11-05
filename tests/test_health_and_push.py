from conftest import make_gw, make_hs, make_sf, make_slack
from fde_connector_pack.canonical import Contact, DirectoryUser, Message
from fde_connector_pack.clock import FakeClock


def test_all_connectors_health():
    assert make_sf().health() is True
    assert make_slack().health() is True
    assert make_hs().health() is True
    assert make_gw().health() is True


def test_push_round_trips():
    c = Contact(external_id="X-1", first_name="Ada", last_name="Fixture",
                email="ada@fixture.example", company="Fixture Co", phone="+1-555-0100")
    assert make_sf().push(c).vendor_id.startswith("SF-NEW-")
    assert make_hs().push(c).vendor_id.startswith("HS-NEW-")
    u = DirectoryUser(external_id="GU-X", primary_email="ada@fixture.example",
                      given_name="Ada", family_name="Fixture")
    assert make_gw().push(u).vendor_id.startswith("GU-NEW-")
    m = Message(external_id="M-1", channel="C-FIXTURE-1", text="hello", user="U-1")
    assert make_slack().push(m).vendor_id == "1700000999.000100"


def test_hubspot_batch_api():
    hs = make_hs()
    good = Contact(external_id="X-1", first_name="Ada", last_name="F",
                   email="ada@fixture.example", company="Co", phone="")
    bad = Contact(external_id="X-2", first_name="Bad", last_name="F",
                  email="bad@invalid.example", company="Co", phone="")
    body = hs.push_batch([good, bad])
    assert body["status"] == "COMPLETE"
    assert len(body["results"]) == 1 and len(body["errors"]) == 1
    assert body["errors"][0]["category"] == "VALIDATION_ERROR"


def test_fixture_token_and_refresh():
    clock = FakeClock()
    sf = make_sf(clock=clock, token_ttl=10.0)
    assert sf.tokens.get_token() == "fixture-salesforce-token-1"
    clock.sleep(11.0)  # pass the virtual expiry
    assert sf.tokens.get_token() == "fixture-salesforce-token-2"
    assert sf.tokens.refresh_count == 1
    assert sf.tokens.headers() == {"Authorization": "Bearer fixture-salesforce-token-2"}


def test_idempotency_key_format():
    c = Contact(external_id="SF-001", first_name="A", last_name="B",
                email="a@fixture.example", company="", phone="")
    assert make_sf().idempotency_key(c) == "salesforce:SF-001"
    assert make_hs().idempotency_key(c) == "hubspot:SF-001"
