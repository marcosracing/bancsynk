"""Contrato base dos adaptadores bancarios."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BankAdapter(ABC):
    """Interface comum para os bancos conectados ao BancSynk."""

    banco_codigo: str = ""
    banco_nome: str = ""
    read_only: bool = True

    @abstractmethod
    def auth_check(self) -> dict:
        """Verifica conectividade e autenticacao."""

    @abstractmethod
    def get_contas(self) -> list:
        """Retorna contas disponiveis."""

    @abstractmethod
    def get_saldo(self, conta_id: str) -> dict:
        """Retorna saldo atual de uma conta."""

    @abstractmethod
    def get_extrato(self, conta_id: str, data_ini: str, data_fim: str, pagina: int = 1) -> dict:
        """Retorna extrato padronizado do periodo."""

    def send_pix(self, payload: dict) -> dict:
        raise NotImplementedError("Pix pagamento esta fora da Fase 1 read-only")

    def create_boleto(self, payload: dict) -> dict:
        raise NotImplementedError("Cobranca/boleto esta fora da Fase 1 read-only")

    def pay_boleto(self, payload: dict) -> dict:
        raise NotImplementedError("Pagamento de boleto esta fora da Fase 1 read-only")

    def get_dda(self, data_ini: str, data_fim: str) -> list:
        raise NotImplementedError("DDA esta fora da Fase 1 read-only")
