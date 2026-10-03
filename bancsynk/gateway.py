"""Ponto unico de acesso aos adaptadores bancarios do BancSynk."""

from __future__ import annotations

import logging
from typing import Dict
from urllib.parse import urlencode

from bancsynk.adapters.base import BankAdapter
from bancsynk.adapters.btg.accounts import BTGReadOnlyAdapter
from bancsynk.adapters.santander.accounts import SantanderReadOnlyAdapter

log = logging.getLogger("bancsynk.gateway")


class BancSynk:
    """Gateway bancario unificado.

    A Fase 1 registra apenas adaptadores read-only. Operacoes de escrita devem ser
    adicionadas em fase propria, com ADR/contrato e controles de aprovacao.
    """

    def __init__(self, enable_btg: bool = True, enable_santander: bool = True):
        self._adapters: Dict[str, BankAdapter] = {}
        if enable_btg:
            self._register_btg()
        if enable_santander:
            self._register_santander()

    def _register_btg(self) -> None:
        adapter = BTGReadOnlyAdapter()
        self._adapters[adapter.banco_codigo] = adapter
        self._adapters["208"] = adapter
        log.info("BancSynk: adaptador BTG registrado em modo read-only")

    def _register_santander(self) -> None:
        adapter = SantanderReadOnlyAdapter()
        self._adapters[adapter.banco_codigo] = adapter
        self._adapters["santander"] = adapter
        log.info("BancSynk: adaptador Santander registrado em modo read-only")

    def get_adapter(self, banco: str, company_id=None, credenciais=None) -> BankAdapter:
        code = banco.lower().strip()
        if code not in self._adapters:
            raise ValueError(f"Banco '{banco}' nao configurado no BancSynk")
        adapter = self._adapters[code]
        if credenciais is not None:
            # Credenciais injetadas: so o adaptador BTG as aceita.
            if not isinstance(adapter, BTGReadOnlyAdapter):
                raise ValueError(f"Banco '{banco}' nao aceita credenciais injetadas")
            return BTGReadOnlyAdapter(company_id=company_id, credenciais=credenciais)
        if company_id is not None:
            cls = type(adapter)
            try:
                return cls(company_id=company_id)
            except TypeError:
                # Adapter nao aceita company_id (ex.: BTG global).
                return adapter
        return adapter

    def get_contas(self, banco: str) -> list:
        return self.get_adapter(banco).get_contas()

    def get_saldo(self, banco: str, conta_id: str) -> dict:
        return self.get_adapter(banco).get_saldo(conta_id)

    def get_extrato(
        self,
        banco: str,
        conta_id: str,
        data_ini: str,
        data_fim: str,
        pagina: int = 1,
    ) -> dict:
        return self.get_adapter(banco).get_extrato(conta_id, data_ini, data_fim, pagina)

    def get_dda(self, banco: str, company_id=None, **filtros) -> dict:
        """Delega para o adapter. Levanta NotImplementedError se o adapter
        não sobrescreveu get_dda (bancos sem suporte a DDA)."""
        adapter = self.get_adapter(banco, company_id=company_id)
        return adapter.get_dda(**filtros)

    # ── Interface CtrlOne — multiempresa via BANCSYNC_{banco}_{company_id}_* ─
    def health(self) -> dict:
        from bancsynk.config import get_all_env, has_credential

        env = get_all_env()
        bancos: Dict[str, dict] = {}
        for key in env:
            if not (key.startswith("BANCSYNC_") and key.endswith("_CLIENT_ID")):
                continue
            parts = key.split("_")
            if len(parts) < 4:
                continue
            banco, cid = parts[1], parts[2]
            bancos[f"{banco}_{cid}"] = {
                "banco": banco,
                "company_id": cid,
                "has_client_id": True,
                "has_secret": has_credential(banco, cid, "CLIENT_SECRET"),
                "has_token": has_credential(banco, cid, "ACCESS_TOKEN"),
            }
        return {"ok": True, "integracoes": bancos}

    @staticmethod
    def _is_santander(banco: str) -> bool:
        return str(banco).lower().strip() in {"033", "santander"}

    @staticmethod
    def _is_btg(banco: str) -> bool:
        return str(banco).lower().strip() in {"208", "btg"}

    def gerar_url_consentimento(
        self, banco: str, company_id, redirect_uri: str, scope: str,
        state: str = "",
    ) -> str:
        if not state:
            # Sem state o code de volta não se amarra a quem pediu (CSRF).
            raise ValueError("state obrigatorio no consentimento OAuth.")
        if self._is_santander(banco):
            from bancsynk.adapters.santander.auth import SantanderAuth

            return SantanderAuth(company_id=company_id).build_authorize_url(
                redirect_uri=redirect_uri, scope=scope or None, state=state
            )

        from bancsynk.config import env_key, get_all_env, get_credential

        if self._is_btg(banco):
            banco = "208"
        env = get_all_env()
        authorize_url = (
            get_credential(banco, company_id, "AUTHORIZE_URL")
            or env.get(env_key(banco, company_id, "AUTHORIZE_URL"))
            or env.get("BTG_AUTHORIZE_URL", "")
        )
        client_id = get_credential(banco, company_id, "CLIENT_ID")
        if not authorize_url or not client_id:
            raise ValueError("AUTHORIZE_URL ou CLIENT_ID nao configurados no .env")
        params = {
            "client_id": client_id,
            "response_type": "code",
            "scope": scope,
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return f"{authorize_url}?{urlencode(params)}"

    def trocar_code(
        self, banco: str, company_id, code: str, redirect_uri: str
    ) -> dict:
        if self._is_santander(banco):
            from bancsynk.adapters.santander.auth import SantanderAuth

            return SantanderAuth(company_id=company_id).exchange_code(
                code=code, redirect_uri=redirect_uri
            )

        import requests
        from requests.auth import HTTPBasicAuth

        from bancsynk.config import (
            env_key,
            get_all_env,
            get_credential,
            save_credential,
        )

        env = get_all_env()
        if self._is_btg(banco):
            banco = "208"
        auth_url = (
            get_credential(banco, company_id, "AUTH_URL")
            or env.get(env_key(banco, company_id, "AUTH_URL"))
            or env.get("BTG_AUTH_URL", "")
        )
        client_id = get_credential(banco, company_id, "CLIENT_ID")
        secret = get_credential(banco, company_id, "CLIENT_SECRET")
        if not auth_url or not client_id or not secret:
            raise ValueError("AUTH_URL, CLIENT_ID ou CLIENT_SECRET nao configurados no .env")
        resp = requests.post(
            auth_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            auth=HTTPBasicAuth(client_id, secret),
            timeout=15,
        )
        resp.raise_for_status()
        tokens = resp.json()
        if tokens.get("access_token"):
            save_credential(banco, company_id, "ACCESS_TOKEN", tokens["access_token"])
        if tokens.get("refresh_token"):
            save_credential(banco, company_id, "REFRESH_TOKEN", tokens["refresh_token"])
        log.info("BancSynk: token %s/%s salvo no .env", banco, company_id)
        return {
            "ok": True,
            "banco": banco,
            "company_id": str(company_id),
            "has_access_token": bool(tokens.get("access_token")),
            "has_refresh_token": bool(tokens.get("refresh_token")),
            "expires_in": tokens.get("expires_in"),
            "token_type": tokens.get("token_type"),
            "scope": tokens.get("scope"),
        }
