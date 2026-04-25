# -*- coding: utf-8 -*-
"""FastAPI app principal del Conecta AI Gateway."""
from __future__ import annotations

import json
import logging
import secrets
from functools import lru_cache

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .config import Settings, get_settings
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
    version="1.0.0",
    description="Webhook receiver → GitHub Copilot CLI → callback a Odoo.",
)


@lru_cache(maxsize=1)
def _settings() -> Settings:
    return get_settings()


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
