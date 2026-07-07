# BancSynk

Gateway bancario transversal da plataforma RLogix.

O BancSynk nasce como projeto proprio, separado do CtrlOne. O CtrlOne/Tesouraria deve consumir este gateway por contrato/API/client, sem carregar adaptadores bancarios, certificados ou detalhes de autenticacao dentro do repo `rlogix`.

## Escopo da Fase 1

Fase 1 e estritamente read-only para BTG Pactual sandbox:

- autenticacao OAuth2 `client_credentials`;
- consulta de contas;
- consulta de saldo;
- consulta de extrato.

Observacao apos leitura da documentacao BTG Empresas: `client_credentials` valida a autenticacao aplicacao-a-aplicacao, mas as APIs de banking, incluindo conta/saldo/extrato, exigem Authorization Code quando houver acesso a dados de conta. Portanto, a primeira prova tecnica deve separar:

- token de aplicacao: `client_credentials`, usando `Client ID + Secret`;
- token de banking: Authorization Code com consentimento, para contas/saldo/extrato.

Pix pagamento, boletos, tributos, DDA, webhooks e qualquer operacao de escrita ficam fora da Fase 1. As interfaces existem apenas como direcao futura, sem implementacao ativa.

## Estrutura

```text
BancSynk/
  bancsynk/
    gateway.py
    adapters/
      base.py
      btg/
        auth.py
        accounts.py
        sandbox.py
      itau/
      safra/
    models/
    sync/
    docs/
  scripts/
  tests/
```

## Uso interno

```python
from bancsynk.gateway import BancSynk

bs = BancSynk()
health = bs.health()
contas = bs.get_contas("btg")
saldo = bs.get_saldo("btg", conta_id="...")
extrato = bs.get_extrato("btg", conta_id="...", data_ini="2026-07-01", data_fim="2026-07-07")
```

## Variaveis de ambiente

Copie `.env.example` para `.env` e preencha localmente. O `.env`, certificados e resultados de discovery ficam fora do git.

```text
BTG_CLIENT_ID=
BTG_CLIENT_SECRET=
BTG_ENV=sandbox
BTG_REDIRECT_URI=https://localhost.com
BTG_SCOPE=
BTG_CERT_PATH=
BTG_KEY_PATH=
```

`BTG_CERT_PATH` e `BTG_KEY_PATH` sao opcionais. No app BTG atual, o fluxo esperado nao usa certificado/mTLS.

## Discovery BTG

O discovery e manual e controlado:

```bash
python3 scripts/discover_btg.py
```

O resultado e salvo em `bancsynk/docs/discovery_btg.json`, ignorado pelo git por poder conter payload bancario sensivel.

## Authorization Code

Para banking, gere a URL de consentimento:

```bash
python3 scripts/build_btg_auth_url.py
```

Abra a URL no navegador, faca login/consentimento e copie o `code` retornado na `redirect_uri`.

Depois troque o codigo por token:

```bash
python3 scripts/exchange_btg_code.py --code "CODIGO_RETORNADO"
```

O token e salvo em `bancsynk/docs/btg_tokens.local.json`, ignorado pelo git.

## Contrato com CtrlOne

O CtrlOne nao deve importar detalhes internos de `bancsynk.adapters.*`. O acoplamento recomendado e um client fino na Tesouraria chamando somente o gateway ou uma API HTTP futura.
