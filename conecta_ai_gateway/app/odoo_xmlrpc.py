# -*- coding: utf-8 -*-
"""Cliente XMLRPC liviano hacia Odoo.

Se usa para que el gateway exponga endpoints derivados de datos en Odoo
(p. ej. lista de clientes con soporte contratado) sin que el consumidor
externo (Hermes) tenga que hablar XMLRPC ni conocer credenciales.
"""
from __future__ import annotations

import logging
import xmlrpc.client
from functools import lru_cache
from typing import Any, Iterable, Optional

from .config import Settings

logger = logging.getLogger(__name__)


class OdooXmlrpcError(RuntimeError):
    """Error genérico de comunicación XMLRPC con Odoo."""


class OdooXmlrpcClient:
    """Wrapper mínimo sobre xmlrpc.client para search_read y execute_kw."""

    def __init__(self, url: str, db: str, login: str, password: str, timeout: int = 30):
        self.url = url.rstrip("/")
        self.db = db
        self.login = login
        self.password = password
        self.timeout = timeout
        self._uid: Optional[int] = None

    @property
    def common(self) -> xmlrpc.client.ServerProxy:
        # Comentario en español: endpoint /xmlrpc/2/common para autenticación
        return xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)

    @property
    def models(self) -> xmlrpc.client.ServerProxy:
        # Comentario en español: endpoint /xmlrpc/2/object para llamadas a modelos
        return xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)

    def authenticate(self) -> int:
        if self._uid is not None:
            return self._uid
        try:
            uid = self.common.authenticate(self.db, self.login, self.password, {})
        except Exception as err:  # noqa: BLE001
            raise OdooXmlrpcError(f"XMLRPC authenticate failed: {err}") from err
        if not uid:
            raise OdooXmlrpcError("Invalid Odoo credentials (uid=False)")
        self._uid = int(uid)
        return self._uid

    def execute_kw(
        self,
        model: str,
        method: str,
        args: Iterable[Any],
        kwargs: Optional[dict] = None,
    ) -> Any:
        uid = self.authenticate()
        try:
            return self.models.execute_kw(
                self.db, uid, self.password, model, method, list(args), kwargs or {}
            )
        except xmlrpc.client.Fault as err:
            raise OdooXmlrpcError(
                f"XMLRPC fault calling {model}.{method}: {err.faultString}"
            ) from err
        except Exception as err:  # noqa: BLE001
            raise OdooXmlrpcError(f"XMLRPC error on {model}.{method}: {err}") from err

    def search_read(
        self,
        model: str,
        domain: list,
        fields: list,
        limit: Optional[int] = None,
        offset: int = 0,
        order: Optional[str] = None,
    ) -> list:
        kwargs: dict = {"fields": fields, "offset": offset}
        if limit is not None:
            kwargs["limit"] = limit
        if order:
            kwargs["order"] = order
        return self.execute_kw(model, "search_read", [domain], kwargs)


@lru_cache(maxsize=1)
def get_odoo_client(settings: Settings) -> OdooXmlrpcClient:
    return OdooXmlrpcClient(
        url=settings.odoo_url,
        db=settings.odoo_db,
        login=settings.odoo_login,
        password=settings.odoo_password,
        timeout=settings.odoo_request_timeout,
    )

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
