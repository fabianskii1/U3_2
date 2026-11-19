#!/usr/bin/env bash
set -euo pipefail

fe_ci_image="${1:?Usage: bash fe/deploy/ci-smoke.sh IMAGE}"
fe_ci_id="skadi-fe-ci-${RANDOM}-${RANDOM}"
fe_ci_frontend="${fe_ci_id}-frontend"
fe_ci_backend="${fe_ci_id}-backend"
fe_ci_network="${fe_ci_id}-network"
fe_ci_tmp="$(mktemp -d)"

cleanup() {
  fe_ci_exit_status=$?
  if [ "$fe_ci_exit_status" -ne 0 ]; then
    docker logs --tail 100 "$fe_ci_frontend" >&2 || true
    docker logs --tail 100 "$fe_ci_backend" >&2 || true
  fi
  docker rm --force --volumes "$fe_ci_frontend" "$fe_ci_backend" >/dev/null 2>&1 || true
  docker network rm "$fe_ci_network" >/dev/null 2>&1 || true
  rm -rf "$fe_ci_tmp"
  exit "$fe_ci_exit_status"
}
trap cleanup EXIT

fe_ci_platform="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$fe_ci_image")"
if [ "$fe_ci_platform" != linux/amd64 ]; then
  printf 'Expected linux/amd64, got %s\n' "$fe_ci_platform" >&2
  exit 1
fi

docker network create --internal "$fe_ci_network" >/dev/null

# Reuse the tested image's Nginx as a fake API; no external service or secrets.
cat >"$fe_ci_tmp/default.conf" <<'NGINX'
server {
    listen 8000;
    location / {
        default_type text/plain;
        return 200 "$request_uri";
    }
}
NGINX
docker create --name "$fe_ci_backend" --platform linux/amd64 \
  --network "$fe_ci_network" --network-alias backend \
  --entrypoint nginx "$fe_ci_image" -g 'daemon off;' >/dev/null
docker cp "$fe_ci_tmp/default.conf" "$fe_ci_backend:/etc/nginx/conf.d/default.conf"
docker start "$fe_ci_backend" >/dev/null

check_frontend() {
  fe_ci_ready=false
  for fe_ci_attempt in {1..30}; do
    if docker exec "$fe_ci_frontend" wget -T 5 -qO- http://127.0.0.1/ >"$fe_ci_tmp/index.html" 2>/dev/null; then
      fe_ci_ready=true
      break
    fi
    if [ "$(docker inspect --format '{{.State.Running}}' "$fe_ci_frontend")" != true ]; then
      printf 'Frontend exited during initialization.\n' >&2
      exit 1
    fi
    sleep 1
  done
  if [ "$fe_ci_ready" != true ]; then
    printf 'Frontend did not become ready after %s checks.\n' "$fe_ci_attempt" >&2
    exit 1
  fi

  grep -q '<div id="root"' "$fe_ci_tmp/index.html"
  sed -nE 's/.*(src|href)="(\/assets\/[^" ]*)".*/\2/p' \
    "$fe_ci_tmp/index.html" >"$fe_ci_tmp/assets.txt"
  grep -q '\.js$' "$fe_ci_tmp/assets.txt"
  grep -q '\.css$' "$fe_ci_tmp/assets.txt"
  while IFS= read -r fe_ci_asset; do
    docker exec "$fe_ci_frontend" wget -T 5 -qO- "http://127.0.0.1$fe_ci_asset" >"$fe_ci_tmp/asset"
    test -s "$fe_ci_tmp/asset"
    if cmp -s "$fe_ci_tmp/index.html" "$fe_ci_tmp/asset"; then
      printf 'Asset incorrectly returned the SPA HTML: %s\n' "$fe_ci_asset" >&2
      exit 1
    fi
  done <"$fe_ci_tmp/assets.txt"

  docker cp "$fe_ci_frontend:/usr/share/nginx/html/console.html" "$fe_ci_tmp/console.html"
  test -s "$fe_ci_tmp/console.html"
  docker exec "$fe_ci_frontend" wget -T 5 -qO- http://127.0.0.1/console.html >"$fe_ci_tmp/console-served.html"
  cmp "$fe_ci_tmp/console.html" "$fe_ci_tmp/console-served.html"
  if cmp -s "$fe_ci_tmp/index.html" "$fe_ci_tmp/console-served.html"; then
    printf 'Console asset incorrectly returned the SPA HTML.\n' >&2
    exit 1
  fi

  docker exec "$fe_ci_frontend" wget -T 5 -qO- http://127.0.0.1/equipment/ci-deep-link >"$fe_ci_tmp/spa.html"
  cmp "$fe_ci_tmp/index.html" "$fe_ci_tmp/spa.html"
  fe_ci_response="$(docker exec "$fe_ci_frontend" wget -T 5 -qO- 'http://127.0.0.1/api/ci-proxy?check=path')"
  if [ "$fe_ci_response" != '/api/ci-proxy?check=path' ]; then
    printf 'API path/query changed through the proxy: %s\n' "$fe_ci_response" >&2
    exit 1
  fi
  docker exec "$fe_ci_frontend" nginx -T >"$fe_ci_tmp/nginx.conf" 2>&1
  grep -q 'proxy_buffering off;' "$fe_ci_tmp/nginx.conf"
}

# Test the EKS Service default, then an explicit Compose-style override.
docker run --detach --name "$fe_ci_frontend" --platform linux/amd64 \
  --network "$fe_ci_network" "$fe_ci_image" >/dev/null
check_frontend
docker rm --force --volumes "$fe_ci_frontend" >/dev/null
docker network disconnect "$fe_ci_network" "$fe_ci_backend"
docker network connect --alias be "$fe_ci_network" "$fe_ci_backend"
docker run --detach --name "$fe_ci_frontend" --platform linux/amd64 \
  --network "$fe_ci_network" --env BACKEND_UPSTREAM=be:8000 "$fe_ci_image" >/dev/null
check_frontend

printf 'FE image smoke test passed: %s (default and overridden upstream)\n' "$fe_ci_image"
