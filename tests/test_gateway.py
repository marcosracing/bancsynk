import os

from bancsynk.gateway import BancSynk
from bancsynk.adapters.btg.auth_code import get_authorize_url


def _clear_santander_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("BANCSYNC_033_"):
            monkeypatch.delenv(key, raising=False)


def _clear_btg_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("BANCSYNC_208_") or key.startswith("BTG_"):
            monkeypatch.delenv(key, raising=False)


def test_gateway_registers_btg_adapter_without_credentials():
    gateway = BancSynk()

    adapter = gateway.get_adapter("btg")

    assert adapter.banco_codigo == "btg"
    assert adapter.read_only is True


def test_gateway_registers_btg_adapter_by_bank_code():
    gateway = BancSynk()

    adapter = gateway.get_adapter("208")

    assert adapter.banco_codigo == "btg"
    assert adapter.banco_nome == "BTG Pactual"
    assert adapter.read_only is True


def test_btg_get_adapter_returns_company_scoped_instance():
    adapter = BancSynk().get_adapter("208", company_id=1)

    assert adapter.banco_codigo == "btg"
    assert adapter.company_id == "1"


def test_btg_auth_check_with_credentials_without_token(monkeypatch):
    _clear_btg_env(monkeypatch)
    monkeypatch.setenv("BANCSYNC_208_1_CLIENT_ID", "btg-client")
    monkeypatch.setenv("BANCSYNC_208_1_CLIENT_SECRET", "btg-secret")

    result = BancSynk().get_adapter("208", company_id=1).auth_check()

    assert result["ok"] is False
    assert result["has_client_id"] is True
    assert result["has_secret"] is True
    assert "consentimento pendente" in result["msg"]


def test_write_operations_are_blocked_in_phase_1():
    adapter = BancSynk().get_adapter("btg")

    try:
        adapter.send_pix({})
    except NotImplementedError as exc:
        assert "Fase 1 read-only" in str(exc)
    else:
        raise AssertionError("send_pix deveria estar bloqueado na Fase 1")


def test_authorize_url_uses_authorization_code(monkeypatch):
    monkeypatch.setenv("BTG_CLIENT_ID", "client-123")
    monkeypatch.setenv("BTG_REDIRECT_URI", "https://localhost.com")
    monkeypatch.setenv("BTG_SCOPE", "openid empresas.btgpactual.com/accounts.readonly")

    url = get_authorize_url()

    assert "response_type=code" in url
    assert "client_id=client-123" in url
    assert "scope=openid+" in url


def test_btg_gateway_gerar_url_consentimento_by_bank_code(monkeypatch):
    _clear_btg_env(monkeypatch)
    monkeypatch.setenv("BANCSYNC_208_1_CLIENT_ID", "btg-client")
    monkeypatch.setenv(
        "BANCSYNC_208_1_AUTHORIZE_URL",
        "https://id.sandbox.btgpactual.com/oauth2/authorize",
    )

    url = BancSynk().gerar_url_consentimento(
        "208",
        company_id=1,
        redirect_uri="https://localhost.com",
        scope="openid empresas.btgpactual.com/accounts.readonly",
    )

    assert url.startswith("https://id.sandbox.btgpactual.com/oauth2/authorize?")
    assert "response_type=code" in url
    assert "client_id=btg-client" in url
    assert "scope=openid+" in url
    assert "redirect_uri=https%3A%2F%2Flocalhost.com" in url


def test_btg_trocar_code_uses_basic_auth_and_saves_tokens(monkeypatch):
    _clear_btg_env(monkeypatch)
    monkeypatch.setenv("BANCSYNC_208_1_CLIENT_ID", "btg-client")
    monkeypatch.setenv("BANCSYNC_208_1_CLIENT_SECRET", "btg-secret")
    monkeypatch.setenv("BANCSYNC_208_1_AUTH_URL", "https://id.sandbox.btgpactual.com/oauth2/token")

    captured = {}
    saved = {}

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "access_token": "BTG-AT",
                "refresh_token": "BTG-RT",
                "expires_in": 86400,
                "token_type": "Bearer",
                "scope": "openid",
            }

    def fake_post(url, data=None, auth=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["data"] = data
        captured["auth"] = auth
        return FakeResp()

    def fake_save(banco, company_id, campo, valor):
        saved[(banco, str(company_id), campo)] = valor

    import requests as _requests

    monkeypatch.setattr(_requests, "post", fake_post)
    monkeypatch.setattr("bancsynk.config.save_credential", fake_save)

    result = BancSynk().trocar_code(
        "208", company_id=1, code="BTG-CODE", redirect_uri="https://localhost.com"
    )

    assert captured["url"].endswith("/oauth2/token")
    assert captured["auth"].username == "btg-client"
    assert captured["auth"].password == "btg-secret"
    assert captured["data"]["grant_type"] == "authorization_code"
    assert captured["data"]["code"] == "BTG-CODE"
    assert saved[("208", "1", "ACCESS_TOKEN")] == "BTG-AT"
    assert saved[("208", "1", "REFRESH_TOKEN")] == "BTG-RT"
    assert result["ok"] is True
    assert result["has_access_token"] is True
    assert "BTG-AT" not in str(result)
    assert "BTG-RT" not in str(result)


# ── Santander 033 ───────────────────────────────────────────────────────────
def test_gateway_registers_santander_adapter_by_code():
    adapter = BancSynk().get_adapter("033")

    assert adapter.banco_codigo == "033"
    assert adapter.banco_nome == "Santander"
    assert adapter.read_only is True


def test_gateway_registers_santander_adapter_by_alias():
    adapter = BancSynk().get_adapter("santander")

    assert adapter.banco_codigo == "033"
    assert adapter.read_only is True


def test_santander_auth_check_without_credentials(monkeypatch):
    _clear_santander_env(monkeypatch)

    adapter = BancSynk().get_adapter("033", company_id=999)
    result = adapter.auth_check()

    assert result.get("ok") is False
    assert "CLIENT_ID" in result.get("msg", "")


def test_santander_write_operations_blocked():
    adapter = BancSynk().get_adapter("santander")

    try:
        adapter.send_pix({})
    except NotImplementedError as exc:
        assert "Fase 1 read-only" in str(exc)
    else:
        raise AssertionError("send_pix Santander deveria estar bloqueado")


def test_santander_get_adapter_returns_company_scoped_instance():
    gateway = BancSynk()
    adapter = gateway.get_adapter("033", company_id=2)

    assert adapter.banco_codigo == "033"
    assert adapter.company_id == "2"


# ── Santander Authorization Code ────────────────────────────────────────────
def test_santander_gateway_gerar_url_consentimento(monkeypatch):
    _clear_santander_env(monkeypatch)
    monkeypatch.setenv("BANCSYNC_033_2_CLIENT_ID", "sant-client-2")

    url = BancSynk().gerar_url_consentimento(
        "033", company_id=2, redirect_uri="https://localhost.com", scope=""
    )

    assert url.startswith("https://api-sandbox.santander.com/santander/external/oauth/authorize?")
    assert "response_type=code" in url
    assert "client_id=sant-client-2" in url
    assert "scope=ACCLIST.READ+ACCDET.READ+ACCTRAN.READ" in url
    assert "country=BR" in url
    assert "redirect_uri=https%3A%2F%2Flocalhost.com" in url


def test_santander_gateway_alias_gerar_url_consentimento(monkeypatch):
    _clear_santander_env(monkeypatch)
    monkeypatch.setenv("BANCSYNC_033_2_CLIENT_ID", "sant-client-2")

    url = BancSynk().gerar_url_consentimento(
        "santander", company_id=2, redirect_uri="https://localhost.com", scope=""
    )

    assert "response_type=code" in url
    assert "country=BR" in url


def test_santander_build_authorize_url_accepts_state(monkeypatch):
    from bancsynk.adapters.santander.auth import SantanderAuth

    _clear_santander_env(monkeypatch)
    monkeypatch.setenv("BANCSYNC_033_2_CLIENT_ID", "sant-client-2")

    url = SantanderAuth(company_id=2).build_authorize_url(
        redirect_uri="https://localhost.com", state="xyz"
    )

    assert "state=xyz" in url


def test_santander_exchange_code_uses_basic_auth_and_saves_tokens(monkeypatch):
    from bancsynk.adapters.santander import auth as santander_auth_mod
    from bancsynk.adapters.santander.auth import SantanderAuth

    _clear_santander_env(monkeypatch)
    monkeypatch.setenv("BANCSYNC_033_2_CLIENT_ID", "cid-2")
    monkeypatch.setenv("BANCSYNC_033_2_CLIENT_SECRET", "sec-2")

    captured = {}
    saved = {}

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "access_token": "AT-ABC",
                "refresh_token": "RT-XYZ",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "ACCLIST.READ ACCDET.READ ACCTRAN.READ",
            }

    def fake_post(url, data=None, auth=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["data"] = data
        captured["auth"] = auth
        return FakeResp()

    def fake_save(banco, company_id, campo, valor):
        saved[(banco, str(company_id), campo)] = valor

    import requests as _requests

    monkeypatch.setattr(_requests, "post", fake_post)
    monkeypatch.setattr("bancsynk.config.save_credential", fake_save)

    result = SantanderAuth(company_id=2).exchange_code(
        code="AUTHCODE-1", redirect_uri="https://localhost.com"
    )

    # Endpoint e credenciais Basic Auth corretos.
    assert captured["url"].endswith("/oauth/token")
    assert captured["auth"].username == "cid-2"
    assert captured["auth"].password == "sec-2"

    # Body Santander (country obrigatorio, grant_type authorization_code).
    body = captured["data"]
    assert body["grant_type"] == "authorization_code"
    assert body["code"] == "AUTHCODE-1"
    assert body["country"] == "BR"
    assert body["scope"] == "ACCLIST.READ ACCDET.READ ACCTRAN.READ"

    # Tokens salvos via save_credential.
    assert saved[("033", "2", "ACCESS_TOKEN")] == "AT-ABC"
    assert saved[("033", "2", "REFRESH_TOKEN")] == "RT-XYZ"

    # Resposta nao expoe token bruto.
    assert result["ok"] is True
    assert result["has_access_token"] is True
    assert result["has_refresh_token"] is True
    assert result["expires_in"] == 3600
    assert "access_token" not in result
    assert "refresh_token" not in result
    assert "AT-ABC" not in str(result)
    assert "RT-XYZ" not in str(result)


def test_santander_exchange_code_requires_client_credentials(monkeypatch):
    from bancsynk.adapters.santander.auth import SantanderAuth

    _clear_santander_env(monkeypatch)

    try:
        SantanderAuth(company_id=2).exchange_code(
            code="AUTHCODE", redirect_uri="https://localhost.com"
        )
    except ValueError as exc:
        assert "CLIENT_ID" in str(exc) or "CLIENT_SECRET" in str(exc)
    else:
        raise AssertionError("exchange_code sem credenciais deveria falhar com ValueError")
