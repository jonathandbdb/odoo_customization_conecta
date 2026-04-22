# -*- coding: utf-8 -*-
{
    "name": "helpdesk_ticket_creation_notify",
    "version": "18.0.1.0.0",
    "summary": "Notifica por correo a la compañía al crear un ticket de Helpdesk",
    "description": """
Módulo que envía un correo electrónico al email de la compañía cada vez que
se crea un nuevo ticket en el módulo Helpdesk (OCA - helpdesk_mgmt).

Características:
- Se dispara automáticamente al crear el ticket.
- Utiliza una plantilla de correo configurable.
- Usa el servidor de correo saliente por defecto (Gmail OAuth configurado).
- Destinatario: email de la compañía del ticket.
    """,
    "category": "Helpdesk",
    "author": "NEXIT",
    "website": "https://www.nexit.com.uy",
    "license": "OPL-1",
    "depends": [
        "mail",
        "helpdesk_mgmt",
    ],
    "data": [
        "security/helpdesk_notify_groups.xml",
        "data/mail_template_data.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
