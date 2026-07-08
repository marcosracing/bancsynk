"""Autenticacao BTG Pactual para a Fase 1 read-only.

OAuth2 BTG:
    POST {AUTH_URL}
    Authorization: Basic base64(client_id:client_secret)
    Content-Type: application/x-www-form-urlencoded
    Body: grant_type=<...>&scope=<...>

Tokens armazenados no .env do BancSynk (chave BANCSYNC_208_<CID>_*):
    ACCESS_TOKEN   — validade tipica 24h
    REFRESH_TOKEN  — validade tipica 10 dias
"""

from __future__ import annotations

import base64
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("bancsynk.btg.auth")

BANCO_CODIGO = "208"
BTG_ENV = os.environ.get("BTG_ENV", "sandbox")

BTG_BASE_URL = os.environ.get(
    "BTG_BASE_URL",
    "https://api.sandbox.empresas.btgpactual.com"
    if BTG_ENV == "sandbox"
    else "https://api.empresas.btgpactual.com",
)

# URL correta conforme documentacao BTG: /oauth2/token
BTG_AUTH_URL = os.environ.get(
    "BTG_AUTH_URL",
    "https://id.sandbox.btgpactual.com/oauth2/token"
    if BTG_ENV == "sandbox"
    else "https://id.btgpactual.com/oauth2/token",
)


class BTGAuth:
    """Cliente BTG vinculado a uma empresa (Authorization Code + refresh)."""

    def __init__(self, company_id: Optional[str] = None) -> None:
        self.company_id: Optional[str] = str(company_id) if company_id is not None else None
        # Cache em memoria para nao rele-r .env a cada request.
        self._cached_access_token: Optional[str] = None
        self._cached_token_exp: float = 0.0

    # ── Descoberta de company_id ────────────────────────────────────────────
    def _resolve_company(self) -> Optional[str]:
        if self.company_id:
            return self.company_id
        prefix = f"BANCSYNC_{BANCO_CODIGO}_"
        for key in os.environ:
            if key.startswith(prefix) and key.endswith("_CLIENT_ID"):
                parts = key.split("_")
                if len(parts) >= 4:
                    return parts[2]
        return None

    # ── Leitura de configuracao (env .env do BancSynk + fallback legacy BTG_*) ─
    def config_value(self, campo: str, default: str = "") -> str:
        from bancsynk.config import get_credential

        cid = self._resolve_company()
        if cid is not None:
            value = get_credential(BANCO_CODIGO, cid, campo)
            if value:
                return value
        legacy_key = f"BTG_{campo.upper()}"
        return os.environ.get(legacy_key, default)

    @property
    def client_id(self) -> str:
        return self.config_value("CLIENT_ID")

    @property
    def client_secret(self) -> str:
        return self.config_value("CLIENT_SECRET")

    @property
    def access_token(self) -> str:
        return self.config_value("ACCESS_TOKEN")

    @property
    def refresh_token(self) -> str:
        return self.config_value("REFRESH_TOKEN")

    @property
    def cert_path(self) -> str:
        return os.path.expanduser(self.config_value("CERT_PATH"))

    @property
    def key_path(self) -> str:
        return os.path.expanduser(self.config_value("KEY_PATH"))

    @property
    def base_url(self) -> str:
        return self.config_value("BASE_URL", BTG_BASE_URL)

    @property
    def auth_url(self) -> str:
        return self.config_value("AUTH_URL", BTG_AUTH_URL)

    @property
    def scope(self) -> str:
        return self.config_value("SCOPE", "accounts openfinance")

    @property
    def cert(self) -> Optional[Tuple[str, str]]:
        if not self.cert_path or not self.key_path:
            return None
        cert_file = Path(self.cert_path)
        key_file = Path(self.key_path)
        if cert_file.exists() and key_file.exists():
            return (str(cert_file), str(key_file))
        return None

    # ── Persistencia de tokens ──────────────────────────────────────────────
    def _save_cred(self, campo: str, valor: str) -> None:
        from bancsynk.config import save_credential

        cid = self._resolve_company()
        if cid is None:
            log.warning("BTG: sem company_id — token nao persistido no .env")
            return
        save_credential(BANCO_CODIGO, cid, campo, valor)

    # ── HTTP: request token com Basic Auth base64 ───────────────────────────
    def _basic_auth_header(self) -> str:
        raw = f"{self.client_id}:{self.client_secret}"
        return "Basic " + base64.b64encode(raw.encode("utf-8")).decode("ascii")

    def _request_token(self, grant_type: str, extra_params: Optional[dict] = None) -> dict:
        """POST BTG /oauth2/token — Basic Auth + form-urlencoded."""
        body = {"grant_type": grant_type, "scope": self.scope}
        if extra_params:
            body.update(extra_params)
        headers = {
            "Authorization": self._basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp = requests.post(
            self.auth_url,
            headers=headers,
            data=body,
            cert=self.cert,
            timeout=15,
        )
        if resp.status_code != 200:
            log.error(
                "BTG auth %s falhou: %s %s",
                grant_type,
                resp.status_code,
                resp.text[:200],
            )
        resp.raise_for_status()
        return resp.json() or {}

    def _store_tokens(self, tokens: dict) -> None:
        access = tokens.get("access_token") or ""
        refresh = tokens.get("refresh_token") or ""
        expires_in = int(tokens.get("expires_in") or 86400)
        if access:
            self._cached_access_token = access
            self._cached_token_exp = time.time() + expires_in - 300
            self._save_cred("ACCESS_TOKEN", access)
        if refresh:
            self._save_cred("REFRESH_TOKEN", refresh)
        log.info(
            "BTG: token armazenado (expira em ~%dh) para company_id=%s",
            expires_in // 3600,
            self._resolve_company(),
        )

    def refresh_access_token(self) -> bool:
        """Tenta renovar via refresh_token (10 dias)."""
        rt = self.refresh_token
        if not rt:
            return False
        try:
            tokens = self._request_token("refresh_token", {"refresh_token": rt})
        except Exception as exc:  # pragma: no cover - depende de rede
            log.warning("BTG: refresh_token falhou: %s", exc)
            return False
        self._store_tokens(tokens)
        return True

    def fetch_client_credentials_token(self) -> dict:
        """Obtem token via client_credentials (Basic Auth base64)."""
        if not self.client_id or not self.client_secret:
            raise ValueError(
                "BTG 208: CLIENT_ID/CLIENT_SECRET ausentes no .env — configure na tela 8.5.0."
            )
        tokens = self._request_token("client_credentials")
        self._store_tokens(tokens)
        return tokens

    # ── get_token / request ─────────────────────────────────────────────────
    def get_token(self) -> str:
        """Retorna access_token valido, renovando automaticamente quando possivel."""
        if self._cached_access_token and time.time() < self._cached_token_exp:
            return self._cached_access_token

        env_token = self.access_token
        if env_token:
            self._cached_access_token = env_token
            # Sem info de expiracao no .env — usa cache curto (5min) para evitar rele-r toda hora.
            self._cached_token_exp = time.time() + 300
            return env_token

        if self.refresh_token and self.refresh_access_token():
            return self._cached_access_token or ""

        # Fallback client_credentials so quando ha creds sem qualquer token.
        if self.client_id and self.client_secret:
            self.fetch_client_credentials_token()
            return self._cached_access_token or ""

        raise ValueError(
            "BTG 208: sem ACCESS_TOKEN/REFRESH_TOKEN/CLIENT_ID — configure na tela 8.5.0."
        )

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        token = self.get_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        return requests.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            cert=self.cert,
            timeout=30,
            **kwargs,
        )

    def get(self, path: str, params: dict | None = None) -> dict:
        resp = self.request("GET", path, params=params or {})
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, json: dict | None = None) -> dict:
        resp = self.request("POST", path, json=json or {})
        resp.raise_for_status()
        return resp.json()

    # ── Check nao-destrutivo (introspeccao segura, nao faz request) ─────────
    def check(self) -> dict:
        cid = self._resolve_company()
        base = {
            "banco": BANCO_CODIGO,
            "company_id": cid,
            "env": BTG_ENV,
            "base_url": self.base_url,
            "cert_configured": self.cert is not None,
        }
        if not self.client_id or not self.client_secret:
            return {
                **base,
                "ok": False,
                "msg": "BTG 208: CLIENT_ID/CLIENT_SECRET ausentes no .env.",
            }
        if not self.access_token:
            return {
                **base,
                "ok": False,
                "msg": "BTG 208: consentimento pendente — ACCESS_TOKEN ausente.",
                "has_client_id": True,
                "has_secret": True,
            }
        return {
            **base,
            "ok": True,
            "msg": "BTG 208: credenciais e token presentes.",
            "has_client_id": True,
            "has_secret": True,
            "has_token": True,
        }
