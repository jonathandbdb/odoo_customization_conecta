# -*- coding: utf-8 -*-
"""FastAPI app principal del Conecta AI Gateway."""
from __future__ import annotations

import json
import logging
import secrets
from functools import lru_cache
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .config import Settings, get_settings
from .odoo_xmlrpc import OdooXmlrpcError, get_odoo_client
from .schemas import TicketPayload
from .security import verify_signature
from .tasks import run_diagnosis_task

logger = logging.getLogger("conecta_ai_gateway")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Conecta AI Gateway",
    version="1.1.0",
    description="Webhook receiver → GitHub Copilot CLI → callback a Odoo, "
                "más endpoints internos para Hermes.",
)


@lru_cache(maxsize=1)
def _settings() -> Settings:
    return get_settings()


# --- Niveles de soporte válidos para el endpoint /support-clients ---
_VALID_SUPPORT_LEVELS = {"standard", "medium", "full"}


def _require_hermes_bearer(authorization: Optional[str], settings: Settings) -> None:
    """Comentario en español: valida el token Bearer enviado por Hermes."""
    if not settings.hermes_api_token:
        raise HTTPException(status_code=503, detail="HERMES_API_TOKEN not configured")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    provided = authorization.split(" ", 1)[1].strip()
    if not secrets.compare_digest(provided, settings.hermes_api_token):
        raise HTTPException(status_code=401, detail="invalid bearer token")


@app.get("/healthz")
async def healthz():
    return {"ok": True, "service": "conecta-ai-gateway"}


@app.post("/process-ticket")
async def process_ticket(request: Request, background: BackgroundTasks):
    settings = _settings()
    body = await verify_signature(
        request, settings.webhook_secret, settings.timestamp_tolerance
    )
    try:
        payload_dict = json.loads(body.decode("utf-8"))
        payload = TicketPayload(**payload_dict)
    except (ValueError, ValidationError) as err:
        logger.warning("Payload inválido: %s", err)
        raise HTTPException(status_code=400, detail=f"invalid payload: {err}")

    run_id = secrets.token_hex(8)
    logger.info(
        "Aceptado ticket=%s project=%s run=%s",
        payload.ticket_id, payload.client.project_name, run_id,
    )
    background.add_task(run_diagnosis_task, payload, settings, run_id)
    return JSONResponse(
        status_code=202,
        content={"accepted": True, "run_id": run_id, "ticket_id": payload.ticket_id},
    )


@app.get("/support-clients")
async def support_clients(
    level: Optional[str] = Query(
        default=None,
        description="CSV con niveles a filtrar (standard,medium,full). Vacío = todos.",
    ),
    authorization: Optional[str] = Header(default=None),
):
    """Devuelve los proyectos con soporte contratado y sus datos de conexión.

    Consumidor previsto: el agente Hermes. Requiere Bearer token.
    """
    settings = _settings()
    _require_hermes_bearer(authorization, settings)

    # Comentario en español: parseo y validación del filtro de niveles
    if level:
        levels = [lvl.strip().lower() for lvl in level.split(",") if lvl.strip()]
        invalid = [lvl for lvl in levels if lvl not in _VALID_SUPPORT_LEVELS]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"invalid level(s): {invalid}. allowed: {sorted(_VALID_SUPPORT_LEVELS)}",
            )
    else:
        levels = sorted(_VALID_SUPPORT_LEVELS)

    domain = [
        ("active", "=", True),
        ("support_level", "in", levels),
    ]
    fields = [
        "id",
        "name",
        "partner_id",
        "support_level",
        "client_ssh_host",
        "client_ssh_user",
        "client_ssh_port",
        "client_ai_credential_ref",
        "client_ssh_notes",
        "ai_diagnosis_enabled",
    ]
    try:
        records = get_odoo_client(settings).search_read(
            "project.project", domain, fields, order="name asc"
        )
    except OdooXmlrpcError as err:
        logger.exception("Error consultando Odoo: %s", err)
        raise HTTPException(status_code=502, detail=f"odoo upstream error: {err}")

    # Comentario en español: aplanado de partner y respuesta limpia
    clients = []
    for rec in records:
        partner = rec.get("partner_id") or [None, ""]
        clients.append({
            "project_id": rec["id"],
            "project_name": rec.get("name") or "",
            "partner_id": partner[0] if isinstance(partner, list) else None,
            "partner_name": partner[1] if isinstance(partner, list) else "",
            "support_level": rec.get("support_level") or "",
            "ssh_host": rec.get("client_ssh_host") or "",
            "ssh_user": rec.get("client_ssh_user") or "",
            "ssh_port": rec.get("client_ssh_port") or 22,
            "credential_ref": rec.get("client_ai_credential_ref") or "",
            "notes": rec.get("client_ssh_notes") or "",
            "ai_diagnosis_enabled": bool(rec.get("ai_diagnosis_enabled")),
        })

    return {
        "count": len(clients),
        "filter": {"support_level": levels},
        "clients": clients,
    }

