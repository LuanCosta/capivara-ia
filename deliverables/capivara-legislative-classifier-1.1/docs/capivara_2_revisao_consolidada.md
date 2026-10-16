# Capivara 2.0 — Revisão consolidada do classificador legislativo

## 1. Escopo

Esta entrega revisa o protótipo offline do classificador legislativo do
Capivara 2.0. Nenhuma rota FastAPI, banco de dados, backend ou rotina de
publicação foi alterada.

O protótipo continua com as seguintes proteções:

- `annotationStatus=AUTOMATIC_PROPOSAL_NOT_HUMAN_VALIDATED`;
- `publication.eligibility=BLOCKED_PENDING_REVIEW`;
- nenhuma publicação automática;
- nenhum resultado tratado como padrão-ouro;
- nenhuma declaração de precisão estatística sem rótulos humanos.

## 2. Objetivo da revisão

Além de identificar o objeto votado por meio de `votingType`, o classificador
agora identifica o papel que aquela votação exerce no andamento da proposta.

Isso resolve casos em que o objeto formal é uma emenda, mas a votação representa
a decisão principal sobre uma PEC naquele turno.

## 3. Contrato atualizado

O contrato de classificação passa da versão `1.0` para `1.1` e adiciona o campo
obrigatório `decisionRole`.

O novo campo não substitui:

- `votingType`: objeto formal votado;
- `textForm`: forma textual do objeto;
- `contextualMechanism`: mecanismo usado, como destaque ou DTQ;
- `legislativeStage`: estágio explicitamente comprovado.

### 3.1. Valores de `decisionRole`

| Valor | Significado |
|---|---|
| `MAIN_PROPOSAL_DECISION` | Decisão principal sobre a proposta naquele estágio. Não implica promulgação, vigência ou transformação em lei. |
| `PARTIAL_TEXT_DECISION` | Decisão sobre parte do texto, emenda, destaque ou redação. |
| `PROCEDURAL_DECISION` | Decisão de rito, urgência, requerimento, preferência ou procedimento equivalente. |
| `INDETERMINATE` | A evidência oficial disponível não permite determinar o papel com segurança. |

### 3.2. Trecho relevante do JSON Schema 1.1

```json
{
  "schemaVersion": "1.1",
  "classification": {
    "votingType": "BASE_TEXT",
    "legislativeStage": "SECOND_ROUND",
    "deliberationResult": "APPROVED",
    "textDecisionStatus": "TEXT_DECISION_CONFIRMED",
    "textForm": "ORIGINAL_OR_UNQUALIFIED",
    "decisionRole": "MAIN_PROPOSAL_DECISION",
    "contextualMechanism": null,
    "objectStatus": "CONFIRMED_FROM_EXPLICIT_OFFICIAL_TEXT",
    "houseCompletionStatus": "INDETERMINATE",
    "individualVoteAvailability": "UNKNOWN",
    "requiresHumanReview": false
  }
}
```

Valores permitidos pelo schema:

```json
{
  "decisionRole": {
    "enum": [
      "MAIN_PROPOSAL_DECISION",
      "PARTIAL_TEXT_DECISION",
      "PROCEDURAL_DECISION",
      "INDETERMINATE"
    ]
  }
}
```

## 4. Relação entre os campos

Os campos devem permanecer independentes. Exemplo:

```json
{
  "votingType": "AMENDMENT",
  "legislativeStage": "FIRST_ROUND",
  "textForm": "AGGLUTINATIVE_AMENDMENT",
  "contextualMechanism": null,
  "decisionRole": "MAIN_PROPOSAL_DECISION"
}
```

Nesse caso, o objeto formal é uma emenda aglutinativa. Entretanto, a descrição
oficial informa que a PEC foi aprovada em primeiro turno na forma dessa emenda.
Assim, o objeto permanece `AMENDMENT`, mas o papel é
`MAIN_PROPOSAL_DECISION`.

## 5. Regras propostas

### 5.1. Decisão procedimental

São classificadas como `PROCEDURAL_DECISION`:

- `REQUIREMENT`;
- `URGENCY_REQUEST`;
- `OTHER_PROCEDURAL`.

Essas votações não concorrem à seleção da votação principal da proposta.

### 5.2. Decisão parcial

São classificadas normalmente como `PARTIAL_TEXT_DECISION`:

- emendas comuns;
- destaques e DTQs;
- redação final;
- emendas de redação.

### 5.3. Decisão principal

São classificadas como `MAIN_PROPOSAL_DECISION` quando existe evidência oficial:

- votação do texto-base;
- aprovação explícita de substitutivo que ocupa o lugar do texto-base;
- aprovação da proposta na forma de emenda aglutinativa;
- aprovação da proposta na forma de emenda aglutinativa substitutiva.

### 5.4. Resultado indeterminado

É usado `INDETERMINATE` quando:

- o objeto é desconhecido;
- a descrição é insuficiente;
- não há evidência para distinguir decisão principal, parcial ou procedimento;
- existem vínculos ou candidatos concorrentes sem critério seguro de desempate.

## 6. Análise das PECs

### 6.1. PEC 383/2017

| votingId | Objeto | Turno | Forma | Papel | Revisão |
|---|---|---|---|---|---|
| `2162116-161` | `REQUIREMENT` | `UNKNOWN` | `NOT_APPLICABLE` | `PROCEDURAL_DECISION` | Sim |
| `2162116-169` | `AMENDMENT` | `FIRST_ROUND` | `AGGLUTINATIVE_AMENDMENT` | `MAIN_PROPOSAL_DECISION` | Não |
| `2162116-178` | `BASE_TEXT` | `SECOND_ROUND` | `ORIGINAL_OR_UNQUALIFIED` | `MAIN_PROPOSAL_DECISION` | Não |
| `2162116-181` | `AMENDMENT` | `UNKNOWN` | `NOT_APPLICABLE` | `PARTIAL_TEXT_DECISION` | Não |

Em `2162116-169`, a descrição oficial registra a aprovação da PEC em primeiro
turno na forma da Emenda Aglutinativa 2. Por isso, o objeto é uma emenda, mas o
papel é uma decisão principal do turno.

### 6.2. PEC 221/2019

| votingId | Objeto | Turno | Forma | Papel | Revisão |
|---|---|---|---|---|---|
| `2233802-416` | `REQUIREMENT` | `UNKNOWN` | `NOT_APPLICABLE` | `PROCEDURAL_DECISION` | Sim |
| `2233802-424` | `AMENDMENT` | `FIRST_ROUND` | `AGGLUTINATIVE_AMENDMENT` | `MAIN_PROPOSAL_DECISION` | Sim |
| `2233802-438` | `BASE_TEXT` | `SECOND_ROUND` | `ORIGINAL_OR_UNQUALIFIED` | `MAIN_PROPOSAL_DECISION` | Não |

O caso `2233802-424` permanece em revisão humana. A descrição oficial registra
a aprovação da PEC no primeiro turno, enquanto a abertura identifica a votação
da Emenda Aglutinativa 1. A combinação sustenta uma proposta de papel principal,
mas não elimina a necessidade de revisão.

### 6.3. PEC 5/2023

| votingId | Objeto | Turno | Forma | Papel | Revisão |
|---|---|---|---|---|---|
| `2351506-95` | `REQUIREMENT` | `UNKNOWN` | `NOT_APPLICABLE` | `PROCEDURAL_DECISION` | Sim |
| `2351506-102` | `OTHER_PROCEDURAL` | `UNKNOWN` | `NOT_APPLICABLE` | `PROCEDURAL_DECISION` | Não |
| `2351506-104` | `SUBSTITUTE_TEXT` | `FIRST_ROUND` | `SUBSTITUTE_OR_SUBAMENDMENT` | `MAIN_PROPOSAL_DECISION` | Não |
| `2351506-108` | `HIGHLIGHT` | `UNKNOWN` | `NOT_APPLICABLE` | `PARTIAL_TEXT_DECISION` | Sim |
| `2351506-112` | `HIGHLIGHT` | `UNKNOWN` | `NOT_APPLICABLE` | `PARTIAL_TEXT_DECISION` | Sim |
| `2351506-115` | `HIGHLIGHT` | `UNKNOWN` | `NOT_APPLICABLE` | `PARTIAL_TEXT_DECISION` | Sim |
| `2351506-122` | `BASE_TEXT` | `SECOND_ROUND` | `ORIGINAL_OR_UNQUALIFIED` | `MAIN_PROPOSAL_DECISION` | Não |

Em `2351506-104`, a proposta foi aprovada em primeiro turno na forma da Emenda
Aglutinativa Substitutiva 3. O classificador preserva simultaneamente:

- `votingType=SUBSTITUTE_TEXT`;
- `textForm=SUBSTITUTE_OR_SUBAMENDMENT`;
- `legislativeStage=FIRST_ROUND`;
- `decisionRole=MAIN_PROPOSAL_DECISION`.

## 7. Votações conjuntas de emendas

Descrições como:

```text
Rejeitadas as Emendas de Plenário.
```

não individualizam as emendas nem demonstram integralmente a relação de cada
uma com o texto.

O caso real `2618177-73` ficou como:

```json
{
  "votingType": "AMENDMENT",
  "legislativeStage": "UNKNOWN",
  "textForm": "NOT_APPLICABLE",
  "decisionRole": "PARTIAL_TEXT_DECISION",
  "requiresHumanReview": true
}
```

Conclusão: votações conjuntas de múltiplas emendas devem exigir revisão humana.

## 8. Revisão de `SINGLE_ROUND`

O classificador não infere turno único pelo tipo da proposição, pela ordem
cronológica ou pela ausência de outro turno.

`SINGLE_ROUND` só é atribuído quando:

1. a descrição oficial contém explicitamente `turno único`; ou
2. a abertura oficial relaciona explicitamente `votação` com `turno único`.

Exemplo suficiente:

```text
Votação, quanto ao mérito, em turno único.
```

Exemplo insuficiente quando aparece isoladamente na abertura:

```text
Tramitação em turno único.
```

No segundo caso, o resultado é `legislativeStage=UNKNOWN`.

A evidência agora registra o campo oficial exato:

- `description`; ou
- `latestVotingOpening.description`.

O rótulo genérico anterior `description_or_opening` deixou de ser usado.

## 9. Seleção da votação principal por proposição

Foi criada uma proposta conservadora de seleção. Ela não publica resultados e
não afirma que uma proposição virou lei.

### 9.1. Algoritmo

1. Agrupar votações por `proposalReferences.id`.
2. Considerar somente `decisionRole=MAIN_PROPOSAL_DECISION`.
3. Preferir, nesta ordem:
   - `SECOND_ROUND`;
   - `SINGLE_ROUND`;
   - `FIRST_ROUND`;
   - estágio desconhecido.
4. Retornar `INDETERMINATE` quando:
   - não houver decisão principal;
   - houver empate na maior prioridade;
   - a votação tiver múltiplas proposições vinculadas;
   - o melhor candidato exigir revisão humana.
5. Quando houver evidência suficiente, retornar
   `SELECTED_FOR_HUMAN_VALIDATION`, nunca “publicável”.

### 9.2. Contrato proposto

Seleção possível:

```json
{
  "proposalId": "2162116",
  "status": "SELECTED_FOR_HUMAN_VALIDATION",
  "selectedVotingId": "2162116-178",
  "candidateVotingIds": ["2162116-178", "2162116-169"],
  "rationale": "Maior estágio explicitamente comprovado entre decisões principais; a seleção ainda não autoriza publicação."
}
```

Seleção indeterminada:

```json
{
  "proposalId": "exemplo",
  "status": "INDETERMINATE",
  "selectedVotingId": null,
  "suggestedVotingId": null,
  "candidateVotingIds": [],
  "rationale": "Nenhuma decisão principal foi sustentada pelo texto oficial."
}
```

### 9.3. Resultado para as PECs examinadas

| Proposição | Votação proposta | Motivo |
|---|---|---|
| PEC 383/2017 | `2162116-178` | Segundo turno explícito |
| PEC 221/2019 | `2233802-438` | Segundo turno explícito |
| PEC 5/2023 | `2351506-122` | Segundo turno explícito |

Essa seleção não comprova conclusão na Casa, promulgação, vigência ou conversão
em lei.

## 10. Validação do JSON Schema

O contrato foi atualizado para JSON Schema Draft 2020-12, versão `1.1`.

Foi criado um validador offline, sem dependência externa, para o subconjunto do
JSON Schema usado pelo contrato. Ele valida:

- `type`;
- `required`;
- `properties`;
- `additionalProperties`;
- `enum`;
- `const`;
- `oneOf`;
- `items`;
- `minItems`;
- `uniqueItems`;
- `minLength`;
- `pattern`;
- formatos `date-time` e `uri`.

Resultado da validação:

```text
OK: 200 registro(s) válidos contra capivara_classificacao_contrato.json
```

Também existe um teste que altera `decisionRole` para um valor inexistente e
confirma que o JSON é rejeitado.

## 11. Testes de regressão

Foram executados 28 testes do protótipo, cobrindo:

- urgência antes de requerimento genérico;
- substitutivo antes de emenda;
- destaque sem substituir o objeto formal;
- PEC como texto-base;
- recursos contra emendas;
- falsos `UNKNOWN` de emendas;
- emenda votada por destaque;
- texto original, emenda aglutinativa, substitutivo e PLV;
- redação final;
- descrições genéricas;
- evidência explícita de turno;
- exigência especial para `SINGLE_ROUND`;
- `decisionRole` separado de `votingType`;
- PEC 383/2017;
- PEC 221/2019;
- PEC 5/2023;
- destaque como decisão parcial;
- emendas conjuntas com revisão obrigatória;
- seleção do segundo turno;
- empate retornando `INDETERMINATE`;
- votação somente procedimental;
- múltiplas proposições bloqueando seleção;
- validação e rejeição pelo JSON Schema.

Resultado:

```text
Ran 28 tests
OK
```

Também foram executados os testes existentes da aplicação FastAPI para detectar
regressões acidentais:

```text
52 passed
```

## 12. Distribuição das saídas do protótipo

Nos 200 registros congelados, o protótipo gerou aproximadamente:

- 94 `PROCEDURAL_DECISION`;
- 55 `PARTIAL_TEXT_DECISION`;
- 47 `MAIN_PROPOSAL_DECISION`;
- 4 `INDETERMINATE`.

Essas quantidades são apenas distribuição das saídas automáticas. Não são
métricas de acurácia, precisão ou qualidade.

Na seleção por proposição, o protótipo produziu:

- 44 casos `SELECTED_FOR_HUMAN_VALIDATION`;
- 78 casos `INDETERMINATE`.

A quantidade elevada de abstenções é intencional nesta fase conservadora.

## 13. Ambiguidades restantes

1. `2233802-424`: a descrição registra a decisão da PEC e a abertura registra a
   emenda aglutinativa. O papel principal é plausível, mas exige revisão humana.
2. Votações com várias proposições vinculadas não permitem determinar
   automaticamente qual vínculo é o objeto principal.
3. “Mantido o texto” sem abertura específica permanece insuficiente.
4. Emendas conjuntas continuam sem individualização.
5. Um segundo turno presente no corpus não prova conclusão da tramitação,
   promulgação ou vigência.
6. A prioridade por estágio é uma política conservadora proposta, não uma
   interpretação jurídica validada.
7. Não existe conjunto humano rotulado suficiente para declarar precisão.

## 14. Arquivos implementados

- `classifier.py`: classificação e regras de `decisionRole`.
- `principal_vote.py`: seleção conservadora da votação principal.
- `validate_schema.py`: validação offline do contrato.
- `analyze_corpus.py`: geração de classificações, fila e seleção principal.
- `artifacts/capivara_classificacao_contrato.json`: JSON Schema 1.1.
- `artifacts/prototype_classifications.json`: 200 classificações regeneradas.
- `artifacts/principal_vote_selection.json`: proposta de seleção por proposição.
- `tests/test_classifier.py`: regressões do classificador.
- `tests/test_principal_vote.py`: regressões da seleção.
- `tests/test_schema_validation.py`: regressões do contrato.

## 15. Conclusão

O protótipo agora separa corretamente:

- qual objeto foi votado;
- qual forma textual foi usada;
- qual mecanismo contextual apareceu;
- qual estágio foi explicitamente informado;
- qual papel a decisão exerce sobre a proposta.

A revisão preserva primeiro e segundo turnos, emenda aglutinativa e emenda
aglutinativa substitutiva. Casos sem evidência suficiente retornam
`INDETERMINATE` ou exigem revisão humana.

Esta entrega está pronta para validação humana e discussão de integração, mas
não para publicação automática ou uso como classificação definitiva.
