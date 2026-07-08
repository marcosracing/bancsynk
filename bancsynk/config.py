"""Gerencia credenciais bancarias multiempresa no .env do BancSynk.

Chave padronizada: BANCSYNC_{BANCO}_{COMPANY_ID}_{CAMPO}
Exemplo: BANCSYNC_208_1_CLIENT_ID (BTG, Racing).

Credenciais nunca sao gravadas no banco do CtrlOne — apenas neste .env local.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv, set_key

BANCSYNC_ENV = Path(__file__).resolve().parent.parent / ".env"

load_dotenv(BANCSYNC_ENV)


def env_key(banco: str, company_id, campo: str) -> str:
    return f"BANCSYNC_{str(banco).upper()}_{company_id}_{campo.upper()}"


def save_credential(banco: str, company_id, campo: str, valor: str) -> None:
    key = env_key(banco, company_id, campo)
    set_key(str(BANCSYNC_ENV), key, valor)
    os.environ[key] = valor


def get_credential(banco: str, company_id, campo: str) -> str:
    return os.environ.get(env_key(banco, company_id, campo), "")


def has_credential(banco: str, company_id, campo: str) -> bool:
    return bool(get_credential(banco, company_id, campo))


def get_all_env() -> dict:
    return dotenv_values(str(BANCSYNC_ENV))
