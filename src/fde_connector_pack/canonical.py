from __future__ import annotations
from pydantic import BaseModel, Field


class Contact(BaseModel):
    external_id: str
    first_name: str
    last_name: str
    email: str
    company: str = ""
    phone: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Account(BaseModel):
    external_id: str
    name: str
    domain: str = ""
    industry: str = ""


class Message(BaseModel):
    external_id: str
    channel: str
    text: str
    user: str = ""
    ts: str = ""


class DirectoryUser(BaseModel):
    external_id: str
    primary_email: str
    given_name: str
    family_name: str
    org_unit: str = "/"
    suspended: bool = False
