from __future__ import annotations
from ..base import BaseConnector, Page, PushResult
from ..canonical import Contact


def contact_to_hubspot(c: Contact) -> dict:
    return {"properties": {"firstname": c.first_name, "lastname": c.last_name,
                           "email": c.email, "company": c.company, "phone": c.phone}}


def contact_from_hubspot(raw: dict) -> Contact:
    p = raw.get("properties", {})
    return Contact(external_id=raw["id"], first_name=p.get("firstname", ""),
                   last_name=p.get("lastname", ""), email=p.get("email", ""),
                   company=p.get("company", ""), phone=p.get("phone", ""))


class HubSpotConnector(BaseConnector):
    name = "hubspot"

    def fetch(self, cursor=None, limit: int = 4) -> Page:
        params = {"limit": limit}
        if cursor:
            params["after"] = cursor
        resp = self.request("GET", "/crm/v3/objects/contacts", params=params)
        body = resp.json()
        records = [contact_from_hubspot(r) for r in body["results"]]
        nxt = body.get("paging", {}).get("next", {}).get("after")
        return Page(records=records, next_cursor=nxt, done=nxt is None)

    def push(self, record: Contact) -> PushResult:
        resp = self.request("POST", "/crm/v3/objects/contacts",
                            json=contact_to_hubspot(record))
        body = resp.json()
        return PushResult(external_id=record.external_id, created=True,
                          vendor_id=body.get("id", ""))

    def push_batch(self, records: list[Contact]) -> dict:
        resp = self.request("POST", "/crm/v3/objects/contacts/batch/create",
                            json={"inputs": [contact_to_hubspot(r) for r in records]})
        return resp.json()

    def health(self) -> bool:
        try:
            resp = self.client.get("/health")
            return resp.status_code == 200 and resp.json().get("status") == "ok"
        except Exception:
            return False
