"""Fluxo Authorization Code do BTG Id."""

from __future__ import annotations

import os
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()

DEFAULT_SCOPE = (
    "openid "
    "empresas.btgpactual.com/accounts.readonly "
    "brn:btg:empresas:openfinance:accounts:info.readonly "
    "brn:btg:empresas:openfinance:accounts:balances.readonly"
)


def get_authorize_url(state: str) -> str:
    if not state:
        raise ValueError("state obrigatorio no consentimento OAuth.")
    authorize_url = os.environ.get(
        "BTG_AUTHORIZE_URL",
        "https://id.sandbox.btgpactual.com/oauth2/authorize",
    )
    params = {
        "client_id": os.environ["BTG_CLIENT_ID"],
        "response_type": "code",
        "redirect_uri": os.environ.get("BTG_REDIRECT_URI", "https://localhost.com"),
        "scope": os.environ.get("BTG_SCOPE") or DEFAULT_SCOPE,
        "prompt": "login",
        "state": state,
    }
    return f"{authorize_url}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    token_url = os.environ.get("BTG_AUTH_URL", "https://id.sandbox.btgpactual.com/oauth2/token")
    client_id = os.environ["BTG_CLIENT_ID"]
    client_secret = os.environ["BTG_CLIENT_SECRET"]
    redirect_uri = os.environ.get("BTG_REDIRECT_URI", "https://localhost.com")

    resp = requests.post(
        token_url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        auth=HTTPBasicAuth(client_id, client_secret),
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()
