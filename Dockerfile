FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system styrai \
    && useradd --system --gid styrai --home-dir /app styrai \
    && mkdir -p /app/work \
    && chown -R styrai:styrai /app

COPY --chown=styrai:styrai pyproject.toml README.md ./
COPY --chown=styrai:styrai murphyos/ ./murphyos/
COPY --chown=styrai:styrai web/ ./web/
COPY --chown=styrai:styrai samples/ ./samples/

USER styrai

EXPOSE 8080

CMD ["python", "-m", "murphyos.web", "--host", "0.0.0.0", "--port", "8080", "--audit-path", "/app/work/web-demo-audit.jsonl"]
