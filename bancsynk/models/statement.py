"""Modelo padronizado de extrato bancario."""

from __future__ import annotations

from dataclasses import dataclass, field

from bancsynk.models.movement import BankMovement


@dataclass(frozen=True)
class BankStatement:
    banco: str
    conta_id: str
    data_ini: str
    data_fim: str
    movimentos: list[BankMovement] = field(default_factory=list)
