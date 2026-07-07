"""Consultas read-only do adaptador BTG."""

from __future__ import annotations

from bancsynk.adapters.base import BankAdapter
from bancsynk.adapters.btg.auth import BTGAuth


class BTGReadOnlyAdapter(BankAdapter):
    """Adaptador BTG limitado a consultas de Fase 1."""

    banco_codigo = "btg"
    banco_nome = "BTG Pactual"
    read_only = True

    def __init__(self, auth: BTGAuth | None = None) -> None:
        self.auth = auth or BTGAuth()

    def auth_check(self) -> dict:
        return self.auth.check()

    def get_contas(self) -> list:
        data = self.auth.get("/v2/accounts")
        if isinstance(data, list):
            return data
        return data.get("accounts") or data.get("contas") or [data]

    def get_saldo(self, conta_id: str) -> dict:
        return self.auth.get("/v2/accounts/balance", params={"accountId": conta_id})

    def get_extrato(self, conta_id: str, data_ini: str, data_fim: str, pagina: int = 1) -> dict:
        return self.auth.get(
            "/v2/accounts/statement",
            params={
                "accountId": conta_id,
                "startDate": data_ini,
                "endDate": data_fim,
                "page": pagina,
            },
        )
