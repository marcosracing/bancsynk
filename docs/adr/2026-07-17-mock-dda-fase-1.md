# ADR — 2026-07-17 · Mock interno BTG DDA (Fase 1)

**Status:** APROVADO (Fase 1)
**Escopo:** BancSynk + CtrlOne
**Precedência:** ADR-0042 (BancSynk)

## Contexto
A integração real com a API DDA do BTG (`GET /direct-debit/debits`) depende de:

- credenciais Client ID/Secret ativas por CNPJ,
- scope `authorized-direct-debits.readonly` habilitado no BTG Id,
- eventualmente mTLS/certificado por empresa,
- conectividade externa à VM.

Antes de apontar para o sandbox real do BTG, precisamos comprovar o
end-to-end interno: cliente → adapter → gateway → rota CtrlOne, com
resposta estruturalmente idêntica ao contrato oficial.

## Decisão
1. **Mock interno fiel ao contrato oficial** em `bancsynk/mock/btg_sandbox.py`.
2. Nenhum campo inventado. Todo o schema espelha
   `developers.empresas.btgpactual.com` para `POST /oauth2/token` e
   `GET /direct-debit/debits`.
3. Switch de ambiente por env: `BTG_BASE_URL` + `BTG_AUTH_URL` +
   `BTG_AUTHORIZE_URL`. O adapter não muda; só a URL alvo muda.
4. Autenticação continua sendo Authorization Code + Refresh Token
   existentes; o mock aceita Basic Auth e devolve tokens fictícios.
5. Dataset de 8 DDAs realistas de transportadora (diesel, pedágio,
   seguro frota, peças, manutenção) com 6 status distintos para
   exercitar filtros.

## Contrato coberto (oficial)
- `POST /oauth2/token`: grant_type ∈ {`authorization_code`, `refresh_token`}
- `GET /direct-debit/debits`: query params `pageNumber`, `pageSize`,
  `status`, `minDueDate`, `maxDueDate`, `payeeDocument`, `payeeBankCode`,
  `hidden`, `minAmount`, `maxAmount`.
- Envelope: `{ "data": [...], "links": { "next": ..., "previous": ... } }`.
- Status válidos: `CREATED`, `OVERDUE`, `PAYMENT_PENDING_APPROVAL`,
  `PAYMENT_PROCESSING`, `PAYMENT_CONFIRMED`, `SCHEDULED`.

## O que foi implementado
- `bancsynk/mock/btg_sandbox.py` — `BTGMockServer` instalável em
  `pytest_httpserver.HTTPServer`.
- `bancsynk/models/dda.py` — `BankDDA` dataclass + `from_api()`.
- `bancsynk/adapters/btg/accounts.py::BTGReadOnlyAdapter.get_dda()`
  com todos os filtros oficiais + flag `all_pages` opcional.
- `bancsynk/adapters/btg/sandbox.py::READ_ONLY_ENDPOINTS` inclui DDA.
- `bancsynk/gateway.py::BancSynk.get_dda()` delegando ao adapter.
- CtrlOne: `GET /api/bancsynk/integracoes/<id>/dda` — query params
  espelham o contrato BTG.
- `tests/test_dda_mock.py` — 8 testes cobrindo caminho feliz,
  filtros, paginação, 401, resposta vazia, sanity token.
- `pyproject.toml` — dependência de teste `pytest-httpserver>=1.0`.

## Débitos explícitos (Fase 2)
Estes NÃO foram implementados nesta fase e estão registrados como
tarefas para a próxima:

1. **401 reativo → refresh automático**. Hoje `raise_for_status()`
   explode com `HTTPError` no primeiro 401. Um teste explícito
   (`test_dda_401_com_token_invalido_estoura_hoje`) documenta o
   comportamento atual.
2. **Retry/backoff** para 5xx transientes e 429. Sem `tenacity`,
   sem `urllib3.Retry`.
3. **Rate limit / `Retry-After`**. Nenhuma leitura do header.
4. **Auditoria persistente** de chamadas externas (request/response
   sem segredo, corpo com hash). Fora do escopo Fase 1.
5. **Painel operacional DDA no CtrlOne**. Rota existe, UI não.
6. **Apontamento para o sandbox real BTG**. Só depois de:
   habilitar plano no BTG, obter credenciais reais, ter refresh
   reativo (débito 1) e retry (débito 2) prontos.

## Como apontar para o mock em teste manual
```bash
# 1. Rodar um pytest-httpserver isolado (ou reaproveitar em teste)
# 2. Setar no BancSynk/.env:
BTG_BASE_URL=http://127.0.0.1:8123
BTG_AUTH_URL=http://127.0.0.1:8123/oauth2/token
BTG_AUTHORIZE_URL=http://127.0.0.1:8123/oauth2/authorize
BANCSYNC_208_1_ACCESS_TOKEN=mock-access-token-btg-v1
# 3. GET /api/bancsynk/integracoes/1/dda no CtrlOne local
```

## Riscos residuais
- **Baixo:** divergência silenciosa se BTG alterar contrato. Mitigação: revisar
  este mock no início de cada iteração.
- **Baixo:** confusão operador — chip da UI ainda mostra estado do
  Oracle, não sinaliza modo mock. Aceito para Fase 1.

## Referências
- ADR-0042 (BancSynk gateway)
- `developers.empresas.btgpactual.com` (contrato oficial)
- Fase 0 discovery: `docs/adr/_handoff/2026-07-17-...` no CtrlOne
