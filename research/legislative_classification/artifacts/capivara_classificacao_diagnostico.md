# Diagnóstico do corpus de classificação legislativa

## Escopo e conclusão

Foram auditados integralmente os cinco anexos congelados, sem rede, banco,
endpoint de produção ou LLM. O corpus é internamente consistente para pesquisa,
mas **não contém verdade anotada suficiente para medir acurácia** e não deve ser
usado diretamente para publicar afirmações sobre o voto de parlamentares.

O que está comprovado pelo arquivo:

- 200 votações, todas da Câmara/Plenário, entre 02/02/2026 e 14/10/2026;
- 200 chaves `house + votingId` únicas e nenhuma duplicata;
- 122 propostas com metadados compartilhados;
- 212 vínculos de propostas em 200 votações; 12 votações têm dois vínculos;
- nenhuma referência de proposta aponta para metadado ausente;
- `proposalReferences`, `affectedProposals` e o bruto arquivado coincidem nos
  IDs, mas isso comprova vínculo, não o objeto deliberado;
- os 200 hashes SHA-256 do JSON oficial parseado foram reproduzidos com sucesso;
- os números do arquivo de disponibilidade coincidem com o corpus principal.

O que permanece incerto:

- o objeto único de muitas votações;
- se a matéria terminou a tramitação na Câmara;
- se um endpoint `/votos` contém voto nominal individual em cada caso;
- a interpretação de descrições genéricas sem abertura/evento/documento;
- qualquer métrica de precisão, pois não há rótulos revisados por humanos.

## Integridade e disponibilidade

| Verificação | Resultado |
|---|---:|
| Chaves duplicadas | 0 |
| Referências sem metadados | 0 |
| Divergências referência × afetadas | 0 |
| Divergências afetadas × JSON bruto | 0 |
| `aprovacao=1` | 123 |
| `aprovacao=0` | 58 |
| `aprovacao=null` | 19 |
| `objetosPossiveis` preenchido | 190 |
| `objetosPossiveis` vazio | 10 |
| `efeitosRegistrados` preenchido | 46 |
| `efeitosRegistrados` vazio | 154 |
| abertura preenchida | 108 |
| abertura nula | 92 |
| evento com ID | 199 |
| evento sem ID | 1 |

Há 3.946 objetos possíveis: média 19,73, mediana 14 e máximo 212 em uma
única votação. Portanto, `possibleObjects` não pode ser tratado como objeto
confirmado nem enviado integralmente a um classificador sem seleção e
proveniência.

Há 118 efeitos registrados em 46 votações. Array vazio significa somente que o
campo veio vazio no snapshot. Não prova ausência de efeito legislativo.

Os 200 registros têm referência ao endpoint oficial `/votos`; 124 vínculos
arquivados têm `totalRecordedVotes > 0`. O campo `individualVotesComplete` aparece
como verdadeiro em 199 registros, inclusive em parte dos casos com zero votos.
Logo, esse booleano isolado não comprova votação nominal recuperável.

## Padrões que exigem contexto

- 19 descrições começam com `Mantido o texto`; todas têm abertura preenchida.
  A abertura mostra que são destaques ou votações em separado, mas essa
  associação ainda deve conservar as duas evidências.
- 40 começam com `Rejeitado o Requerimento`; somente duas têm abertura. O texto
  confirma a família `REQUIREMENT`, mas normalmente não identifica qual
  requerimento ou seu efeito.
- `Resultado. Sim: 182; Não: 182...` não identifica o objeto sem a abertura.
- `Alteração do Regime de Tramitação...` parece efeito administrativo, não uma
  descrição clara da deliberação; deve permanecer `UNKNOWN`.
- `ressalvado o destaque` dentro da aprovação de substitutivo não transforma a
  votação principal em `HIGHLIGHT`.
- `Proposta de Emenda à Constituição` é uma proposição-base, não uma `AMENDMENT`
  comum. A expressão precisa de regra própria.
- `Recurso ... contra parecer ... à Emenda` tem como objeto o recurso, não a
  emenda mencionada.

## Cinco linhas do tempo

### MPV 1357/2026

As nove entradas mostram admissibilidade preliminar, texto na forma de projeto
de lei de conversão, emendas, destaque, requerimento e redação final. A sequência
demonstra por que `aprovacao` não é rótulo do mérito: há decisões distintas na
mesma matéria. O corpus não prova que essas nove sejam a tramitação completa.

### PEC 5/2023

Há requerimento, preferência, primeiro turno na forma de emenda aglutinativa,
três destaques com `Mantido o texto` e segundo turno. “Mantido” só é interpretável
com a abertura do DTQ. Primeiro e segundo turno precisam permanecer separados.

### PL 287/2024

A urgência foi votada semanas antes do texto-base. Depois aparecem emenda,
destaque, emenda de redação e redação final. É um falso positivo editorial grave
dizer que a urgência aprovou o PL ou que o destaque expressa posição irrestrita
sobre o projeto.

### PLP 74/2026

A votação `2644910-8` possui vínculos com o PLP e com o requerimento de urgência;
os efeitos confirmam alteração de regime. Isso mostra por que múltiplos vínculos
devem ser preservados, sem promover automaticamente o primeiro a objeto.

### MSC 85/2023

A mensagem está vinculada a uma decisão sobre PDL e depois à redação final. A
proposição vinculada e o objeto textual podem ter identificações diferentes.

## Exemplos auditáveis

| votingId | Interpretação sustentada | Limite |
|---|---|---|
| `2644910-8` | `URGENCY_REQUEST`, aprovado | não aprovou o conteúdo do PLP 74/2026 |
| `2611313-31` | `SUBSTITUTE_TEXT`, aprovado | não prova sanção ou fim da tramitação |
| `2589671-51` | `AMENDMENT`, rejeitada | não equivale a rejeitar o PL inteiro |
| `2589671-55` | possível `HIGHLIGHT`, texto mantido | depende da abertura; requer revisão |
| `1229705-77` | família `REQUIREMENT`, rejeitado | objeto específico não identificado |
| `2624161-42` | requerimento rejeitado | abertura parece reaproveitada do DTQ anterior; conflito perigoso |
| `2422887-23` | requerimento rejeitado, dois vínculos | nenhum vínculo é objeto confirmado |

## Resultado do protótipo

As regras produziram sugestões para 199 registros e abstiveram em 1. Desses 200,
108 ficaram com `requiresHumanReview=true`. Distribuição proposta:

| Tipo | Quantidade |
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

Esses números medem apenas o comportamento das regras. Não são precisão,
acurácia nem distribuição representativa das votações brasileiras.

## Falsos positivos bloqueados por regressão

1. Substitutivo `ressalvado o destaque` classificado incorretamente como destaque.
2. PEC classificada como emenda comum pela palavra “Emenda”.
3. Recurso contra parecer relativo a emenda classificado como voto na emenda.
4. `Mantido o texto` classificado sem a abertura do DTQ.
5. Turno inferido pela sequência em vez de trecho explícito.

## Próxima dependência humana

Um especialista legislativo deve revisar amostra estratificada, conflitos entre
descrição e abertura, todos os múltiplos vínculos e todas as classes raras. Só
depois essa revisão poderá receber o status `HUMAN_REVIEWED_REFERENCE` e ser
usada para medir ou treinar modelos.
