# Conecta AI Gateway

Gateway FastAPI que recibe webhooks del módulo Odoo `helpdesk_ai_diagnosis`,
ejecuta GitHub Copilot CLI en modo agente con allowlist de herramientas
read-only, y devuelve el resultado al ticket vía callback firmado.

## Arquitectura

```
Odoo (helpdesk_ai_diagnosis)
   │  POST firmado HMAC-SHA256 → /process-ticket
   ▼
conecta-ai-gateway (FastAPI)
   │  subprocess: copilot -p "<prompt>" --allow-tool ...
   ▼
GitHub Copilot CLI agéntico
   │  ssh -i ~/.ssh/<key> user@cliente '<comando read-only>'
   ▼
Servidor del CLIENTE (logs, docker, psql -c "SELECT ...")
   │
   ▼  parse <RESULT>{...}</RESULT>
Odoo callback firmado (POST /ai_diagnosis/callback)
   │
   ▼
Nota interna en el chatter del ticket
```

## Setup en el host de Odoo

1. **Build de la imagen y arranque:**
   ```bash
   cd conecta_ai_gateway
   cp .env.example .env  # editar con secrets reales
   mkdir -p gateway-data/{ssh,copilot,runs}
   docker compose -f docker-compose.gateway.yml build
   docker compose -f docker-compose.gateway.yml up -d
   ```
2. **Inyectar claves SSH del cliente:**
   ```bash
   cp ~/.ssh/id_rsa_conecta gateway-data/ssh/id_rsa_conecta
   chmod 600 gateway-data/ssh/id_rsa_conecta
   # known_hosts opcional pero recomendado:
   ssh-keyscan -p 22 <ip_cliente> >> gateway-data/ssh/known_hosts
   ```
3. **Autenticar la CLI de Copilot (una sola vez por host):**
   ```bash
   docker exec -it conecta-ai-gateway copilot auth login
   # seguir el device flow; el token queda persistido en gateway-data/copilot/
   ```
4. **Configurar Odoo** en *Ajustes → AI Diagnosis*:
   - Gateway URL: `http://127.0.0.1:8080/process-ticket` (si Odoo corre en
     el mismo host fuera de la red docker del gateway, usar el puerto
     loopback expuesto).
   - Webhook HMAC Secret: el mismo `WEBHOOK_SECRET` del `.env`.
   - Callback HMAC Secret: el mismo `CALLBACK_SECRET` del `.env`.
   - Odoo Base URL: URL pública/interna alcanzable desde el contenedor del
     gateway hacia Odoo.

## Seguridad — V1 read-only

- El agente corre con **allowlist** de tools (`shell(ssh)`, `shell(grep)`,
  `shell(docker)`, etc.). **No** se usa `--allow-all-tools`.
- Las reglas duras viven en `AGENTS.md` y se copian al workdir de cada run.
- Webhook entrante validado por HMAC-SHA256 + timestamp (anti-replay 5 min).
- Callback a Odoo firmado igual y atado a un token de un solo uso por
  ticket (`ai_diagnosis_request_token`).
- Sin `sudo` por defecto. La clave SSH del cliente es la única credencial
  presente en el contenedor; vive en volumen read-only.
- Puerto expuesto solo a `127.0.0.1` para evitar exposición pública.

## V2 (futura) — auto-remediación con aprobación

Cambios mínimos previstos cuando se quiera habilitar fixes automáticos:
- Añadir `pending_human_approval` como estado intermedio en el ticket.
- Permitir comandos de mutación solo si el callback trae `requires_approval=true`
  y un usuario con grupo `ai_diagnosis_remediation` aprueba desde el form.
- El gateway re-ejecuta el agente con un prompt distinto que aplique el
  fix aprobado.

## Smoke test local

```bash
# generar firma manual y disparar el endpoint
python - <<'PY'
import json, hmac, hashlib, time, urllib.request
secret = b"change-me-please-32+chars-random"
body = json.dumps({
  "ticket_id": 1, "ticket_number": "T0001", "ticket_name": "test",
  "ticket_url": "http://localhost", "priority": "1", "category": "",
  "team": "", "requester": "tester", "description": "smoke",
  "client": {"project_id": 1, "project_name": "demo",
             "ssh_host": "127.0.0.1", "ssh_user": "root",
             "ssh_port": 22, "credential_ref": "", "notes": ""},
  "callback": {"url": "http://localhost:8069/ai_diagnosis/callback",
               "ticket_id": 1, "token": "x"},
  "issued_at": int(time.time()),
}).encode()
sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
req = urllib.request.Request(
  "http://127.0.0.1:8080/process-ticket", data=body,
  headers={"Content-Type":"application/json",
           "X-Conecta-Signature": f"sha256={sig}",
           "X-Conecta-Timestamp": str(int(time.time()))})
print(urllib.request.urlopen(req).read())
PY
```
