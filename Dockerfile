FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    DATA_DIR=/app/data/input \
    ARTIFACTS_DIR=/app/artifacts \
    CONFIG_DIR=/app/config \
    ANNOTATIONS_DIR=/app/data/anotacoes

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r /app/requirements.txt

COPY src/ /app/src/
COPY tests/ /app/tests/
COPY data/ /app/data/
COPY config/ /app/config/
COPY prompts/ /app/prompts/

# Usuário sem privilégios; o UID/GID efetivo pode ser trocado no compose (APP_UID/APP_GID)
# para coincidir com o dono do diretório artifacts/ montado do host.
RUN mkdir -p /app/artifacts && useradd --create-home --uid 10001 appuser && \
    chown -R appuser:appuser /app/artifacts
USER appuser

ENTRYPOINT ["python", "-m", "vicio_case.cli"]
CMD ["classify", "--mode", "ensemble"]
