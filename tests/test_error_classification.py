import pytest

from conftest import make_gw, make_hs, make_sf, make_slack
from fde_connector_pack.canonical import Contact, DirectoryUser, Message
from fde_connector_pack.errors import (PermanentError, classify_status)


@pytest.mark.parametrize("status,expected", [
    (429, "retryable"), (500, "retryable"), (502, "retryable"),
    (503, "retryable"), (504, "retryable"),
    (400, "permanent"), (401, "permanent"), (403, "permanent"),
    (404, "permanent"), (422, "permanent"),
])
def test_classify_status(status, expected):
    assert classify_status(status) == expected


BAD = Contact(external_id="X-BAD", first_name="Bad", last_name="Record",
              email="bad@invalid.example", company="Fixture Co", phone="")


def test_hubspot_permanent_rejection_not_retried():
    hs = make_hs()
    with pytest.raises(PermanentError) as ei:
        hs.push(BAD)
    assert ei.value.error_class == "permanent" and ei.value.status == 400
    assert ei.value.code == "VALIDATION_ERROR"
    assert hs.retry_count == 0 and hs.request_count == 1


def test_salesforce_permanent_rejection():
    sf = make_sf()
    bad = Contact(external_id="X-BAD", first_name="Bad", last_name="Record",
                  email="no-at-sign", company="", phone="")
    with pytest.raises(PermanentError) as ei:
        sf.push(bad)
    assert ei.value.code == "INVALID_EMAIL_ADDRESS"


def test_google_permanent_rejection():
    gw = make_gw()
    bad = DirectoryUser(external_id="GU-BAD", primary_email="bad@invalid.example",
                        given_name="Bad", family_name="User")
    with pytest.raises(PermanentError) as ei:
        gw.push(bad)
    assert ei.value.status == 400 and ei.value.code == "invalid"


def test_slack_permanent_rejection():
    slack = make_slack()
    bad = Message(external_id="M-BAD", channel="C-FIXTURE-1", text="", user="U-1")
    with pytest.raises(PermanentError) as ei:
        slack.push(bad)
    assert ei.value.code == "invalid_arguments"


def test_missing_auth_is_permanent():
    # A connector whose token does not match the fixture's vendor prefix:
    # simulate by calling the fixture with a wrong-vendor token provider.
    from fastapi.testclient import TestClient
    from fde_connector_pack.connectors.salesforce import SalesforceConnector
    from fde_connector_pack.fixtures.hubspot import create_hubspot_app
    conn = SalesforceConnector(TestClient(create_hubspot_app()))
    # Salesforce token against a HubSpot-shaped route still 404s permanently;
    # the classification point: 4xx never consumes the retry budget.
    with pytest.raises(PermanentError):
        conn.fetch()
    assert conn.retry_count == 0
