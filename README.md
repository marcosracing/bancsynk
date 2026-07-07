# BancSynk

Gateway bancario transversal da plataforma RLogix.

O BancSynk nasce como projeto proprio, separado do CtrlOne. O CtrlOne/Tesouraria deve consumir este gateway por contrato/API/client, sem carregar adaptadores bancarios, certificados ou detalhes de autenticacao dentro do repo `rlogix`.

## Escopo da Fase 1

Fase 1 e estritamente read-only para BTG Pactual sandbox:

- autenticacao OAuth2 `client_credentials`;
- consulta de contas;
- consulta de saldo;
- consulta de extrato.

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
BTG_CERT_PATH=bancsynk/adapters/btg/cert/btg.crt
BTG_KEY_PATH=bancsynk/adapters/btg/cert/btg.key
BTG_ENV=sandbox
```

## Discovery BTG

O discovery e manual e controlado:

```bash
python3 scripts/discover_btg.py
```

O resultado e salvo em `bancsynk/docs/discovery_btg.json`, ignorado pelo git por poder conter payload bancario sensivel.

## Contrato com CtrlOne

O CtrlOne nao deve importar detalhes internos de `bancsynk.adapters.*`. O acoplamento recomendado e um client fino na Tesouraria chamando somente o gateway ou uma API HTTP futura.
