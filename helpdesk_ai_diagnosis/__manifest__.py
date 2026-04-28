# -*- coding: utf-8 -*-
{
    "name": "helpdesk_ai_diagnosis",
    "version": "18.0.1.1.0",
    "summary": "Diagnóstico IA de tickets vía webhook a gateway FastAPI + GitHub Copilot CLI",
    "description": """
Reemplaza la integración con Openclaw por un flujo basado en webhook
hacia un gateway FastAPI que invoca el agente de GitHub Copilot CLI
en modo de diagnóstico (solo lectura) sobre el servidor del cliente.

Flujo:
  1) Se crea un ticket de Helpdesk (o se aplica la etiqueta
     "Investigación-IA"). El módulo lo marca como pending y lo
     procesa en background vía cron.
  2) Se envía un POST firmado (HMAC-SHA256) al gateway local
     ``conecta-ai-gateway`` con el contexto del ticket y el
     identificador del proyecto cliente.
  3) El gateway dispara el agente Copilot CLI con tools en
     allowlist (SSH lectura, docker logs, grep) y devuelve la
     respuesta como nota interna en el ticket usando el
     callback firmado de este módulo.

Sin almacenamiento de credenciales sensibles en la base de datos:
las claves SSH viven solo en el gateway. El módulo guarda
host/user/puerto del cliente y un identificador opaco que el
gateway resuelve contra su propio almacenamiento de claves.
    """,
    "category": "Helpdesk",
    "author": "NEXIT",
    "website": "https://www.nexit.com.uy",
    "license": "OPL-1",
    "depends": [
        "helpdesk_mgmt",
        "helpdesk_mgmt_project",
        "project",
        "mail",
    ],
    "external_dependencies": {
        "python": ["requests"],
    },
    "data": [
        "security/ai_diagnosis_security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter_data.xml",
        "data/ir_cron_data.xml",
        "data/helpdesk_tag_data.xml",
        "views/project_project_views.xml",
        "views/helpdesk_ticket_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
