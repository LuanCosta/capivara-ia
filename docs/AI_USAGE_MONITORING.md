# Medição de consumo de IA

Implementada no serviço Python existente. Não altera os contratos públicos de notícias,
explicações ou classificação, modelos, prompts, regras de retry ou conteúdo gerado.
Não usa IA para medir, não grava no Supabase e não requer migration ou novas secrets.
Requer deploy do Python para começar a observar produção. Nada foi publicado por este trabalho.

## O que é medido

| Identificador nos logs | Operação |
|---|---|
| `legislative.explain` | Explicação da votação e perfis de impacto; versão registrada na referência |
| `news.explain_news` | Explicação simples da notícia |
| `news.people_mentioned` | Pessoas citadas |
| `news.how_it_affects_me` | Impactos da notícia |
| `plans.ask` | Resposta sobre plano de governo |
| `plans.document_analysis` | Índices temáticos do documento |
| `embeddings.question` | Vetor da pergunta |
| `embeddings.document` | Vetores dos trechos de documentos |
| `embeddings.other` | Demais chamadas de vetorização |

Cada tentativa HTTP do SDK gera um evento `AI_USAGE` com:
modelo retornado, identificador de correlação, número da tentativa, status HTTP,
latência, request ID do provedor, tokens de entrada/saída/cache e custo estimado USD.
Um evento `AI_OPERATION` correlacionado informa conclusão ou falha da chamada SDK.
Os hooks leem o consumo antes da desserialização estruturada: uma resposta inválida
que já gastou tokens também é registrada. O SDK mantém as mesmas retentativas.
Timeouts sem consumo informado ficam com tokens/custo nulos e contagem de desconhecidos.
Não presumimos que uma tentativa com erro foi gratuita nem que necessariamente foi cobrada.

Não registramos prompts, perguntas, notícias, respostas, embeddings, senhas ou headers de autenticação.
Os únicos dados de referência adicionais são ID numérico da notícia e casa/versão legislativa.

`cached_input_tokens` é cache de entrada do provedor, incluso em `input_tokens`.
Não é a quantidade de respostas servidas pelo cache Kotlin. Uma resposta reutilizada
pelo backend não chega ao Python e não gera evento de consumo. O compartilhamento
Android da notícia não chama a IA. O classificador 1.1 e a comparação de índices já
armazenados não chamam OpenAI e não geram eventos de consumo.

## Consulta rápida

```powershell
fly logs -a capivara-proposals-ai | Select-String 'AI_USAGE |AI_OPERATION '
```

Para capturar e somar um período, execute a partir da pasta do Python:

```powershell
fly logs -a capivara-proposals-ai | Tee-Object -FilePath ai-usage.log
# Depois de observar o período desejado, interrompa com Ctrl+C.
.\.venv\Scripts\python.exe tools/ai_usage_report.py ai-usage.log
```

O relatório aceita os prefixos dos logs Fly e arquivos UTF-8/UTF-16. Remove repetições
do mesmo `event_id` em exportações sobrepostas e ordena os grupos por custo estimado
conhecido. Não consulta API, não chama IA e não acessa banco. Não ter eventos é reportado
explicitamente; isso não prova gasto zero.

Também há `GET /internal/ai-usage`, protegido pelo mesmo `X-Internal-Secret` das rotas
Python. Nunca configurar esse segredo no Android. A consulta é somente leitura e
retorna `scope=current_process_only`, início da medição, grupos por funcionalidade/modelo,
tentativas, retries, erros HTTP, tokens e `known_estimated_usd`/`cost_unknown_attempts`.
O endpoint não guarda histórico por votação e os contadores têm cardinalidade limitada.
`AI_OPERATION` mostra falhas de parsing além dos erros HTTP disponíveis no resumo.

## Limitações e cobrança

- Os tokens vêm do `usage` real devolvido pelo provedor. Não estimamos tokens pelo tamanho do texto.
- Os dólares são estimativas de tarifa padrão, não a fatura. Casos desconhecidos ficam nulos.
- Preços usados por milhão de tokens, conferidos em 17/10/2026:
  - `gpt-4.1-mini` e `gpt-4.1-mini-2025-04-14`: entrada US$ 0,40, entrada em cache US$ 0,10, saída US$ 1,60.
  - `text-embedding-3-small`: entrada US$ 0,02.
- Tarifa flex/priority ou modelo sem preço cadastrado não recebe estimativa. Os tokens continuam registrados.
- Fórmula: `(entrada - cache) × preço_entrada + cache × preço_cache + saída × preço_saída`, dividido por um milhão.
- Preços estão datados em `app/ai_usage.py`; revisar se o modelo/tarifa mudar. Não há conversão cambial automática.
- O resumo em memória reinicia com o processo. No Fly, auto-stop também pode causar reinícios.
  Cada máquina/processo tem seu próprio resumo. Para somar processos/deploys, conservar e agregar os logs.
- Os logs seguem a retenção da infraestrutura; este código não cria armazenamento durável externo.
- O relatório soma somente os eventos capturados no arquivo. Não recupera gastos anteriores à instrumentação,
  eventos já expirados, chamadas de outros serviços ou tentativas sem `usage` retornado.
- Não mede assinaturas ChatGPT/Codex nem execuções de editores/plugins fora deste serviço.
- Não é um limitador de orçamento. Não altera frequência de geração, cache ou retentativas.

Fontes oficiais para conferir campos e preços:

- https://developers.openai.com/api/docs/guides/prompt-caching
- https://developers.openai.com/api/docs/models/gpt-4.1-mini
- https://developers.openai.com/api/docs/models/text-embedding-3-small

## Validação local

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Os testes usam HTTPX MockTransport e o SDK real, sem rede externa ou chamadas pagas.
Cobrem consumo Responses/embeddings, cache sem dupla cobrança, preço desconhecido,
modelo retornado, retries HTTP/timeout, saída estruturada inválida, concorrência,
cancelamento, falha da própria telemetria, proteção da rota, contadores limitados,
reinício e deduplicação no relatório offline. Os testes anteriores continuam passando.

Rollback: reverter `app/ai_usage.py`, imports/instrumentação dos cinco serviços e a rota
em `app/main.py`, removendo o relatório se desejado. Não há dados do banco a reverter.
