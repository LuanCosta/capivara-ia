FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app

RUN test -f app/legislative_classification/classifier.py \
    && test -f app/legislative_classification/principal_vote.py \
    && test -f app/legislative_classification/capivara_classificacao_contrato.json \
    && pip install --upgrade pip \
    && pip install .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
