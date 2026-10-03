"""Gera URL de consentimento BTG para o fluxo Authorization Code."""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

# Permite rodar direto: python3 bancsynk/scripts/build_btg_auth_url.py
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from bancsynk.adapters.btg.auth import BTGAuth


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--company-id", default="1", help="Company id no BancSynk (default: 1)")
    parser.add_argument("--state", default=None,
                        help="Parametro state OAuth2 (gerado se omitido)")
    args = parser.parse_args()
    state = args.state or secrets.token_urlsafe(32)

    auth = BTGAuth(company_id=args.company_id)
    url = auth.get_authorize_url(state=state)
    print(f"state: {state} (confira que volta igual no redirect)")

    print("=== URL DE CONSENTIMENTO BTG ===")
    print(url)
    print()
    print("Passos:")
    print("  1. Abra a URL acima no browser.")
    print("  2. Logue no Internet Banking BTG da empresa.")
    print("  3. Autorize os escopos solicitados.")
    print("  4. Copie o parametro 'code' da URL de redirect.")
    print("  5. Rode:")
    print(
        f"     python3 bancsynk/scripts/exchange_btg_code.py "
        f"--company-id {args.company_id} --code SEU_CODE"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
