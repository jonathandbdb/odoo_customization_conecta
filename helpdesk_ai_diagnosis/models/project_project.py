# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    # Datos de conexión SSH al servidor del cliente.
    # No se guardan claves privadas: el gateway resuelve la clave a partir
    # del identificador opaco `client_ai_credential_ref`.
    client_ssh_host = fields.Char(
        string="Client SSH Host",
        help="IP o hostname del servidor del cliente al que se conecta el agente IA.",
        groups="helpdesk_ai_diagnosis.group_ai_diagnosis_manager",
    )
    client_ssh_port = fields.Integer(
        string="Client SSH Port",
        default=22,
        groups="helpdesk_ai_diagnosis.group_ai_diagnosis_manager",
    )
    client_ssh_user = fields.Char(
        string="Client SSH User",
        default="root",
        groups="helpdesk_ai_diagnosis.group_ai_diagnosis_manager",
    )
    client_ai_credential_ref = fields.Char(
        string="Gateway Credential Reference",
        help="Identificador opaco que el gateway usa para resolver la clave "
             "SSH del cliente. La clave privada NUNCA se guarda en Odoo.",
        groups="helpdesk_ai_diagnosis.group_ai_diagnosis_manager",
    )
    client_ssh_notes = fields.Html(
        string="Client Connection Notes",
        help="Contexto pasado al agente IA (stack, paths de logs, versión "
             "de Odoo, contenedores, etc.).",
        groups="helpdesk_ai_diagnosis.group_ai_diagnosis_manager",
    )
    ai_diagnosis_enabled = fields.Boolean(
        string="Enable AI Diagnosis",
        default=True,
        help="Si está habilitado, los tickets de este proyecto pueden "
             "disparar el diagnóstico IA automático.",
        groups="helpdesk_ai_diagnosis.group_ai_diagnosis_manager",
    )
    # Nivel de soporte contratado por el cliente. Vacío = sin soporte.
    # Lo consume el endpoint /support-clients del gateway para que Hermes
    # sepa a qué clientes puede atender vía SSH.
    support_level = fields.Selection(
        selection=[
            ("standard", "Standard"),
            ("medium", "Medium"),
            ("full", "Full"),
        ],
        string="Support Level",
        help="Contracted support level. Empty means the client has no support contract.",
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
