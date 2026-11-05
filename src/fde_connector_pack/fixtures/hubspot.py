from __future__ import annotations
import zlib
from fastapi import FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse

from . import FaultPlan, FixtureState, check_auth

CONTACTS = [
    {"id": f"HS-{i:03d}",
     "properties": {"firstname": f"Fixture{i}", "lastname": f"Contact{i}",
                    "email": f"contact{i}@fixture.example",
                    "company": "Fixture Co", "phone": f"+1-555-02{i:02d}"}}
    for i in range(1, 12)  # 11 contacts
]


def _invalid_email(email: str) -> bool:
    return "@" not in email or email.endswith("@invalid.example")


def create_hubspot_app(plan: FaultPlan | None = None):
    plan = plan or FaultPlan()
    state = FixtureState()
    app = FastAPI(title="hubspot-fixture")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "hubspot-fixture"}

    @app.get("/crm/v3/objects/contacts")
    def list_contacts(authorization: str | None = Header(default=None),
                      after: str | None = Query(default=None),
                      limit: int = Query(default=4)):
        if state.check_rate_limit(plan):
            return JSONResponse(status_code=429, headers={"Retry-After": plan.retry_after},
                                content={"status": "error", "message": "fixture rate limit",
                                         "category": "RATE_LIMITS"})
        if not check_auth(authorization, "hubspot"):
            return JSONResponse(status_code=401,
                                content={"status": "error", "message": "fixture auth required",
                                         "category": "EXPIRED_AUTHENTICATION"})
        fault = state.cursor_fault(plan, after)
        if fault == "500":
            return JSONResponse(status_code=500,
                                content={"status": "error", "message": "fixture transient failure",
                                         "category": "INTERNAL_ERROR"})
        if fault == "429":
            return JSONResponse(status_code=429, headers={"Retry-After": plan.retry_after},
                                content={"status": "error", "message": "fixture rate limit",
                                         "category": "RATE_LIMITS"})
        offset = int(after.split("-")[-1]) if after else 0
        page = CONTACTS[offset:offset + limit]
        nxt = offset + limit
        body = {"results": page}
        if nxt < len(CONTACTS):
            body["paging"] = {"next": {"after": f"hs-{nxt}"}}
        return body

    @app.post("/crm/v3/objects/contacts")
    async def create_contact(request: Request,
                             authorization: str | None = Header(default=None)):
        if not check_auth(authorization, "hubspot"):
            return JSONResponse(status_code=401,
                                content={"status": "error", "message": "fixture auth required",
                                         "category": "EXPIRED_AUTHENTICATION"})
        payload = await request.json()
        email = payload.get("properties", {}).get("email", "")
        if _invalid_email(email):
            return JSONResponse(status_code=400,
                                content={"status": "error",
                                         "message": f"Email address {email} is invalid",
                                         "category": "VALIDATION_ERROR"})
        return JSONResponse(status_code=201,
                            content={"id": f"HS-NEW-{zlib.crc32(email.encode()) % 10000:04d}",
                                     "properties": payload["properties"]})

    @app.post("/crm/v3/objects/contacts/batch/create")
    async def batch_create(request: Request,
                           authorization: str | None = Header(default=None)):
        if not check_auth(authorization, "hubspot"):
            return JSONResponse(status_code=401,
                                content={"status": "error", "message": "fixture auth required",
                                         "category": "EXPIRED_AUTHENTICATION"})
        payload = await request.json()
        results, errors = [], []
        for item in payload.get("inputs", []):
            email = item.get("properties", {}).get("email", "")
            if _invalid_email(email):
                errors.append({"status": "error", "message": f"invalid email {email}",
                               "category": "VALIDATION_ERROR"})
            else:
                results.append({"id": f"HS-NEW-{zlib.crc32(email.encode()) % 10000:04d}",
                                "properties": item["properties"]})
        return {"status": "COMPLETE", "results": results, "errors": errors}

    app.state.fixture_state = state
    app.state.fault_plan = plan
    return app
