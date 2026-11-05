from __future__ import annotations
from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse

from . import FaultPlan, FixtureState, check_auth

CHANNEL = "C-FIXTURE-1"
MESSAGES = [
    {"ts": f"17000000{i:02d}.000100", "channel": CHANNEL,
     "text": f"Fixture message {i}", "user": "U-FIXTURE-1"}
    for i in range(1, 10)  # 9 messages
]


def create_slack_app(plan: FaultPlan | None = None):
    plan = plan or FaultPlan()
    state = FixtureState()
    app = FastAPI(title="slack-fixture")

    @app.get("/health")
    def health():
        return {"ok": True, "service": "slack-fixture"}

    @app.get("/api/conversations.list")
    def conversations_list(authorization: str | None = Header(default=None)):
        if not check_auth(authorization, "slack"):
            return JSONResponse(status_code=401, content={"ok": False, "error": "invalid_auth"})
        return {"ok": True, "channels": [{"id": CHANNEL, "name": "fixture-general"}]}

    @app.get("/api/conversations.history")
    def history(authorization: str | None = Header(default=None),
                channel: str = Query(default=CHANNEL),
                cursor: str | None = Query(default=None),
                limit: int = Query(default=4)):
        if state.check_rate_limit(plan):
            return JSONResponse(status_code=429, headers={"Retry-After": plan.retry_after},
                                content={"ok": False, "error": "ratelimited"})
        if not check_auth(authorization, "slack"):
            return JSONResponse(status_code=401, content={"ok": False, "error": "invalid_auth"})
        fault = state.cursor_fault(plan, cursor)
        if fault == "500":
            return JSONResponse(status_code=500, content={"ok": False, "error": "internal_error"})
        if fault == "429":
            return JSONResponse(status_code=429, headers={"Retry-After": plan.retry_after},
                                content={"ok": False, "error": "ratelimited"})
        offset = int(cursor.split("-")[-1]) if cursor else 0
        page = MESSAGES[offset:offset + limit]
        nxt = offset + limit
        body = {"ok": True, "messages": page, "has_more": nxt < len(MESSAGES),
                "response_metadata": {}}
        if nxt < len(MESSAGES):
            body["response_metadata"] = {"next_cursor": f"slack-{nxt}"}
        return body

    @app.post("/api/chat.postMessage")
    async def post_message(request: Request,
                           authorization: str | None = Header(default=None)):
        if state.check_rate_limit(plan):
            return JSONResponse(status_code=429, headers={"Retry-After": plan.retry_after},
                                content={"ok": False, "error": "ratelimited"})
        if not check_auth(authorization, "slack"):
            return JSONResponse(status_code=401, content={"ok": False, "error": "invalid_auth"})
        payload = await request.json()
        if not payload.get("text") or not payload.get("channel"):
            return JSONResponse(status_code=400,
                                content={"ok": False, "error": "invalid_arguments"})
        return {"ok": True, "channel": payload["channel"],
                "ts": "1700000999.000100", "message": {"text": payload["text"]}}

    app.state.fixture_state = state
    app.state.fault_plan = plan
    return app
