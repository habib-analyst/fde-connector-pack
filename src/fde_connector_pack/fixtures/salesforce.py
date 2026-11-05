from __future__ import annotations
import zlib
from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse

from . import FaultPlan, FixtureState, check_auth

CONTACTS = [
    {"Id": f"SF-{i:03d}", "FirstName": f"Fixture{i}", "LastName": f"Contact{i}",
     "Email": f"contact{i}@fixture.example", "AccountId": "ACC-FIXTURE-1",
     "Phone": f"+1-555-01{i:02d}"}
    for i in range(1, 13)  # 12 contacts
]
# One permanently bad record, served on the last page: invalid email shape.
CONTACTS[11] = {**CONTACTS[11], "Email": "bad-record-at-invalid.example"}


def create_salesforce_app(plan: FaultPlan | None = None):
    plan = plan or FaultPlan()
    state = FixtureState()
    app = FastAPI(title="salesforce-fixture")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "salesforce-fixture"}

    @app.get("/services/data/v59.0/query")
    def query(authorization: str | None = Header(default=None),
              cursor: str | None = Query(default=None),
              page_size: int = Query(default=5)):
        if state.check_rate_limit(plan):
            return JSONResponse(status_code=429,
                                headers={"Retry-After": plan.retry_after},
                                content=[{"errorCode": "REQUEST_LIMIT_EXCEEDED",
                                          "message": "fixture rate limit"}])
        if not check_auth(authorization, "salesforce"):
            return JSONResponse(status_code=401,
                                content=[{"errorCode": "INVALID_SESSION_ID",
                                          "message": "fixture auth required"}])
        fault = state.cursor_fault(plan, cursor)
        if fault == "500":
            return JSONResponse(status_code=500,
                                content=[{"errorCode": "INTERNAL_ERROR",
                                          "message": "fixture transient failure"}])
        if fault == "429":
            return JSONResponse(status_code=429,
                                headers={"Retry-After": plan.retry_after},
                                content=[{"errorCode": "REQUEST_LIMIT_EXCEEDED",
                                          "message": "fixture rate limit"}])
        offset = int(cursor.split("-")[-1]) if cursor else 0
        page = CONTACTS[offset:offset + page_size]
        nxt = offset + page_size
        done = nxt >= len(CONTACTS)
        body = {"totalSize": len(CONTACTS), "done": done, "records": page}
        if not done:
            body["nextRecordsUrl"] = f"/services/data/v59.0/query?cursor=sf-{nxt}"
            body["nextCursor"] = f"sf-{nxt}"
        return body

    @app.post("/services/data/v59.0/sobjects/Contact")
    async def create_contact(request: Request,
                             authorization: str | None = Header(default=None)):
        if not check_auth(authorization, "salesforce"):
            return JSONResponse(status_code=401,
                                content=[{"errorCode": "INVALID_SESSION_ID",
                                          "message": "fixture auth required"}])
        payload = await request.json()
        email = payload.get("Email", "")
        if "@" not in email or email.endswith("@invalid.example"):
            return JSONResponse(status_code=400,
                                content=[{"errorCode": "INVALID_EMAIL_ADDRESS",
                                          "message": f"Email is invalid: {email}"}])
        return JSONResponse(status_code=201,
                            content={"id": f"SF-NEW-{zlib.crc32(email.encode()) % 10000:04d}",
                                     "success": True, "errors": []})

    app.state.fixture_state = state
    app.state.fault_plan = plan
    return app
