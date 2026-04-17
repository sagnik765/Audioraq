#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${SCRIPT_DIR}/oracle.env"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.oracle.yml"

if [[ ! -f "${ENV_FILE}" ]]; then
  cp "${SCRIPT_DIR}/oracle.env.example" "${ENV_FILE}"
  echo "Created ${ENV_FILE}. Fill in the secrets and rerun the script."
  exit 1
fi

cd "${ROOT_DIR}"

COMPOSE_PROFILE_ARGS=()
if grep -Eq "^(AI_AUDIO_REQUIRE_NEURAL_WORKER|AI_STUDIO_INSTALL_KOKORO|AI_STUDIO_INSTALL_CHATTERBOX)=true$" "${ENV_FILE}"; then
  COMPOSE_PROFILE_ARGS=(--profile ai-studio)
fi

docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "${COMPOSE_PROFILE_ARGS[@]}" up -d --build
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "${COMPOSE_PROFILE_ARGS[@]}" ps

echo
echo "Audioraq is deploying on Oracle Cloud."
echo "When DNS is pointed at the instance, verify: https://www.audioraq.com/api/health"
