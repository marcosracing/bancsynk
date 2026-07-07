# Itau API Discovery - BancSynk

**Data:** 2026-07-07
**Status:** discovery documental, sem credenciais Itau

## Conclusao

O Itau pode ser candidato para o BancSynk, mas nao substitui o bloqueio BTG como caminho imediato sem onboarding bancario. Para consulta de extrato/saldo, o caminho oficial e o produto **Extrato (Account Statement)** no Itau Developers, com credenciais e certificado dinamico/mTLS.

## O que esta disponivel

No portal Itau Developers aparecem produtos e APIs relacionados a:

- Open Finance;
- Pix no Itau;
- Iniciacao de pagamentos;
- Banco Tesoureiro;
- Cambio e comercio exterior;
- Extrato (Account Statement), via documentacao de credenciais/certificado.

Para BancSynk, o candidato relevante e **Extrato (Account Statement)**, pois cobre a necessidade de consulta de movimentacao financeira para conciliacao.

## Requisitos tecnicos identificados

- Produto contratado/habilitado junto ao Itau.
- Acesso ao portal Itau Developers.
- Credenciais: `client_id`, `client_secret` ou token temporario de onboarding, conforme etapa.
- Certificado dinamico emitido pelo STS Itau.
- Chave privada correspondente ao certificado.
- Consumo das APIs com OAuth 2.0 Client Credentials + mTLS.
- Em producao, chamada com `Authorization: Bearer {access_token}` e certificado configurado.

## Implicacao para BancSynk

O adaptador Itau deve nascer separado do fluxo BTG:

```text
bancsynk/adapters/itau/
  auth.py              # STS/OAuth client_credentials + mTLS
  certificate.py       # paths/validacao/renovacao de certificado
  statement.py         # extrato Account Statement
  README.md            # onboarding e variaveis de ambiente
```

Variaveis esperadas:

```text
ITAU_ENV=
ITAU_CLIENT_ID=
ITAU_CLIENT_SECRET=
ITAU_CERT_PATH=
ITAU_KEY_PATH=
ITAU_STS_URL=
ITAU_API_BASE_URL=
```

## Riscos

- Sem produto contratado, nao ha discovery real.
- Certificado dinamico e chave privada sao ativos sensiveis e precisam ficar fora do git.
- O fluxo de credenciais do Itau tem etapas de onboarding e renovacao; nao e apenas Client ID + Secret.
- A documentacao completa de APIs e sandbox exige login/contratacao no portal.

## Decisao recomendada

Nao trocar BTG por Itau como Fase 0 imediata sem antes confirmar com gerente/portal:

1. se a Racing tem produto **Extrato (Account Statement)** habilitado;
2. se e possivel gerar credenciais de homologacao;
3. se o certificado dinamico pode ser emitido agora;
4. quais endpoints e OpenAPI estao disponiveis apos login.

Enquanto isso, manter Itau como **Fase 0B - discovery de alternativa bancaria**, paralela ao desbloqueio comercial do BTG.

## Fontes oficiais

- https://devportal.itau.com.br/como-comecar
- https://devportal.itau.com.br/nossas-apis/openfinance
- https://devportal.itau.com.br/pre-requisitos-para-se-conectar-ao-ambiente-itau
- https://devportal.itau.com.br/certificado-dinamico
- https://devportal.itau.com.br/certificado-dinamico-credenciais
- https://devportal.itau.com.br/como-fazer-a-primeira-chamada-a-uma-api
