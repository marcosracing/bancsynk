"""Discovery read-only dos endpoints BTG sandbox."""

from __future__ import annotations

import json
from pathlib import Path

from bancsynk.adapters.btg.auth import BTG_BASE_URL, BTG_ENV, BTGAuth
from bancsynk.adapters.btg.sandbox import READ_ONLY_ENDPOINTS


def main() -> int:
    auth = BTGAuth()
    check = auth.check()
    print("=== AUTH CHECK ===")
    print(json.dumps(check, indent=2, ensure_ascii=False))

    if not check.get("ok"):
        print("\nConfigure .env e certificados antes do discovery.")
        return 0

    resultados = {}
    for method, path, descricao in READ_ONLY_ENDPOINTS:
        try:
            resp = auth.request(method, path)
            resultados[path] = {
                "descricao": descricao,
                "status": resp.status_code,
                "ok": resp.status_code < 400,
                "preview": resp.text[:200],
            }
            print(f"[{resp.status_code}] {path} - {descricao}")
        except Exception as exc:
            resultados[path] = {
                "descricao": descricao,
                "status": "ERR",
                "ok": False,
                "error": str(exc)[:200],
            }
            print(f"[ERR] {path} - {exc}")

    output = Path("bancsynk/docs/discovery_btg.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "ambiente": BTG_ENV,
                "base_url": BTG_BASE_URL,
                "endpoints": resultados,
                "ok_count": sum(1 for v in resultados.values() if v.get("ok")),
                "total": len(resultados),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nDiscovery salvo em {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
