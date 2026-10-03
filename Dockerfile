# Build only application files; credentials and local state are excluded from context.
FROM ghcr.io/astral-sh/uv:0.12.6 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --python /usr/local/bin/python
COPY aedrova_site ./aedrova_site
COPY scripts ./scripts
COPY config ./config
RUN useradd --uid 10001 --create-home aedrova && chown -R aedrova:aedrova /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER aedrova
EXPOSE 8090
CMD ["python", "-m", "scripts.serve"]
