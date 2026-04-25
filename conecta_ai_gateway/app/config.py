# -*- coding: utf-8 -*-
"""Configuración del gateway cargada desde variables de entorno."""
from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Webhook entrante (Odoo → gateway) ---
    webhook_secret: str = Field(..., description="HMAC secret para firmar payloads de Odoo.")
    callback_secret: str = Field(..., description="HMAC secret para firmar el callback al Odoo.")
    timestamp_tolerance: int = 300  # segundos

    # --- Copilot CLI ---
    copilot_bin: str = "copilot"
    copilot_model: str = "claude-sonnet-4.5"
    copilot_extra_args: str = ""  # tipo: "--allow-tool 'shell(grep)' --allow-tool 'shell(ssh)'"
    # En V1 NO usamos --allow-all-tools. Allowlist de tools (read-only):
    copilot_allow_tools: List[str] = [
        "shell(ssh)",
        "shell(grep)",
        "shell(cat)",
        "shell(tail)",
        "shell(head)",
        "shell(awk)",
        "shell(sed)",
        "shell(less)",
        "shell(docker)",  # para `docker logs`, `docker ps`, `docker exec ... psql -c "SELECT..."`
        "shell(systemctl)",  # solo `systemctl status` está permitido por convención (ver AGENTS.md)
        "shell(df)",
        "shell(free)",
        "shell(uptime)",
        "shell(journalctl)",
        "shell(ps)",
    ]
    copilot_timeout_seconds: int = 600
    copilot_workdir: str = "/tmp/copilot-runs"

    # --- SSH ---
    ssh_keys_dir: str = "/home/gateway/.ssh"
    ssh_default_key_name: str = "id_rsa_conecta"
    ssh_known_hosts_file: str = "/home/gateway/.ssh/known_hosts"

    # --- Odoo callback ---
    odoo_request_timeout: int = 30

    # --- Server ---
    log_level: str = "info"

    @property
    def workdir_path(self) -> Path:
        p = Path(self.copilot_workdir)
        p.mkdir(parents=True, exist_ok=True)
        return p


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
