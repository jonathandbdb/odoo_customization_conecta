# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import logging
import re
import secrets
import time

import requests
from markupsafe import Markup
from odoo.exceptions import UserError

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Parámetros de sistema
ICP_ENABLED = "ai_diagnosis.enabled"
ICP_GATEWAY_URL = "ai_diagnosis.gateway_url"
ICP_WEBHOOK_SECRET = "ai_diagnosis.webhook_secret"
ICP_TIMEOUT = "ai_diagnosis.timeout"
ICP_ODOO_BASE_URL = "ai_diagnosis.odoo_base_url"
ICP_TRIGGER_TAG = "ai_diagnosis.trigger_tag_id"

# Truncado de descripción para evitar prompts gigantes
DESCRIPTION_TRUNCATE = 4000


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    # Estado del diagnóstico IA (con prefijo ai_dx_ para evitar colisión con
    # el módulo legacy openclaw_helpdesk_integration mientras coexisten).
    ai_dx_state = fields.Selection(
        [
            ("not_applicable", "Not Applicable"),
            ("pending", "Pending"),
            ("dispatched", "Dispatched"),
            ("answered", "Answered"),
            ("error", "Error"),
        ],
        string="AI Diagnosis State",
        default="not_applicable",
        readonly=True,
        copy=False,
    )
    ai_dx_last_dispatched_at = fields.Datetime(
        string="AI Diagnosis Last Dispatched",
        readonly=True,
        copy=False,
    )
    ai_dx_last_error = fields.Text(
        string="AI Diagnosis Last Error",
        readonly=True,
        copy=False,
    )
    ai_dx_run_id = fields.Char(
        string="Gateway Run Id",
        readonly=True,
        copy=False,
        help="Identificador opaco asignado por el gateway para esta corrida.",
    )
    ai_dx_request_token = fields.Char(
        string="Callback Token",
        readonly=True,
        copy=False,
        help="Token de un solo uso que el gateway debe presentar al postear "
             "el resultado por callback.",
    )

    # ---------------------------------------------------------------- create
    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        to_queue = tickets.filtered(lambda t: t._ai_diagnosis_is_applicable())
        if to_queue:
            to_queue.sudo().write({"ai_dx_state": "pending"})
            cron = self.env.ref(
                "helpdesk_ai_diagnosis.ir_cron_ai_diagnosis_dispatch",
                raise_if_not_found=False,
            )
            if cron:
                cron.sudo()._trigger()
        return tickets

    def write(self, vals):
        # Comentario en español: si se aplica la etiqueta de trigger después
        # de la creación, también encolar.
        res = super().write(vals)
        if "tag_ids" in vals:
            to_queue = self.filtered(
                lambda t: t.ai_dx_state in ("not_applicable", False)
                and t._ai_diagnosis_is_applicable()
            )
            if to_queue:
                to_queue.sudo().write({"ai_dx_state": "pending"})
                cron = self.env.ref(
                    "helpdesk_ai_diagnosis.ir_cron_ai_diagnosis_dispatch",
                    raise_if_not_found=False,
                )
                if cron:
                    cron.sudo()._trigger()
        return res

    # --------------------------------------------------------------- helpers
    def _ai_diagnosis_is_applicable(self):
        """Retorna True si el ticket debe disparar el flujo IA."""
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        if icp.get_param(ICP_ENABLED, "False").lower() not in ("1", "true", "t", "yes"):
            return False
        if not self.project_id:
            return False
        project = self.project_id.sudo()
        if not project.ai_diagnosis_enabled:
            return False
        if not project.client_ssh_host:
            return False
        # Tag-based trigger opcional
        trigger_tag_id = icp.get_param(ICP_TRIGGER_TAG)
        if trigger_tag_id:
            try:
                tag_id = int(trigger_tag_id)
            except (TypeError, ValueError):
                tag_id = 0
            if tag_id and tag_id not in self.tag_ids.ids:
                return False
        return True

    def _ai_diagnosis_ticket_url(self):
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        base = icp.get_param(ICP_ODOO_BASE_URL) or icp.get_param("web.base.url") or ""
        base = base.rstrip("/")
        return f"{base}/odoo/helpdesk/{self.team_id.id}/{self.id}" if self.team_id \
            else f"{base}/web#id={self.id}&model=helpdesk.ticket&view_type=form"

    def _ai_diagnosis_build_payload(self):
        """Construye el payload JSON enviado al gateway."""
        self.ensure_one()
        project = self.project_id.sudo()
        description = re.sub(r"<[^>]+>", " ", (self.description or "")).strip()
        if len(description) > DESCRIPTION_TRUNCATE:
            description = description[:DESCRIPTION_TRUNCATE] + "…"
        ssh_notes = re.sub(r"<[^>]+>", " ", (project.client_ssh_notes or "")).strip()
        # Token de callback de un solo uso
        token = secrets.token_urlsafe(32)
        self.sudo().write({"ai_dx_request_token": token})
        icp = self.env["ir.config_parameter"].sudo()
        base = icp.get_param(ICP_ODOO_BASE_URL) or icp.get_param("web.base.url") or ""
        return {
            "ticket_id": self.id,
            "ticket_number": self.number or "",
            "ticket_name": self.name or "",
            "ticket_url": self._ai_diagnosis_ticket_url(),
            "priority": self.priority or "",
            "category": self.category_id.display_name or "",
            "team": self.team_id.display_name or "",
            "requester": (
                self.partner_id.display_name
                or self.partner_name
                or self.partner_email
                or ""
            ),
            "description": description,
            "client": {
                "project_id": project.id,
                "project_name": project.display_name,
                "ssh_host": project.client_ssh_host,
                "ssh_user": project.client_ssh_user or "root",
                "ssh_port": project.client_ssh_port or 22,
                "credential_ref": project.client_ai_credential_ref or "",
                "notes": ssh_notes,
            },
            "callback": {
                "url": f"{base.rstrip('/')}/ai_diagnosis/callback",
                "ticket_id": self.id,
                "token": token,
            },
            "issued_at": int(time.time()),
        }

    def _ai_diagnosis_sign(self, secret, body_bytes):
        """Calcula HMAC-SHA256 del body con el secret compartido."""
        return hmac.new(
            secret.encode("utf-8"), body_bytes, hashlib.sha256
        ).hexdigest()

    # ------------------------------------------------------------- dispatch
    @api.model
    def _cron_ai_diagnosis_dispatch_pending(self, batch_size=10):
        """Procesa tickets en estado 'pending' enviándolos al gateway."""
        pending = self.search(
            [("ai_dx_state", "=", "pending")],
            limit=batch_size,
            order="id asc",
        )
        if not pending:
            return
        for ticket in pending:
            try:
                with self.env.cr.savepoint():
                    ticket._ai_diagnosis_dispatch()
            except Exception as error:  # noqa: BLE001
                _logger.exception(
                    "AI Diagnosis dispatch failed for ticket %s: %s",
                    ticket.display_name, error,
                )
                ticket.sudo().write({
                    "ai_dx_state": "error",
                    "ai_dx_last_error": str(error)[:2000],
                    "ai_dx_last_dispatched_at": fields.Datetime.now(),
                })
        remaining = self.search_count([("ai_dx_state", "=", "pending")])
        if remaining:
            cron = self.env.ref(
                "helpdesk_ai_diagnosis.ir_cron_ai_diagnosis_dispatch",
                raise_if_not_found=False,
            )
            if cron:
                cron.sudo()._trigger()

    def action_ai_diagnosis_request(self):
        """Botón manual: forzar el envío al gateway."""
        for ticket in self:
            if not ticket.project_id:
                raise UserError(_("The ticket has no project assigned."))
            if not ticket.project_id.sudo().client_ssh_host:
                raise UserError(_(
                    "The project %s has no SSH host configured."
                ) % ticket.project_id.display_name)
            ticket.sudo().write({"ai_dx_state": "pending"})
            ticket._ai_diagnosis_dispatch()
        return True

    def _ai_diagnosis_dispatch(self):
        """POST firmado al gateway."""
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        gateway_url = (icp.get_param(ICP_GATEWAY_URL) or "").strip()
        secret = (icp.get_param(ICP_WEBHOOK_SECRET) or "").strip()
        timeout = int(icp.get_param(ICP_TIMEOUT) or 15)
        if not gateway_url or not secret:
            self.sudo().write({
                "ai_dx_state": "error",
                "ai_dx_last_error": "Gateway URL or webhook secret not configured.",
                "ai_dx_last_dispatched_at": fields.Datetime.now(),
            })
            _logger.warning("AI Diagnosis: configuración incompleta (gateway/secret).")
            return

        payload = self._ai_diagnosis_build_payload()
        body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = self._ai_diagnosis_sign(secret, body_bytes)
        headers = {
            "Content-Type": "application/json",
            "X-Conecta-Signature": f"sha256={signature}",
            "X-Conecta-Timestamp": str(payload["issued_at"]),
        }
        _logger.info(
            "AI Diagnosis: enviando ticket %s al gateway %s.",
            self.display_name, gateway_url,
        )
        try:
            response = requests.post(
                gateway_url, data=body_bytes, headers=headers, timeout=timeout,
            )
        except requests.RequestException as err:
            self.sudo().write({
                "ai_dx_state": "error",
                "ai_dx_last_error": f"Gateway unreachable: {err}",
                "ai_dx_last_dispatched_at": fields.Datetime.now(),
            })
            _logger.warning("AI Diagnosis: gateway inalcanzable: %s", err)
            return
        if response.status_code >= 300:
            self.sudo().write({
                "ai_dx_state": "error",
                "ai_dx_last_error": (
                    f"Gateway returned {response.status_code}: {response.text[:500]}"
                ),
                "ai_dx_last_dispatched_at": fields.Datetime.now(),
            })
            _logger.warning(
                "AI Diagnosis: gateway HTTP %s: %s",
                response.status_code, response.text[:500],
            )
            return
        try:
            data = response.json()
        except ValueError:
            data = {}
        self.sudo().write({
            "ai_dx_state": "dispatched",
            "ai_dx_last_error": False,
            "ai_dx_last_dispatched_at": fields.Datetime.now(),
            "ai_dx_run_id": (data.get("run_id") or "")[:64] if isinstance(data, dict) else "",
        })
        _logger.info(
            "AI Diagnosis: ticket %s aceptado por gateway (run_id=%s).",
            self.display_name, (data.get("run_id") if isinstance(data, dict) else None),
        )

    # ----------------------------------------------------------- callback
    def _ai_diagnosis_apply_result(self, payload):
        """Aplica el resultado recibido por callback (ya autenticado)."""
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        post_note = (icp.get_param("ai_diagnosis.post_reply_as_note", "True") or "").lower() in (
            "1", "true", "t", "yes",
        )
        status = (payload.get("status") or "").strip().lower()
        if status == "error":
            self.sudo().write({
                "ai_dx_state": "error",
                "ai_dx_last_error": (payload.get("error") or "")[:2000],
            })
            return
        # Estructura esperada del agente: dict con error_root_cause, fix_applied, client_summary
        result = payload.get("result") or {}
        client_summary = (result.get("client_summary") or "").strip()
        root_cause = (result.get("error_root_cause") or "").strip()
        fix_applied = (result.get("fix_applied") or "").strip()
        run_id = (payload.get("run_id") or "")[:64]
        self.sudo().write({
            "ai_dx_state": "answered",
            "ai_dx_last_error": False,
            "ai_dx_run_id": run_id or self.ai_dx_run_id,
            "ai_dx_request_token": False,  # invalidar token usado
        })
        if post_note and (client_summary or root_cause):
            self._ai_diagnosis_post_note(client_summary, root_cause, fix_applied)

    def _ai_diagnosis_post_note(self, summary, root_cause, fix_applied):
        """Publica el diagnóstico como nota interna en el chatter."""
        self.ensure_one()

        def _to_html(text):
            text = (text or "").strip()
            if not text:
                return ""
            if re.search(r"<(p|ul|ol|li|strong|em|code|pre|br|div|span|h[1-6])\b", text, re.IGNORECASE):
                return text
            # Markdown muy básico → HTML
            escaped = (
                text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
            )
            return "<pre>" + escaped + "</pre>"

        body = Markup(
            "<p><strong>🤖 Diagnóstico IA — gateway Conecta</strong></p>"
        )
        if summary:
            body += Markup("<h4>Resumen para el cliente</h4>")
            body += Markup(_to_html(summary))
        if root_cause:
            body += Markup("<h4>Causa raíz detectada</h4>")
            body += Markup(_to_html(root_cause))
        if fix_applied:
            body += Markup("<h4>Acciones realizadas</h4>")
            body += Markup(_to_html(fix_applied))
        self.sudo().message_post(body=body, subtype_xmlid="mail.mt_note")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
