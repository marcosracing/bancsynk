"""
Mock interno fiel do BTG Empresas Banking — usado em testes antes de apontar
para o sandbox real.

Endpoints implementados:
  POST /oauth2/token           — grant_type=authorization_code | refresh_token
  GET  /direct-debit/debits    — filtros, paginação, envelope oficial

Contrato: developers.empresas.btgpactual.com. Nenhum campo inventado.

Uso típico com pytest-httpserver:

    from pytest_httpserver import HTTPServer
    from bancsynk.mock.btg_sandbox import BTGMockServer

    def test_algo(httpserver: HTTPServer):
        mock = BTGMockServer(httpserver)
        mock.install()
        # httpserver.url_for("") vira BTG_BASE_URL/BTG_AUTH_URL...
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

# ── Dataset fixo de 8 DDAs fictícios de uma transportadora ──────────────────
# Cenários realistas: diesel (2), pedágio (2), seguro frota, peça, aluguel,
# manutenção. Datas de vencimento espalhadas entre 2026-07-20 e 2026-08-15.
# Mix de status para exercitar filtros. Nenhum dado real.
DDA_DATASET: List[Dict[str, Any]] = [
    {
        "id": "dda-2026-0001",
        "amount": 42350.75,
        "dueDate": "2026-07-20",
        "expirationDate": "2026-08-20",
        "digitableLine": "34191790010104351004791020150008889820000042350",
        "payee": {
            "name": "IPIRANGA POSTOS DE SERVICO S/A",
            "document": "33337122000527",
            "bankCode": "341",
        },
        "hidden": False,
        "status": "CREATED",
    },
    {
        "id": "dda-2026-0002",
        "amount": 8790.40,
        "dueDate": "2026-07-22",
        "expirationDate": "2026-08-22",
        "digitableLine": "23791790010104351009821020150008889820000008790",
        "payee": {
            "name": "CCR RODOVIAS SA",
            "document": "02846056000197",
            "bankCode": "237",
        },
        "hidden": False,
        "status": "SCHEDULED",
    },
    {
        "id": "dda-2026-0003",
        "amount": 15420.00,
        "dueDate": "2026-07-10",
        "expirationDate": "2026-08-10",
        "digitableLine": "10491790010104351001121020150008889820000015420",
        "payee": {
            "name": "PORTO SEGURO CIA DE SEGUROS GERAIS",
            "document": "61198164000160",
            "bankCode": "104",
        },
        "hidden": False,
        "status": "OVERDUE",
    },
    {
        "id": "dda-2026-0004",
        "amount": 3120.90,
        "dueDate": "2026-07-25",
        "expirationDate": "2026-08-25",
        "digitableLine": "20891790010104351007791020150008889820000003120",
        "payee": {
            "name": "SEM PARAR SERVICOS LTDA",
            "document": "07122536000175",
            "bankCode": "208",
        },
        "hidden": False,
        "status": "PAYMENT_PENDING_APPROVAL",
    },
    {
        "id": "dda-2026-0005",
        "amount": 6480.20,
        "dueDate": "2026-08-01",
        "expirationDate": "2026-09-01",
        "digitableLine": "07491790010104351005591020150008889820000006480",
        "payee": {
            "name": "BANCO SAFRA SA - SEGURO CARGA",
            "document": "58160789000128",
            "bankCode": "074",
        },
        "hidden": False,
        "status": "PAYMENT_PROCESSING",
    },
    {
        "id": "dda-2026-0006",
        "amount": 1875.00,
        "dueDate": "2026-08-05",
        "expirationDate": "2026-09-05",
        "digitableLine": "34191790010104351009991020150008889820000001875",
        "payee": {
            "name": "AUTO PECAS TRUCK LTDA",
            "document": "12345678000199",
            "bankCode": "341",
        },
        "hidden": True,
        "status": "CREATED",
    },
    {
        "id": "dda-2026-0007",
        "amount": 22800.00,
        "dueDate": "2026-07-15",
        "expirationDate": "2026-08-15",
        "digitableLine": "33191790010104351002281020150008889820000022800",
        "payee": {
            "name": "IPIRANGA POSTOS DE SERVICO S/A",
            "document": "33337122000527",
            "bankCode": "341",
        },
        "hidden": False,
        "status": "PAYMENT_CONFIRMED",
    },
    {
        "id": "dda-2026-0008",
        "amount": 4560.00,
        "dueDate": "2026-08-15",
        "expirationDate": "2026-09-15",
        "digitableLine": "34191790010104351004561020150008889820000004560",
        "payee": {
            "name": "MECANICA GALO PESADO LTDA",
            "document": "98765432000111",
            "bankCode": "341",
        },
        "hidden": False,
        "status": "CREATED",
    },
]


# ── Estado in-memory do mock ─────────────────────────────────────────────────

@dataclass
class _IssuedToken:
    access: str = "mock-access-token-btg-v1"
    refresh: str = "mock-refresh-token-btg-v1"


class _MockState:
    """Estado mutável entre requests (tokens emitidos, contadores)."""

    def __init__(self) -> None:
        self.token = _IssuedToken()
        self.token_requests: int = 0
        self.dda_requests: int = 0


# ── Filtros ──────────────────────────────────────────────────────────────────

def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _apply_filters(
    rows: List[Dict[str, Any]],
    status: Optional[str],
    min_due: Optional[str],
    max_due: Optional[str],
    payee_document: Optional[str],
    payee_bank_code: Optional[str],
    hidden: Optional[str],
    min_amount: Optional[str],
    max_amount: Optional[str],
) -> List[Dict[str, Any]]:
    out = rows
    if status:
        out = [r for r in out if r["status"] == status]
    if payee_document:
        pd = payee_document.strip()
        out = [r for r in out if r["payee"]["document"] == pd]
    if payee_bank_code:
        out = [r for r in out if r["payee"]["bankCode"] == payee_bank_code.strip()]
    if hidden is not None:
        want = str(hidden).lower() in {"true", "1", "yes"}
        out = [r for r in out if r["hidden"] is want]
    dmin = _parse_date(min_due)
    dmax = _parse_date(max_due)
    if dmin:
        out = [r for r in out if _parse_date(r["dueDate"]) and _parse_date(r["dueDate"]) >= dmin]
    if dmax:
        out = [r for r in out if _parse_date(r["dueDate"]) and _parse_date(r["dueDate"]) <= dmax]
    if min_amount:
        try:
            v = Decimal(min_amount)
            out = [r for r in out if Decimal(str(r["amount"])) >= v]
        except (TypeError, ValueError):
            pass
    if max_amount:
        try:
            v = Decimal(max_amount)
            out = [r for r in out if Decimal(str(r["amount"])) <= v]
        except (TypeError, ValueError):
            pass
    return out


def _paginate(
    rows: List[Dict[str, Any]],
    page_number: int,
    page_size: int,
    base_url: str,
    query_string: str,
) -> Dict[str, Any]:
    total = len(rows)
    start = (page_number - 1) * page_size
    end = start + page_size
    slice_ = rows[start:end]
    has_next = end < total
    has_prev = page_number > 1

    def _link(pn: int) -> str:
        from urllib.parse import parse_qsl, urlencode
        pairs = dict(parse_qsl(query_string, keep_blank_values=True))
        pairs["pageNumber"] = str(pn)
        return f"{base_url}?{urlencode(pairs)}"

    links: Dict[str, Optional[str]] = {"next": None, "previous": None}
    if has_next:
        links["next"] = _link(page_number + 1)
    if has_prev:
        links["previous"] = _link(page_number - 1)
    return {"data": slice_, "links": links}


# ── Server ───────────────────────────────────────────────────────────────────

class BTGMockServer:
    """Instala handlers de mock do BTG em uma instância de pytest_httpserver.HTTPServer.

    Uso:
        mock = BTGMockServer(httpserver)
        mock.install()
        base_url = httpserver.url_for("").rstrip("/")
        # aponte BTG_BASE_URL/BTG_AUTH_URL/BTG_AUTHORIZE_URL para base_url
    """

    def __init__(self, httpserver: Any, dataset: Optional[List[Dict[str, Any]]] = None) -> None:
        self.server = httpserver
        self.dataset = list(dataset) if dataset is not None else list(DDA_DATASET)
        self.state = _MockState()

    # ── /oauth2/token ────────────────────────────────────────────────────────
    def _handle_token(self, request) -> Any:
        from werkzeug.wrappers import Response
        self.state.token_requests += 1
        # Basic Auth obrigatório
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Basic "):
            return Response(
                json.dumps({"error": "invalid_client", "error_description": "Basic Auth ausente"}),
                status=401,
                mimetype="application/json",
            )
        # Valida decode
        try:
            base64.b64decode(auth_header.split(" ", 1)[1])
        except Exception:
            return Response(
                json.dumps({"error": "invalid_client", "error_description": "Basic malformado"}),
                status=401,
                mimetype="application/json",
            )
        # grant_type
        form = request.form or {}
        grant = form.get("grant_type")
        if grant not in {"authorization_code", "refresh_token"}:
            return Response(
                json.dumps({"error": "unsupported_grant_type", "error_description": grant or ""}),
                status=400,
                mimetype="application/json",
            )
        if grant == "authorization_code" and not form.get("code"):
            return Response(
                json.dumps({"error": "invalid_request", "error_description": "code ausente"}),
                status=400,
                mimetype="application/json",
            )
        if grant == "refresh_token" and not form.get("refresh_token"):
            return Response(
                json.dumps({"error": "invalid_request", "error_description": "refresh_token ausente"}),
                status=400,
                mimetype="application/json",
            )
        body = {
            "access_token": self.state.token.access,
            "refresh_token": self.state.token.refresh,
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "openid empresas.btgpactual.com/authorized-direct-debits.readonly",
        }
        return Response(json.dumps(body), status=200, mimetype="application/json")

    # ── /direct-debit/debits ────────────────────────────────────────────────
    def _handle_dda(self, request) -> Any:
        from werkzeug.wrappers import Response
        self.state.dda_requests += 1
        # Bearer obrigatório e válido
        auth = request.headers.get("Authorization", "")
        expected = f"Bearer {self.state.token.access}"
        if not auth or not auth.startswith("Bearer "):
            return Response(
                json.dumps({"error": "unauthorized", "error_description": "Bearer ausente"}),
                status=401,
                mimetype="application/json",
            )
        if auth != expected:
            return Response(
                json.dumps({"error": "unauthorized", "error_description": "token invalido"}),
                status=401,
                mimetype="application/json",
            )
        args = request.args
        try:
            page_number = int(args.get("pageNumber") or "1")
        except ValueError:
            page_number = 1
        try:
            page_size = int(args.get("pageSize") or str(len(self.dataset)))
        except ValueError:
            page_size = len(self.dataset)
        filtered = _apply_filters(
            self.dataset,
            status=args.get("status"),
            min_due=args.get("minDueDate"),
            max_due=args.get("maxDueDate"),
            payee_document=args.get("payeeDocument"),
            payee_bank_code=args.get("payeeBankCode"),
            hidden=args.get("hidden"),
            min_amount=args.get("minAmount"),
            max_amount=args.get("maxAmount"),
        )
        base_url = f"{request.host_url.rstrip('/')}/direct-debit/debits"
        envelope = _paginate(filtered, page_number, page_size, base_url, request.query_string.decode("latin-1"))
        return Response(json.dumps(envelope), status=200, mimetype="application/json")

    def install(self) -> None:
        self.server.expect_request("/oauth2/token", method="POST").respond_with_handler(self._handle_token)
        self.server.expect_request("/direct-debit/debits", method="GET").respond_with_handler(self._handle_dda)

    # ── Helpers para os testes ───────────────────────────────────────────────
    def base_url(self) -> str:
        return str(self.server.url_for("")).rstrip("/")

    def invalidate_access_token(self) -> None:
        """Simula revogação. A partir daqui qualquer chamada DDA com o token
        antigo devolve 401 — útil para provar débito Fase 2 (401 reativo)."""
        self.state.token.access = "mock-access-token-btg-v1-REVOKED"
