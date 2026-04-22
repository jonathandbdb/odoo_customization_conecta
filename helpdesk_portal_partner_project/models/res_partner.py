# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Proyecto por defecto para los tickets creados por este contacto
    helpdesk_project_id = fields.Many2one(
        comodel_name="project.project",
        string="Helpdesk Default Project",
        help="Project automatically assigned to Helpdesk tickets created by this contact.",
    )

    def _get_helpdesk_default_project(self):
        """Devuelve el proyecto por defecto para tickets de este partner.

        Si el contacto tiene su propio proyecto configurado, lo devuelve.
        En caso contrario, hereda el del partner padre (compañía).
        """
        self.ensure_one()
        if self.helpdesk_project_id:
            return self.helpdesk_project_id
        if self.parent_id and self.parent_id.helpdesk_project_id:
            return self.parent_id.helpdesk_project_id
        return self.env["project.project"]

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
