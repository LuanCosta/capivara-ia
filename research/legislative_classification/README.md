# Protótipo offline de classificação legislativa

Este diretório é independente do FastAPI de produção. Não acessa rede, banco ou
OpenAI.

Executar testes:

```powershell
cd research\legislative_classification
..\..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Auditar e gerar sugestões:

```powershell
..\..\.venv\Scripts\python.exe analyze_corpus.py `
  "C:\caminho\capivara_votacoes_classificacao.json" `
  --summary artifacts\audit_summary.json `
  --classifications artifacts\prototype_classifications.json `
  --review-queue artifacts\human_review_queue.json `
  --review-table artifacts\human_review_table.md `
  --principal-votes artifacts\principal_vote_selection.json

Validar todas as classificações geradas contra o JSON Schema 1.1:

```powershell
..\..\.venv\Scripts\python.exe validate_schema.py `
  artifacts\capivara_classificacao_contrato.json `
  artifacts\prototype_classifications.json
```
```

`prototype_classifications.json` não é padrão-ouro nem material publicável.
`human_review_queue.json` contém 100 casos diversificados; `humanLabel` começa
como nulo e só pode ser preenchido por revisão humana documentada.
`human_review_table.md` apresenta os mesmos casos em formato legível.
`principal_vote_selection.json` é uma proposta conservadora de seleção e aceita
`INDETERMINATE`; não autoriza publicação automática.
