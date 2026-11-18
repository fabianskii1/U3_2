# SKADI database container

PostgreSQL 17 + TimescaleDB + pgvector. The image is pinned to `timescale/timescaledb:2.32.0-pg17`. The DB image creates the `skadi` database and enables both extensions. Application tables and the supplied Ulsan CLX reference data are managed by the BE Alembic migration service.

## Start

```bash
cd U3_2
cp DB/.env.example DB/.env
# Edit DB/.env and set POSTGRES_PASSWORD to a strong value.
docker compose --env-file DB/.env up -d --build db
```

If you are already in the project root, omit `cd U3_2`. The Compose file is at the project root. The database listens on `127.0.0.1:5433` by default, so an API process on the same server can connect through the host port. Set `POSTGRES_PORT` in `DB/.env` if that port is occupied. A containerized API in the same Compose project should connect to host `db` on port `5432`. To start DB, migrations, and BE together, see [BE/README.md](../BE/README.md).

## Check

```bash
docker compose --env-file DB/.env ps
docker compose --env-file DB/.env exec db psql -U skadi -d skadi -c "SELECT extname, extversion FROM pg_extension WHERE extname IN ('timescaledb', 'vector') ORDER BY extname;"
```

Use the values of `POSTGRES_USER` and `POSTGRES_DB` from `DB/.env` in the second command if you changed them.

The initialization SQL runs only when the named data volume is created for the first time. For an existing volume, enable a missing extension with a migration or `CREATE EXTENSION` in the target database. Do not delete the volume to rerun initialization; that would erase the database. `docker compose --env-file DB/.env down` stops the container while retaining the volume.

## Database image CI

`.github/workflows/build-db.yaml` builds a `linux/amd64` database image when files
under `DB/docker/` or the workflow itself change on `main`. It also supports
Actions → **Build database image** → **Run workflow**, selecting `main`.

The workflow loads the image into the runner's Docker engine, then runs
`DB/docker/ci-smoke.sh` before publishing. The check starts an isolated temporary
database as UID/GID 70 with a memory-backed data directory and random test
credentials. It verifies password authentication, TimescaleDB hypertable writes
and reads, and pgvector distance calculation. The temporary container and its
data are removed on success or failure.

The build context is `DB/docker`; its `.dockerignore` permits only the Dockerfile
and initialization SQL. Application env files, dump files, and the CI script are
not included in the image. CI does not connect to EKS or use production DB data.

Publishing reuses the existing GitHub Actions Secrets `HARBOR_USERNAME` and
`HARBOR_PASSWORD`. No DB password or Argo CD token is required. After the check
passes, the tested image is pushed as:

```text
harbor.skala-us.com/u3-2/db:<full Git commit SHA>
```

The workflow does not update `k8s/db/statefulset.yaml`, sync Argo CD, run
migrations, or restore a dump. The running DB remains on its explicitly selected
image. Before deploying a new tag, check backups and PostgreSQL/extension
compatibility, review the manifest change, then sync the DB Application.
This initial-database check does not validate an upgrade of an existing data volume.

To run the same build and check locally:

```bash
docker buildx build --platform linux/amd64 \
  -f DB/docker/Dockerfile.db \
  -t skadi-db-ci-check:local --load ./DB/docker
bash DB/docker/ci-smoke.sh skadi-db-ci-check:local
```

BE, FE, AI, and DB workflows have separate path filters; a DB-only change does
not start the other component builds. See [the CI guide](../docs/ci.md).
