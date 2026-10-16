# Revisão do papel da decisão legislativa — Capivara 2.0

## Escopo e bloqueios

Esta revisão é um protótipo offline. Ela não foi ligada ao FastAPI, banco,
backend ou rotina de publicação. Toda saída mantém
`annotationStatus=AUTOMATIC_PROPOSAL_NOT_HUMAN_VALIDATED` e
`publication.eligibility=BLOCKED_PENDING_REVIEW`.

As contagens abaixo descrevem saídas do protótipo e **não são precisão**. Não há
rótulos humanos suficientes para calcular acurácia, precisão ou recall.

## Contrato 1.1

`decisionRole` é um novo eixo e não substitui `votingType`, `textForm` nem
`contextualMechanism`:

| Valor | Significado |
|---|---|
| `MAIN_PROPOSAL_DECISION` | decisão principal sobre a proposta naquele estágio; não implica promulgação ou lei |
| `PARTIAL_TEXT_DECISION` | decisão sobre parte, emenda, destaque ou redação do texto |
| `PROCEDURAL_DECISION` | decisão de rito, urgência, requerimento, preferência ou equivalente |
| `INDETERMINATE` | evidência insuficiente para escolher um dos papéis anteriores |

Exemplo em que os eixos precisam permanecer separados:

```json
{
  "votingType": "AMENDMENT",
  "legislativeStage": "FIRST_ROUND",
  "textForm": "AGGLUTINATIVE_AMENDMENT",
  "contextualMechanism": null,
  "decisionRole": "MAIN_PROPOSAL_DECISION"
}
```

O objeto é uma emenda aglutinativa, mas a descrição oficial registra que a PEC
foi aprovada em primeiro turno na forma dessa emenda. Portanto, seu papel no
fluxo da proposição é principal naquele turno.

## Casos reais examinados

| PEC | votingId | Classificação proposta | Diagnóstico |
|---|---|---|---|
| 383/2017 | `2162116-169` | `AMENDMENT`, `FIRST_ROUND`, `AGGLUTINATIVE_AMENDMENT`, `MAIN_PROPOSAL_DECISION` | A descrição vincula expressamente a aprovação da PEC à Emenda Aglutinativa 2. |
| 383/2017 | `2162116-178` | `BASE_TEXT`, `SECOND_ROUND`, `ORIGINAL_OR_UNQUALIFIED`, `MAIN_PROPOSAL_DECISION` | Segundo turno explicitamente registrado. |
| 383/2017 | `2162116-181` | `AMENDMENT`, estágio desconhecido, `PARTIAL_TEXT_DECISION` | Emenda de redação posterior, não substitui a decisão principal. |
| 221/2019 | `2233802-424` | `AMENDMENT`, `FIRST_ROUND`, `AGGLUTINATIVE_AMENDMENT`, `MAIN_PROPOSAL_DECISION`, revisão humana | A descrição registra a PEC em primeiro turno; a abertura identifica a Emenda Aglutinativa 1. Como os dois campos cumprem papéis diferentes, permanece revisão obrigatória. |
| 221/2019 | `2233802-438` | `BASE_TEXT`, `SECOND_ROUND`, `ORIGINAL_OR_UNQUALIFIED`, `MAIN_PROPOSAL_DECISION` | Segundo turno explicitamente registrado. |
| 5/2023 | `2351506-104` | `SUBSTITUTE_TEXT`, `FIRST_ROUND`, `SUBSTITUTE_OR_SUBAMENDMENT`, `MAIN_PROPOSAL_DECISION` | A PEC foi aprovada na forma da Emenda Aglutinativa Substitutiva 3. |
| 5/2023 | `2351506-108`, `-112`, `-115` | `HIGHLIGHT`, estágio desconhecido, `PARTIAL_TEXT_DECISION`, revisão humana | “Mantido o texto” só ganha contexto pelos DTQs na abertura. |
| 5/2023 | `2351506-122` | `BASE_TEXT`, `SECOND_ROUND`, `ORIGINAL_OR_UNQUALIFIED`, `MAIN_PROPOSAL_DECISION` | Segundo turno explicitamente registrado. |

Os requerimentos e a preferência encontrados nessas sequências são
`PROCEDURAL_DECISION`; eles não concorrem como votação principal.

## Emendas conjuntas

Uma descrição como `Rejeitadas as Emendas de Plenário` não individualiza quais
emendas receberam exatamente a mesma decisão nem esclarece todas as relações
com o texto. O protótipo mantém `votingType=AMENDMENT` e
`decisionRole=PARTIAL_TEXT_DECISION`, mas força `requiresHumanReview=true`.

## Regra conservadora de `SINGLE_ROUND`

Não há inferência pelo tipo da proposição, posição cronológica ou ausência de
outro turno. O estágio só é preenchido quando:

1. a descrição oficial contém `turno único`; ou
2. a abertura oficial liga explicitamente `votação` a `turno único`.

`Tramitação em turno único`, isoladamente na abertura, é insuficiente e gera
`legislativeStage=UNKNOWN`. A evidência agora aponta o campo oficial exato, em
vez do antigo rótulo genérico `description_or_opening`.

## Seleção proposta da votação principal

O arquivo `principal_vote_selection.json` agrupa por `proposalReferences.id` e:

1. considera apenas `decisionRole=MAIN_PROPOSAL_DECISION`;
2. prefere segundo turno explícito, depois turno único, primeiro turno e estágio desconhecido;
3. retorna `INDETERMINATE` em empate, múltiplos vínculos, ausência de decisão principal ou quando o melhor candidato exige revisão;
4. usa `SELECTED_FOR_HUMAN_VALIDATION`, nunca “publicável”.

Nos três casos examinados, os candidatos propostos são:

- PEC 383/2017: `2162116-178` (segundo turno);
- PEC 221/2019: `2233802-438` (segundo turno);
- PEC 5/2023: `2351506-122` (segundo turno).

Isso não afirma que a proposta virou lei, foi promulgada ou concluiu todas as
etapas fora do conjunto analisado.

## Validação e testes

- 28 testes unitários e de regressão cobrem papéis, três formas de texto,
  evidência de turno único, emendas conjuntas, seleção e falhas de schema.
- Os 200 registros gerados foram validados contra
  `capivara_classificacao_contrato.json` versão 1.1.
- O validador offline implementa exatamente o subconjunto de JSON Schema usado
  pelo contrato e falha diante de valor de `decisionRole` fora do enum.

## Ambiguidades restantes

- `2233802-424`: o objeto aparece na abertura, enquanto a decisão sobre a PEC
  aparece na descrição; precisa validação humana.
- Votações com várias proposições vinculadas não permitem escolher
  automaticamente qual vínculo é o objeto principal.
- “Mantido o texto” sem abertura específica continua insuficiente.
- Emendas conjuntas permanecem não individualizadas.
- Um segundo turno no corpus não prova, sozinho, conclusão na Casa,
  promulgação ou vigência.
- A seleção por estágio é uma política conservadora proposta, não um rótulo
  jurídico validado.
