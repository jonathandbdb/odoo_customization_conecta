# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Referencia XML de la plantilla de correo utilizada para el aviso
MAIL_TEMPLATE_XMLID = "helpdesk_ticket_creation_notify.mail_template_ticket_creation_company"
# Referencia XML del grupo cuyos usuarios reciben el aviso de nuevo ticket
NOTIFY_GROUP_XMLID = "helpdesk_ticket_creation_notify.group_helpdesk_ticket_creation_notify"


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    @api.model_create_multi
    def create(self, vals_list):
        # Crear los registros usando el comportamiento estándar
        tickets = super().create(vals_list)
        # Enviar notificación por cada ticket creado
        for ticket in tickets:
            ticket._notify_company_on_ticket_creation()
        return tickets

    def _get_ticket_creation_notify_emails(self):
        """Devuelve la lista de emails destino para el aviso de creación.

        Incluye el email de la compañía y los emails de los usuarios que
        pertenecen al grupo definido por ``NOTIFY_GROUP_XMLID``.
        """
        self.ensure_one()
        emails = []
        # Email de la compañía del ticket (o de la compañía actual como fallback)
        company_email = self.company_id.email or self.env.company.email
        if company_email:
            emails.append(company_email)
        # Emails de los usuarios del grupo de notificación
        group = self.env.ref(NOTIFY_GROUP_XMLID, raise_if_not_found=False)
        if group:
            # Usar sudo para poder leer usuarios aunque el creador no tenga permisos
            for user in group.sudo().users:
                user_email = user.email or user.partner_id.email
                if user_email:
                    emails.append(user_email)
        # Deduplicar preservando orden y normalizando a minúsculas
        seen = set()
        unique_emails = []
        for addr in emails:
            key = addr.strip().lower()
            if key and key not in seen:
                seen.add(key)
                unique_emails.append(addr.strip())
        return unique_emails

    def _notify_company_on_ticket_creation(self):
        """Envía un correo a la compañía y a los usuarios configurados al crear un ticket."""
        self.ensure_one()
        # Recolectar destinatarios (compañía + usuarios del grupo)
        recipients = self._get_ticket_creation_notify_emails()
        if not recipients:
            _logger.warning(
                "No se envió aviso de ticket %s: no hay destinatarios configurados "
                "(ni email de compañía ni usuarios en el grupo de notificación).",
                self.display_name,
            )
            return
        # Obtener la plantilla de correo
        template = self.env.ref(MAIL_TEMPLATE_XMLID, raise_if_not_found=False)
        if not template:
            _logger.warning(
                "No se encontró la plantilla %s para el aviso de ticket %s.",
                MAIL_TEMPLATE_XMLID, self.display_name,
            )
            return
        # Enviar correo usando la plantilla. force_send=True para envío inmediato.
        email_to = ",".join(recipients)
        try:
            template.with_context(
                ticket_notify_email_to=email_to,
            ).send_mail(self.id, force_send=True, raise_exception=False)
        except Exception as error:
            # No romper la creación si el envío falla; queda registro en el log
            _logger.exception(
                "Error al enviar notificación de creación de ticket %s: %s",
                self.display_name, error,
            )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
