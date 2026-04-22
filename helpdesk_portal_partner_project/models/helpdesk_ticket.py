# -*- coding: utf-8 -*-
from odoo import api, models


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    @api.model_create_multi
    def create(self, vals_list):
        # Autocompletar project_id desde el partner si no fue indicado
        for vals in vals_list:
            if vals.get("project_id"):
                continue
            partner_id = vals.get("partner_id")
            if not partner_id:
                continue
            partner = self.env["res.partner"].browse(partner_id)
            project = partner._get_helpdesk_default_project()
            if project:
                vals["project_id"] = project.id
        return super().create(vals_list)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
