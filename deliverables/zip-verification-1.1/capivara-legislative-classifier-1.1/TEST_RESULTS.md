# Resultados da verificação do pacote

Data da execução: 2026-10-15.

Ambiente usado para verificar a entrega:

- Windows;
- Python 3.12;
- execução feita a partir da pasta autocontida do pacote;
- nenhuma rede, banco, credencial ou serviço externo utilizado.

## Testes

Comando equivalente:

```powershell
$env:PYTHONPATH = ".\src"
python -m unittest discover -s tests -v
```

Resultado:

```text
Ran 28 tests in 0.011s
OK
```

## Reprodução e validação

O corpus congelado foi novamente processado usando os módulos contidos no
próprio pacote.

Resultados:

```text
Corpus congelado: 200 registros
Classificações geradas: 200 registros
Fila de revisão humana: 100 registros
JSON Schema: OK — 200 registros válidos
```

## Observação de reprodutibilidade

O campo `classifiedAt` registra o momento da execução. Assim, uma nova execução
reproduz as classificações, mas pode gerar hashes diferentes para arquivos de
saída que contenham esse timestamp. O `MANIFEST.json` identifica os bytes exatos
entregues neste ZIP.
