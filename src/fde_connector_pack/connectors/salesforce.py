from __future__ import annotations
from ..base import BaseConnector, Page, PushResult
from ..canonical import Contact


def contact_to_salesforce(c: Contact) -> dict:
    return {"FirstName": c.first_name, "LastName": c.last_name, "Email": c.email,
            "AccountId": "ACC-FIXTURE-1", "Phone": c.phone}


def contact_from_salesforce(raw: dict) -> Contact:
    return Contact(external_id=raw["Id"], first_name=raw.get("FirstName", ""),
                   last_name=raw.get("LastName", ""), email=raw.get("Email", ""),
                   company=raw.get("AccountId", ""), phone=raw.get("Phone", ""))


class SalesforceConnector(BaseConnector):
    name = "salesforce"

    def fetch(self, cursor=None, page_size: int = 5) -> Page:
        params = {"page_size": page_size}
        if cursor:
            params["cursor"] = cursor
        resp = self.request("GET", "/services/data/v59.0/query", params=params)
        body = resp.json()
        records = [contact_from_salesforce(r) for r in body["records"]]
        return Page(records=records, next_cursor=body.get("nextCursor"),
                    done=bool(body.get("done", True)))

    # Engine calls fetch(cursor); keep signature compatible.
    def push(self, record: Contact) -> PushResult:
        resp = self.request("POST", "/services/data/v59.0/sobjects/Contact",
                            json=contact_to_salesforce(record))
        body = resp.json()
        return PushResult(external_id=record.external_id, created=True,
                          vendor_id=body.get("id", ""))

    def health(self) -> bool:
        try:
            resp = self.client.get("/health")
            return resp.status_code == 200 and resp.json().get("status") == "ok"
        except Exception:
            return False
