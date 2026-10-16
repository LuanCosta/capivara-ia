# Taxonomia revisável de votações

## Princípio

Cada eixo responde a uma pergunta diferente. Nenhum campo deve ser derivado
automaticamente de outro.

### 1. `votingType`: qual objeto foi deliberado?

| Valor | Uso |
|---|---|
| `REQUIREMENT` | requerimento ou recurso que não seja urgência |
| `URGENCY_REQUEST` | requerimento explícito de urgência |
| `AMENDMENT` | emenda, subemenda ou emenda de redação não substitutiva |
| `HIGHLIGHT` | destaque/DTQ/votação em separado |
| `SUBSTITUTE_TEXT` | substitutivo ou subemenda substitutiva |
| `BASE_TEXT` | proposição principal ou texto-base |
| `FINAL_WORDING` | redação final |
| `OTHER_PROCEDURAL` | preferência, adiamento, retirada de pauta etc. |
| `OTHER_SUBSTANTIVE` | decisão material explícita fora das classes anteriores |
| `UNKNOWN` | evidência insuficiente ou conflitante |

Compatibilidade: os enums propostos foram mantidos. “Apreciação preliminar”
permanece provisoriamente em `OTHER_SUBSTANTIVE`, acompanhada de evidência. Se a
revisão humana mostrar volume suficiente, uma versão 1.1 pode adicionar
`PRELIMINARY_ADMISSIBILITY`; consumidores 1.0 devem tratá-la como
`OTHER_SUBSTANTIVE`.

### 2. `legislativeStage`: qual etapa explícita?

`FIRST_ROUND`, `SECOND_ROUND`, `SINGLE_ROUND`, `OTHER_STAGE`, `UNKNOWN`.

Turno só é preenchido por texto oficial literal. Ordem temporal não preenche o
campo. Redação final não é convertida automaticamente em “última etapa da casa”.

### 3. `deliberationResult`: o que aconteceu com o objeto?

`APPROVED`, `REJECTED`, `MAINTAINED`, `OTHER`, `UNKNOWN`.

Esse campo descreve o resultado do objeto específico. Não representa aprovação
definitiva da proposição vinculada. O indicador numérico original é preservado
separadamente em `result.originalApprovalIndicator`.

### 4. `textDecisionStatus`: houve decisão sobre texto?

| Valor | Significado |
|---|---|
| `TEXT_DECISION_CONFIRMED` | texto oficial identifica emenda, destaque, substitutivo, base ou redação final |
| `TEXT_DECISION_POSSIBLE` | contexto sugere decisão textual, mas falta confirmação suficiente |
| `NOT_TEXT_DECISION` | objeto procedimental explícito, como urgência/requerimento |
| `INDETERMINATE` | não é possível decidir |

### 4.1. `textForm`: qual forma textual foi explicitada?

`ORIGINAL_OR_UNQUALIFIED`, `AGGLUTINATIVE_AMENDMENT`,
`SUBSTITUTE_OR_SUBAMENDMENT`, `CONVERSION_BILL` ou `NOT_APPLICABLE`.

`ORIGINAL_OR_UNQUALIFIED` não garante texto original sem alterações. Significa
apenas que os campos disponíveis não qualificam emenda, substitutivo ou projeto
de lei de conversão.

### 4.2. `contextualMechanism`

`HIGHLIGHT_OR_DTQ` ou nulo. Permite registrar que uma emenda foi decidida por
meio de destaque/DTQ sem trocar indevidamente o objeto `AMENDMENT` por
`HIGHLIGHT`.

### 5. `houseCompletionStatus`: a matéria terminou na casa?

`COMPLETED_IN_HOUSE_CONFIRMED`, `NOT_COMPLETED_IN_HOUSE_CONFIRMED`,
`INDETERMINATE`.

O protótipo sempre retorna `INDETERMINATE`. Proximidade de um despacho de remessa
ou presença de redação final não bastam para atribuir causalidade à votação.

### 6. `individualVoteAvailability`

`AVAILABLE_IN_ARCHIVED_BINDING`, `OFFICIAL_ENDPOINT_REFERENCED_NOT_VERIFIED`,
`NOT_AVAILABLE_CONFIRMED`, `UNKNOWN`.

Ter URL `/votos` ou `individualVotesComplete=true` com zero registros não prova
que houve votação nominal. Uma afirmação individual exige o voto correspondente,
o objeto comprovado e a completude do conjunto.

### 7. Objeto e vínculos

- `provenObject`: somente objeto sustentado por trecho oficial.
- `proposalReferences`: vínculos preservados, nunca promovidos implicitamente.
- `objectStatus`: `CONFIRMED_FROM_EXPLICIT_OFFICIAL_TEXT`,
  `POSSIBLE_FROM_CONTEXT` ou `UNKNOWN`.
- `evidence`: campo de origem, trecho literal, URL e campos sustentados.

## Precedência das regras

1. Redação final.
2. Requerimento de urgência.
3. Requerimento/recurso explicitamente deliberado.
4. Substitutivo.
5. Proposição-base, incluindo PEC.
6. Emenda comum.
7. Destaque explicitamente deliberado.
8. Outros procedimentos e decisões preliminares.
9. Abertura somente quando a descrição é genérica, como `Mantido o texto`.
10. Abstenção.

Essa ordem evita usar uma menção lateral como objeto. Conflito entre campos deve
gerar revisão, não desempate silencioso.

## Regra editorial

Uma saída classificatória pode existir sem ser publicável. Publicação exige:

- objeto confirmado;
- etapa e resultado compatíveis;
- evidência oficial citável;
- voto individual correspondente quando a frase mencionar parlamentar;
- ausência de conflito relevante;
- política de publicação aprovada fora do classificador.
