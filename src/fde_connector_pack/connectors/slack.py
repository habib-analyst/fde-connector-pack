from __future__ import annotations
from ..base import BaseConnector, Page, PushResult
from ..canonical import Message

CHANNEL = "C-FIXTURE-1"


def message_to_slack(m: Message) -> dict:
    return {"channel": m.channel, "text": m.text}


def message_from_slack(raw: dict) -> Message:
    return Message(external_id=raw["ts"], channel=raw.get("channel", CHANNEL),
                   text=raw.get("text", ""), user=raw.get("user", ""), ts=raw["ts"])


class SlackConnector(BaseConnector):
    name = "slack"

    def fetch(self, cursor=None, limit: int = 4) -> Page:
        params = {"channel": CHANNEL, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        resp = self.request("GET", "/api/conversations.history", params=params)
        body = resp.json()
        records = [message_from_slack(r) for r in body["messages"]]
        next_cursor = body.get("response_metadata", {}).get("next_cursor")
        return Page(records=records, next_cursor=next_cursor,
                    done=not body.get("has_more", False))

    def push(self, record: Message) -> PushResult:
        resp = self.request("POST", "/api/chat.postMessage",
                            json=message_to_slack(record))
        body = resp.json()
        return PushResult(external_id=record.external_id, created=True,
                          vendor_id=body.get("ts", ""))

    def health(self) -> bool:
        try:
            resp = self.client.get("/health")
            return resp.status_code == 200 and resp.json().get("ok") is True
        except Exception:
            return False
