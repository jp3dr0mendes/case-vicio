FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r /app/requirements.txt

COPY src/ /app/src/
COPY data/ /app/data/
COPY prompts/ /app/prompts/
COPY docs/ /app/docs/

RUN mkdir -p /app/artifacts && useradd --create-home --uid 10001 appuser && \
    chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["python", "-m", "vicio_case.cli"]
CMD ["classify", "--mode", "baseline"]
