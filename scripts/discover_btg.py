"""Discovery read-only dos endpoints BTG sandbox usando token Authorization Code."""

from __future__ import annotations

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

BTG_ENV = os.environ.get("BTG_ENV", "sandbox")
BTG_BASE_URL = os.environ.get("BTG_BASE_URL", "https://api.sandbox.empresas.btgpactual.com")
TOKEN_PATH = Path("bancsynk/docs/btg_tokens.local.json")

ENDPOINTS = [
    ("GET", "/v2/accounts", "Listar contas PJ"),
    ("GET", "/v2/accounts/statement", "Extrato sem accountId"),
    ("GET", "/v2/accounts/balance", "Saldo sem accountId"),
    ("GET", "/v2/accounts/investments", "Aplicacoes sem accountId"),
    ("GET", "/v2/pix/keys", "Chaves Pix"),
    ("GET", "/v2/payments", "Pagamentos"),
    ("GET", "/v2/dda/charges", "DDA"),
    ("GET", "/v2/webhooks", "Webhooks"),
    ("GET", "/v2/openfinance/accounts", "Open Finance contas"),
    ("GET", "/v1/accounts", "v1 contas"),
]


def _load_token() -> str:
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            f"Token nao encontrado em {TOKEN_PATH}. Execute scripts/exchange_btg_code.py primeiro."
        )
    data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"{TOKEN_PATH} nao contem access_token")
    return token


def _request(method: str, path: str, token: str, params: dict | None = None) -> requests.Response:
    return requests.request(
        method,
        f"{BTG_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=30,
    )


def _safe_body(resp: requests.Response) -> dict:
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text[:500]}


def _extract_accounts(body) -> list:
    if isinstance(body, list):
        return body
    if not isinstance(body, dict):
        return []
    for key in ("data", "accounts", "contas", "items", "content"):
        value = body.get(key)
        if isinstance(value, list):
            return value
    return []


def _account_id(account: dict) -> str | None:
    for key in ("id", "accountId", "account_id", "accountIdentifier"):
        value = account.get(key)
        if value:
            return str(value)
    return None


def _write_contract_report(discovery: dict) -> Path:
    lines = [
        "# BTG Contract Discovery - BancSynk",
        "",
        f"**Ambiente:** {BTG_ENV}",
        f"**Base URL:** `{BTG_BASE_URL}`",
        "**Status:** Fase 0 ADR-0042",
        "",
        "## Endpoints Sondados",
        "",
        "| Path | Status | Descricao | Observacao |",
        "|---|---:|---|---|",
    ]

    for path, info in discovery["endpoints"].items():
        status = info.get("status_http")
        ok = "OK" if info.get("ok") else "FALHA"
        obs = info.get("error") or info.get("preview") or ""
        lines.append(f"| `{path}` | {status} | {info.get('descricao', '')} | {ok}: {str(obs)[:120]} |")

    lines += [
        "",
        "## Contas Detectadas",
        "",
        f"Total detectado: **{len(discovery.get('accounts', []))}**",
        "",
        "| accountId | Campos observados |",
        "|---|---|",
    ]
    for account in discovery.get("accounts", []):
        account_id = account.get("_account_id", "")
        keys = ", ".join(k for k in account.keys() if k != "_account_id")
        lines.append(f"| `{account_id}` | {keys} |")

    lines += [
        "",
        "## Schemas Confirmados",
        "",
    ]
    for path, info in discovery["endpoints"].items():
        if info.get("ok") and info.get("response_sample") is not None:
            lines += [
                f"### `{path}`",
                "",
                "```json",
                json.dumps(info["response_sample"], indent=2, ensure_ascii=False)[:1200],
                "```",
                "",
            ]

    lines += [
        "## Decisoes Pendentes",
        "",
        "- Confirmar campo canonico de `external_transaction_id` no extrato.",
        "- Confirmar paginacao do extrato.",
        "- Confirmar diferenca entre saldo disponivel, contabil e bloqueado.",
        "- Confirmar se aplicacoes usam endpoint proprio ou aparecem no saldo consolidado.",
        "",
        "_Gerado por `scripts/discover_btg.py`._",
    ]

    output = Path("bancsynk/docs/btg_contract_discovery.md")
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def main() -> int:
    token = _load_token()
    print("=== DISCOVERY BTG SANDBOX ===")
    print(f"base_url={BTG_BASE_URL}")
    print("token=***carregado***")

    discovery = {"ambiente": BTG_ENV, "base_url": BTG_BASE_URL, "endpoints": {}, "accounts": []}
    for method, path, descricao in ENDPOINTS:
        try:
            resp = _request(method, path, token)
            body = _safe_body(resp)
            discovery["endpoints"][path] = {
                "descricao": descricao,
                "status_http": resp.status_code,
                "ok": resp.status_code < 400,
                "preview": json.dumps(body, ensure_ascii=False)[:300],
                "response_sample": body if resp.status_code < 400 else None,
            }
            print(f"[{resp.status_code}] {path} - {descricao}")
        except Exception as exc:
            discovery["endpoints"][path] = {
                "descricao": descricao,
                "status_http": "ERR",
                "ok": False,
                "error": str(exc)[:200],
            }
            print(f"[ERR] {path} - {exc}")

    accounts_body = discovery["endpoints"].get("/v2/accounts", {}).get("response_sample")
    accounts = _extract_accounts(accounts_body)
    for account in accounts[:10]:
        if isinstance(account, dict):
            account_id = _account_id(account)
            sanitized = dict(account)
            sanitized["_account_id"] = account_id or ""
            discovery["accounts"].append(sanitized)
            if account_id:
                for sub_path in (
                    f"/v2/accounts/{account_id}/balance",
                    f"/v2/accounts/{account_id}/statement",
                    f"/v2/accounts/{account_id}/investments",
                ):
                    resp = _request(
                        "GET",
                        sub_path,
                        token,
                        params={"startDate": "2026-06-01", "endDate": "2026-06-30"},
                    )
                    body = _safe_body(resp)
                    discovery["endpoints"][sub_path] = {
                        "descricao": f"Conta {account_id}",
                        "status_http": resp.status_code,
                        "ok": resp.status_code < 400,
                        "preview": json.dumps(body, ensure_ascii=False)[:300],
                        "response_sample": body if resp.status_code < 400 else None,
                    }
                    print(f"[{resp.status_code}] {sub_path}")

    output = Path("bancsynk/docs/discovery_btg_raw.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(discovery, indent=2, ensure_ascii=False), encoding="utf-8")
    report = _write_contract_report(discovery)
    ok_count = sum(1 for v in discovery["endpoints"].values() if v.get("ok"))
    print(f"\nRaw local salvo em {output}")
    print(f"Relatorio gerado em {report}")
    print(f"{ok_count} / {len(discovery['endpoints'])} endpoints ativos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
