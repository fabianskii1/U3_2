#!/usr/bin/env bash
set -euo pipefail

ai_ci_image="${1:?Usage: bash AI/deploy/ci-smoke.sh IMAGE}"
ai_ci_name="skadi-ai-ci-${RANDOM}-${RANDOM}"
ai_ci_container=""

cleanup() {
  ai_ci_exit_status=$?
  if [ -n "$ai_ci_container" ]; then
    if [ "$ai_ci_exit_status" -ne 0 ]; then
      docker logs --tail 100 "$ai_ci_container" >&2 || true
    fi
    docker rm --force --volumes "$ai_ci_container" >/dev/null 2>&1 || true
  fi
  exit "$ai_ci_exit_status"
}
trap cleanup EXIT

ai_ci_platform="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$ai_ci_image")"
if [ "$ai_ci_platform" != linux/amd64 ]; then
  printf 'Expected linux/amd64, got %s\n' "$ai_ci_platform" >&2
  exit 1
fi

# No host env file, model key, published ports, or outbound network access.
ai_ci_container="$(docker create --name "$ai_ci_name" \
  --platform linux/amd64 --network none \
  --cap-drop ALL --security-opt no-new-privileges=true \
  --memory 512m --cpus 1 \
  --env OPENAI_API_KEY= --env api_key= "$ai_ci_image")"
docker start "$ai_ci_container" >/dev/null

ai_ci_ready=false
for ai_ci_attempt in {1..60}; do
  if docker exec "$ai_ci_container" .venv/bin/python -c \
    'import json, urllib.request; response = urllib.request.urlopen("http://127.0.0.1:8001/health", timeout=2); assert response.status == 200; assert json.load(response) == {"status": "ok"}' \
    >/dev/null 2>&1; then
    ai_ci_ready=true
    break
  fi
  if [ "$(docker inspect --format '{{.State.Running}}' "$ai_ci_container")" != true ]; then
    printf 'AI exited during initialization.\n' >&2
    exit 1
  fi
  sleep 1
done
if [ "$ai_ci_ready" != true ]; then
  printf 'AI did not become ready after %s checks.\n' "$ai_ci_attempt" >&2
  exit 1
fi

docker exec -i "$ai_ci_container" .venv/bin/python - <<'PY'
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

assert not Path("/app/.env").exists(), "Image must not contain the application's .env"
assert not os.environ.get("OPENAI_API_KEY")
assert not os.environ.get("api_key")
request = Request(
    "http://127.0.0.1:8001/agents/chat/invoke",
    data=json.dumps({"message": "CI missing-key check"}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urlopen(request, timeout=5) as response:
        raise AssertionError(f"Expected missing-key 503, got {response.status}")
except HTTPError as response:
    assert response.code == 503, f"Expected 503, got {response.code}"
    assert json.load(response)["detail"]["code"] == "MODEL_CONFIG_MISSING"
PY

printf 'AI image smoke test passed: %s\n' "$ai_ci_image"
