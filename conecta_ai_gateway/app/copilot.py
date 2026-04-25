# -*- coding: utf-8 -*-
"""Invocador del binario `copilot` en modo headless (-p)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
from pathlib import Path
from typing import Optional, Tuple

from .config import Settings
from .schemas import AgentResult, TicketPayload

logger = logging.getLogger(__name__)


def _build_prompt(payload: TicketPayload, agents_md_path: str) -> str:
    """Construye el prompt para el agente. Las reglas duras están en AGENTS.md
    (que el agente lee automáticamente del workdir)."""
    c = payload.client
    key_name = c.credential_ref or "id_rsa_conecta"
    return f"""Sos un agente de diagnóstico técnico para tickets de Conecta. Lee \
las reglas en AGENTS.md (en este mismo directorio) ANTES de actuar. Trabajás en \
modo SOLO LECTURA — está prohibido modificar nada en el servidor del cliente.

# Ticket de Helpdesk
- ID: {payload.ticket_id} ({payload.ticket_number})
- Asunto: {payload.ticket_name}
- Solicitante: {payload.requester}
- Prioridad: {payload.priority or "n/a"}
- Categoría: {payload.category or "n/a"}
- URL: {payload.ticket_url}

# Servidor del cliente (SOLO LECTURA)
- host: {c.ssh_host}
- user: {c.ssh_user}
- port: {c.ssh_port}
- proyecto: {c.project_name} (id={c.project_id})
- notas: {c.notes or "—"}

Para conectarte usá: `ssh -i ~/.ssh/{key_name} -p {c.ssh_port} \
{c.ssh_user}@{c.ssh_host} '<comando read-only>'`.

# Descripción del problema reportado
{payload.description or "(sin descripción)"}

# Tu tarea
1. Conectate al servidor del cliente por SSH y diagnosticá el problema.
2. Revisá logs relevantes (`/var/log/odoo/odoo-server.log`, `docker logs`, \
   `journalctl`) usando `grep`/`tail`. NO ejecutes comandos que modifiquen estado.
3. Si necesitás consultar la base de datos del cliente, hacelo con \
   `docker exec <db_container> psql -U <user> -d <db> -c "SELECT ..."` — solo \
   SELECT, jamás UPDATE/DELETE/DDL.
4. Cuando termines tu investigación, devolvé tu RESPUESTA FINAL como UN \
   ÚNICO bloque JSON entre los marcadores <RESULT> y </RESULT>, con esta forma:

<RESULT>
{{
  "error_root_cause": "<causa raíz técnica detectada, 1-3 frases>",
  "fix_applied": "<en V1 siempre 'Ninguna acción aplicada — modo diagnóstico'>",
  "client_summary": "<resumen para el cliente en HTML básico (p, ul, li, strong, code)>"
}}
</RESULT>

No agregues nada después de </RESULT>. Si no podés conectarte o no tenés \
información suficiente, devolvé igualmente el JSON con error_root_cause \
explicando el bloqueo.
""".strip()


_RESULT_RE = re.compile(r"<RESULT>\s*(\{.*?\})\s*</RESULT>", re.DOTALL)


def _parse_agent_output(stdout: str) -> Tuple[Optional[AgentResult], str]:
    """Extrae el bloque <RESULT>{...}</RESULT> del stdout. Devuelve (resultado, raw)."""
    match = _RESULT_RE.search(stdout)
    if not match:
        # Intento permisivo: último JSON del stdout
        candidates = re.findall(r"\{.*?\}", stdout, flags=re.DOTALL)
        for cand in reversed(candidates):
            try:
                data = json.loads(cand)
                if isinstance(data, dict) and "client_summary" in data:
                    return AgentResult(**data), stdout
            except (ValueError, TypeError):
                continue
        return None, stdout
    try:
        data = json.loads(match.group(1))
        return AgentResult(**data), stdout
    except (ValueError, TypeError) as err:
        logger.warning("No se pudo parsear el JSON del agente: %s", err)
        return None, stdout


async def run_copilot(
    payload: TicketPayload,
    settings: Settings,
    run_id: str,
) -> Tuple[Optional[AgentResult], str, int]:
    """Ejecuta `copilot -p <prompt>` con tools en allowlist. Devuelve
    (resultado_parseado, stdout_raw, exit_code)."""
    workdir = settings.workdir_path / run_id
    workdir.mkdir(parents=True, exist_ok=True)
    # Copiar AGENTS.md al workdir para que el agente lo encuentre
    agents_md_src = Path("/app/AGENTS.md")
    agents_md_dst = workdir / "AGENTS.md"
    if agents_md_src.exists() and not agents_md_dst.exists():
        agents_md_dst.write_text(
            agents_md_src.read_text(encoding="utf-8"), encoding="utf-8"
        )

    prompt = _build_prompt(payload, str(agents_md_dst))

    args = [
        settings.copilot_bin,
        "-p", prompt,
        "--no-color",
        "--log-level", "error",
        "--no-ask-user",          # No preguntar al usuario, modo autónomo
        "--allow-all-paths",      # Permitir escribir transcript dentro del workdir
        "--silent",               # Solo respuesta del agente (sin stats)
        "--no-auto-update",       # Bloquear auto-update en runtime
    ]
    if settings.copilot_model:
        args += ["--model", settings.copilot_model]
    for tool in settings.copilot_allow_tools:
        args += ["--allow-tool", tool]
    if settings.copilot_extra_args:
        args += shlex.split(settings.copilot_extra_args)

    logger.info(
        "Copilot run %s: cmd=%s cwd=%s",
        run_id, " ".join(shlex.quote(a) for a in args[:6] + ["..."]),
        workdir,
    )
    env = os.environ.copy()
    env.setdefault("HOME", str(Path.home()))

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workdir),
            env=env,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=settings.copilot_timeout_seconds
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return None, "TIMEOUT", -1
    except FileNotFoundError as err:
        logger.exception("Copilot CLI no encontrado: %s", err)
        return None, f"copilot binary not found: {err}", -2

    stdout = stdout_b.decode("utf-8", errors="replace") if stdout_b else ""
    stderr = stderr_b.decode("utf-8", errors="replace") if stderr_b else ""
    if stderr:
        logger.info("Copilot run %s stderr: %s", run_id, stderr[-500:])

    result, raw = _parse_agent_output(stdout)
    return result, raw, proc.returncode or 0
