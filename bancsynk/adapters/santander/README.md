# BancSynk — Adaptador Santander 033

Status: **Fase 1 read-only**. Sem pagamentos, sem Pix, sem boleto, sem DDA.

## Escopo
- `auth_check` (não-destrutivo)
- `get_contas`, `get_saldo`, `get_extrato`

Herda `BankAdapter`, portanto `send_pix`, `create_boleto`, `pay_boleto` e `get_dda` continuam bloqueados com `NotImplementedError("... Fase 1 read-only")`.

## Credenciais (nunca no Oracle)
Todas em `~/Documents/BancSynk/.env`, chaveadas por empresa:

```
BANCSYNC_033_<COMPANY_ID>_CLIENT_ID
BANCSYNC_033_<COMPANY_ID>_CLIENT_SECRET
BANCSYNC_033_<COMPANY_ID>_ACCESS_TOKEN
BANCSYNC_033_<COMPANY_ID>_REFRESH_TOKEN
BANCSYNC_033_<COMPANY_ID>_AUTHORIZE_URL
BANCSYNC_033_<COMPANY_ID>_AUTH_URL          (default: sandbox oauth/token)
BANCSYNC_033_<COMPANY_ID>_API_BASE_URL
BANCSYNC_033_<COMPANY_ID>_COUNTRY           (default: BR)
BANCSYNC_033_<COMPANY_ID>_ACCOUNTS_PATH
BANCSYNC_033_<COMPANY_ID>_BALANCE_PATH
BANCSYNC_033_<COMPANY_ID>_STATEMENT_PATH
```

Se `API_BASE_URL` ou os `*_PATH` não estiverem configurados, `get_contas/saldo/extrato` levantam `ValueError` com mensagem clara — não inventam schema.

## Uso pelo gateway

```python
from bancsynk.gateway import BancSynk

bs = BancSynk()
adapter = bs.get_adapter("033", company_id=2)   # R1
result = adapter.auth_check()
```

`get_adapter("santander", ...)` também funciona (alias).

## auth_check() sem exception
- Sem `CLIENT_ID`/`CLIENT_SECRET` → `{ok: False, msg: "... CLIENT_ID/CLIENT_SECRET ausentes ..."}`
- Com credenciais mas sem `ACCESS_TOKEN` → `{ok: False, msg: "... consentimento pendente ..."}`
- Com token → `{ok: True, msg: "... credenciais e token presentes."}`

Token nunca é logado nem retornado por inteiro.
