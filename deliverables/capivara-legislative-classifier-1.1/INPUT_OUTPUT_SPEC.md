# Especificação de entrada e saída

## Entrada do classificador

`classifier.classify_record(record)` recebe um objeto JSON de votação. Campos
usados diretamente:

```json
{
  "house": "CAMARA",
  "votingId": "2162116-169",
  "description": "Texto oficial do resultado",
  "result": {
    "originalApprovalIndicator": null
  },
  "proposalReferences": [
    {
      "id": "2162116",
      "identification": "PEC 383/2017",
      "relation": "string ou null"
    }
  ],
  "possibleObjects": [],
  "registeredEffects": [],
  "affectedProposals": [],
  "latestVotingOpening": {
    "description": "Texto oficial da abertura ou null",
    "registrationDateTime": null
  },
  "event": {"id": "string ou null", "uri": "string ou null"},
  "organ": {"id": "string ou null", "acronym": "PLEN", "uri": null},
  "officialReferences": ["https://fonte.oficial/exemplo"],
  "rawMetadata": {
    "officialResponseFetchedAt": "2026-01-01T00:00:00Z",
    "storedBindings": []
  }
}
```

O corpus congelado contém campos adicionais para auditoria. O hash oficial é
calculado sobre o subconjunto documentado em `classifier.official_data_hash`.

## Saída do classificador

A saída completa deve obedecer a
`schema/capivara_classificacao_contrato.json`. Os campos centrais são:

```json
{
  "schemaVersion": "1.1",
  "house": "CAMARA",
  "votingId": "2162116-169",
  "input": {
    "officialDataHash": "sha256",
    "sourceExtractedAt": "date-time ou null"
  },
  "classification": {
    "votingType": "AMENDMENT",
    "legislativeStage": "FIRST_ROUND",
    "deliberationResult": "APPROVED",
    "textDecisionStatus": "TEXT_DECISION_CONFIRMED",
    "textForm": "AGGLUTINATIVE_AMENDMENT",
    "decisionRole": "MAIN_PROPOSAL_DECISION",
    "contextualMechanism": null,
    "objectStatus": "CONFIRMED_FROM_EXPLICIT_OFFICIAL_TEXT",
    "houseCompletionStatus": "INDETERMINATE",
    "individualVoteAvailability": "UNKNOWN",
    "requiresHumanReview": false
  },
  "evidence": [],
  "annotationStatus": "AUTOMATIC_PROPOSAL_NOT_HUMAN_VALIDATED",
  "publication": {
    "eligibility": "BLOCKED_PENDING_REVIEW",
    "reasons": ["Protótipo automático sem validação humana."]
  }
}
```

## Entrada da seleção principal

`principal_vote.select_principal_votes(records, classifications)` recebe duas
listas na mesma ordem:

- registros oficiais do corpus;
- respectivas saídas de `classify_record`.

## Saída da seleção principal

Cada proposição retorna um dos estados:

- `SELECTED_FOR_HUMAN_VALIDATION`;
- `INDETERMINATE`.

Mesmo o primeiro estado não autoriza publicação automática nem permite concluir
que a proposição virou lei.
