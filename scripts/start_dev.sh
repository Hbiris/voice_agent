#!/usr/bin/env bash
# 本地开发启动脚本：激活 venv、加载 .env、启动 LiveKit agent worker（dev 模式）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

# ── 激活虚拟环境 ──────────────────────────────────────────────────────────────
if [[ -f ".venv/bin/activate" ]]; then
    source .venv/bin/activate
elif [[ -n "${VIRTUAL_ENV:-}" ]]; then
    echo "Using active venv: ${VIRTUAL_ENV}"
else
    echo "ERROR: no .venv found. Run: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
    exit 1
fi

# ── 加载 .env ─────────────────────────────────────────────────────────────────
if [[ -f ".env" ]]; then
    set -o allexport
    source .env
    set +o allexport
    echo "Loaded .env"
else
    echo "WARNING: .env not found — copy .env.example to .env and fill in credentials"
fi

# ── 验证必填变量 ───────────────────────────────────────────────────────────────
: "${LIVEKIT_URL:?LIVEKIT_URL is required}"
: "${LIVEKIT_API_KEY:?LIVEKIT_API_KEY is required}"
: "${LIVEKIT_API_SECRET:?LIVEKIT_API_SECRET is required}"
: "${OPENAI_API_KEY:?OPENAI_API_KEY is required (demo profile)}"

echo "Starting visitor-agent worker (profile: ${VOICE_PROFILE:-demo}) ..."
echo "LiveKit: ${LIVEKIT_URL}"

# ── 启动 worker（dev 模式：自动重载）─────────────────────────────────────────
exec python3 -m src.agent.worker dev
