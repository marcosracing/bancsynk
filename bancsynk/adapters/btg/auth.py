"""Autenticacao BTG Pactual para a Fase 1 read-only."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("bancsynk.btg.auth")

BTG_ENV = os.environ.get("BTG_ENV", "sandbox")
BTG_BASE_URL = os.environ.get(
    "BTG_BASE_URL",
    "https://api.sandbox.btgpactual.com"
    if BTG_ENV == "sandbox"
    else "https://api.empresas.btgpactual.com",
)
BTG_AUTH_URL = os.environ.get(
    "BTG_AUTH_URL",
    "https://id.sandbox.btgpactual.com/auth/realms/btg/protocol/openid-connect/token"
    if BTG_ENV == "sandbox"
    else "https://id.empresas.btgpactual.com/auth/realms/btg/protocol/openid-connect/token",
)


class BTGAuth:
    """Cliente OAuth2 BTG com renovacao simples de token."""

    def __init__(self) -> None:
        self.client_id = os.environ.get("BTG_CLIENT_ID", "")
        self.client_secret = os.environ.get("BTG_CLIENT_SECRET", "")
        self.cert_path = os.path.expanduser(os.environ.get("BTG_CERT_PATH", ""))
        self.key_path = os.path.expanduser(os.environ.get("BTG_KEY_PATH", ""))
        self._token: Optional[str] = None
        self._token_exp = 0.0

    @property
    def cert(self) -> Optional[Tuple[str, str]]:
        if not self.cert_path or not self.key_path:
            return None
        cert_file = Path(self.cert_path)
        key_file = Path(self.key_path)
        if cert_file.exists() and key_file.exists():
            return (str(cert_file), str(key_file))
        return None

    def _validate_config(self) -> None:
        missing = []
        if not self.client_id:
            missing.append("BTG_CLIENT_ID")
        if not self.client_secret:
            missing.append("BTG_CLIENT_SECRET")
        if missing:
            raise EnvironmentError(f"Variaveis BTG ausentes: {', '.join(missing)}")

    def get_token(self) -> str:
        self._validate_config()
        if self._token and time.time() < self._token_exp - 60:
            return self._token

        resp = requests.post(
            BTG_AUTH_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            cert=self.cert,
            timeout=15,
        )
        if resp.status_code != 200:
            log.error("Auth BTG falhou: %s %s", resp.status_code, resp.text[:200])
        resp.raise_for_status()

        data = resp.json()
        self._token = data["access_token"]
        self._token_exp = time.time() + int(data.get("expires_in", 3600))
        return self._token

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        token = self.get_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        return requests.request(
            method,
            f"{BTG_BASE_URL}{path}",
            headers=headers,
            cert=self.cert,
            timeout=30,
            **kwargs,
        )

    def get(self, path: str, params: dict | None = None) -> dict:
        resp = self.request("GET", path, params=params or {})
        resp.raise_for_status()
        return resp.json()

    def check(self) -> dict:
        try:
            token = self.get_token()
            return {
                "ok": True,
                "env": BTG_ENV,
                "base_url": BTG_BASE_URL,
                "token_preview": token[:12] + "...",
                "cert_configured": self.cert is not None,
            }
        except Exception as exc:
            return {
                "ok": False,
                "env": BTG_ENV,
                "base_url": BTG_BASE_URL,
                "error": str(exc),
            }
