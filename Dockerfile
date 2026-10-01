FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[postgres]" "uvicorn>=0.29"
COPY alembic.ini ./
COPY migrations ./migrations
RUN useradd --create-home pit && chown -R pit /app
USER pit
EXPOSE 8000
# Migrations run explicitly (never implicitly create_all in production).
CMD ["sh", "-c", "alembic upgrade head && uvicorn pitquant.api.main:app --host 0.0.0.0 --port 8000"]
