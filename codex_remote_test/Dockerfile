# syntax=docker/dockerfile:1
# Keep this explicit: Supervisor may supply an Alpine BUILD_FROM override.
# The Node runtime and apt packages below require this Debian image.
FROM node:22-bookworm-slim

RUN test -f /etc/debian_version && command -v apt-get && command -v npm \
    && apt-get update && apt-get install -y --no-install-recommends \
    python3 git ca-certificates tini util-linux \
    && rm -rf /var/lib/apt/lists/*
# Optional public build CA for managed build environments; never part of the image.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm install --global --ignore-scripts --no-audit --no-fund @openai/codex@0.164.0 \
    && npm cache clean --force \
    && codex --version \
    && codex remote-control --no-daemon --help \
    && codex remote-control pair --help

RUN groupadd --gid 10001 codex-test \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /data/home codex-test
COPY app /app
COPY start.sh /usr/local/bin/start-codex-test
RUN chmod 755 /usr/local/bin/start-codex-test
WORKDIR /data/workspace
EXPOSE 8099
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/start-codex-test"]
