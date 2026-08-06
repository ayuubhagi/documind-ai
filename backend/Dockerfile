# ---- DocMaid AI backend ----
FROM python:3.11-slim

WORKDIR /app

# System deps kept minimal; psycopg2-binary ships its own libpq.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic

# Non-root user for defense in depth
RUN useradd --create-home appuser \
    && mkdir -p /app/uploads /app/chroma_data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD curl -fsS http://localhost:8000/health || exit 1

# Apply pending migrations, then serve. Alembic owns the Postgres schema;
# the app no longer calls create_all outside of the SQLite test suite.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
