# -*- coding: utf-8 -*-
{
    "name": "helpdesk_portal_partner_project",
    "version": "18.0.1.0.0",
    "summary": "Asigna automáticamente un proyecto al ticket según el cliente del portal",
    "description": """
Permite asociar un proyecto por defecto a cada contacto (res.partner).
Cuando un cliente del portal (o cualquier usuario) crea un ticket en Helpdesk,
el ticket se asigna automáticamente al proyecto configurado en el partner.

Reglas de resolución:
- Si el partner del ticket tiene proyecto configurado → se usa ese.
- Si no tiene pero su partner padre (compañía) sí → se usa el del padre.
- Si ninguno tiene → el ticket se crea sin proyecto (no bloquea).

El campo se muestra sólo en el backend, no en el formulario del portal.
    """,
    "category": "Helpdesk",
    "author": "NEXIT",
    "website": "https://www.nexit.com.uy",
    "license": "OPL-1",
    "depends": [
        "helpdesk_mgmt",
        "helpdesk_mgmt_project",
    ],
    "data": [
        "views/res_partner_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
