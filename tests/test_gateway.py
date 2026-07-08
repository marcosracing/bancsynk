import os

from bancsynk.gateway import BancSynk
from bancsynk.adapters.btg.auth_code import get_authorize_url


def _clear_santander_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("BANCSYNC_033_"):
            monkeypatch.delenv(key, raising=False)


def test_gateway_registers_btg_adapter_without_credentials():
    gateway = BancSynk()

    adapter = gateway.get_adapter("btg")

    assert adapter.banco_codigo == "btg"
    assert adapter.read_only is True


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
