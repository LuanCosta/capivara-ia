# Plano e resultados dos experimentos

## Situação da avaliação

Não existe padrão-ouro humano nos anexos. Por isso:

- não foram calculados precisão, macro-F1 ou matriz de confusão;
- saídas automáticas têm `AUTOMATIC_PROPOSAL_NOT_HUMAN_VALIDATED`;
- o corpus não foi dividido artificialmente para produzir métricas;
- nenhuma saída de regra ou IA foi reutilizada como ground truth.

## Experimento A — regras determinísticas

Implementado em `classifier.py`, com precedência, evidência, hash da entrada,
abstenção e 11 testes de regressão. Resultado operacional no corpus:

- 199 sugestões por regra;
- 1 abstenção completa;
- 108 registros exigindo revisão humana;
- 92 sugestões sem flag de revisão pelo critério atual.

Isso é cobertura, não qualidade medida. Antes de uso público, uma pessoa deve
revisar inclusive amostra das 96 sugestões aparentemente diretas.

## Construção do padrão-ouro

Foi produzida uma tabela de 100 casos, ainda sem rótulos humanos, estratificada
por tipo e priorizando riscos. A recomendação continua sendo 80 a 120 votações
efetivamente revisadas, estratificadas por tipo, por
presença de abertura, por múltiplos vínculos e por descrição genérica. Todas as
classes raras e os 108 casos marcados devem ter prioridade.

Cada anotação deve conter:

- `house + votingId`;
- rótulos de cada eixo separadamente;
- trecho literal e URL oficial;
- regra de interpretação;
- `HUMAN_REVIEWED_REFERENCE` e identidade/versão do protocolo de revisão;
- ambiguidade e necessidade de segunda revisão.

Treino e teste devem ser separados por componentes conectados de IDs de
propostas. Se duas votações compartilham uma proposta ou uma votação liga duas
propostas, todo o componente fica em um único split. Isso impede que a mesma
matéria apareça em treino e teste.

## Experimento B — TF-IDF + modelo linear

Não executado: faltam rótulos humanos confiáveis. Após a anotação:

1. concatenar apenas descrição e abertura, com indicadores de origem;
2. TF-IDF de unigramas e bigramas;
3. comparar regressão logística e SVM linear;
4. validação agrupada por componente de propostas;
5. calibrar limiar de abstenção em conjunto separado;
6. medir por classe e especialmente falsos positivos procedimento × mérito.

Classes com poucos exemplos devem permanecer nas regras/UNKNOWN, não receber
oversampling cego.

## Experimento C — embeddings

Só executar se o modelo linear, sob o mesmo split, deixar lacunas relevantes.
Comparar cobertura no mesmo piso de precisão. Embedding não substitui evidência:
o registro final ainda precisa citar texto oficial.

## Experimento D — LLM fallback

Não executado e nenhuma chamada paga foi feita. Um futuro fallback deve receber
somente contexto oficial selecionado, produzir JSON estruturado, citar trechos e
poder retornar `UNKNOWN`. A “confiança” textual do modelo não é probabilidade.

Orçamento hipotético explícito para 10.000 votações/mês:

- 20% chegam ao fallback após regras/modelo linear: 2.000 chamadas;
- teto de 3.000 tokens de entrada e 500 de saída por chamada;
- consumo máximo: 6 milhões de tokens de entrada e 1 milhão de saída/mês;
- custo = `6 × preço_por_1M_entrada + 1 × preço_por_1M_saída` do modelo escolhido.

Os preços não foram fixados neste relatório porque não houve escolha/aprovação de
modelo nem consulta paga. Latência deve ser medida por p50/p95 no piloto, com
timeout, retry limitado e processamento assíncrono.

## Métricas exigidas quando houver padrão-ouro

- precisão, recall e F1 por classe;
- macro-F1;
- matriz de confusão;
- cobertura e taxa de abstenção;
- precisão das saídas publicáveis;
- falsos positivos críticos de mérito versus procedimento;
- resultado em componentes de propostas nunca vistos no treino;
- custo e p50/p95 por método.

O objetivo inicial recomendado é maximizar precisão publicável, aceitando baixa
cobertura. Não há base neste momento para definir ou alegar um valor atingido.

## Roadmap

### Capivara 2.0

- preservar bruto/hash/proveniência;
- aplicar regras de alta precisão;
- enviar UNKNOWN/revisão para fila;
- não publicar frases individuais sem objeto e voto nominal comprovados;
- classificar uma vez por hash de entrada.

### Capivara 2.0.1

- padrão-ouro revisado;
- modelo linear agrupado;
- painel/fila de revisão e rollback;
- piloto controlado de embeddings/LLM somente se superar baseline comparável.

### Dependências do backend

- armazenamento versionado por `house + votingId + officialDataHash`;
- separação entre bruto, projeção, classificação e explicação;
- job assíncrono idempotente;
- estado `PENDING/CLASSIFIED/REVIEW_REQUIRED/FAILED/PUBLISHED`;
- política editorial fora do prompt;
- reclassificação quando hash, taxonomia ou classificador mudar;
- rollback para versão anterior sem apagar evidências.
