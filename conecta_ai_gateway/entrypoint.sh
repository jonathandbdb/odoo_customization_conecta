#!/usr/bin/env bash
# Comentario en español: si COPILOT_TOKEN o GITHUB_TOKEN está presente, se
# usa como token de la CLI de Copilot. Si no, se asume que el volumen
# ~/.copilot ya tiene auth previa hecha con `copilot auth login`.
set -euo pipefail

if [[ -n "${COPILOT_TOKEN:-}" ]]; then
    mkdir -p "${HOME}/.copilot"
    # El layout exacto de auth puede variar entre versiones; persistimos en var
    # de entorno (la CLI también la lee) y en archivo para upgrades futuros.
    echo "${COPILOT_TOKEN}" > "${HOME}/.copilot/token"
    chmod 600 "${HOME}/.copilot/token"
fi

# Verificar disponibilidad del binario sin abortar (logueamos versión).
copilot --version 2>&1 | head -1 || echo "WARN: copilot CLI no responde a --version"

exec "$@"
