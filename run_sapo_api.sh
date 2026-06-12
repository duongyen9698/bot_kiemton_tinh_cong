#!/bin/bash
# Chạy FastAPI Sapo qua uvicorn — dùng bởi systemd sapo-api.service

cd /root/tinh_cong || exit 1

export PATH="/root/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

exec /root/.local/bin/uv run uvicorn sapo.server:app \
  --host 0.0.0.0 \
  --port 8000
