"""Fase 1 — testes do adapter BTG.get_dda contra o mock interno.

Não bate no BTG real. Toda a resposta vem do BTGMockServer instalado
sobre pytest-httpserver.

Débitos de Fase 2 (documentados como expectativas explícitas aqui):
  - 401 reativo não força refresh: hoje explode com HTTPError.
  - Sem retry/backoff nem tratamento de 429.
"""

from __future__ import annotations

import base64
import os
from decimal import Decimal

import pytest
import requests

from bancsynk.adapters.btg.accounts import BTGReadOnlyAdapter
from bancsynk.adapters.btg.auth import BTGAuth
from bancsynk.mock.btg_sandbox import BTGMockServer, DDA_DATASET


# ── Fixtures ────────────────────────────────────────────────────────────────

def _install_env(monkeypatch, base_url: str, access_token: str = "") -> None:
    """Aponta todo o auth do BTG para o mock, e injeta credenciais fictícias."""
    # Limpa fallback global BTG_* que polui outros testes
    for key in list(os.environ):
        if key.startswith("BTG_") or key.startswith("BANCSYNC_208_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BTG_BASE_URL", base_url)
    monkeypatch.setenv("BTG_AUTH_URL", f"{base_url}/oauth2/token")
    monkeypatch.setenv("BTG_AUTHORIZE_URL", f"{base_url}/oauth2/authorize")
    monkeypatch.setenv("BANCSYNC_208_1_CLIENT_ID", "mock-client-id")
    monkeypatch.setenv("BANCSYNC_208_1_CLIENT_SECRET", "mock-client-secret")
    if access_token:
        monkeypatch.setenv("BANCSYNC_208_1_ACCESS_TOKEN", access_token)


@pytest.fixture
def btg_mock(httpserver):
    mock = BTGMockServer(httpserver)
    mock.install()
    return mock


# ── 1. Caminho feliz: página 1 completa ─────────────────────────────────────

def test_dda_pagina_1_dataset_completo(monkeypatch, btg_mock):
    _install_env(monkeypatch, btg_mock.base_url(),
                 access_token="mock-access-token-btg-v1")
    adapter = BTGReadOnlyAdapter(company_id=1)
    result = adapter.get_dda(page_number=1, page_size=50)
    assert result["count"] == 8
    assert len(result["items"]) == 8
    # Todos os campos padronizados
    first = result["items"][0]
    assert first.id == "dda-2026-0001"
    assert first.amount == Decimal("42350.75")
    assert first.due_date == "2026-07-20"
    assert first.expiration_date == "2026-08-20"
    assert first.digitable_line.startswith("34191790010104")
    assert first.payee_name == "IPIRANGA POSTOS DE SERVICO S/A"
    assert first.payee_document == "33337122000527"
    assert first.payee_bank_code == "341"
    assert first.hidden is False
    assert first.status == "CREATED"
    # Sem próxima página quando pageSize >= total
    assert result["next"] is None


# ── 2. Filtro por status ────────────────────────────────────────────────────

def test_dda_filtro_status_overdue(monkeypatch, btg_mock):
    _install_env(monkeypatch, btg_mock.base_url(),
                 access_token="mock-access-token-btg-v1")
    adapter = BTGReadOnlyAdapter(company_id=1)
    result = adapter.get_dda(status="OVERDUE")
    assert result["count"] == 1
    assert result["items"][0].status == "OVERDUE"
    assert result["items"][0].id == "dda-2026-0003"


# ── 3. Filtro por minDueDate/maxDueDate ─────────────────────────────────────

def test_dda_filtro_intervalo_vencimento(monkeypatch, btg_mock):
    _install_env(monkeypatch, btg_mock.base_url(),
                 access_token="mock-access-token-btg-v1")
    adapter = BTGReadOnlyAdapter(company_id=1)
    result = adapter.get_dda(
        min_due_date="2026-07-20",
        max_due_date="2026-07-25",
    )
    ids = sorted(it.id for it in result["items"])
    # Deve pegar 20/07, 22/07, 25/07 = 3 registros do dataset
    assert result["count"] == 3
    assert ids == ["dda-2026-0001", "dda-2026-0002", "dda-2026-0004"]


# ── 4. Paginação: pageSize=3, seguir next até esgotar ───────────────────────

def test_dda_paginacao_page_size_3(monkeypatch, btg_mock):
    _install_env(monkeypatch, btg_mock.base_url(),
                 access_token="mock-access-token-btg-v1")
    adapter = BTGReadOnlyAdapter(company_id=1)
    # 8 registros / 3 por página = 3 páginas (3+3+2)
    result = adapter.get_dda(page_number=1, page_size=3, all_pages=True)
    assert result["count"] == 8
    ids = [it.id for it in result["items"]]
    assert len(ids) == 8
    assert len(set(ids)) == 8, "não pode ter duplicata entre páginas"
    # all_pages consumido → next é None ao final
    assert result["next"] is None
    # Sem all_pages: paginação manual devolve next real
    r1 = adapter.get_dda(page_number=1, page_size=3, all_pages=False)
    assert r1["count"] == 3
    assert r1["next"] is not None
    assert "pageNumber=2" in r1["next"]
    r2 = adapter.get_dda(page_number=2, page_size=3, all_pages=False)
    assert r2["count"] == 3
    assert r2["next"] is not None
    assert "pageNumber=3" in r2["next"]
    r3 = adapter.get_dda(page_number=3, page_size=3, all_pages=False)
    assert r3["count"] == 2
    assert r3["next"] is None


# ── 5. 401 com token inválido — DÉBITO Fase 2 (hoje explode) ────────────────

def test_dda_401_com_token_invalido_estoura_hoje(monkeypatch, btg_mock):
    """Documenta débito Fase 2: 401 reativo não força refresh, hoje o
    requests.raise_for_status() explode. Cliente futuro precisa tentar
    refresh_token e reexecutar a chamada."""
    _install_env(monkeypatch, btg_mock.base_url(),
                 access_token="token-que-nao-bate-com-mock")
    adapter = BTGReadOnlyAdapter(company_id=1)
    with pytest.raises(requests.HTTPError) as excinfo:
        adapter.get_dda(page_number=1, page_size=10)
    # Confirma código 401 e mensagem do mock (não bate no BTG real)
    assert excinfo.value.response.status_code == 401


# ── 6. Resposta vazia (filtro que não bate em nada) ────────────────────────

def test_dda_resposta_vazia_filtro_sem_match(monkeypatch, btg_mock):
    _install_env(monkeypatch, btg_mock.base_url(),
                 access_token="mock-access-token-btg-v1")
    adapter = BTGReadOnlyAdapter(company_id=1)
    result = adapter.get_dda(
        min_due_date="2026-12-01",
        max_due_date="2026-12-31",
    )
    assert result["count"] == 0
    assert result["items"] == []
    assert result["raw"] == []
    assert result["next"] is None


# ── 7. Token endpoint funciona (autorização com refresh_token) ─────────────

def test_mock_oauth_token_refresh(monkeypatch, btg_mock):
    """Sanity: o endpoint /oauth2/token do mock aceita refresh_token e
    devolve access_token + refresh_token + expires_in + token_type."""
    creds = base64.b64encode(b"cli:sec").decode("ascii")
    resp = requests.post(
        f"{btg_mock.base_url()}/oauth2/token",
        headers={"Authorization": f"Basic {creds}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "refresh_token", "refresh_token": "rt-abc"},
        timeout=5,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 3600
    assert body["access_token"] == "mock-access-token-btg-v1"
    assert body["refresh_token"] == "mock-refresh-token-btg-v1"


# ── 8. Dataset é lista de dicts com contrato oficial ──────────────────────

def test_dataset_contrato_oficial():
    assert len(DDA_DATASET) == 8
    for row in DDA_DATASET:
        # Campos obrigatórios da resposta oficial
        for key in ("id", "amount", "dueDate", "expirationDate",
                    "digitableLine", "payee", "hidden", "status"):
            assert key in row, f"campo faltante: {key}"
        payee = row["payee"]
        for key in ("name", "document", "bankCode"):
            assert key in payee, f"campo faltante em payee: {key}"
        assert row["status"] in {
            "CREATED", "OVERDUE", "PAYMENT_PENDING_APPROVAL",
            "PAYMENT_PROCESSING", "PAYMENT_CONFIRMED", "SCHEDULED",
        }
