# -*- coding: utf-8 -*-
"""Esquemas Pydantic del payload entrante y la respuesta estructurada del agente."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ClientInfo(BaseModel):
    project_id: int
    project_name: str = ""
    ssh_host: str
    ssh_user: str = "root"
    ssh_port: int = 22
    credential_ref: str = ""
    notes: str = ""


class CallbackInfo(BaseModel):
    url: str
    ticket_id: int
    token: str


class TicketPayload(BaseModel):
    ticket_id: int
    ticket_number: str = ""
    ticket_name: str = ""
    ticket_url: str = ""
    priority: str = ""
    category: str = ""
    team: str = ""
    requester: str = ""
    description: str = ""
    client: ClientInfo
    callback: CallbackInfo
    issued_at: int


class AgentResult(BaseModel):
    error_root_cause: str = ""
    fix_applied: str = ""
    client_summary: str = ""


class CallbackPayload(BaseModel):
    ticket_id: int
    token: str
    run_id: str
    status: str = Field(..., pattern="^(ok|error)$")
    result: Optional[AgentResult] = None
    error: Optional[str] = None
