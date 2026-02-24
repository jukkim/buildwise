FROM python:3.12-slim

WORKDIR /app

# System dependencies (gcc for C extensions, libpq for asyncpg, curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies (cached layer — only rebuilds when pyproject.toml changes)
COPY pyproject.toml ./
COPY app/__init__.py ./app/
RUN pip install --no-cache-dir .

# Application code (overridden by volume mount in dev)
COPY . .

# Entrypoint: run Alembic migrations, then start app
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Run as non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
