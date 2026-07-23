"""Consultas read-only do adaptador BTG."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from bancsynk.adapters.base import BankAdapter
from bancsynk.adapters.btg.auth import BTGAuth
from bancsynk.models.dda import BankDDA


class BTGReadOnlyAdapter(BankAdapter):
    """Adaptador BTG limitado a consultas de Fase 1."""

    banco_codigo = "btg"
    banco_nome = "BTG Pactual"
    read_only = True

    def __init__(self, company_id: Optional[str] = None, auth: BTGAuth | None = None) -> None:
        self.company_id: Optional[str] = str(company_id) if company_id is not None else None
        self.auth = auth or BTGAuth(company_id=self.company_id)

    def auth_check(self) -> dict:
        return self.auth.check()

    def get_contas(self) -> list:
        data = self.auth.get("/{companyId}/banking/accounts")
        if isinstance(data, list):
            rows: list = []
            for item in data:
                if isinstance(item, dict) and isinstance(item.get("data"), list):
                    rows.extend(item["data"])
                else:
                    rows.append(item)
            return rows
        if isinstance(data, dict):
            return data.get("accounts") or data.get("contas") or data.get("data") or [data]
        return []

    def get_saldo(self, conta_id: str) -> dict:
        return self.auth.get(f"/{{companyId}}/banking/accounts/{conta_id}/balances")

    def get_extrato(self, conta_id: str, data_ini: str, data_fim: str, pagina: int = 1) -> dict:
        return self.auth.get(
            f"/{{companyId}}/banking/accounts/{conta_id}/statements",
            params={
                "startDate": data_ini,
                "endDate": data_fim,
                "type": "simple",
                "pageSize": 100,
                "page": pagina,
            },
        )

    # ── DDA — GET /direct-debit/debits ───────────────────────────────────────
    def get_dda(
        self,
        page_number: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
        min_due_date: Optional[str] = None,
        max_due_date: Optional[str] = None,
        payee_document: Optional[str] = None,
        payee_bank_code: Optional[str] = None,
        hidden: Optional[bool] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        all_pages: bool = False,
    ) -> Dict[str, Any]:
        """Consulta DDAs no BTG. Contrato oficial:
        GET /direct-debit/debits?pageNumber&pageSize&status&minDueDate&maxDueDate&...

        Retorna:
            {
              "items":      [BankDDA, ...],       # dataclasses parseadas
              "raw":        [dict, ...],          # payload bruto (data[])
              "next":       str | None,           # links.next
              "previous":   str | None,           # links.previous
              "page_number": int,
              "page_size":   int,
              "count":       int,                  # len(items) na página
            }

        Se all_pages=True, itera automaticamente enquanto links.next existir
        e concatena os resultados; nesse caso next=None no final.

        NÃO trata 401 reativo — comportamento documentado como débito para
        Fase 2 (Retry/Refresh reativo).
        """
        params: Dict[str, Any] = {"pageNumber": page_number, "pageSize": page_size}
        if status is not None:
            params["status"] = status
        if min_due_date is not None:
            params["minDueDate"] = min_due_date
        if max_due_date is not None:
            params["maxDueDate"] = max_due_date
        if payee_document is not None:
            params["payeeDocument"] = payee_document
        if payee_bank_code is not None:
            params["payeeBankCode"] = payee_bank_code
        if hidden is not None:
            params["hidden"] = "true" if hidden else "false"
        if min_amount is not None:
            params["minAmount"] = min_amount
        if max_amount is not None:
            params["maxAmount"] = max_amount

        collected_raw: List[Dict[str, Any]] = []
        collected_items: List[BankDDA] = []
        current_page = page_number
        next_link: Optional[str] = None
        previous_link: Optional[str] = None
        while True:
            params["pageNumber"] = current_page
            payload = self.auth.get("/direct-debit/debits", params=params) or {}
            data = payload.get("data") or []
            links = payload.get("links") or {}
            next_link = links.get("next") if isinstance(links, dict) else None
            previous_link = links.get("previous") if isinstance(links, dict) else None
            for row in data:
                if isinstance(row, dict):
                    collected_raw.append(row)
                    collected_items.append(BankDDA.from_api(row))
            if not all_pages or not next_link or not data:
                break
            current_page += 1

        return {
            "items": collected_items,
            "raw": collected_raw,
            "next": next_link if not all_pages else None,
            "previous": previous_link,
            "page_number": page_number if not all_pages else current_page,
            "page_size": page_size,
            "count": len(collected_items),
        }
