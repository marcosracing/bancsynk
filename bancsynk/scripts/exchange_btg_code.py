"""Troca authorization code BTG por access_token + refresh_token."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from bancsynk.adapters.btg.auth import BTGAuth


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--company-id", default="1", help="Company id no BancSynk (default: 1)")
    parser.add_argument("--code", required=True, help="Authorization code retornado pelo BTG")
    args = parser.parse_args()

    auth = BTGAuth(company_id=args.company_id)
    print(f"Trocando code por token (company_id={args.company_id})...")
    tokens = auth.exchange_code(args.code)

    # Nao exibimos o token bruto; apenas prefixo curto e flags.
    access = tokens.get("access_token") or ""
    refresh = tokens.get("refresh_token") or ""
    print()
    print("=== TOKENS OBTIDOS ===")
    print(f"access_token:  {access[:12] + '...' if access else 'ausente'}")
    print(f"refresh_token: {'presente' if refresh else 'ausente'}")
    print(f"expires_in:    {tokens.get('expires_in')}s")
    print(f"token_type:    {tokens.get('token_type')}")
    print(f"scope:         {tokens.get('scope')}")
    print()
    print("Tokens gravados em ~/Documents/BancSynk/.env")
    print("check():", auth.check())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
