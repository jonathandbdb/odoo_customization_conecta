# -*- coding: utf-8 -*-
"""Verificación HMAC del webhook entrante de Odoo."""
from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import HTTPException, Request


async def verify_signature(
    request: Request, secret: str, tolerance: int
) -> bytes:
    """Lee el body raw, valida firma HMAC y timestamp. Devuelve el body."""
    body = await request.body()
    signature_header = request.headers.get("x-conecta-signature", "")
    timestamp_header = request.headers.get("x-conecta-timestamp", "")

    try:
        ts = int(timestamp_header)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="invalid timestamp")
    if abs(int(time.time()) - ts) > tolerance:
        raise HTTPException(status_code=400, detail="timestamp out of range")

    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=").strip()
    if not provided or not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="invalid signature")
    return body


def sign_body(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
