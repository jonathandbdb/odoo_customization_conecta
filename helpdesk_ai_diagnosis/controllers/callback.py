# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import logging
import time

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Tolerancia de drift de timestamp (segundos) para mitigar replay
TIMESTAMP_TOLERANCE = 300


class AIDiagnosisCallbackController(http.Controller):
    """Endpoint público (sin sesión) que recibe el resultado del gateway.

    Está protegido por:
      - HMAC-SHA256 sobre el body con `ai_diagnosis.callback_secret`.
      - Verificación de timestamp para evitar replay.
      - Token de un solo uso (`ai_dx_request_token`) emitido al
        ticket en el dispatch y consumido al postear el resultado.
    """

    @http.route(
        "/ai_diagnosis/callback",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def callback(self, **kwargs):
        body = request.httprequest.get_data(cache=False, as_text=False) or b""
        signature_header = request.httprequest.headers.get("X-Conecta-Signature", "")
        timestamp_header = request.httprequest.headers.get("X-Conecta-Timestamp", "")

        env = request.env(user=1)  # SUPERUSER_ID; nada se hace sin token válido
        icp = env["ir.config_parameter"].sudo()
        secret = (icp.get_param("ai_diagnosis.callback_secret") or "").strip()
        if not secret:
            _logger.warning("AI Diagnosis callback: secret no configurado.")
            return _json_response({"error": "callback secret not configured"}, status=503)

        # Verificación de timestamp (anti-replay)
        try:
            ts = int(timestamp_header)
        except (TypeError, ValueError):
            return _json_response({"error": "invalid timestamp"}, status=400)
        if abs(int(time.time()) - ts) > TIMESTAMP_TOLERANCE:
            return _json_response({"error": "timestamp out of range"}, status=400)

        # Verificación HMAC
        expected_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        provided_sig = signature_header.removeprefix("sha256=").strip()
        if not hmac.compare_digest(expected_sig, provided_sig):
            _logger.warning("AI Diagnosis callback: firma inválida.")
            return _json_response({"error": "invalid signature"}, status=401)

        # Parseo del body
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, ValueError):
            return _json_response({"error": "invalid json"}, status=400)
        ticket_id = payload.get("ticket_id")
        token = payload.get("token") or ""
        if not ticket_id or not token:
            return _json_response({"error": "missing ticket_id or token"}, status=400)

        ticket = env["helpdesk.ticket"].sudo().browse(int(ticket_id)).exists()
        if not ticket:
            return _json_response({"error": "ticket not found"}, status=404)
        if not ticket.ai_dx_request_token or not hmac.compare_digest(
            ticket.ai_dx_request_token or "", token
        ):
            _logger.warning(
                "AI Diagnosis callback: token inválido o ya consumido (ticket=%s).",
                ticket_id,
            )
            return _json_response({"error": "invalid or consumed token"}, status=401)

        try:
            ticket._ai_diagnosis_apply_result(payload)
        except Exception as err:  # noqa: BLE001
            _logger.exception("AI Diagnosis callback: error aplicando resultado: %s", err)
            return _json_response({"error": "internal error"}, status=500)

        return _json_response({"ok": True}, status=200)


def _json_response(data, status=200):
    return request.make_response(
        json.dumps(data, separators=(",", ":")),
        headers=[("Content-Type", "application/json")],
        status=status,
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
