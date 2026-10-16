# Capivara 2.0 — pacote offline do classificador legislativo 1.1

Este pacote é autocontido e não acessa banco, rede, OpenAI ou qualquer serviço
externo. Não requer credenciais. Ele contém um corpus oficial previamente
congelado, as regras determinísticas, os artefatos gerados e os testes.

## Requisitos

- Python 3.10 ou superior;
- PowerShell apenas para o comando de reprodução fornecido;
- nenhuma biblioteca Python externa.

## Estrutura

```text
capivara-legislative-classifier-1.1/
├── src/
│   ├── classifier.py
│   ├── principal_vote.py
│   ├── analyze_corpus.py
│   └── validate_schema.py
├── fixtures/
│   └── frozen_corpus.json
├── schema/
│   └── capivara_classificacao_contrato.json
├── generated/
│   ├── prototype_classifications.json
│   ├── principal_vote_selection.json
│   ├── human_review_queue.json
│   ├── human_review_table.md
│   └── audit_summary.json
├── tests/
├── docs/
├── reproduce.ps1
├── requirements.txt
└── MANIFEST.json
```

## Testar

Na raiz descompactada:

```powershell
python -m unittest discover -s tests -v
```

## Reproduzir todos os artefatos

```powershell
.\reproduce.ps1
```

O script:

1. executa os testes;
2. recria as 200 classificações;
3. recria os 100 casos de revisão humana;
4. recria a seleção de votação principal;
5. valida as 200 classificações contra o JSON Schema 1.1.

Os timestamps `classifiedAt` são informativos e mudam a cada reprodução. Por
isso, o hash dos arquivos gerados pode mudar mesmo quando a classificação não
muda. Os hashes no manifesto identificam exatamente os arquivos entregues.

## Segurança e publicação

Este é um protótipo para validação humana. Nenhuma saída autoriza publicação
automática. Consulte `docs/capivara_2_revisao_consolidada.md`.
