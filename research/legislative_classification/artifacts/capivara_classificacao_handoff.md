# Handoff completo — classificação de votações legislativas do Capivara 2.0

## 1. Objetivo

Investigar e prototipar um método confiável, auditável e economicamente viável
para identificar:

1. o objeto real de uma votação da Câmara;
2. a etapa legislativa explicitamente informada;
3. o resultado da deliberação sobre aquele objeto;
4. se houve decisão sobre texto;
5. se há prova de encerramento da tramitação na casa;
6. se votos nominais individuais estão realmente disponíveis.

Este trabalho é uma investigação offline. Não houve alteração em banco,
migrations, serviços de produção, endpoints FastAPI ou aplicativo Android. Não
houve publicação nem chamada paga a LLM.

## 2. Arquivos analisados

- `capivara_votacoes_classificacao.json`: corpus principal.
- `capivara_disponibilidade_campos.json`: resumo de disponibilidade.
- `capivara_linhas_do_tempo.json`: cinco sequências legislativas.
- `capivara_linhas_do_tempo.md`: versão legível das sequências.
- `capivara_plano_preservacao_e_limitacoes.md`: proveniência e limitações.

Os arquivos representam um snapshot parcial da Câmara/Plenário. Não são uma
amostra representativa de todas as votações de 2026 e não incluem Senado ou
comissões.

## 3. Regras de interpretação preservadas

- `proposalReferences` representa vínculos armazenados, não objeto comprovado.
- `possibleObjects` contém candidatos a objeto, não objetos confirmados.
- Histórico de tramitação fornece contexto; proximidade temporal não prova
  causalidade.
- Array vazio de efeitos não comprova ausência de efeito legislativo.
- `aprovacao=1` não significa aprovação definitiva da proposição.
- `aprovacao=0` não significa rejeição do mérito da proposição.
- Emenda, substitutivo, destaque, requerimento e redação final não equivalem ao
  texto original inteiro.
- Saída automática anterior ou explicação de IA não é ground truth.
- IDs, textos e descrições oficiais devem permanecer preservados.

## 4. Resultado da auditoria

### Estrutura

| Métrica | Resultado |
|---|---:|
| Votações | 200 |
| Chaves únicas `house + votingId` | 200 |
| Duplicatas | 0 |
| Casas | 200 `CAMARA` |
| Período | 02/02/2026 a 14/10/2026 |
| Propostas com metadados | 122 |
| Vínculos de propostas | 212 |
| Votações com dois vínculos | 12 |

### Integridade

- Nenhuma referência aponta para metadado de proposta ausente.
- Não há divergência entre IDs de `proposalReferences` e
  `affectedProposals`.
- Não há divergência entre `affectedProposals` projetado e o JSON bruto.
- Os 200 hashes SHA-256 do JSON oficial parseado foram reproduzidos.

Essas verificações comprovam integridade de transporte e relacionamento, não o
objeto legislativo efetivamente deliberado.

### Disponibilidade

| Campo | Preenchido | Vazio/nulo |
|---|---:|---:|
| `aprovacao` | 181 | 19 |
| `objetosPossiveis` | 190 | 10 |
| `efeitosRegistrados` | 46 | 154 |
| descrição da abertura | 108 | 92 |
| ID do evento | 199 | 1 |
| propostas afetadas | 200 | 0 |

O indicador original contém:

- 123 registros com `1`;
- 58 registros com `0`;
- 19 registros com `null`.

Há 3.946 objetos possíveis, com média 19,73, mediana 14 e máximo de 212
objetos em uma votação. Portanto, não é seguro selecionar automaticamente o
primeiro `possibleObject`.

Há 118 efeitos registrados distribuídos em 46 votações. Os outros 154 arrays
vazios não provam que nada ocorreu.

Todos os registros têm URL oficial `/votos`, mas somente 124 vínculos arquivados
têm `totalRecordedVotes > 0`. O booleano `individualVotesComplete` aparece como
verdadeiro em 199 registros, inclusive em alguns casos com zero votos. Ele não
deve ser usado sozinho como prova de votação nominal individual.

## 5. Problemas encontrados

### Descrições genéricas

- 19 registros começam com `Mantido o texto`. Todos precisam da abertura para
  identificar que se trata de destaque ou votação em separado.
- 40 começam com `Rejeitado o Requerimento`. O texto confirma a família
  `REQUIREMENT`, mas geralmente não identifica qual requerimento.
- `Resultado. Sim: 182; Não: 182...` não identifica o objeto sem contexto.
- `Alteração do Regime de Tramitação...` parece efeito administrativo e não
  descreve claramente a deliberação.

### Falsos positivos perigosos

1. `Aprovado o substitutivo, ressalvado o destaque` não é votação de destaque.
2. `Proposta de Emenda à Constituição` é uma proposição-base, não uma emenda
   comum.
3. `Recurso contra parecer relativo a emenda` é votação do recurso, não da
   emenda citada.
4. `Mantido o texto` não pode ser interpretado sem a abertura correspondente.
5. Ordem temporal não permite inferir primeiro ou segundo turno.
6. Redação final não comprova isoladamente que a proposição encerrou toda a
   tramitação na Câmara ou virou lei.

### Conflito real importante

Na votação `2624161-42`, a descrição diz `Rejeitado o Requerimento`, mas a
abertura parece repetir o DTQ da votação anterior. Esse caso demonstra que a
abertura não deve sempre substituir a descrição e que conflitos precisam de
revisão humana.

## 6. Análise das cinco linhas do tempo

### MPV 1357/2026

As nove entradas incluem apreciação preliminar, texto na forma de projeto de
lei de conversão, emendas, destaque, requerimento e redação final. O mesmo
indicador de aprovação aparece em objetos diferentes, então não representa
automaticamente aprovação do mérito da MPV inteira.

### PEC 5/2023

Há requerimento, preferência, primeiro turno na forma de emenda aglutinativa,
três destaques com `Mantido o texto` e segundo turno. O primeiro e o segundo
turno precisam permanecer separados e os destaques não podem ser apresentados
como apoio irrestrito à PEC.

### PL 287/2024

A urgência foi aprovada antes da votação do texto-base. Depois aparecem emenda,
destaque, emenda de redação e redação final. Aprovar urgência não aprovou o
conteúdo do PL.

### PLP 74/2026

A votação `2644910-8` está vinculada ao PLP e ao requerimento de urgência. Os
efeitos indicam alteração de regime, mas os dois vínculos precisam ser
preservados sem escolher automaticamente um como objeto.

### MSC 85/2023

A mensagem está vinculada a uma votação sobre projeto de decreto legislativo e
posteriormente a uma redação final. A proposição armazenada e o objeto votado
podem ter identificações diferentes.

## 7. Taxonomia proposta

### `votingType`

- `REQUIREMENT`
- `URGENCY_REQUEST`
- `AMENDMENT`
- `HIGHLIGHT`
- `SUBSTITUTE_TEXT`
- `BASE_TEXT`
- `FINAL_WORDING`
- `OTHER_PROCEDURAL`
- `OTHER_SUBSTANTIVE`
- `UNKNOWN`

`OTHER_SUBSTANTIVE` abriga provisoriamente apreciações preliminares. Uma versão
futura pode adicionar `PRELIMINARY_ADMISSIBILITY` após revisão humana.

### `legislativeStage`

- `FIRST_ROUND`
- `SECOND_ROUND`
- `SINGLE_ROUND`
- `OTHER_STAGE`
- `UNKNOWN`

A etapa só pode ser preenchida quando houver texto oficial explícito.

### `deliberationResult`

- `APPROVED`
- `REJECTED`
- `MAINTAINED`
- `OTHER`
- `UNKNOWN`

Esse resultado pertence ao objeto deliberado, não necessariamente à proposta
original inteira.

### `textDecisionStatus`

- `TEXT_DECISION_CONFIRMED`
- `TEXT_DECISION_POSSIBLE`
- `NOT_TEXT_DECISION`
- `INDETERMINATE`

Urgência, requerimento e outros procedimentos normalmente recebem
`NOT_TEXT_DECISION`. Emenda, destaque, substitutivo, base e redação final podem
receber confirmação quando o texto oficial for explícito.

### `houseCompletionStatus`

- `COMPLETED_IN_HOUSE_CONFIRMED`
- `NOT_COMPLETED_IN_HOUSE_CONFIRMED`
- `INDETERMINATE`

O protótipo sempre retorna `INDETERMINATE`, pois o corpus não sustenta uma regra
causal segura para encerramento da tramitação na casa.

### `individualVoteAvailability`

- `AVAILABLE_IN_ARCHIVED_BINDING`
- `OFFICIAL_ENDPOINT_REFERENCED_NOT_VERIFIED`
- `NOT_AVAILABLE_CONFIRMED`
- `UNKNOWN`

## 8. Protótipo implementado

O protótipo fica isolado em:

```text
research/legislative_classification/
```

Arquivos principais:

- `classifier.py`: regras conservadoras, proveniência e hash.
- `analyze_corpus.py`: auditoria, geração das sugestões e fila de revisão.
- `tests/test_classifier.py`: testes de regressão.

O código utiliza somente a biblioteca padrão do Python. Não acessa rede, banco
ou OpenAI e não é importado pelo FastAPI.

### Precedência

1. Redação final.
2. Requerimento de urgência.
3. Requerimento ou recurso explicitamente deliberado.
4. Substitutivo.
5. Proposição-base, incluindo PEC.
6. Emenda comum.
7. Destaque explicitamente deliberado.
8. Outros procedimentos e decisões preliminares.
9. Abertura apenas para descrição genérica como `Mantido o texto`.
10. `UNKNOWN`.

### Resultado no corpus

| Tipo sugerido | Quantidade |
|---|---:|
| `URGENCY_REQUEST` | 47 |
| `REQUIREMENT` | 46 |
| `SUBSTITUTE_TEXT` | 25 |
| `BASE_TEXT` | 22 |
| `FINAL_WORDING` | 20 |
| `HIGHLIGHT` | 20 |
| `AMENDMENT` | 16 |
| `OTHER_SUBSTANTIVE` | 2 |
| `OTHER_PROCEDURAL` | 1 |
| `UNKNOWN` | 1 |

As regras sugeriram classificação para 199 registros. Um permaneceu sem
classificação e 108 receberam `requiresHumanReview=true`.

Esses números representam cobertura das regras, não precisão. Nenhum rótulo foi
validado por humano.

Todas as saídas do protótipo têm:

```json
{
  "annotationStatus": "AUTOMATIC_PROPOSAL_NOT_HUMAN_VALIDATED",
  "publication": {
    "eligibility": "BLOCKED_PENDING_REVIEW"
  }
}
```

## 9. Contrato de saída

O contrato completo está definido como JSON Schema em
`capivara_classificacao_contrato.json`.

Estrutura simplificada:

```json
{
  "schemaVersion": "1.0",
  "house": "CAMARA",
  "votingId": "2644910-8",
  "input": {
    "officialDataHash": "sha256",
    "sourceExtractedAt": "2026-10-15T22:24:12Z"
  },
  "classification": {
    "votingType": "URGENCY_REQUEST",
    "legislativeStage": "UNKNOWN",
    "deliberationResult": "APPROVED",
    "textDecisionStatus": "NOT_TEXT_DECISION",
    "textForm": "NOT_APPLICABLE",
    "contextualMechanism": null,
    "objectStatus": "CONFIRMED_FROM_EXPLICIT_OFFICIAL_TEXT",
    "houseCompletionStatus": "INDETERMINATE",
    "individualVoteAvailability": "OFFICIAL_ENDPOINT_REFERENCED_NOT_VERIFIED",
    "requiresHumanReview": false
  },
  "provenObject": {
    "kind": "URGENCY_REQUEST",
    "officialText": "Aprovado o Requerimento de Urgência...",
    "proposalId": null,
    "note": "O tipo está comprovado, mas o vínculo não foi promovido automaticamente."
  },
  "result": {
    "originalApprovalIndicator": 1,
    "officialDescription": "Aprovado o Requerimento de Urgência..."
  },
  "proposalReferences": [],
  "evidence": [],
  "method": "RULE_HIGH_PRECISION",
  "ruleId": "R02_URGENCY",
  "classifierVersion": "rules-0.2.0",
  "modelVersion": null,
  "classifiedAt": "2026-10-15T00:00:00Z",
  "annotationStatus": "AUTOMATIC_PROPOSAL_NOT_HUMAN_VALIDATED",
  "publication": {
    "eligibility": "BLOCKED_PENDING_REVIEW",
    "reasons": ["Protótipo automático sem validação humana."]
  },
  "notes": null
}
```

`proposalReferences` continua sendo vínculo. O ID do objeto somente deve ser
preenchido quando a evidência oficial comprovar a identidade.

## 10. Padrão-ouro necessário

Ainda não existe padrão-ouro. Foi criada uma fila de 100 casos diversos,
com:

```json
{
  "annotationStatus": "AWAITING_HUMAN_REVIEW",
  "humanLabel": null
}
```

Recomendação: revisar entre 80 e 120 votações, priorizando:

- todas as classes raras;
- os 108 casos marcados para revisão;
- múltiplos vínculos;
- conflitos entre descrição e abertura;
- descrições genéricas;
- amostra das regras aparentemente simples.

Cada anotação humana precisa guardar identificador do revisor, versão do
protocolo, evidência literal, URL, ambiguidade e eventual segunda revisão.

Treino e teste devem ser separados por componentes conectados de propostas. Se
duas votações compartilham uma proposta, devem ficar no mesmo split.

## 11. Experimentos futuros

### A. Regras determinísticas

Já implementadas como baseline de alta precisão e com opção de abstenção.

### B. TF-IDF + modelo linear

Somente após existir padrão-ouro humano:

1. TF-IDF de unigramas e bigramas.
2. Regressão logística e/ou SVM linear.
3. Separação por grupos de propostas.
4. Limiar de abstenção calibrado em conjunto separado.
5. Comparação contra as mesmas regras.

### C. Embeddings

Somente se houver ganho demonstrável sobre TF-IDF no mesmo split e no mesmo
piso de precisão.

### D. LLM fallback

Somente para casos ambíguos restantes. Deve receber contexto oficial pequeno e
selecionado, citar evidências, retornar JSON estruturado e poder se abster.
Confiança textual do LLM não deve ser tratada como probabilidade.

Nenhuma chamada LLM foi realizada nesta investigação.

## 12. Avaliação futura

Quando houver padrão-ouro suficiente, medir:

- precisão, recall e F1 por classe;
- macro-F1;
- matriz de confusão;
- cobertura;
- taxa de abstenção;
- precisão das saídas publicáveis;
- falsos positivos de mérito versus procedimento;
- desempenho em propostas não vistas no treino;
- custo e latência p50/p95.

Não há dados hoje para publicar qualquer uma dessas métricas.

## 13. Custo hipotético de fallback LLM

Cenário explícito:

- 10.000 votações por mês;
- 20% enviadas ao fallback: 2.000 chamadas;
- limite de 3.000 tokens de entrada e 500 de saída por chamada;
- total máximo de 6 milhões de tokens de entrada e 1 milhão de saída.

Fórmula mensal:

```text
6 × preço por 1 milhão de tokens de entrada
+ 1 × preço por 1 milhão de tokens de saída
```

O valor monetário depende do modelo aprovado no momento da implementação. Não
foi inventado um preço nem escolhida uma LLM nesta etapa.

## 14. Segurança editorial

Nunca publicar automaticamente:

- “deputado X votou contra a PEC” quando o objeto era emenda, destaque,
  requerimento, urgência ou substitutivo;
- “a Câmara aprovou a proposta” quando somente a urgência foi aprovada;
- “virou lei” a partir de votação favorável;
- sentido individual a partir do placar agregado;
- voto individual em votação simbólica ou sem registro nominal comprovado.

Cards ou frases compartilháveis exigem objeto, etapa, resultado e voto nominal
correspondente comprovados. Casos incertos permanecem indeterminados.

## 15. Arquitetura futura recomendada

```text
coleta oficial
    ↓
preservação do JSON, hash e proveniência
    ↓
classificação assíncrona idempotente
    ↓
validação automática e/ou humana
    ↓
persistência versionada
    ↓
política editorial de publicação
    ↓
API do Capivara
    ↓
Android
```

Regras operacionais:

- classificar uma vez por versão/hash da entrada;
- nunca chamar LLM por abertura de tela;
- reclassificar quando entrada, taxonomia ou classificador mudar;
- manter bruto, projeção, classificação e explicação separados;
- não apagar último resultado válido quando enriquecimento falhar;
- retries com backoff, checkpoint e limite;
- logs sem segredos;
- rollback para versão anterior;
- política de publicação fora do prompt da IA.

Estados sugeridos:

```text
PENDING
CLASSIFIED
REVIEW_REQUIRED
FAILED
PUBLISHED
```

## 16. Roadmap recomendado

### Capivara 2.0

- preservar metadados oficiais e hash;
- aplicar regras conservadoras;
- manter `UNKNOWN` e fila de revisão;
- bloquear publicação individual sem evidência nominal;
- armazenar classificação versionada por votação.

### Capivara 2.0.1

- produzir padrão-ouro humano;
- avaliar TF-IDF e modelo linear;
- implementar revisão manual e rollback;
- testar embeddings/LLM apenas com comparação justa.

## 17. Testes realizados

- 15 testes específicos do classificador passaram.
- 52 testes existentes do serviço FastAPI continuaram passando.
- Os artefatos JSON foram carregados e validados sintaticamente.
- Foram geradas 200 sugestões e 100 itens de revisão.

Testes de regressão cobrem urgência, substitutivo, PEC, recurso, redação final,
destaque com descrição genérica, etapa explícita, hash e bloqueio de publicação.

## 18. Conclusão

O corpus é adequado para construir uma fila de revisão e um baseline de regras,
mas não para alegar acurácia ou treinar um modelo supervisionado confiável sem
anotação humana.

A abordagem mínima segura para o Capivara 2.0 é:

1. preservar os dados oficiais;
2. classificar somente padrões explícitos;
3. abster-se em ambiguidades;
4. bloquear publicação automática das sugestões atuais;
5. criar padrão-ouro humano antes de ML ou LLM;
6. tratar votos individuais como camada separada que exige prova própria.

O que está comprovado: integridade estrutural do snapshot, cobertura dos campos,
padrões textuais explícitos e riscos de interpretação.

O que permanece incerto: precisão das regras, objeto específico de descrições
genéricas, término de tramitação e disponibilidade nominal em parte dos casos.

O que o backend precisará implementar depois: preservação versionada,
idempotência, fila assíncrona, revisão, política editorial, retry e rollback.
