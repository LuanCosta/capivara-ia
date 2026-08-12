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

As rotas `/documents/{document_id}/process` e `/ask` exigem o cabeçalho
`X-Internal-Secret`. O BFF Ktor deve obter esse segredo no ambiente do servidor;
ele nunca deve estar no aplicativo Android.

## Comparação temática

`POST /compare` compara a distribuição aproximada do conteúdo de dois planos.
Os identificadores são sempre valores de `candidates.id`, nunca números
eleitorais.

```json
{
  "candidateAId": 13,
  "candidateBId": 9
}
```

A rota usa os embeddings já armazenados nos chunks. Somente as descrições dos
seis temas são transformadas em embeddings durante a comparação; os documentos
completos não são enviados novamente ao modelo generativo. Cada chunk com
classificação suficientemente clara contribui conforme seu tamanho textual. O
arredondamento final garante que os seis percentuais de cada candidato somem
exatamente 100.

Os temas fixos são Economia, Saúde, Educação, Segurança, Social e
Infraestrutura. O resultado mede presença relativa de conteúdo, não qualidade,
viabilidade ou mérito político das propostas.
