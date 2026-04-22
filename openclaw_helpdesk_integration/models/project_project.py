# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    # Datos de conexión SSH al servidor del cliente (usados por el agente IA)
    client_ssh_host = fields.Char(
        string="Client SSH Host",
        help="IP or hostname of the client server where the AI agent will connect via SSH.",
        groups="openclaw_helpdesk_integration.group_openclaw_connection_manager",
    )
    client_ssh_port = fields.Integer(
        string="Client SSH Port",
        default=22,
        groups="openclaw_helpdesk_integration.group_openclaw_connection_manager",
    )
    client_ssh_user = fields.Char(
        string="Client SSH User",
        default="root",
        groups="openclaw_helpdesk_integration.group_openclaw_connection_manager",
    )
    client_ssh_notes = fields.Html(
        string="Client Connection Notes",
        help="Context passed to the AI agent (stack, log paths, Odoo version, etc.).",
        groups="openclaw_helpdesk_integration.group_openclaw_connection_manager",
    )
    ai_diagnosis_enabled = fields.Boolean(
        string="Enable AI Diagnosis",
        default=True,
        help="If enabled, tickets on this project will trigger an automatic AI diagnosis.",
        groups="openclaw_helpdesk_integration.group_openclaw_connection_manager",
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
