FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/root/.local/bin:/root/.kiro/bin:/app/.venv/bin:${PATH}"

WORKDIR /app

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://cli.kiro.dev/install | bash \
    && kiro-cli --version

COPY pyproject.toml uv.lock .python-version README.md ./
COPY src ./src

RUN uv sync --locked --no-dev

CMD ["simple-kirolets"]
