# DB 덤프 백업 및 복원

명령은 프로젝트 루트(`compose.yaml`이 있는 디렉터리)에서 실행한다. `DB/.env`가 있어야 하고 Docker가 실행 중이어야 한다. 이 프로젝트는 PostgreSQL 17, TimescaleDB, pgvector를 사용하며 DB 데이터는 Docker named volume `postgres_data`에 저장된다. `docker compose down`은 볼륨을 유지하지만 `docker compose down -v`는 삭제한다.

## 덤프 만들기

DB 컨테이너를 시작한다.

```bash
docker compose --env-file DB/.env up -d db
```

날짜와 시간이 붙은 전체 DB 덤프를 `DB/dump/`에 저장한다. `-T`는 덤프의 바이너리 출력이 터미널에 의해 변형되지 않게 한다. 실행 중인 DB에서도 `pg_dump`는 일관된 스냅샷을 만든다.

```bash
mkdir -p DB/dump
dump_file="DB/dump/skadi_$(date +%Y%m%d-%H%M%S).dump"
docker compose --env-file DB/.env exec -T db \
  sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "$dump_file"
```

덤프를 읽어 보고 크기를 확인한다. 아래 `dump_file`은 바로 위 명령과 같은 셸에서 실행할 때 사용 가능하다. 다른 터미널이라면 실제 파일 경로로 바꾼다.

```bash
docker compose --env-file DB/.env exec -T db pg_restore --file=/dev/null < "$dump_file"
ls -lh "$dump_file"
```

기존 덤프 파일을 같은 이름으로 다시 만들면 즉시 덮어써진다. 새 파일로 백업하고 검사가 끝난 뒤 필요한 파일을 교체한다. `DB/dump/*.dump`는 `.gitignore`에 등록되어 Git에 올라가지 않는다.

TimescaleDB 내부 테이블(`continuous_agg` 등)의 순환 외래 키 경고가 나올 수 있다. 위 명령은 `--data-only`가 아닌 전체 DB 덤프다. 경고 자체는 백업 실패를 뜻하지 않지만, 명령 종료 상태와 덤프 검사는 확인한다.

## 덤프 복원하기

복원은 **비어 있는 DB**에 한다. 현재 데이터가 들어 있는 `skadi`에 그대로 `pg_restore`를 실행하지 않는다. 먼저 같은 Docker 이미지에서 별도의 `skadi_restore` DB를 만들어 복원하고 결과를 확인한다. TimescaleDB와 PostgreSQL 버전은 덤프를 만든 환경과 맞춘다.

`DB/dump/`에서 적용할 `.dump` 파일을 선택한다. 아래 예시는 `skadi_20261120-094247.dump`를 사용한다. 다른 파일을 적용하려면 `dump_file` 값만 바꾼다. `skadi_restore`가 이미 있다면 새 이름을 정해 아래 명령 전체에서 일관되게 바꾼다.

```bash
ls -lh DB/dump/*.dump
dump_file="DB/dump/skadi_20261120-094247.dump"
test -f "$dump_file" || { echo "덤프 파일이 없습니다: $dump_file" >&2; exit 1; }

docker compose --env-file DB/.env up -d db

docker compose --env-file DB/.env exec -T db \
  sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE skadi_restore"'

docker compose --env-file DB/.env exec -T db \
  sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d skadi_restore -c "CREATE EXTENSION IF NOT EXISTS timescaledb; CREATE EXTENSION IF NOT EXISTS vector;"'

docker compose --env-file DB/.env exec -T db \
  sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d skadi_restore -c "SELECT timescaledb_pre_restore();"'

docker compose --env-file DB/.env exec -T db \
  sh -c 'exec pg_restore --exit-on-error --no-owner --no-acl -U "$POSTGRES_USER" -d skadi_restore' \
  < "$dump_file"

docker compose --env-file DB/.env exec -T db \
  sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d skadi_restore -c "SELECT timescaledb_post_restore();"'
```

복원된 주요 테이블의 행 수를 확인한다.

```bash
docker compose --env-file DB/.env exec -T db \
  sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d skadi_restore -c "SELECT count(*) FROM sensor_signal; SELECT count(*) FROM sensor_data_1m; SELECT count(*) FROM equipment_run_state_1m;"'
```

### 복원한 DB를 서비스에 연결하기

`skadi_restore`에 복원해도 서비스의 연결 대상은 자동으로 바뀌지 않는다. `DB/.env`가 `POSTGRES_DB=skadi`인 상태라면 화면은 계속 기존 `skadi` DB를 조회한다. 복원한 DB의 행 수를 확인한 뒤 `DB/.env`에서 아래 값을 설정한다.

```dotenv
POSTGRES_DB=skadi_restore
```

서비스를 다시 실행하면 Compose가 바뀐 환경 변수를 적용하고, 복원 DB에 마이그레이션을 실행한 뒤 BE와 FE를 시작한다. 이 프로젝트에서 추가한 마이그레이션 파일이 이미지에도 포함되도록 빌드한다.

```bash
docker compose --env-file DB/.env up -d --build
docker compose --env-file DB/.env ps -a
docker compose --env-file DB/.env exec -T db \
  sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT current_database(); SELECT count(*) FROM sensor_data_1m; SELECT count(*) FROM equipment_run_state_1m;"'
```

기존 `skadi` DB와 볼륨은 그대로 유지된다. DB 조회·백업 명령도 이후에는 `POSTGRES_DB`에 지정된 DB를 대상으로 실행된다.

DB 이름을 `skadi`로 유지하며 복원할 때는 **새로 만든 빈 볼륨의 DB**에서 DB 컨테이너만 먼저 시작하고, 위 복원 절차의 대상 DB 이름을 `skadi`로 바꿔 실행한다. 이 경우 `CREATE DATABASE` 단계는 생략한다. 복원이 완료된 다음에 BE와 FE를 시작한다. 기존 볼륨에 데이터가 있다면 볼륨을 삭제하거나 기존 DB를 덮어쓰지 말고, 위의 별도 DB 복원으로 먼저 확인한다.

TimescaleDB 복원에는 `timescaledb_pre_restore()`와 `timescaledb_post_restore()`가 필요하다. `pg_restore -j` 병렬 복원은 TimescaleDB 카탈로그 복원에 문제가 생길 수 있으므로 사용하지 않는다. 복원 중 오류가 나면 `timescaledb_post_restore()`를 실행해 복원 모드를 해제한 후 오류를 확인한다.

참고: [Tiger Data의 논리 백업·복원 문서](https://github.com/timescale/Tiger-Data-Docs/blob/main/src/content/docs/deploy/self-hosted/backup-and-restore/logical-backup.mdx), [PostgreSQL `pg_dump`](https://www.postgresql.org/docs/17/app-pgdump.html), [PostgreSQL `pg_restore`](https://www.postgresql.org/docs/17/app-pgrestore.html)
