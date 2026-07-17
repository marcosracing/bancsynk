"""Helpers controlados para sondagem do sandbox BTG."""

from __future__ import annotations

READ_ONLY_ENDPOINTS = [
    ("GET", "/v2/accounts", "Listar contas PJ"),
    ("GET", "/v2/accounts/balance", "Saldo consolidado"),
    ("GET", "/v2/accounts/statement", "Extrato"),
    ("GET", "/direct-debit/debits", "DDA (Debito Direto Autorizado)"),
]
