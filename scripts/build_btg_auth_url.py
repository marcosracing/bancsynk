"""Imprime a URL de consentimento BTG para Authorization Code."""

from __future__ import annotations

from bancsynk.adapters.btg.auth_code import get_authorize_url


def main() -> int:
    print(get_authorize_url())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
