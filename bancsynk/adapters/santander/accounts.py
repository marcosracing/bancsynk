"""Consultas read-only do adaptador Santander 033."""

from __future__ import annotations

from typing import Optional

from bancsynk.adapters.base import BankAdapter
from bancsynk.adapters.santander.auth import SantanderAuth


class SantanderReadOnlyAdapter(BankAdapter):
    """Adaptador Santander limitado a consultas de Fase 1."""

    banco_codigo = "033"
    banco_nome = "Santander"
    read_only = True

    def __init__(
        self,
        company_id: Optional[str] = None,
        auth: Optional[SantanderAuth] = None,
    ) -> None:
        self.company_id: Optional[str] = str(company_id) if company_id is not None else None
        self.auth = auth or SantanderAuth(company_id=self.company_id)

    def auth_check(self) -> dict:
        return self.auth.check()

    def get_contas(self) -> list:
        path = self.auth.get("ACCOUNTS_PATH")
        data = self.auth.request_get(path)
        if isinstance(data, list):
            return data
        return data.get("accounts") or data.get("contas") or [data]

    def get_saldo(self, conta_id: str) -> dict:
        path = self.auth.get("BALANCE_PATH")
        return self.auth.request_get(path, params={"accountId": conta_id})

    def get_extrato(
        self,
        conta_id: str,
        data_ini: str,
        data_fim: str,
        pagina: int = 1,
    ) -> dict:
        path = self.auth.get("STATEMENT_PATH")
        return self.auth.request_get(
            path,
            params={
                "accountId": conta_id,
                "startDate": data_ini,
                "endDate": data_fim,
                "page": pagina,
            },
        )
