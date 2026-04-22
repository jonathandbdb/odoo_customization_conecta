# -*- coding: utf-8 -*-
import json
import logging
import re
import shlex
import subprocess

from markupsafe import Markup
from odoo.exceptions import UserError

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Parámetros de sistema utilizados por la integración
ICP_ENABLED = "openclaw.enabled"
ICP_EXEC_MODE = "openclaw.exec_mode"          # 'ssh' | 'docker'
ICP_SSH_HOST = "openclaw.ssh_host"
ICP_SSH_PORT = "openclaw.ssh_port"
ICP_SSH_USER = "openclaw.ssh_user"
ICP_SSH_KEY = "openclaw.ssh_key_path"
ICP_CONTAINER = "openclaw.container_name"
ICP_AGENT_ID = "openclaw.agent_id"
ICP_AGENT_TIMEOUT = "openclaw.agent_timeout"
ICP_ODOO_BASE_URL = "openclaw.odoo_base_url"
ICP_POST_REPLY_NOTE = "openclaw.post_reply_as_note"

# Truncado de la descripción al armar el prompt para el agente
DESCRIPTION_TRUNCATE = 4000


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    # Estado del diagnóstico IA
    ai_diagnosis_state = fields.Selection(
        [
            ("not_applicable", "Not Applicable"),
            ("pending", "Pending"),
            ("sent", "Sent"),
            ("error", "Error"),
        ],
        string="AI Diagnosis State",
        default="not_applicable",
        readonly=True,
        copy=False,
    )
    ai_diagnosis_last_dispatched_at = fields.Datetime(
        string="AI Diagnosis Last Dispatched",
        readonly=True,
        copy=False,
    )
    ai_diagnosis_last_error = fields.Text(
        string="AI Diagnosis Last Error",
        readonly=True,
        copy=False,
    )
    ai_diagnosis_external_ref = fields.Char(
        string="Openclaw Run Id",
        readonly=True,
        copy=False,
        help="Identificador de la corrida del agente Openclaw (runId/sessionId).",
    )

    # --- Creación: disparo automático ----------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        # Disparo síncrono con try/except: nunca debe romper la creación
        for ticket in tickets:
            try:
                ticket._openclaw_dispatch_on_create()
            except Exception as error:  # noqa: BLE001
                _logger.exception(
                    "Openclaw dispatch failed for ticket %s: %s",
                    ticket.display_name, error,
                )
        return tickets

    def _openclaw_dispatch_on_create(self):
        """Evalúa si corresponde disparar el diagnóstico IA y lo hace."""
        self.ensure_one()
        if not self._openclaw_is_applicable():
            return
        self._openclaw_dispatch_to_agent()

    def _openclaw_is_applicable(self):
        """Retorna True si el ticket cumple todas las condiciones para notificar."""
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        # 1) Integración habilitada a nivel sistema
        if icp.get_param(ICP_ENABLED, "False").lower() not in ("1", "true", "t", "yes"):
            return False
        # 2) Debe tener proyecto asignado
        if not self.project_id:
            return False
        # 3) El proyecto debe tener la IA habilitada
        project = self.project_id.sudo()
        if not project.ai_diagnosis_enabled:
            return False
        # 4) El proyecto debe tener host SSH configurado
        if not project.client_ssh_host:
            return False
        return True

    # --- Acción manual -------------------------------------------------------
    def action_openclaw_request_diagnosis(self):
        """Botón manual: fuerza el envío del diagnóstico para los tickets seleccionados."""
        for ticket in self:
            if not ticket.project_id:
                raise UserError(_("The ticket has no project assigned."))
            if not ticket.project_id.sudo().client_ssh_host:
                raise UserError(_(
                    "The project %s has no SSH host configured for the AI agent."
                ) % ticket.project_id.display_name)
            ticket._openclaw_dispatch_to_agent()
        return True

    # --- Utilidades ----------------------------------------------------------
    def _openclaw_get_ticket_url(self):
        """URL absoluta al ticket en el backend."""
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        base = icp.get_param(ICP_ODOO_BASE_URL) or icp.get_param("web.base.url") or ""
        base = base.rstrip("/")
        return f"{base}/web#id={self.id}&model=helpdesk.ticket&view_type=form"

    def _openclaw_build_prompt(self):
        """Arma el prompt que se pasará al agente openclaw."""
        self.ensure_one()
        project = self.project_id.sudo()
        # Limpiar HTML básico de descripción y notas SSH
        description = re.sub(r"<[^>]+>", "", (self.description or "")).strip()
        if len(description) > DESCRIPTION_TRUNCATE:
            description = description[:DESCRIPTION_TRUNCATE] + "…"
        ssh_notes = re.sub(r"<[^>]+>", "", (project.client_ssh_notes or "")).strip() or "—"
        requester = (
            self.partner_id.display_name
            or self.partner_name
            or self.partner_email
            or "—"
        )
        ticket_url = self._openclaw_get_ticket_url()
        lines = [
            "Nuevo ticket en Odoo requiere diagnóstico técnico.",
            "",
            f"Ticket: #{self.id} — {self.number or ''} — {self.name or ''}",
            f"Cliente/Proyecto: {project.display_name}",
            f"Solicitante: {requester}",
            f"Categoría: {self.category_id.display_name or '—'}",
            f"Prioridad: {self.priority or '—'}",
            f"Equipo: {self.team_id.display_name or '—'}",
            f"URL: {ticket_url}",
            "",
            "Conexión SSH del cliente (read-only):",
            f"  host: {project.client_ssh_host}",
            f"  user: {project.client_ssh_user or 'root'}",
            f"  port: {project.client_ssh_port or 22}",
            f"  notas: {ssh_notes}",
            "",
            "Descripción del ticket:",
            description or "(sin descripción)",
            "",
            "Tarea: conéctate por SSH usando la clave id_rsa_conecta, realiza un "
            "diagnóstico EXCLUSIVAMENTE EN MODO LECTURA (logs, estado de "
            "servicios, uso de disco/cpu/ram, errores recientes relevantes al "
            "problema descrito). NO modifiques nada en el servidor. Al finalizar, "
            f"publica tus hallazgos como NOTA INTERNA en el ticket #{self.id} "
            "usando la API de Odoo (helpdesk.ticket → message_post con "
            "subtype_xmlid='mail.mt_note'). Incluye un resumen corto al inicio "
            "y los detalles técnicos después.",
        ]
        return "\n".join(lines)

    def _openclaw_build_command(self, prompt):
        """Construye la lista argv para invocar el CLI openclaw."""
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        exec_mode = (icp.get_param(ICP_EXEC_MODE) or "ssh").strip().lower()
        container = (icp.get_param(ICP_CONTAINER) or "openclaw_gateway").strip()
        agent_id = (icp.get_param(ICP_AGENT_ID) or "main").strip()
        timeout = int(icp.get_param(ICP_AGENT_TIMEOUT) or 600)
        # Comando interno dentro del container: node dist/index.js agent ...
        inner_cmd = [
            "docker", "exec", container,
            "node", "dist/index.js", "agent",
            "--agent", agent_id,
            "--message", prompt,
            "--json",
            "--timeout", str(timeout),
        ]
        if exec_mode == "docker":
            return inner_cmd, timeout
        # Modo SSH: envolvemos el docker exec en ssh con shell remoto
        ssh_host = (icp.get_param(ICP_SSH_HOST) or "").strip()
        if not ssh_host:
            raise UserError(_("Openclaw: 'openclaw.ssh_host' is not configured."))
        ssh_user = (icp.get_param(ICP_SSH_USER) or "root").strip()
        ssh_port = int(icp.get_param(ICP_SSH_PORT) or 22)
        ssh_key = (icp.get_param(ICP_SSH_KEY) or "").strip()
        # Construir comando remoto escapando argumentos (el mensaje puede tener saltos/comillas)
        remote_cmd = " ".join(shlex.quote(arg) for arg in inner_cmd)
        argv = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "BatchMode=yes",
            "-p", str(ssh_port),
        ]
        if ssh_key:
            argv += ["-i", ssh_key]
        argv += [f"{ssh_user}@{ssh_host}", remote_cmd]
        return argv, timeout

    # --- Envío al agente openclaw -------------------------------------------
    def _openclaw_dispatch_to_agent(self):
        """Invoca el CLI openclaw agent y guarda el resultado en el ticket."""
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        prompt = self._openclaw_build_prompt()
        try:
            argv, timeout = self._openclaw_build_command(prompt)
        except UserError as ue:
            self.sudo().write({
                "ai_diagnosis_state": "error",
                "ai_diagnosis_last_error": str(ue),
                "ai_diagnosis_last_dispatched_at": fields.Datetime.now(),
            })
            _logger.warning("Openclaw: configuración incompleta: %s", ue)
            return
        _logger.info(
            "Openclaw: disparando agente para ticket %s (timeout=%ss).",
            self.display_name, timeout,
        )
        try:
            # Comentario en español: damos margen extra sobre el timeout del agente
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout + 60,
                check=False,
            )
        except FileNotFoundError as err:
            self.sudo().write({
                "ai_diagnosis_state": "error",
                "ai_diagnosis_last_error": f"Command not found: {err}",
                "ai_diagnosis_last_dispatched_at": fields.Datetime.now(),
            })
            _logger.exception("Openclaw: ejecutable no encontrado: %s", err)
            return
        except subprocess.TimeoutExpired:
            self.sudo().write({
                "ai_diagnosis_state": "error",
                "ai_diagnosis_last_error": _("Agent call timed out after %s seconds.") % timeout,
                "ai_diagnosis_last_dispatched_at": fields.Datetime.now(),
            })
            _logger.warning("Openclaw: timeout al ejecutar agente para ticket %s.", self.display_name)
            return

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        if proc.returncode != 0:
            self.sudo().write({
                "ai_diagnosis_state": "error",
                "ai_diagnosis_last_error": (stderr or stdout)[:2000],
                "ai_diagnosis_last_dispatched_at": fields.Datetime.now(),
            })
            _logger.warning(
                "Openclaw: exit=%s para ticket %s. stderr=%s",
                proc.returncode, self.display_name, stderr[:500],
            )
            return

        # Intentar parsear la última línea JSON válida del stdout
        data = self._openclaw_parse_json_output(stdout)
        run_id = ""
        reply_text = ""
        if isinstance(data, dict):
            run_id = str(data.get("runId") or data.get("sessionId") or "")
            result = data.get("result") or {}
            payloads = result.get("payloads") or []
            if payloads and isinstance(payloads, list):
                reply_text = "\n\n".join(
                    (p.get("text") or "") for p in payloads if isinstance(p, dict)
                ).strip()

        self.sudo().write({
            "ai_diagnosis_state": "sent",
            "ai_diagnosis_last_error": False,
            "ai_diagnosis_last_dispatched_at": fields.Datetime.now(),
            "ai_diagnosis_external_ref": run_id,
        })
        _logger.info(
            "Openclaw: agente respondió para ticket %s (runId=%s, chars=%s).",
            self.display_name, run_id, len(reply_text),
        )

        # Publicar la respuesta inicial del agente como nota interna, si se configuró
        post_note = (icp.get_param(ICP_POST_REPLY_NOTE, "True") or "").lower() in (
            "1", "true", "t", "yes",
        )
        if post_note and reply_text:
            body = Markup(
                "<p><strong>🦞 Openclaw — respuesta inicial del agente</strong></p>"
                "<pre>%s</pre>"
            ) % reply_text
            self.sudo().message_post(
                body=body,
                subtype_xmlid="mail.mt_note",
            )

    @staticmethod
    def _openclaw_parse_json_output(stdout):
        """Busca la última línea que sea JSON válido en la salida del CLI."""
        # Intento 1: todo el stdout es JSON
        try:
            return json.loads(stdout)
        except (ValueError, TypeError):
            pass
        # Intento 2: escanear bloques que empiecen con '{' y terminen con '}'
        candidates = re.findall(r"\{.*\}", stdout, flags=re.DOTALL)
        for cand in reversed(candidates):
            try:
                return json.loads(cand)
            except ValueError:
                continue
        return None

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
