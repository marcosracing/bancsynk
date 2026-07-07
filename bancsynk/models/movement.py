"""Modelo padronizado de movimento bancario."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BankMovement:
    banco: str
    conta_id: str
    data: str
    valor: Decimal
    descricao: str
    documento: str | None = None
    raw_id: str | None = None
