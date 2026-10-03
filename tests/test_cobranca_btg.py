"""BB-01..02: cobranca BTG (boleto) e x-response do DDA no sandbox, sem rede real."""

from __future__ import annotations

import pytest

from bancsynk.adapters.btg import auth as auth_mod
from bancsynk.adapters.btg.accounts import BTGReadOnlyAdapter
from bancsynk.adapters.btg.auth import SANDBOX_COMPANY_ID
from bancsynk.adapters.btg.collections import BTGCobrancaAdapter
from bancsynk.gateway import BancSynk


class Cofre:
    def __init__(self, **campos):
        self.dados = dict(campos)

    def get(self, campo):
        return self.dados.get(campo, "")

    def save(self, campo, valor):
        self.dados[campo] = valor


class Resp:
    def __init__(self, status=200, corpo=None):
        self.status_code = status
        self._corpo = corpo if corpo is not None else {}

    def json(self):
        return self._corpo

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http")


def _cofre(ambiente="sandbox"):
    return Cofre(
        CLIENT_ID="client-falso", CLIENT_SECRET="segredo-falso",
        ACCESS_TOKEN="acesso-falso", REFRESH_TOKEN="refresh-falso",
        AMBIENTE=ambiente, COMPANY_CNPJ="11222333000181",
    )


@pytest.fixture
def chamadas(monkeypatch):
    lista = []

    def falso(metodo, url, **kw):
        lista.append((metodo, url, kw))
        return Resp(204 if metodo == "DELETE" else 200, {"collectionId": "c-1", "status": "CREATED"})

    monkeypatch.setattr(auth_mod.requests, "request", falso)
    return lista


def test_adaptador_nao_e_somente_leitura():
    assert BTGCobrancaAdapter(credenciais=_cofre()).read_only is False


def test_tres_metodos_montam_o_caminho_sandbox(chamadas):
    ad = BTGCobrancaAdapter(company_id=5, credenciais=_cofre("sandbox"))
    base = f"https://api.sandbox.empresas.btgpactual.com/{SANDBOX_COMPANY_ID}/banking/collections"
    assert ad.criar({"amount": 10})["collectionId"] == "c-1"
    assert ad.consultar("c-1")["status"] == "CREATED"
    assert ad.cancelar("c-1") is None
    assert [(m, u) for m, u, _ in chamadas] == [
        ("POST", base), ("GET", f"{base}/c-1"), ("DELETE", f"{base}/c-1"),
    ]
    assert chamadas[0][2]["json"] == {"amount": 10}
    for _, _, kw in chamadas:
        assert kw["headers"]["x-response"] == "success"
        assert kw["headers"]["Authorization"] == "Bearer acesso-falso"


def test_producao_usa_cnpj_do_cofre_e_nao_manda_x_response(chamadas):
    ad = BTGCobrancaAdapter(company_id=5, credenciais=_cofre("producao"))
    ad.criar({})
    ad.consultar("c-9")
    assert chamadas[0][1] == "https://api.empresas.btgpactual.com/11222333000181/banking/collections"
    assert chamadas[1][1].endswith("/11222333000181/banking/collections/c-9")
    for _, _, kw in chamadas:
        assert "x-response" not in kw["headers"]


@pytest.mark.parametrize("ruim", ["", "../x", "a/b", "a?b=1", "a b"])
def test_collection_id_invalido_nao_chama_rede(chamadas, ruim):
    ad = BTGCobrancaAdapter(credenciais=_cofre())
    with pytest.raises(ValueError):
        ad.consultar(ruim)
    with pytest.raises(ValueError):
        ad.cancelar(ruim)
    assert chamadas == []


def test_host_fora_do_btg_e_recusado_sem_rede(chamadas, monkeypatch):
    ad = BTGCobrancaAdapter(credenciais=_cofre())
    monkeypatch.setattr(auth_mod.BTGAuth, "base_url", property(lambda s: "https://evil.com"))
    with pytest.raises(PermissionError):
        ad.criar({"amount": 1})
    with pytest.raises(PermissionError):
        ad.cancelar("c-1")
    assert chamadas == []


def test_erro_http_levanta_sem_vazar_corpo(monkeypatch):
    monkeypatch.setattr(auth_mod.requests, "request", lambda *a, **k: Resp(500, {"x": "CORPO-SECRETO"}))
    ad = BTGCobrancaAdapter(credenciais=_cofre())
    with pytest.raises(RuntimeError) as exc:
        ad.criar({})
    assert "CORPO-SECRETO" not in str(exc.value)


def test_gateway_get_cobranca(chamadas):
    c = _cofre()
    ad = BancSynk(enable_santander=False).get_cobranca(company_id=5, credenciais=c)
    assert isinstance(ad, BTGCobrancaAdapter)
    assert ad.auth.credenciais is c


# ── BB-02: DDA ────────────────────────────────────────────────────────────

def test_dda_sandbox_manda_x_response(chamadas):
    chamadas.clear()
    ad = BTGReadOnlyAdapter(company_id=5, credenciais=_cofre("sandbox"))
    # a fixture devolve um dict sem "data": lista vazia
    r = ad.get_dda()
    assert r["count"] == 0
    metodo, url, kw = chamadas[0]
    assert metodo == "GET" and "/banking/direct-debit/debits" in url
    assert kw["headers"]["x-response"] == "success"


def test_dda_producao_nao_manda_x_response(chamadas):
    ad = BTGReadOnlyAdapter(company_id=5, credenciais=_cofre("producao"))
    ad.get_dda()
    assert "x-response" not in chamadas[0][2]["headers"]


def test_cobranca_sem_cofre_e_recusada():
    # Revisão do Codex: escrita no banco nunca no modo legado (aceita localhost).
    import pytest
    from bancsynk.adapters.btg.collections import BTGCobrancaAdapter
    with pytest.raises(ValueError):
        BTGCobrancaAdapter(company_id="1")
