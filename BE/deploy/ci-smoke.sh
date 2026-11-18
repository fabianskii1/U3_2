#!/usr/bin/env bash
set -euo pipefail

be_ci_image="${1:?Usage: bash BE/deploy/ci-smoke.sh IMAGE NETWORK}"
be_ci_network="${2:?Pass the disposable database network (database alias: db)}"
be_ci_name="skadi-be-ci-${RANDOM}-${RANDOM}"

cleanup() {
  be_ci_exit_status=$?
  if [ "$be_ci_exit_status" -ne 0 ]; then
    docker logs --tail 100 "$be_ci_name" >&2 || true
  fi
  docker rm --force --volumes "$be_ci_name" >/dev/null 2>&1 || true
  exit "$be_ci_exit_status"
}
trap cleanup EXIT

be_ci_platform="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$be_ci_image")"
if [ "$be_ci_platform" != linux/amd64 ]; then
  printf 'Expected linux/amd64, got %s\n' "$be_ci_platform" >&2
  exit 1
fi

# The caller supplies a migrated disposable DB, never an application env file.
docker run --detach --name "$be_ci_name" \
  --platform linux/amd64 --network "$be_ci_network" \
  --env DATABASE_URL=postgresql+asyncpg://ci_backend:ci_backend_only@db:5432/ci_backend \
  --env AI_BASE_URL=http://127.0.0.1:9 \
  "$be_ci_image" >/dev/null

be_ci_ready=false
for be_ci_attempt in {1..30}; do
  if docker exec "$be_ci_name" python -c \
    'import json, urllib.request; assert json.load(urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2)) == {"status": "ok"}' \
    >/dev/null 2>&1; then
    be_ci_ready=true
    break
  fi
  if [ "$(docker inspect --format '{{.State.Running}}' "$be_ci_name")" != true ]; then
    printf 'Backend exited during startup.\n' >&2
    exit 1
  fi
  sleep 2
done
if [ "$be_ci_ready" != true ]; then
  printf 'Backend did not become healthy after %s checks.\n' "$be_ci_attempt" >&2
  exit 1
fi

docker exec -i "$be_ci_name" python - <<'PY'
import json
import urllib.request


def get(path):
    with urllib.request.urlopen(f"http://127.0.0.1:8000{path}", timeout=5) as response:
        assert response.status == 200
        return json.load(response)


assert get("/health") == {"status": "ok"}
hierarchy = get("/api/hierarchy")
assert any(plant["plant_id"] == "PLANT-01" for plant in hierarchy["plants"])
assert any(equipment["equipment_id"] == "P1" for equipment in hierarchy["equipment"])
equipment = get("/api/equipment/P1")
assert equipment["equipment_id"] == "P1"
assert len(equipment["sensors"]) == 8
print("Backend health and migrated database read checks passed.")
PY

printf 'BE image smoke test passed: %s\n' "$be_ci_image"
