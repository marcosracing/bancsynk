# BTG Contract Discovery - BancSynk

**Data:** 2026-07-07  
**Ambiente:** sandbox  
**Status:** bloqueado por habilitacao bancaria/API

## Resultado

A Fase 0 BTG nao chegou ao consentimento OAuth. O app sandbox existe no portal BTG Empresas e o Client ID/Secret foram configurados localmente, mas o BTG Id retornou `AppNotFoundError` ao tentar iniciar o fluxo Authorization Code.

## Evidencia

```text
Erro: AppNotFoundError
Mensagem: App client not found with id
Ambiente: sandbox
Endpoint testado: https://id.sandbox.btgpactual.com/oauth2/authorize
```

O Client ID confirmado no portal e o Client ID configurado localmente sao iguais. A causa operacional informada foi necessidade de alteracao/habilitacao do plano/API bancario BTG para acesso ao BTG Empresas Developers.

## Impacto

Sem a habilitacao do plano/API:

- nao ha `code` de consentimento;
- nao ha `access_token`/`refresh_token`;
- nao ha chamadas reais de saldo/extrato;
- nao ha schema real de resposta para mapear `BankStatement` e `BankMovement`.

## Estado dos endpoints

| Operacao logica | Status | Observacao |
|---|---|---|
| Authorization Code | Bloqueado | `AppNotFoundError` antes do login |
| Listar contas | Nao executado | depende de token |
| Saldo | Nao executado | depende de token |
| Extrato | Nao executado | depende de token |
| Aplicacoes | Nao executado | depende de token |

## Decisao

Manter o adaptador BTG preparado no BancSynk, mas nao iniciar Fase 1 ate concluir a Fase 0 real.

Proxima tentativa deve ocorrer somente apos:

1. habilitacao/alteracao do plano BTG;
2. confirmacao de que o app sandbox esta publicado para OAuth;
3. nova tentativa de Authorization Code;
4. troca do `code` por token;
5. discovery real dos endpoints.

## Alternativa

Itau foi avaliado como Fase 0B. Para extrato/saldo, o caminho e **Extrato (Account Statement)** com credenciais e certificado dinamico/mTLS; tambem depende de onboarding bancario.
