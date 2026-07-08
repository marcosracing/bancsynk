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
        log.info("BancSynk: adaptador BTG registrado em modo read-only")

    def _register_santander(self) -> None:
        adapter = SantanderReadOnlyAdapter()
        self._adapters[adapter.banco_codigo] = adapter
        self._adapters["santander"] = adapter
        log.info("BancSynk: adaptador Santander registrado em modo read-only")

    def get_adapter(self, banco: str, company_id=None) -> BankAdapter:
        code = banco.lower().strip()
        if code not in self._adapters:
            raise ValueError(f"Banco '{banco}' nao configurado no BancSynk")
        adapter = self._adapters[code]
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

    def gerar_url_consentimento(
        self, banco: str, company_id, redirect_uri: str, scope: str
    ) -> str:
        from bancsynk.config import env_key, get_all_env, get_credential

        env = get_all_env()
        authorize_url = env.get(env_key(banco, company_id, "AUTHORIZE_URL")) or env.get(
            "BTG_AUTHORIZE_URL", ""
        )
        client_id = get_credential(banco, company_id, "CLIENT_ID")
        if not authorize_url or not client_id:
            raise ValueError("AUTHORIZE_URL ou CLIENT_ID nao configurados no .env")
        params = {
            "client_id": client_id,
            "response_type": "code",
            "scope": scope,
            "redirect_uri": redirect_uri,
        }
        return f"{authorize_url}?{urlencode(params)}"

    def trocar_code(
        self, banco: str, company_id, code: str, redirect_uri: str
    ) -> dict:
        import requests

        from bancsynk.config import (
            env_key,
            get_all_env,
            get_credential,
            save_credential,
        )

        env = get_all_env()
        auth_url = env.get(env_key(banco, company_id, "AUTH_URL")) or env.get(
            "BTG_AUTH_URL", ""
        )
        client_id = get_credential(banco, company_id, "CLIENT_ID")
        secret = get_credential(banco, company_id, "CLIENT_SECRET")
        resp = requests.post(
            auth_url,
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            timeout=15,
        )
        resp.raise_for_status()
        tokens = resp.json()
        if tokens.get("access_token"):
            save_credential(banco, company_id, "ACCESS_TOKEN", tokens["access_token"])
        if tokens.get("refresh_token"):
            save_credential(banco, company_id, "REFRESH_TOKEN", tokens["refresh_token"])
        log.info("BancSynk: token %s/%s salvo no .env", banco, company_id)
        return tokens
