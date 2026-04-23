# -*- coding: utf-8 -*-
{
    "name": "openclaw_helpdesk_integration",
    "version": "18.0.1.2.0",
    "summary": "Integración Odoo <-> Openclaw (diagnóstico IA de tickets)",
    "description": """
Al crear un ticket de Helpdesk, invoca directamente el agente IA Openclaw
(CLI ``openclaw agent``) vía SSH o ``docker exec`` y, si corresponde, publica
la primera respuesta del agente como nota interna en el ticket.

Incluye:

- Información del ticket (número, cliente, proyecto, solicitante, etc.) en el
  prompt del agente.
- Datos de conexión SSH al servidor del cliente (host/user/port/notas).
- Instrucción explícita de *solo lectura* al agente y que publique el
  diagnóstico como nota interna vía API Odoo (``message_post`` con subtype
  ``mail.mt_note``).
- Campos de conexión en ``project.project``, botón manual "Request AI
  Diagnosis" en la ficha del ticket y parámetros de configuración en Ajustes.
    """,
    "category": "Helpdesk",
    "author": "NEXIT",
    "website": "https://www.nexit.com.uy",
    "license": "OPL-1",
    "depends": [
        "helpdesk_mgmt",
        "helpdesk_mgmt_project",
        "project",
    ],
    "data": [
        "security/openclaw_security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter_data.xml",
        "data/ir_cron_data.xml",
        "views/project_project_views.xml",
        "views/helpdesk_ticket_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
