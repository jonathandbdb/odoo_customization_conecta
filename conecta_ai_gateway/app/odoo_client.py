# -*- coding: utf-8 -*-
"""Cliente HTTP para postear el resultado al callback de Odoo (firmado HMAC)."""
from __future__ import annotations

import json
import logging
import time
from typing import Optional

import httpx

from .config import Settings
from .schemas import AgentResult
from .security import sign_body

logger = logging.getLogger(__name__)


async def post_callback(
    settings: Settings,
    callback_url: str,
    ticket_id: int,
    token: str,
    run_id: str,
    status: str,
    result: Optional[AgentResult] = None,
    error: Optional[str] = None,
) -> bool:
    """POST firmado con HMAC al endpoint /ai_diagnosis/callback de Odoo."""
    payload = {
        "ticket_id": ticket_id,
        "token": token,
        "run_id": run_id,
        "status": status,
    }
    if result is not None:
        payload["result"] = result.model_dump()
    if error:
        payload["error"] = error[:2000]

    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ts = int(time.time())
    headers = {
        "Content-Type": "application/json",
        "X-Conecta-Signature": f"sha256={sign_body(settings.callback_secret, body)}",
        "X-Conecta-Timestamp": str(ts),
    }
    try:
        async with httpx.AsyncClient(timeout=settings.odoo_request_timeout) as client:
            resp = await client.post(callback_url, content=body, headers=headers)
        if resp.status_code >= 300:
            logger.warning(
                "Callback a Odoo falló: %s %s — body=%s",
                resp.status_code, callback_url, resp.text[:300],
            )
            return False
        logger.info("Callback a Odoo OK (ticket=%s, run=%s)", ticket_id, run_id)
        return True
    except httpx.HTTPError as err:
        logger.exception("Error al postear callback: %s", err)
        return False
