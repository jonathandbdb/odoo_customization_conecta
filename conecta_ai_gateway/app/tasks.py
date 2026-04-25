# -*- coding: utf-8 -*-
"""Tareas asíncronas que ejecutan el agente y postean al callback."""
from __future__ import annotations

import logging

from .config import Settings
from .copilot import run_copilot
from .odoo_client import post_callback
from .schemas import AgentResult, TicketPayload

logger = logging.getLogger(__name__)


async def run_diagnosis_task(
    payload: TicketPayload, settings: Settings, run_id: str
) -> None:
    """Tarea de fondo: ejecuta Copilot y postea al callback."""
    logger.info("Iniciando run %s para ticket %s", run_id, payload.ticket_id)
    result, raw, exit_code = await run_copilot(payload, settings, run_id)

    if exit_code == -1:
        await post_callback(
            settings, payload.callback.url, payload.ticket_id,
            payload.callback.token, run_id, "error",
            error=f"Agent timed out after {settings.copilot_timeout_seconds}s",
        )
        return
    if exit_code == -2:
        await post_callback(
            settings, payload.callback.url, payload.ticket_id,
            payload.callback.token, run_id, "error",
            error="Copilot CLI binary not found in gateway image",
        )
        return
    if result is None:
        # Si no se pudo parsear, devolvemos el raw como client_summary para
        # que el operador humano vea algo. Marcamos como error.
        fallback = AgentResult(
            error_root_cause="No structured result returned by agent.",
            fix_applied="Ninguna acción aplicada — modo diagnóstico",
            client_summary=(
                "<p>El agente no devolvió un resultado estructurado. "
                "Salida bruta (truncada):</p><pre>" + (raw[:3000] or "(vacío)") + "</pre>"
            ),
        )
        await post_callback(
            settings, payload.callback.url, payload.ticket_id,
            payload.callback.token, run_id, "error",
            result=fallback, error="Unparseable agent output",
        )
        return

    await post_callback(
        settings, payload.callback.url, payload.ticket_id,
        payload.callback.token, run_id, "ok", result=result,
    )
