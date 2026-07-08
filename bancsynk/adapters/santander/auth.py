"""Autenticacao Santander 033 — Fase 1 read-only, sem pagamentos.

Credenciais lidas exclusivamente do .env do BancSynk, chaveadas por empresa:
    BANCSYNC_033_{COMPANY_ID}_CLIENT_ID
    BANCSYNC_033_{COMPANY_ID}_CLIENT_SECRET
    BANCSYNC_033_{COMPANY_ID}_ACCESS_TOKEN
    BANCSYNC_033_{COMPANY_ID}_REFRESH_TOKEN
    BANCSYNC_033_{COMPANY_ID}_AUTHORIZE_URL
    BANCSYNC_033_{COMPANY_ID}_AUTH_URL
    BANCSYNC_033_{COMPANY_ID}_API_BASE_URL
    BANCSYNC_033_{COMPANY_ID}_COUNTRY
    BANCSYNC_033_{COMPANY_ID}_ACCOUNTS_PATH
    BANCSYNC_033_{COMPANY_ID}_BALANCE_PATH
    BANCSYNC_033_{COMPANY_ID}_STATEMENT_PATH
"""

from __future__ import annotations

import logging
import os
from typing import Optional
from urllib.parse import urlencode

log = logging.getLogger("bancsynk.santander.auth")

BANCO_CODIGO = "033"

DEFAULT_SCOPE = "ACCLIST.READ ACCDET.READ ACCTRAN.READ"

DEFAULTS = {
    "AUTHORIZE_URL": "https://api-sandbox.santander.com/santander/external/oauth/authorize",
    "AUTH_URL": "https://api-sandbox.santander.com/santander/external/oauth/token",
    "COUNTRY": "BR",
    "SCOPE": DEFAULT_SCOPE,
}


class SantanderAuth:
    """Cliente Santander vinculado a uma empresa (multiempresa via env chaveado)."""

    def __init__(self, company_id: Optional[str] = None) -> None:
        self.company_id: Optional[str] = str(company_id) if company_id is not None else None

    # ── Leitura de configuracao ─────────────────────────────────────────────
    def _resolve_company(self) -> Optional[str]:
        if self.company_id:
            return self.company_id
        # Auto-descobre a primeira empresa com CLIENT_ID configurado.
        prefix = f"BANCSYNC_{BANCO_CODIGO}_"
        for key in os.environ:
            if key.startswith(prefix) and key.endswith("_CLIENT_ID"):
                parts = key.split("_")
                if len(parts) >= 4:
                    return parts[2]
        return None

    def get(self, campo: str, default: str = "") -> str:
        cid = self._resolve_company()
        if cid is None:
            return DEFAULTS.get(campo, default)
        key = f"BANCSYNC_{BANCO_CODIGO}_{cid}_{campo.upper()}"
        return os.environ.get(key) or DEFAULTS.get(campo, default)

    @property
    def client_id(self) -> str:
        return self.get("CLIENT_ID")

    @property
    def client_secret(self) -> str:
        return self.get("CLIENT_SECRET")

    @property
    def access_token(self) -> str:
        return self.get("ACCESS_TOKEN")

    @property
    def refresh_token(self) -> str:
        return self.get("REFRESH_TOKEN")

    @property
    def api_base_url(self) -> str:
        return self.get("API_BASE_URL")

    # ── Check nao-destrutivo ────────────────────────────────────────────────
    def check(self) -> dict:
        cid = self._resolve_company()
        base = {"banco": BANCO_CODIGO, "company_id": cid, "env": "sandbox"}
        if not self.client_id or not self.client_secret:
            return {
                **base,
                "ok": False,
                "msg": (
                    "Santander 033: CLIENT_ID/CLIENT_SECRET ausentes no .env. "
                    f"Preencha BANCSYNC_{BANCO_CODIGO}_<COMPANY_ID>_CLIENT_ID e _CLIENT_SECRET."
                ),
            }
        if not self.access_token:
            return {
                **base,
                "ok": False,
                "msg": (
                    "Santander 033: consentimento pendente — ACCESS_TOKEN ausente. "
                    "Rodar fluxo Authorization Code / Open Finance BR."
                ),
                "has_client_id": True,
                "has_secret": True,
            }
        return {
            **base,
            "ok": True,
            "msg": "Santander 033: credenciais e token presentes.",
            "has_client_id": True,
            "has_secret": True,
            "has_token": True,
        }

    # ── Authorization Code: URL de consentimento ────────────────────────────
    def build_authorize_url(
        self,
        redirect_uri: str,
        scope: Optional[str] = None,
        state: Optional[str] = None,
    ) -> str:
        """Monta URL de consentimento Santander (country=BR obrigatorio)."""
        cid = self._resolve_company()
        if not self.client_id:
            raise ValueError(
                f"Santander 033: CLIENT_ID ausente em BANCSYNC_{BANCO_CODIGO}_{cid or '<COMPANY_ID>'}_CLIENT_ID"
            )
        authorize_url = self.get("AUTHORIZE_URL")
        if not authorize_url:
            raise ValueError("Santander 033: AUTHORIZE_URL nao configurado")
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": scope or self.get("SCOPE", DEFAULT_SCOPE),
            "country": self.get("COUNTRY", "BR"),
            "redirect_uri": redirect_uri,
        }
        if state:
            params["state"] = state
        return f"{authorize_url}?{urlencode(params)}"

    # ── Authorization Code: troca de code por tokens ────────────────────────
    def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        scope: Optional[str] = None,
    ) -> dict:
        """Troca authorization code por access/refresh token via Basic Auth.

        Salva ACCESS_TOKEN e REFRESH_TOKEN via save_credential (nunca no Oracle).
        Retorna apenas metadados nao-sensiveis (flags, expires_in, token_type, scope).
        """
        import requests
        from requests.auth import HTTPBasicAuth

        from bancsynk.config import save_credential

        cid = self._resolve_company()
        if cid is None:
            raise ValueError(
                "Santander 033: company_id indefinido — passe company_id ao instanciar SantanderAuth"
            )
        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Santander 033: CLIENT_ID/CLIENT_SECRET ausentes no .env"
            )
        auth_url = self.get("AUTH_URL")
        if not auth_url:
            raise ValueError("Santander 033: AUTH_URL nao configurado")
        body = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "country": self.get("COUNTRY", "BR"),
            "scope": scope or self.get("SCOPE", DEFAULT_SCOPE),
        }
        resp = requests.post(
            auth_url,
            data=body,
            auth=HTTPBasicAuth(self.client_id, self.client_secret),
            timeout=20,
        )
        resp.raise_for_status()
        tokens = resp.json() or {}

        access = tokens.get("access_token") or ""
        refresh = tokens.get("refresh_token") or ""
        if access:
            save_credential(BANCO_CODIGO, cid, "ACCESS_TOKEN", access)
        if refresh:
            save_credential(BANCO_CODIGO, cid, "REFRESH_TOKEN", refresh)
        log.info("Santander 033: tokens salvos para company_id=%s", cid)

        return {
            "ok": True,
            "banco": BANCO_CODIGO,
            "company_id": cid,
            "has_access_token": bool(access),
            "has_refresh_token": bool(refresh),
            "expires_in": tokens.get("expires_in"),
            "token_type": tokens.get("token_type"),
            "scope": tokens.get("scope"),
        }

    # ── HTTP GET usando token existente ─────────────────────────────────────
    def request_get(self, path: str, params: dict | None = None) -> dict:
        import requests  # import local para nao pesar import-time

        if not path:
            raise ValueError("Santander 033: path da chamada nao configurado no .env")
        base = self.api_base_url
        if not base:
            raise ValueError(
                "Santander 033: BANCSYNC_033_<COMPANY_ID>_API_BASE_URL nao configurado no .env"
            )
        token = self.access_token
        if not token:
            raise ValueError(
                "Santander 033: ACCESS_TOKEN ausente — consentimento pendente"
            )
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        resp = requests.get(f"{base}{path}", headers=headers, params=params or {}, timeout=30)
        resp.raise_for_status()
        return resp.json()
