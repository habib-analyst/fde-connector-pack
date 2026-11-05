from fde_connector_pack.canonical import Contact, DirectoryUser, Message
from fde_connector_pack.connectors.salesforce import contact_from_salesforce, contact_to_salesforce
from fde_connector_pack.connectors.hubspot import contact_from_hubspot, contact_to_hubspot
from fde_connector_pack.connectors.slack import message_from_slack, message_to_slack
from fde_connector_pack.connectors.google_workspace import user_from_google, user_to_google

C = Contact(external_id="X-1", first_name="Ada", last_name="Fixture",
            email="ada@fixture.example", company="Fixture Co", phone="+1-555-0100")


def test_salesforce_mapping_exact_shape():
    assert contact_to_salesforce(C) == {
        "FirstName": "Ada", "LastName": "Fixture", "Email": "ada@fixture.example",
        "AccountId": "ACC-FIXTURE-1", "Phone": "+1-555-0100"}
    back = contact_from_salesforce({"Id": "SF-001", "FirstName": "Ada",
        "LastName": "Fixture", "Email": "ada@fixture.example",
        "AccountId": "ACC-9", "Phone": "+1-555-0100"})
    assert (back.external_id, back.first_name, back.email) == ("SF-001", "Ada", "ada@fixture.example")


def test_hubspot_mapping_exact_shape():
    payload = contact_to_hubspot(C)
    assert payload == {"properties": {"firstname": "Ada", "lastname": "Fixture",
                       "email": "ada@fixture.example", "company": "Fixture Co",
                       "phone": "+1-555-0100"}}
    back = contact_from_hubspot({"id": "HS-001", "properties": payload["properties"]})
    assert (back.external_id, back.last_name, back.company) == ("HS-001", "Fixture", "Fixture Co")


def test_slack_mapping_exact_shape():
    m = Message(external_id="1700000001.000100", channel="C-FIXTURE-1",
                text="hello fixture", user="U-FIXTURE-1", ts="1700000001.000100")
    assert message_to_slack(m) == {"channel": "C-FIXTURE-1", "text": "hello fixture"}
    back = message_from_slack({"ts": "1700000001.000100", "channel": "C-FIXTURE-1",
                               "text": "hello fixture", "user": "U-FIXTURE-1"})
    assert (back.external_id, back.text, back.user) == ("1700000001.000100", "hello fixture", "U-FIXTURE-1")


def test_google_mapping_exact_shape():
    u = DirectoryUser(external_id="GU-1", primary_email="ada@fixture.example",
                      given_name="Ada", family_name="Fixture", org_unit="/eng")
    assert user_to_google(u) == {"primaryEmail": "ada@fixture.example",
        "name": {"givenName": "Ada", "familyName": "Fixture"},
        "orgUnitPath": "/eng", "suspended": False}
    back = user_from_google({"id": "GU-1", "primaryEmail": "ada@fixture.example",
        "name": {"givenName": "Ada", "familyName": "Fixture"},
        "orgUnitPath": "/eng", "suspended": False})
    assert (back.external_id, back.given_name, back.org_unit) == ("GU-1", "Ada", "/eng")
