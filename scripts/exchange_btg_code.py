"""Troca o authorization code BTG por token e salva localmente."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bancsynk.adapters.btg.auth_code import exchange_code


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", required=True, help="Authorization code retornado pelo BTG Id")
    args = parser.parse_args()

    token = exchange_code(args.code)
    output = Path("bancsynk/docs/btg_tokens.local.json")
    output.write_text(json.dumps(token, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Token salvo em {output}")
    print(f"scope={token.get('scope', '')}")
    print(f"expires_in={token.get('expires_in', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
