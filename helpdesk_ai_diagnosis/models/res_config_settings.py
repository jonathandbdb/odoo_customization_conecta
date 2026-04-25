# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Parámetros globales del flujo de diagnóstico IA
    ai_diagnosis_enabled = fields.Boolean(
        string="Enable AI Diagnosis",
        config_parameter="ai_diagnosis.enabled",
    )
    ai_diagnosis_gateway_url = fields.Char(
        string="Gateway URL",
        config_parameter="ai_diagnosis.gateway_url",
        help="URL completa del endpoint del gateway, ej: "
             "http://conecta-ai-gateway:8080/process-ticket",
    )
    ai_diagnosis_webhook_secret = fields.Char(
        string="Webhook HMAC Secret",
        config_parameter="ai_diagnosis.webhook_secret",
        help="Secret compartido para firmar el payload (HMAC-SHA256). "
             "Debe coincidir con WEBHOOK_SECRET del gateway.",
    )
    ai_diagnosis_callback_secret = fields.Char(
        string="Callback HMAC Secret",
        config_parameter="ai_diagnosis.callback_secret",
        help="Secret usado por el gateway para firmar las respuestas "
             "que postea al endpoint /ai_diagnosis/callback de Odoo.",
    )
    ai_diagnosis_timeout = fields.Integer(
        string="Webhook Timeout (s)",
        config_parameter="ai_diagnosis.timeout",
        default=15,
        help="Timeout para el POST al gateway (no para la corrida del agente).",
    )
    ai_diagnosis_odoo_base_url = fields.Char(
        string="Odoo Base URL",
        config_parameter="ai_diagnosis.odoo_base_url",
        help="URL pública de Odoo, accesible desde el gateway, para "
             "construir links al ticket y recibir el callback.",
    )
    ai_diagnosis_post_reply_as_note = fields.Boolean(
        string="Post Agent Reply as Internal Note",
        config_parameter="ai_diagnosis.post_reply_as_note",
        default=True,
    )
    ai_diagnosis_trigger_tag_id = fields.Many2one(
        comodel_name="helpdesk.ticket.tag",
        string="Trigger Tag",
        config_parameter="ai_diagnosis.trigger_tag_id",
        help="Etiqueta cuya presencia dispara el diagnóstico IA. "
             "Si no se define, todos los tickets de proyectos con IA "
             "habilitada disparan el flujo.",
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
