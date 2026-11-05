from __future__ import annotations
import zlib
from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse

from . import FaultPlan, FixtureState, check_auth

USERS = [
    {"id": f"GU-{i:03d}", "primaryEmail": f"user{i}@fixture.example",
     "name": {"givenName": f"Fixture{i}", "familyName": f"User{i}"},
     "orgUnitPath": "/", "suspended": False}
    for i in range(1, 11)  # 10 users
]


def _error(status: int, message: str, reason: str):
    return JSONResponse(status_code=status, content={
        "error": {"code": status, "message": message,
                  "errors": [{"domain": "global", "reason": reason, "message": message}]}})


def create_google_workspace_app(plan: FaultPlan | None = None):
    plan = plan or FaultPlan()
    state = FixtureState()
    app = FastAPI(title="google-workspace-fixture")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "google-workspace-fixture"}

    @app.get("/admin/directory/v1/users")
    def list_users(authorization: str | None = Header(default=None),
                   pageToken: str | None = Query(default=None),
                   maxResults: int = Query(default=4)):
        if state.check_rate_limit(plan):
            resp = _error(429, "fixture rate limit", "rateLimitExceeded")
            resp.headers["Retry-After"] = plan.retry_after
            return resp
        if not check_auth(authorization, "google"):
            return _error(401, "fixture auth required", "authError")
        fault = state.cursor_fault(plan, pageToken)
        if fault == "500":
            return _error(500, "fixture transient failure", "backendError")
        if fault == "429":
            resp = _error(429, "fixture rate limit", "rateLimitExceeded")
            resp.headers["Retry-After"] = plan.retry_after
            return resp
        offset = int(pageToken.split("-")[-1]) if pageToken else 0
        page = USERS[offset:offset + maxResults]
        nxt = offset + maxResults
        body = {"kind": "admin#directory#users", "users": page}
        if nxt < len(USERS):
            body["nextPageToken"] = f"gw-{nxt}"
        return body

    @app.post("/admin/directory/v1/users")
    async def create_user(request: Request,
                          authorization: str | None = Header(default=None)):
        if not check_auth(authorization, "google"):
            return _error(401, "fixture auth required", "authError")
        payload = await request.json()
        email = payload.get("primaryEmail", "")
        if "@" not in email or email.endswith("@invalid.example"):
            return _error(400, f"Invalid Input: primaryEmail {email}", "invalid")
        return JSONResponse(status_code=201, content={
            "id": f"GU-NEW-{zlib.crc32(email.encode()) % 10000:04d}", **payload})

    app.state.fixture_state = state
    app.state.fault_plan = plan
    return app
