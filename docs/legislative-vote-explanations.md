# Explicações de votações legislativas

## Responsabilidades

O backend coleta e normaliza os dados oficiais, chama o serviço Python e decide
quando salvar, reutilizar ou tentar novamente uma explicação. O serviço Python
não consulta Câmara, Senado ou banco de dados. Ele somente valida o JSON recebido,
gera uma explicação com saída estruturada e a devolve.

Essa separação impede que a IA altere os dados oficiais e permite que a mesma
explicação seja compartilhada por todos os parlamentares de uma votação.

## Rota

```http
POST /legislative/votes/explain
Content-Type: application/json
X-Internal-Secret: <INTERNAL_API_SECRET>
```

### Entrada

| Campo | Tipo | Regra |
| --- | --- | --- |
| `house` | `CAMARA \| SENADO` | obrigatório |
| `votingId` | string | 1 a 120 caracteres |
| `proposals` | array | 1 a 20 propostas |
| `proposals[].identification` | string | 1 a 120 caracteres |
| `proposals[].description` | string | 1 a 12.000 caracteres |
| `proposals[].officialUrls` | array de URL | 1 a 10 URLs oficiais |
| `votingDescription.type` | enum | `URGENCY`, `AMENDMENT`, `SUBSTITUTE`, `MAIN_TEXT`, `OTHER` ou `UNKNOWN` |
| `votingDescription.identification` | string/nulo | até 120 caracteres |
| `votingDescription.description` | string | 1 a 16.000 caracteres |
| `originalResult` | objeto/nulo | resultado coletivo oficial |
| `originalResult.code` | string/nulo | código bruto, até 100 caracteres |
| `originalResult.description` | string/nulo | significado oficial, até 4.000 caracteres |
| `originalResult.totals` | objeto/nulo | `yes`, `no`, `abstention`, `obstruction`, `other`; inteiros não negativos |
| `secret` | boolean/nulo | informação oficial de sigilo, quando disponível |
| `officialResultCodeMappings` | objeto | até 50 códigos oficialmente validados |

O JSON completo não pode ultrapassar 60.000 caracteres. Um código só pode ser
interpretado quando `originalResult.description` vier preenchido pela fonte ou
quando existir em `officialResultCodeMappings`.

Exemplo com duas propostas vinculadas:

```json
{
  "house": "CAMARA",
  "votingId": "VOT-2026-145",
  "proposals": [
    {
      "identification": "PL 100/2026",
      "description": "Descrição oficial da primeira proposta.",
      "officialUrls": ["https://www.camara.leg.br/exemplo/pl-100"]
    },
    {
      "identification": "PL 101/2026",
      "description": "Descrição oficial da segunda proposta vinculada.",
      "officialUrls": ["https://www.camara.leg.br/exemplo/pl-101"]
    }
  ],
  "votingDescription": {
    "type": "URGENCY",
    "identification": "Requerimento de urgência",
    "description": "Votação do requerimento de urgência para a tramitação."
  },
  "originalResult": {
    "code": "APROVADO",
    "description": "Requerimento aprovado",
    "totals": {
      "yes": 300,
      "no": 100,
      "abstention": 5,
      "obstruction": 0,
      "other": 0
    }
  },
  "secret": false,
  "officialResultCodeMappings": {
    "APROVADO": "Requerimento aprovado"
  }
}
```

### Saída

```json
{
  "title": "Urgência aprovada para duas propostas",
  "proposalExplanation": "As propostas vinculadas tratam dos assuntos descritos nos textos oficiais enviados.",
  "votingExplanation": "A votação aprovou o pedido para acelerar ou priorizar a tramitação. O conteúdo final das propostas não foi aprovado por esta votação.",
  "resultExplanation": "O resultado coletivo informado registra a aprovação do requerimento de urgência.",
  "limitations": [
    "Esta votação não permite concluir que as propostas foram aprovadas em definitivo ou viraram lei."
  ],
  "affectedProfiles": [
    {
      "profile": "Pessoa que atende aos critérios descritos na proposta",
      "possibleImpact": "Poderá receber o atendimento previsto no texto.",
      "impactDirection": "POSSIBLE_BENEFIT",
      "conditions": "Se a proposta entrar em vigor e os critérios forem atendidos."
    }
  ],
  "explanationVersion": "legislative-vote-v2"
}
```

`affectedProfiles` contém no máximo três perfis hipotéticos. As direções aceitas
são `POSSIBLE_BENEFIT`, `POSSIBLE_COST`, `MIXED` e `UNCERTAIN`. Valores, faixas
de renda, profissões e condições somente podem aparecer quando estiverem nos
dados oficiais enviados pelo backend. Quando não houver impacto individual
identificável, a lista fica vazia e a limitação deve ser informada.

## Erros

| HTTP | Significado | Ação do backend |
| --- | --- | --- |
| `401` | segredo ausente ou inválido | corrigir configuração; não repetir continuamente |
| `422` | entrada fora do contrato ou dos limites | registrar validação e corrigir o mapeamento |
| `502` | falha da OpenAI ou resposta estruturada inválida | manter dados oficiais e agendar nova tentativa |
| `504` | OpenAI excedeu o timeout | manter dados oficiais e tentar depois com backoff |

## Reutilização no backend

1. Normalize os dados oficiais no contrato acima.
2. Gere um hash SHA-256 de um JSON canônico contendo `house`, `votingId`,
   propostas, descrição da votação, resultado, sigilo e mapeamentos oficiais.
3. Reutilize a explicação quando o hash e `explanationVersion` forem iguais.
4. Chame o Python somente para votação nova, dados alterados ou tentativa pendente.
5. Salve separadamente os textos oficiais, o hash, a explicação, a versão, o
   estado da tentativa e o horário da última falha.
6. Ao substituir um lote, remova explicações órfãs somente depois de confirmar
   que nenhuma votação ou participação ainda as referencia.
7. Nas telas de detalhes e “Como votou”, anexe a mesma explicação ao objeto da
   votação sem remover ou renomear os campos oficiais existentes.
8. Se a IA falhar, confirme o lote mesmo assim com os dados oficiais e reprocesse
   apenas as explicações pendentes. Use backoff e limite de tentativas.

O cache deve pertencer à votação, não ao parlamentar. Não inclua dados do
parlamentar no hash nem no pedido enviado à IA.

## Configuração do consumidor

O backend precisa destas configurações:

```env
CAPIVARA_LLM_BASE_URL=https://capivara-proposals-ai.fly.dev
CAPIVARA_LLM_INTERNAL_SECRET=mesmo-valor-de-INTERNAL_API_SECRET
CAPIVARA_LLM_EXPLANATION_VERSION=legislative-vote-v2
CAPIVARA_LLM_CONNECT_TIMEOUT_MS=5000
CAPIVARA_LLM_REQUEST_TIMEOUT_MS=40000
```

O serviço Python usa:

```env
OPENAI_API_KEY=
OPENAI_RESPONSE_MODEL=gpt-4.1-mini
OPENAI_LEGISLATIVE_TIMEOUT_SECONDS=30
INTERNAL_API_SECRET=
```

O timeout do backend deve ser um pouco maior que o timeout interno do Python.
Segredos não devem ser enviados ao Android, registrados em logs ou armazenados
junto ao conteúdo da votação.

## Limitações conhecidas

- A explicação é tão completa quanto os textos oficiais enviados pelo backend.
- O serviço não confirma se a proposta foi sancionada, promulgada ou virou lei.
- O serviço não descobre o significado de códigos internos sem mapeamento oficial.
- Totais ausentes não são reconstruídos.
- Em votações secretas, nenhuma preferência individual é inferida.
- A classificação do objeto (`type`) é responsabilidade do mapeamento do backend;
  use `UNKNOWN` e envie a descrição original quando a fonte não permitir classificá-lo.
