#!/usr/bin/env bash
set -euo pipefail

db_ci_image="${1:?Usage: bash DB/docker/ci-smoke.sh IMAGE}"
db_ci_name="skadi-db-ci-${RANDOM}-${RANDOM}"

cleanup() {
  db_ci_exit_status=$?
  if [ "$db_ci_exit_status" -ne 0 ]; then
    docker logs --tail 100 "$db_ci_name" >&2 || true
  fi
  docker rm --force --volumes "$db_ci_name" >/dev/null 2>&1 || true
  exit "$db_ci_exit_status"
}
trap cleanup EXIT

db_ci_platform="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$db_ci_image")"
if [ "$db_ci_platform" != linux/amd64 ]; then
  printf 'Expected linux/amd64, got %s\n' "$db_ci_platform" >&2
  exit 1
fi

# Disposable credentials only; never read the application's env or dump files.
db_ci_password="$(openssl rand -hex 24)"
printf 'POSTGRES_DB=ci_db\nPOSTGRES_USER=ci_user\nPOSTGRES_PASSWORD=%s\nPGDATA=/var/lib/postgresql/data/pgdata\nNO_TS_TUNE=true\nTIMESCALEDB_TELEMETRY=off\n' "$db_ci_password" |
  docker run --detach --name "$db_ci_name" \
    --platform linux/amd64 --network none --user 70:70 \
    --cap-drop ALL --security-opt no-new-privileges=true \
    --memory 1g --cpus 1 \
    --tmpfs /var/lib/postgresql/data:rw,uid=0,gid=70,mode=2770,size=536870912 \
    --env-file /dev/stdin --entrypoint sh "$db_ci_image" -ec \
    'mkdir -p /var/lib/postgresql/data/lost+found; exec docker-entrypoint.sh "$@"' \
    -- postgres -c shared_buffers=128MB -c max_connections=50 >/dev/null

db_ci_ready=false
for db_ci_attempt in {1..60}; do
  if docker exec "$db_ci_name" pg_isready -h 127.0.0.1 -U ci_user -d ci_db >/dev/null 2>&1; then
    db_ci_ready=true
    break
  fi
  if [ "$(docker inspect --format '{{.State.Running}}' "$db_ci_name")" != true ]; then
    printf 'Database exited during initialization.\n' >&2
    exit 1
  fi
  sleep 2
done
if [ "$db_ci_ready" != true ]; then
  printf 'Database did not become ready after %s checks.\n' "$db_ci_attempt" >&2
  exit 1
fi

docker exec -i "$db_ci_name" sh -ec \
  'PGPASSWORD="$POSTGRES_PASSWORD" exec psql --no-password -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' <<'SQL'
CREATE TABLE ci_readings (observed_at timestamptz NOT NULL, reading double precision);
SELECT create_hypertable('ci_readings', 'observed_at');
INSERT INTO ci_readings VALUES ('2026-01-01 00:00:00+00', 1.0);

CREATE TABLE ci_embeddings (id integer PRIMARY KEY, embedding vector(3));
INSERT INTO ci_embeddings VALUES (1, '[1,2,3]');

DO $$
BEGIN
  IF (SELECT count(*) FROM ci_readings) <> 1 THEN
    RAISE EXCEPTION 'TimescaleDB write/read check failed';
  END IF;
  IF (SELECT embedding <-> '[1,2,3]'::vector FROM ci_embeddings WHERE id = 1) <> 0 THEN
    RAISE EXCEPTION 'pgvector distance check failed';
  END IF;
END
$$;

SELECT extname, extversion FROM pg_extension
WHERE extname IN ('timescaledb', 'vector') ORDER BY extname;
SQL

printf 'DB image smoke test passed: %s\n' "$db_ci_image"
