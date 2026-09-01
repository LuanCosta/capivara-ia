# Capivara Proposals AI

Serviço FastAPI que processa planos de governo em PDF e responde perguntas
exclusivamente com base nos trechos armazenados no Supabase.

## Requisitos locais

- Python 3.12+
- Uma conta e um projeto no Supabase
- Uma chave da API da OpenAI com créditos

## Configuração

Copie `.env.example` para `.env` e preencha:

```env
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
OPENAI_API_KEY=
INTERNAL_API_SECRET=
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_RESPONSE_MODEL=gpt-4.1-mini
```

`INTERNAL_API_SECRET` deve ter pelo menos 16 caracteres. O arquivo `.env` é
local e não deve ser enviado ao Git, Docker ou Fly.io.

## Executar no Windows PowerShell

```powershell
cd "C:\Users\Pichau\Documents\Capivara IA\capivara-proposals-ai"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Em outro PowerShell:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Fly.io

O `fly.toml` configura:

- região primária `gru` (São Paulo);
- porta interna `8000`;
- uma CPU compartilhada e 512 MB de memória;
- desligamento automático;
- zero máquinas mínimas;
- verificação de saúde em `/health`.

Depois de instalar o `flyctl`, autentique-se:

```powershell
fly auth login
```

Crie o aplicativo apenas na primeira publicação:

```powershell
fly apps create capivara-proposals-ai
```

O nome de um aplicativo Fly precisa ser único globalmente. Se esse nome já
estiver ocupado, escolha outro e atualize `app` no `fly.toml`.

Envie as variáveis do `.env` para o cofre do Fly sem adicioná-las ao
`fly.toml`:

```powershell
Get-Content .env | fly secrets import
```

Confira somente os nomes das variáveis cadastradas:

```powershell
fly secrets list
```

Publique:

```powershell
fly deploy
```

Verifique a aplicação:

```powershell
fly status
Invoke-RestMethod -Uri "https://SEU-APP.fly.dev/health"
```

As rotas `/documents/{document_id}/process`, `/ask`, `/compare` e
`/news/questions` exigem o cabeçalho `X-Internal-Secret`. O BFF Ktor deve obter
esse segredo no ambiente do servidor; ele nunca deve estar no aplicativo Android.

## Comparação temática

`POST /compare` mede o detalhamento das propostas em seis temas fixos.

Os índices são calculados uma única vez pela OpenAI durante
`POST /documents/{document_id}/process` e ficam armazenados em
`proposal_document_analysis`. Assim, chamadas posteriores de `/compare` apenas
leem os valores do Supabase e não geram novo custo de OpenAI.

Antes de publicar esta versão, execute no SQL Editor do Supabase o arquivo
`supabase/proposal_document_analysis.sql`. Depois, reprocesse os documentos para
preencher a análise persistida.
Os identificadores são sempre valores de `candidates.id`, nunca números
eleitorais.

```json
{
  "candidateAId": 13,
  "candidateBId": 9
}
```

Durante o processamento, o serviço seleciona trechos distribuídos ao longo de
cada documento e analisa cada plano separadamente. O nome e o partido do
candidato não são enviados no prompt. A rota `/compare` apenas lê os índices.
Os temas continuam sendo Economia, Saúde, Educação, Segurança, Social e
Infraestrutura, mantendo o contrato consumido pelo Android.

Em cada tema, o percentual estima o detalhamento explícito sobre fonte de recursos,
custo, prazo, responsável, caminho legal e instrumento de execução. Os índices são
independentes e não precisam somar 100%. O resultado não mede qualidade, resultado
futuro ou mérito político.

## Explicação de notícias

`POST /news/questions` recebe do BFF todo o conteúdo necessário para explicar
uma notícia ou identificar as pessoas citadas. O Python não consulta a internet,
não acessa `feed_explanations` e não salva a resposta; o cache permanece no BFF.

Tipos aceitos:

- `EXPLAIN_NEWS`: retorna uma explicação simples em `answer` e `people` vazio.
- `PEOPLE_MENTIONED`: retorna `answer` nulo e uma lista estruturada em `people`.

O serviço utiliza Structured Outputs com modelos Pydantic e a mesma variável
`OPENAI_RESPONSE_MODEL` usada pelas demais respostas textuais.
