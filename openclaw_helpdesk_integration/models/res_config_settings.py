# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Parámetros globales de la integración Openclaw
    openclaw_enabled = fields.Boolean(
        string="Enable Openclaw Integration",
        config_parameter="openclaw.enabled",
    )
    openclaw_exec_mode = fields.Selection(
        [("ssh", "SSH (remote)"), ("docker", "Docker (local)")],
        string="Exec Mode",
        config_parameter="openclaw.exec_mode",
        default="ssh",
        help="Cómo invocar el CLI openclaw: por SSH a un host remoto o docker exec local.",
    )
    openclaw_ssh_host = fields.Char(
        string="SSH Host",
        config_parameter="openclaw.ssh_host",
        help="Host donde corre el container openclaw_gateway (modo SSH).",
    )
    openclaw_ssh_port = fields.Integer(
        string="SSH Port",
        config_parameter="openclaw.ssh_port",
        default=22,
    )
    openclaw_ssh_user = fields.Char(
        string="SSH User",
        config_parameter="openclaw.ssh_user",
        default="root",
    )
    openclaw_ssh_key_path = fields.Char(
        string="SSH Key Path",
        config_parameter="openclaw.ssh_key_path",
        help="Ruta absoluta a la clave privada SSH dentro del container Odoo.",
    )
    openclaw_container_name = fields.Char(
        string="Openclaw Container Name",
        config_parameter="openclaw.container_name",
        default="openclaw_gateway",
    )
    openclaw_agent_id = fields.Char(
        string="Openclaw Agent Id",
        config_parameter="openclaw.agent_id",
        default="main",
    )
    openclaw_agent_timeout = fields.Integer(
        string="Agent Timeout (s)",
        config_parameter="openclaw.agent_timeout",
        default=600,
    )
    openclaw_odoo_base_url = fields.Char(
        string="Odoo Base URL",
        config_parameter="openclaw.odoo_base_url",
        help="Base URL de Odoo accesible por el agente para publicar notas. Ej: https://odoo.conecta.sh",
    )
    openclaw_post_reply_as_note = fields.Boolean(
        string="Post Agent Reply as Internal Note",
        config_parameter="openclaw.post_reply_as_note",
        default=True,
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
