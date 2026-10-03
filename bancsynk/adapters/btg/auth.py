"""BancSynk — Adaptador BTG Pactual (Fase 1 read-only).

Fluxo OBRIGATORIO no BTG Banking: Authorization Code.

Conforme documentacao BTG:
    "voce so consegue ter acesso aos dados de uma conta PJ utilizando o fluxo
    do AUTHORIZATION CODE sendo ele, portanto, um fluxo OBRIGATORIO"

client_credentials NAO libera Banking (saldo/extrato/Pix). So serve para APIs
sem titular. Fluxo desta classe:
    1. get_authorize_url()  → usuario abre no browser e autoriza
    2. exchange_code(code)  → salva ACCESS_TOKEN + REFRESH_TOKEN no .env
    3. refresh_access_token() → renova automaticamente enquanto refresh valido (10d)

Chaves persistidas no ~/Documents/BancSynk/.env (via bancsynk.config):
    BANCSYNC_208_<COMPANY_ID>_CLIENT_ID
    BANCSYNC_208_<COMPANY_ID>_CLIENT_SECRET
    BANCSYNC_208_<COMPANY_ID>_ACCESS_TOKEN
    BANCSYNC_208_<COMPANY_ID>_REFRESH_TOKEN
    BANCSYNC_208_<COMPANY_ID>_CERT_PATH   (opcional)
    BANCSYNC_208_<COMPANY_ID>_KEY_PATH    (opcional)

Fallback legado: BTG_CLIENT_ID / BTG_CLIENT_SECRET etc. no mesmo .env.

Tokens:
    access_token:  ~24h
    refresh_token: ~10 dias

Sandbox: companyId (CNPJ) e fixo em 30306294000145.
"""

from __future__ import annotations

import base64
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlencode

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
BTG_AUTH_URL = os.environ.get(
    "BTG_AUTH_URL",
    "https://id.sandbox.btgpactual.com/oauth2/token"
    if BTG_ENV == "sandbox"
    else "https://id.btgpactual.com/oauth2/token",
)
BTG_AUTHORIZE_URL = os.environ.get(
    "BTG_AUTHORIZE_URL",
    "https://id.sandbox.btgpactual.com/oauth2/authorize"
    if BTG_ENV == "sandbox"
    else "https://id.btgpactual.com/oauth2/authorize",
)
BTG_SCOPE_DEFAULT = os.environ.get(
    "BTG_SCOPE", "openid empresas.btgpactual.com/accounts.readonly"
)
BTG_REDIRECT_URI = os.environ.get("BTG_REDIRECT_URI", "https://localhost.com")

# No sandbox o companyId (CNPJ) e fixo.
SANDBOX_COMPANY_ID = "30306294000145"

# Enderecos por ambiente, usados quando as credenciais sao injetadas (cofre).
_ENDERECOS = {
    "sandbox": {
        "base": "https://api.sandbox.empresas.btgpactual.com",
        "token": "https://id.sandbox.btgpactual.com/oauth2/token",
        "authorize": "https://id.sandbox.btgpactual.com/oauth2/authorize",
    },
    "producao": {
        "base": "https://api.empresas.btgpactual.com",
        "token": "https://id.btgpactual.com/oauth2/token",
        "authorize": "https://id.btgpactual.com/oauth2/authorize",
    },
}
_SCOPE_PADRAO = "openid empresas.btgpactual.com/accounts.readonly"


def validar_url_btg(url: str, permitir_local: bool = False) -> str:
    """Recusa URL fora de https://*.btgpactual.com antes de enviar segredo.

    permitir_local: so no modo legado (sem cofre), aceita loopback para os mocks de teste.
    """
    from urllib.parse import urlsplit

    try:
        partes = urlsplit(str(url or ""))
        host = (partes.hostname or "").lower()
    except ValueError:
        partes = None
        host = ""
    if permitir_local and partes is not None and host in ("127.0.0.1", "localhost", "::1"):
        return url
    if (
        partes is None
        or partes.scheme != "https"
        or partes.username is not None
        or partes.password is not None
        or not (host == "btgpactual.com" or host.endswith(".btgpactual.com"))
    ):
        raise PermissionError("BTG 208: endereco recusado (somente https em btgpactual.com).")
    return url


class BTGAuth:
    """Autenticacao Authorization Code do BTG (Fase 1 read-only)."""

    def __init__(self, company_id: Optional[str] = None, credenciais=None) -> None:
        # credenciais: objeto com get(campo) e save(campo, valor) (cofre do chamador).
        self.credenciais = credenciais
        self.company_id: Optional[str] = (
            str(company_id) if company_id is not None else None
        )
        # Cache em memoria de access_token para evitar releitura de .env.
        self._cached_access_token: Optional[str] = None
        self._cached_token_exp: float = 0.0

    # ── Descoberta de company_id ────────────────────────────────────────────
    def _resolve_company(self) -> Optional[str]:
        if self.company_id:
            return self.company_id
        if self.credenciais is not None:
            return None  # com cofre injetado nao varre o ambiente do processo
        prefix = f"BANCSYNC_{BANCO_CODIGO}_"
        for key in os.environ:
            if key.startswith(prefix) and key.endswith("_CLIENT_ID"):
                parts = key.split("_")
                if len(parts) >= 4:
                    return parts[2]
        return None

    # ── Leitura/escrita de configuracao ─────────────────────────────────────
    @property
    def ambiente(self) -> str:
        if self.credenciais is None:
            return BTG_ENV
        valor = str(self.credenciais.get("AMBIENTE") or "").strip().lower()
        return "producao" if valor == "producao" else "sandbox"

    def config_value(self, campo: str, default: str = "") -> str:
        if self.credenciais is not None:
            # Cofre injetado: le so dele, sem variaveis de ambiente nem arquivo local.
            return str(self.credenciais.get(campo) or default)
        from bancsynk.config import get_credential

        cid = self._resolve_company()
        if cid is not None:
            value = get_credential(BANCO_CODIGO, cid, campo)
            if value:
                return value
        legacy_key = f"BTG_{campo.upper()}"
        return os.environ.get(legacy_key, default)

    def _save_cred(self, campo: str, valor: str) -> None:
        if self.credenciais is not None:
            self.credenciais.save(campo, valor)
            return
        from bancsynk.config import save_credential

        cid = self._resolve_company()
        if cid is None:
            log.warning("BTG: sem company_id definido — %s nao persistido", campo)
            return
        save_credential(BANCO_CODIGO, cid, campo, valor)

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
        if self.credenciais is not None:
            return _ENDERECOS[self.ambiente]["base"]
        return self.config_value("BASE_URL", BTG_BASE_URL)

    @property
    def auth_url(self) -> str:
        if self.credenciais is not None:
            return _ENDERECOS[self.ambiente]["token"]
        return self.config_value("AUTH_URL", BTG_AUTH_URL)

    @property
    def authorize_url(self) -> str:
        if self.credenciais is not None:
            return _ENDERECOS[self.ambiente]["authorize"]
        return self.config_value("AUTHORIZE_URL", BTG_AUTHORIZE_URL)

    @property
    def scope(self) -> str:
        return self.config_value(
            "SCOPE", _SCOPE_PADRAO if self.credenciais is not None else BTG_SCOPE_DEFAULT
        )

    @property
    def redirect_uri(self) -> str:
        return self.config_value(
            "REDIRECT_URI", "" if self.credenciais is not None else BTG_REDIRECT_URI
        )

    @property
    def cert(self) -> Optional[Tuple[str, str]]:
        if not self.cert_path or not self.key_path:
            return None
        cert_file = Path(self.cert_path)
        key_file = Path(self.key_path)
        if cert_file.exists() and key_file.exists():
            return (str(cert_file), str(key_file))
        return None

    # ── Basic Auth base64 ───────────────────────────────────────────────────
    def _basic_auth_header(self) -> str:
        raw = f"{self.client_id}:{self.client_secret}"
        return "Basic " + base64.b64encode(raw.encode("utf-8")).decode("ascii")

    # ── Authorization Code: URL de consentimento ────────────────────────────
    def get_authorize_url(self, state: Optional[str] = None) -> str:
        if not self.client_id:
            raise EnvironmentError(
                "BTG 208: CLIENT_ID nao configurado — usar tela 8.5.0 BancSynk."
            )
        if not state:
            # Sem state o code de volta não se amarra a quem pediu (CSRF).
            raise ValueError("BTG 208: state obrigatorio no consentimento OAuth.")
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": self.scope,
            "redirect_uri": self.redirect_uri,
            "state": state,
        }
        return f"{validar_url_btg(self.authorize_url, self.credenciais is None)}?{urlencode(params)}"

    # ── Authorization Code: troca de code por tokens ────────────────────────
    def exchange_code(self, code: str) -> dict:
        if not self.client_id or not self.client_secret:
            raise EnvironmentError(
                "BTG 208: CLIENT_ID/CLIENT_SECRET ausentes no .env."
            )
        url = validar_url_btg(self.auth_url, self.credenciais is None)  # antes de enviar secret e code
        log.info("BTG 208: trocando authorization code por tokens")
        resp = requests.post(
            url,
            headers={
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
            },
            cert=self.cert,
            timeout=20,
        )
        if resp.status_code != 200:
            # Sem corpo da resposta no log: pode trazer token ou code.
            log.error("BTG exchange_code falhou: HTTP %s", resp.status_code)
        resp.raise_for_status()
        tokens = resp.json() or {}
        self._store_tokens(tokens)
        return tokens

    # ── Refresh Token ───────────────────────────────────────────────────────
    def refresh_access_token(self) -> bool:
        rt = self.refresh_token
        if not rt or not self.client_id or not self.client_secret:
            return False
        url = validar_url_btg(self.auth_url, self.credenciais is None)  # PermissionError fora do try
        try:
            resp = requests.post(
                url,
                headers={
                    "Authorization": self._basic_auth_header(),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "refresh_token", "refresh_token": rt},
                cert=self.cert,
                timeout=15,
            )
            resp.raise_for_status()
            self._store_tokens(resp.json() or {})
            return True
        except Exception as exc:  # pragma: no cover - depende de rede
            log.warning("BTG refresh_token falhou: %s", type(exc).__name__)
            return False

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
            "BTG 208: token armazenado (expira em ~%dh) company_id=%s",
            expires_in // 3600,
            self._resolve_company(),
        )

    # ── get_token / request ─────────────────────────────────────────────────
    def get_token(self) -> str:
        if self._cached_access_token and time.time() < self._cached_token_exp:
            return self._cached_access_token
        env_token = self.access_token
        if env_token:
            self._cached_access_token = env_token
            self._cached_token_exp = time.time() + 300
            return env_token
        if self.refresh_token and self.refresh_access_token():
            return self._cached_access_token or ""
        raise PermissionError(
            "BTG 208: sem ACCESS_TOKEN/REFRESH_TOKEN — execute o fluxo "
            "Authorization Code (get_authorize_url + exchange_code)."
        )

    def _resolve_path(self, path: str) -> str:
        if "{companyId}" not in path:
            return path
        if self.ambiente == "sandbox":
            company = SANDBOX_COMPANY_ID
        elif self.credenciais is not None:
            company = str(self.credenciais.get("COMPANY_CNPJ") or "")
        else:
            company = os.environ.get(
                f"BTG_COMPANY_{self._resolve_company()}_CNPJ", self._resolve_company() or ""
            )
        return path.replace("{companyId}", company)

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        validar_url_btg(self.base_url, self.credenciais is None)  # antes de obter ou renovar o token
        token = self.get_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        url = validar_url_btg(
            f"{self.base_url}{self._resolve_path(path)}", self.credenciais is None
        )
        return requests.request(
            method,
            url,
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

    # ── Check nao-destrutivo (introspeccao, sem request externo) ────────────
    def check(self) -> dict:
        cid = self._resolve_company()
        base = {
            "banco": BANCO_CODIGO,
            "company_id": cid,
            "env": self.ambiente,
            "base_url": self.base_url,
            "cert_configured": self.cert is not None,
        }
        if not self.client_id or not self.client_secret:
            return {
                **base,
                "ok": False,
                "status": "nao_configurado",
                "msg": "BTG 208: CLIENT_ID/CLIENT_SECRET ausentes no .env.",
            }
        if not self.access_token:
            result = {
                **base,
                "ok": False,
                "status": "consentimento_pendente",
                "has_client_id": True,
                "has_secret": True,
                "msg": (
                    "BTG 208: consentimento pendente — execute o fluxo "
                    "Authorization Code."
                ),
            }
            # Sem URL de consentimento aqui: ela exige o state de quem a pede.
            return result
        return {
            **base,
            "ok": True,
            "status": "ativo",
            "has_client_id": True,
            "has_secret": True,
            "has_token": True,
            "msg": "BTG 208: token presente — pronto para chamadas.",
        }
