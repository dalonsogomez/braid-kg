#!/usr/bin/env bash
set -euo pipefail
# WikiForge cognee-mcp launcher. ADR 0001 sec. 2.4: API key vive en secrets.env (chmod 600).
SECRETS="${HOME}/.config/wikiforge/secrets.env"
if [[ ! -r "${SECRETS}" ]]; then
  echo "FATAL: ${SECRETS} not readable" >&2
  exit 1
fi
# shellcheck disable=SC1090
source "${SECRETS}"
export LLM_API_KEY="${GEMINI_API_KEY:?GEMINI_API_KEY missing in secrets.env}"
export EMBEDDING_API_KEY="${GEMINI_API_KEY}"
cd "${HOME}/.wikiforge/cognee-mcp/cognee-mcp"
exec uv run python src/server.py --transport stdio "$@"
