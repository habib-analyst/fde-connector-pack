from __future__ import annotations
from ..base import BaseConnector, Page, PushResult
from ..canonical import DirectoryUser


def user_to_google(u: DirectoryUser) -> dict:
    return {"primaryEmail": u.primary_email,
            "name": {"givenName": u.given_name, "familyName": u.family_name},
            "orgUnitPath": u.org_unit, "suspended": u.suspended}


def user_from_google(raw: dict) -> DirectoryUser:
    name = raw.get("name", {})
    return DirectoryUser(external_id=raw["id"], primary_email=raw.get("primaryEmail", ""),
                         given_name=name.get("givenName", ""),
                         family_name=name.get("familyName", ""),
                         org_unit=raw.get("orgUnitPath", "/"),
                         suspended=bool(raw.get("suspended", False)))


class GoogleWorkspaceConnector(BaseConnector):
    name = "google"

    def fetch(self, cursor=None, max_results: int = 4) -> Page:
        params = {"maxResults": max_results}
        if cursor:
            params["pageToken"] = cursor
        resp = self.request("GET", "/admin/directory/v1/users", params=params)
        body = resp.json()
        records = [user_from_google(r) for r in body.get("users", [])]
        nxt = body.get("nextPageToken")
        return Page(records=records, next_cursor=nxt, done=nxt is None)

    def push(self, record: DirectoryUser) -> PushResult:
        resp = self.request("POST", "/admin/directory/v1/users",
                            json=user_to_google(record))
        body = resp.json()
        return PushResult(external_id=record.external_id, created=True,
                          vendor_id=body.get("id", ""))

    def health(self) -> bool:
        try:
            resp = self.client.get("/health")
            return resp.status_code == 200 and resp.json().get("status") == "ok"
        except Exception:
            return False
