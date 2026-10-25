#!/bin/sh
set -eu
umask 077
# HA provides this add-on's own /data. No host, shared or Home Agent mounts.
python3 /app/prepare.py
exec setpriv --reuid=10001 --regid=10001 --init-groups \
    env -i PATH=/usr/local/bin:/usr/bin:/bin LANG=C.UTF-8 \
    HOME=/data/home CODEX_HOME=/data/home/.codex \
    python3 /app/server.py
