# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# psycopg (binary) needs no build chain; libpq is the only runtime requirement.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

FROM base AS deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

FROM deps AS runtime
RUN groupadd --system app && useradd --system --gid app app

COPY --chown=app:app . .

# Writable mount points for collected static and uploaded media.
RUN mkdir -p /app/staticfiles /app/media && chown -R app:app /app/staticfiles /app/media

USER app

# Build-time only: collectstatic must import settings without real services.
RUN DJANGO_SETTINGS_MODULE=core.settings \
    SECRET_KEY=build-only-placeholder \
    ALLOWED_HOSTS=localhost \
    PUBLIC_BASE_URL=http://localhost \
    CSRF_TRUSTED_ORIGINS=http://localhost \
    DB_ENGINE=django.db.backends.sqlite3 \
    DB_NAME=/tmp/build.sqlite3 \
    DB_USER=unused DB_PASSWORD=unused DB_HOST=localhost DB_PORT=5432 \
    REDIS_URL=redis://localhost:6379/0 \
    CELERY_BROKER_URL=redis://localhost:6379/1 \
    CELERY_RESULT_BACKEND=redis://localhost:6379/2 \
    EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend \
    EMAIL_HOST=localhost EMAIL_PORT=25 \
    DEFAULT_FROM_EMAIL=build@localhost \
    FIELD_ENCRYPTION_KEY=KQej0ydSrtLbDBU125BoWGFq55isrBPakPGJM50gX0E= \
    python manage.py collectstatic --noinput

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz/ || exit 1

# migrate && serve; gunicorn config lives in deploy/gunicorn.conf.py
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn core.wsgi:application -c deploy/gunicorn.conf.py"]
