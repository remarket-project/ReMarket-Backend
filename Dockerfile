# FROM python:3.10

# ENV PYTHONUNBUFFERED=1

# # Install uv
# # Ref: https://docs.astral.sh/uv/guides/integration/docker/#installing-uv
# COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

# # Compile bytecode
# # Ref: https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode
# ENV UV_COMPILE_BYTECODE=1

# # uv Cache
# # Ref: https://docs.astral.sh/uv/guides/integration/docker/#caching
# ENV UV_LINK_MODE=copy

# WORKDIR /app/

# # Place executables in the environment at the front of the path
# # Ref: https://docs.astral.sh/uv/guides/integration/docker/#using-the-environment
# ENV PATH="/app/.venv/bin:$PATH"

# # Install dependencies
# # Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
# RUN --mount=type=cache,target=/root/.cache/uv \
#     --mount=type=bind,source=uv.lock,target=uv.lock \
#     --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
#     uv sync --frozen --no-install-workspace --package app

# COPY ./backend/scripts /app/backend/scripts

# COPY ./backend/pyproject.toml ./backend/alembic.ini /app/backend/

# COPY ./backend/app /app/backend/app

# # Sync the project
# # Ref: https://docs.astral.sh/uv/guides/integration/docker/#intermediate-layers
# RUN --mount=type=cache,target=/root/.cache/uv \
#     --mount=type=bind,source=uv.lock,target=uv.lock \
#     --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
#     uv sync --frozen --package app

# WORKDIR /app/backend/

# CMD ["fastapi", "run", "--workers", "4", "app/main.py"]

FROM python:3.10-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and install dependencies
COPY pyproject.toml .

# Install all dependencies including dev
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    fastapi[standard]>=0.114.2 \
    python-multipart>=0.0.7 \
    email-validator>=2.1.0.post1 \
    tenacity>=8.2.3 \
    pydantic>2.0 \
    emails>=0.6 \
    jinja2>=3.1.4 \
    alembic>=1.12.1 \
    httpx>=0.25.1 \
    psycopg[binary]>=3.1.13 \
    sqlmodel>=0.0.21 \
    pydantic-settings>=2.2.1 \
    sentry-sdk[fastapi]>=2.0.0 \
    pyjwt>=2.8.0 \
    pwdlib[argon2,bcrypt]>=0.3.0 \
    python-jose[cryptography]>=3.3.0 \
    passlib[bcrypt]>=1.7.4 \
    asyncpg>=0.29.0 \
    slowapi>=0.1.9 \
    uvicorn[standard]>=0.24.0

# Production image
FROM python:3.10-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# Copy app code
COPY . .

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/utils/health-check/', timeout=5)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]