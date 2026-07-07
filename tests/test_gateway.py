from bancsynk.gateway import BancSynk
from bancsynk.adapters.btg.auth_code import get_authorize_url


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
