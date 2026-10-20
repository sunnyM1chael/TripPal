FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md ./
COPY requirements-mysql.txt ./
COPY app ./app
RUN uv sync --frozen --no-dev
ARG INSTALL_MYSQL=true
RUN if [ "$INSTALL_MYSQL" = "true" ]; then uv pip install --python /app/.venv/bin/python -r requirements-mysql.txt; fi

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
