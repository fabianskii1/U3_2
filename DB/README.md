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
