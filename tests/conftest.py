import pytest
from fastapi.testclient import TestClient

from fde_connector_pack.clock import FakeClock, RetryPolicy
from fde_connector_pack.connectors.salesforce import SalesforceConnector
from fde_connector_pack.connectors.slack import SlackConnector
from fde_connector_pack.connectors.hubspot import HubSpotConnector
from fde_connector_pack.connectors.google_workspace import GoogleWorkspaceConnector
from fde_connector_pack.fixtures import FaultPlan
from fde_connector_pack.fixtures.salesforce import create_salesforce_app
from fde_connector_pack.fixtures.slack import create_slack_app
from fde_connector_pack.fixtures.hubspot import create_hubspot_app
from fde_connector_pack.fixtures.google_workspace import create_google_workspace_app
from fde_connector_pack.store import SyncStore


def make_sf(plan=None, **kw):
    return SalesforceConnector(TestClient(create_salesforce_app(plan or FaultPlan())), **kw)

def make_slack(plan=None, **kw):
    return SlackConnector(TestClient(create_slack_app(plan or FaultPlan())), **kw)

def make_hs(plan=None, **kw):
    return HubSpotConnector(TestClient(create_hubspot_app(plan or FaultPlan())), **kw)

def make_gw(plan=None, **kw):
    return GoogleWorkspaceConnector(TestClient(create_google_workspace_app(plan or FaultPlan())), **kw)


@pytest.fixture
def store(tmp_path):
    s = SyncStore(tmp_path / "sync.db")
    yield s
    s.close()
