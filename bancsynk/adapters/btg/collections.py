"""Cobranca (boleto) do BTG: criar, consultar e cancelar.

Unico adaptador do BancSynk com escrita; so cobra, nunca paga nem move saldo.
Documentacao: Banking - Collections (/{companyId}/banking/collections).
"""

from __future__ import annotations

from typing import Optional

from bancsynk.adapters.base import BankAdapter
from bancsynk.adapters.btg.auth import BTGAuth

_CAMINHO = "/{companyId}/banking/collections"


class BTGCobrancaAdapter(BankAdapter):
    """Cobranca BTG (boleto hibrido com Pix). Escreve so em /collections."""

    banco_codigo = "btg-cobranca"
    banco_nome = "BTG Pactual - Cobranca"
    read_only = False

    def __init__(
        self,
        company_id: Optional[str] = None,
        auth: BTGAuth | None = None,
        credenciais=None,
    ) -> None:
        self.company_id: Optional[str] = str(company_id) if company_id is not None else None
        self.auth = auth or BTGAuth(company_id=self.company_id, credenciais=credenciais)
        # Escrita no banco só com o cofre: sem ele não há endereço travado em
        # https *.btgpactual.com (o modo legado aceita localhost).
        if getattr(self.auth, "credenciais", None) is None:
            raise ValueError("Cobranca BTG exige credenciais do cofre.")

    # ── contrato base: este adaptador nao le contas ───────────────────────
    def auth_check(self) -> dict:
        return self.auth.check()

    def get_contas(self) -> list:
        raise NotImplementedError("Adaptador de cobranca nao lista contas")

    def get_saldo(self, conta_id: str) -> dict:
        raise NotImplementedError("Adaptador de cobranca nao consulta saldo")

    def get_extrato(self, conta_id: str, data_ini: str, data_fim: str, pagina: int = 1) -> dict:
        raise NotImplementedError("Adaptador de cobranca nao consulta extrato")

    def _cabecalhos(self) -> dict:
        # O sandbox (Wiremock) exige x-response para escolher a resposta.
        if self.auth.ambiente == "sandbox":
            return {"x-response": "success"}
        return {}

    @staticmethod
    def _id(collection_id: str) -> str:
        valor = str(collection_id or "").strip()
        if not valor or not all(c.isalnum() or c in "-_" for c in valor):
            raise ValueError("collection_id invalido")
        return valor

    def criar(self, payload: dict) -> dict:
        resp = self.auth.request(
            "POST", _CAMINHO, json=payload or {}, headers=self._cabecalhos()
        )
        resp.raise_for_status()
        return resp.json()

    def consultar(self, collection_id: str) -> dict:
        resp = self.auth.request(
            "GET", f"{_CAMINHO}/{self._id(collection_id)}", headers=self._cabecalhos()
        )
        resp.raise_for_status()
        return resp.json()

    def cancelar(self, collection_id: str) -> None:
        resp = self.auth.request(
            "DELETE", f"{_CAMINHO}/{self._id(collection_id)}", headers=self._cabecalhos()
        )
        resp.raise_for_status()  # 204 sem corpo
        return None
