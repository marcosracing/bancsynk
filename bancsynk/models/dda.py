"""Modelo padronizado de DDA (Débito Direto Autorizado) BTG.

Espelha o contrato oficial do endpoint GET /direct-debit/debits em
developers.empresas.btgpactual.com. Nenhum campo inventado.

Preserva o payload bruto em `raw` para que consumidores possam ler campos
extras sem quebrar quando o BTG evoluir o schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class BankDDA:
    id: str
    amount: Decimal
    due_date: str
    expiration_date: str
    digitable_line: str
    payee_name: str
    payee_document: str
    payee_bank_code: str
    hidden: bool
    status: str
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "BankDDA":
        payee = data.get("payee") or {}
        amount = data.get("amount")
        if isinstance(amount, Decimal):
            amount_dec = amount
        else:
            try:
                amount_dec = Decimal(str(amount)) if amount is not None else Decimal("0")
            except Exception:
                amount_dec = Decimal("0")
        return cls(
            id=str(data.get("id") or ""),
            amount=amount_dec,
            due_date=str(data.get("dueDate") or ""),
            expiration_date=str(data.get("expirationDate") or ""),
            digitable_line=str(data.get("digitableLine") or ""),
            payee_name=str(payee.get("name") or ""),
            payee_document=str(payee.get("document") or ""),
            payee_bank_code=str(payee.get("bankCode") or ""),
            hidden=bool(data.get("hidden") or False),
            status=str(data.get("status") or ""),
            raw=dict(data),
        )
