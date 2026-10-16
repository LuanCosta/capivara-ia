# Revisão de emendas, `BASE_TEXT` e substitutivos

## Resultado

Os seis falsos `UNKNOWN` relacionados a emendas foram identificados e
corrigidos. A regra anterior só reconhecia expressões específicas como “Emenda
de Plenário”, “Emenda de Redação” e “Subemenda”. Ela não reconhecia “Emenda nº
99” nem o plural “Emendas de Plenário”.

Após a correção, somente `2545792-26` permanece `UNKNOWN`. Sua descrição informa
alteração de regime decorrente de outro requerimento, mas não descreve com
segurança a votação atual.

## Seis casos corrigidos

| votingId | Evidência na descrição | Contexto da abertura | Classificação proposta |
|---|---|---|---|
| `2610975-23` | Rejeitada a Emenda nº 102 | DTQ/destaque da emenda | `AMENDMENT`, mecanismo `HIGHLIGHT_OR_DTQ`, revisão humana |
| `2618177-73` | Rejeitadas as Emendas de Plenário | emendas ao substitutivo | `AMENDMENT`, revisão humana de conjunto |
| `2624161-25` | Rejeitada a Emenda nº 99 | DTQ/destaque da emenda | `AMENDMENT`, mecanismo `HIGHLIGHT_OR_DTQ`, revisão humana |
| `2624161-43` | Rejeitada a Emenda nº 2 | DTQ/destaque da emenda | `AMENDMENT`, mecanismo `HIGHLIGHT_OR_DTQ`, revisão humana |
| `2624161-46` | Rejeitada a Emenda nº 96 | DTQ/destaque da emenda | `AMENDMENT`, mecanismo `HIGHLIGHT_OR_DTQ`, revisão humana |
| `2624161-49` | Rejeitada a Emenda nº 97 | DTQ/destaque da emenda | `AMENDMENT`, mecanismo `HIGHLIGHT_OR_DTQ`, revisão humana |

A escolha de `AMENDMENT` preserva o objeto decidido indicado pelo resultado. O
DTQ/destaque é registrado separadamente como mecanismo contextual. Essa decisão
continua pendente de validação especializada e não é declarada como verdade.

## Revisão de `BASE_TEXT`

Antes da revisão havia 24 casos. Dois eram emendas aglutinativas:

- `2162116-169`: a própria descrição diz que a PEC foi aprovada na forma da
  Emenda Aglutinativa nº 2;
- `2233802-424`: a descrição fala da PEC, mas a abertura diz “Votação da Emenda
  Aglutinativa nº 1”.

Ambos passaram para `AMENDMENT` com
`textForm=AGGLUTINATIVE_AMENDMENT`. O segundo exige revisão porque a conclusão
depende da abertura.

Os 22 casos restantes em `BASE_TEXT` estão separados em:

- 19 `ORIGINAL_OR_UNQUALIFIED`: PL, PLP, PDL, PEC em segundo turno ou MPV sem
  forma alternativa explicitada;
- 3 `CONVERSION_BILL`: MPV aprovada na forma de Projeto de Lei de Conversão.

`ORIGINAL_OR_UNQUALIFIED` não afirma que nenhuma alteração ocorreu; significa
somente que a descrição recebida não qualifica outra forma textual.

## Revisão de substitutivos

Há 25 registros `SUBSTITUTE_TEXT`, todos marcados como
`SUBSTITUTE_OR_SUBAMENDMENT`. A regra exige objeto substitutivo explícito:

- “Substitutivo ao Projeto...”;
- “Subemenda Substitutiva...”;
- “Emenda Aglutinativa Substitutiva...”.

Uma simples menção a “emendas ao substitutivo” não transforma a votação das
emendas em votação do substitutivo. Esse caso possui teste de regressão indireto
no corpus e foi corrigido para `AMENDMENT`.

## Alteração no contrato experimental

Foram adicionados dois eixos:

```json
{
  "textForm": "ORIGINAL_OR_UNQUALIFIED | AGGLUTINATIVE_AMENDMENT | SUBSTITUTE_OR_SUBAMENDMENT | CONVERSION_BILL | NOT_APPLICABLE",
  "contextualMechanism": "HIGHLIGHT_OR_DTQ | null"
}
```

Isso impede que o único campo `votingType` precise representar simultaneamente
o objeto textual e o mecanismo procedimental.

## Testes adicionados

- seis variações antes classificadas como `UNKNOWN`;
- emenda votada por DTQ preservando os dois eixos;
- texto-base original/não qualificado;
- emenda aglutinativa;
- substitutivo/subemenda substitutiva;
- projeto de lei de conversão;
- manutenção das regressões para PEC, recurso e “ressalvado o destaque”.

O protótipo possui agora 15 testes, todos aprovados.

## Amostra para validação humana

Foi produzida uma tabela com 100 casos. A seleção usa round-robin entre os tipos
sugeridos, prioriza casos com revisão e múltiplos vínculos, e preserva
`groupKey` para impedir vazamento futuro entre treino e teste.

Nenhuma linha é verdade anotada. O JSON correspondente mantém
`humanLabel=null` e `annotationStatus=AWAITING_HUMAN_REVIEW`.
