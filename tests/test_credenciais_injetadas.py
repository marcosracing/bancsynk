"""BS-01..03: credenciais injetadas, endereco seguro e Open Finance (sem rede real)."""

from __future__ import annotations

import pytest

from bancsynk.adapters.btg import auth as auth_mod
from bancsynk.adapters.btg.accounts import BTGReadOnlyAdapter
from bancsynk.adapters.btg.auth import BTGAuth, SANDBOX_COMPANY_ID
from bancsynk.gateway import BancSynk


class Cofre:
    def __init__(self, **campos):
        self.dados = dict(campos)
        self.salvos = []

    def get(self, campo):
        return self.dados.get(campo, "")

    def save(self, campo, valor):
        self.salvos.append(campo)
        self.dados[campo] = valor


class Resp:
    def __init__(self, status=200, corpo=None):
        self.status_code = status
        self._corpo = corpo if corpo is not None else {}
        self.text = "CORPO-SECRETO"

    def json(self):
        return self._corpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http")


def _cofre(ambiente="sandbox", **extra):
    base = dict(
        CLIENT_ID="client-falso",
        CLIENT_SECRET="segredo-falso",
        ACCESS_TOKEN="acesso-falso",
        REFRESH_TOKEN="refresh-falso",
        AMBIENTE=ambiente,
        COMPANY_CNPJ="11222333000181",
        REDIRECT_URI="https://app.exemplo.com.br/cb",
    )
    base.update(extra)
    return Cofre(**base)


@pytest.fixture
def ambiente_hostil(monkeypatch):
    """Variaveis de ambiente com valores que nao podem vazar para o cofre."""
    for k in ("BTG_CLIENT_ID", "BTG_CLIENT_SECRET", "BTG_ACCESS_TOKEN", "BTG_REFRESH_TOKEN",
              "BANCSYNC_208_77_CLIENT_ID", "BANCSYNC_208_77_ACCESS_TOKEN", "BTG_BASE_URL"):
        monkeypatch.setenv(k, "https://evil.com" if k.endswith("URL") else "ENV-FALSO")


def test_get_adapter_repassa_credenciais(ambiente_hostil):
    c = _cofre()
    ad = BancSynk(enable_santander=False).get_adapter("208", company_id=5, credenciais=c)
    assert isinstance(ad, BTGReadOnlyAdapter)
    assert ad.auth.credenciais is c


def test_credenciais_leem_so_do_cofre(ambiente_hostil):
    a = BTGAuth(company_id="77", credenciais=_cofre())
    assert a.client_id == "client-falso"
    assert a.client_secret == "segredo-falso"
    assert a.access_token == "acesso-falso"
    assert a.base_url == "https://api.sandbox.empresas.btgpactual.com"
    assert a.auth_url == "https://id.sandbox.btgpactual.com/oauth2/token"
    # Cofre sem o campo: vazio, sem cair no ambiente.
    vazio = BTGAuth(company_id="77", credenciais=Cofre())
    assert vazio.client_id == "" and vazio.access_token == ""


def test_nao_le_os_environ_para_credencial(monkeypatch):
    lidos = []

    class Espiao(dict):
        def get(self, k, d=None):
            lidos.append(k)
            return super().get(k, d)

        def __getitem__(self, k):
            lidos.append(k)
            return super().__getitem__(k)

        def __iter__(self):
            lidos.append("*iter*")
            return super().__iter__()

    monkeypatch.setattr(auth_mod.os, "environ", Espiao({"BTG_CLIENT_ID": "x"}))
    a = BTGAuth(company_id="1", credenciais=_cofre())
    _ = (a.client_id, a.client_secret, a.access_token, a.refresh_token, a.scope,
         a.redirect_uri, a.base_url, a.auth_url, a.authorize_url, a._resolve_path("/{companyId}/x"))
    assert lidos == []


def test_ambiente_producao_define_enderecos_e_cnpj_injetado(ambiente_hostil):
    a = BTGAuth(company_id="1", credenciais=_cofre("producao"))
    assert a.base_url == "https://api.empresas.btgpactual.com"
    assert a.auth_url == "https://id.btgpactual.com/oauth2/token"
    assert a.authorize_url == "https://id.btgpactual.com/oauth2/authorize"
    assert a._resolve_path("/{companyId}/banking") == "/11222333000181/banking"


def test_sandbox_usa_cnpj_fixo(ambiente_hostil):
    a = BTGAuth(company_id="1", credenciais=_cofre("sandbox"))
    assert a._resolve_path("/{companyId}/banking") == f"/{SANDBOX_COMPANY_ID}/banking"


def test_refresh_grava_pelo_save(monkeypatch, ambiente_hostil):
    c = _cofre()
    chamadas = []

    def post(url, **kw):
        chamadas.append(url)
        return Resp(200, {"access_token": "novo-acesso", "refresh_token": "novo-refresh", "expires_in": 3600})

    monkeypatch.setattr(auth_mod.requests, "post", post)
    a = BTGAuth(company_id="1", credenciais=c)
    assert a.refresh_access_token() is True
    assert chamadas == ["https://id.sandbox.btgpactual.com/oauth2/token"]
    assert c.salvos == ["ACCESS_TOKEN", "REFRESH_TOKEN"]
    assert c.dados["ACCESS_TOKEN"] == "novo-acesso"


def test_sem_credenciais_nada_muda(monkeypatch):
    a = BTGAuth(company_id="9")
    assert a.credenciais is None
    monkeypatch.setattr(auth_mod, "BTG_ENV", "sandbox")
    assert a._resolve_path("/{companyId}/x") == f"/{SANDBOX_COMPANY_ID}/x"
    assert BancSynk(enable_santander=False).get_adapter("208", company_id=9).auth.credenciais is None


# ── BS-02: endereco seguro ────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "https://evil.com/oauth2/token",
    "http://id.btgpactual.com/oauth2/token",
    "https://id.btgpactual.com.evil.com/oauth2/token",
    "https://evilbtgpactual.com/x",
    "https://user:pw@id.btgpactual.com/x",
    "",
])
def test_validar_url_recusa(url):
    with pytest.raises(PermissionError):
        auth_mod.validar_url_btg(url)


@pytest.mark.parametrize("url", [
    "https://btgpactual.com/x",
    "https://id.btgpactual.com/oauth2/token",
    "https://api.sandbox.empresas.btgpactual.com/a",
])
def test_validar_url_aceita(url):
    assert auth_mod.validar_url_btg(url) == url


def _sem_rede(monkeypatch):
    def proibido(*a, **k):
        raise AssertionError("requests nao pode ser chamado")

    monkeypatch.setattr(auth_mod.requests, "post", proibido)
    monkeypatch.setattr(auth_mod.requests, "request", proibido)


@pytest.mark.parametrize("url", ["https://evil.com/oauth2/token", "http://id.btgpactual.com/oauth2/token"])
def test_exchange_refresh_request_recusam_host_ruim(monkeypatch, url):
    _sem_rede(monkeypatch)
    a = BTGAuth(company_id="1", credenciais=_cofre())
    monkeypatch.setattr(BTGAuth, "auth_url", property(lambda s: url))
    monkeypatch.setattr(BTGAuth, "base_url", property(lambda s: url))
    with pytest.raises(PermissionError):
        a.exchange_code("code-falso")
    with pytest.raises(PermissionError):
        a.refresh_access_token()
    with pytest.raises(PermissionError):
        a.request("GET", "/{companyId}/banking/accounts")


def test_log_de_erro_nao_traz_corpo(monkeypatch, caplog, ambiente_hostil):
    monkeypatch.setattr(auth_mod.requests, "post", lambda *a, **k: Resp(400))
    a = BTGAuth(company_id="1", credenciais=_cofre())
    with caplog.at_level("DEBUG"):
        with pytest.raises(RuntimeError):
            a.exchange_code("code-falso")
    texto = caplog.text
    for proibido in ("CORPO-SECRETO", "code-falso", "segredo-falso", "acesso-falso", "refresh-falso"):
        assert proibido not in texto


# ── BS-03: Open Finance ───────────────────────────────────────────────────

def test_get_contas_open_finance_manda_parametro(monkeypatch):
    chamadas = []

    class FakeAuth:
        def get(self, path, params=None):
            chamadas.append((path, params))
            return []

    ad = BTGReadOnlyAdapter(auth=FakeAuth())
    ad.get_contas()
    ad.get_contas(origem="OPEN_FINANCE")
    assert chamadas[0] == ("/{companyId}/banking/accounts", None)
    assert chamadas[1] == ("/{companyId}/banking/accounts", {"accountOrigin": "OPEN_FINANCE"})


def test_loopback_so_no_modo_legado():
    assert auth_mod.validar_url_btg("http://127.0.0.1:5000/x", permitir_local=True)
    with pytest.raises(PermissionError):
        auth_mod.validar_url_btg("http://127.0.0.1:5000/x")
    with pytest.raises(PermissionError):
        auth_mod.validar_url_btg("https://evil.com/x", permitir_local=True)
