$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = Join-Path $root "src"

python -m unittest discover -s (Join-Path $root "tests") -v

python (Join-Path $root "src\analyze_corpus.py") `
    (Join-Path $root "fixtures\frozen_corpus.json") `
    --summary (Join-Path $root "generated\audit_summary.json") `
    --classifications (Join-Path $root "generated\prototype_classifications.json") `
    --review-queue (Join-Path $root "generated\human_review_queue.json") `
    --review-table (Join-Path $root "generated\human_review_table.md") `
    --principal-votes (Join-Path $root "generated\principal_vote_selection.json")

python (Join-Path $root "src\validate_schema.py") `
    (Join-Path $root "schema\capivara_classificacao_contrato.json") `
    (Join-Path $root "generated\prototype_classifications.json")
