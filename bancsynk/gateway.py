"""Ponto unico de acesso aos adaptadores bancarios do BancSynk."""

from __future__ import annotations

import logging
from typing import Dict

from bancsynk.adapters.base import BankAdapter
from bancsynk.adapters.btg.accounts import BTGReadOnlyAdapter

log = logging.getLogger("bancsynk.gateway")


class BancSynk:
    """Gateway bancario unificado.

    A Fase 1 registra apenas adaptadores read-only. Operacoes de escrita devem ser
    adicionadas em fase propria, com ADR/contrato e controles de aprovacao.
    """

    def __init__(self, enable_btg: bool = True):
        self._adapters: Dict[str, BankAdapter] = {}
        if enable_btg:
            self._register_btg()

    def _register_btg(self) -> None:
        adapter = BTGReadOnlyAdapter()
        self._adapters[adapter.banco_codigo] = adapter
        log.info("BancSynk: adaptador BTG registrado em modo read-only")

    def health(self) -> dict:
        return {
            code: adapter.auth_check()
            for code, adapter in self._adapters.items()
        }

    def get_adapter(self, banco: str) -> BankAdapter:
        code = banco.lower().strip()
        if code not in self._adapters:
            raise ValueError(f"Banco '{banco}' nao configurado no BancSynk")
        return self._adapters[code]

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
