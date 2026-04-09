FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    gnupg \
    tini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.7.3 /uv /uvx /bin/

RUN curl -sL -o /etc/apt/trusted.gpg.d/morph027-signal-cli.asc \
    https://packaging.gitlab.io/signal-cli/gpg.key \
    && echo "deb https://packaging.gitlab.io/signal-cli signalcli main" \
    > /etc/apt/sources.list.d/morph027-signal-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends signal-cli-native \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

VOLUME ["/root/.local/share/signal-cli"]

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash"]
