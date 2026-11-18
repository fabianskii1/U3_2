"""Import the 2026 CDU P1-P6 CSV files into 1-minute telemetry tables.

Run after Alembic upgrade. Each monthly file is one transaction; reruns skip
identical rows and reject changed values instead of overwriting them.
"""

import argparse
import asyncio
import csv
import math
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import asyncpg
from sqlalchemy.engine import make_url

from app.config import get_settings

KST = ZoneInfo("Asia/Seoul")
METRICS = (
    "vibration_rms_mm_s",
    "bearing_temp_c",
    "fluid_temp_c",
    "suction_pressure_kpa_g",
    "discharge_pressure_kpa_g",
    "motor_current_a",
    "motor_rpm",
    "voltage_v",
)
CSV_COLUMNS = ("timestamp", "pump_id", "run_status", *METRICS)
STAGE_COLUMNS = ("equipment_id", "measured_at", "run_status", *METRICS)
VALID_STATUSES = {"RUNNING", "STOPPED"}
STAGE_SQL = """
CREATE TEMP TABLE cdu_import_stage (
  equipment_id varchar(30) NOT NULL,
  measured_at timestamptz NOT NULL,
  run_status varchar(16) NOT NULL,
  vibration_rms_mm_s double precision NOT NULL,
  bearing_temp_c double precision NOT NULL,
  fluid_temp_c double precision NOT NULL,
  suction_pressure_kpa_g double precision NOT NULL,
  discharge_pressure_kpa_g double precision NOT NULL,
  motor_current_a double precision NOT NULL,
  motor_rpm double precision NOT NULL,
  voltage_v double precision NOT NULL
) ON COMMIT DELETE ROWS
"""
VALUES_SQL = ", ".join(f"('{name}', s.{name})" for name in METRICS)
SIGNAL_ROWS_SQL = f"""
FROM cdu_import_stage s
CROSS JOIN LATERAL (VALUES {VALUES_SQL}) AS v(source_column, value)
JOIN sensor sn ON sn.equipment_id = s.equipment_id
JOIN sensor_signal sig ON sig.sensor_id = sn.sensor_id
                      AND sig.source_column = v.source_column
"""


def expected_files(root: Path) -> list[Path]:
    files = [
        root / f"P{pump}" / f"P{pump}_2026-{month:02d}.csv"
        for pump in range(1, 7)
        for month in range(1, 13)
    ]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise ValueError(f"Missing {len(missing)} CSV files; first: {missing[0]}")
    return files


def csv_records(path: Path):
    pump = path.parent.name
    month = path.stem[-2:]
    previous = None
    count = 0
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CSV_COLUMNS:
            raise ValueError(f"{path}: unexpected CSV header: {reader.fieldnames}")
        for line, row in enumerate(reader, 2):
            if row["pump_id"] != pump:
                raise ValueError(f"{path}:{line}: pump_id {row['pump_id']!r} != {pump}")
            if row["run_status"] not in VALID_STATUSES:
                raise ValueError(f"{path}:{line}: invalid run_status {row['run_status']!r}")
            try:
                local = datetime.fromisoformat(row["timestamp"])
                if local.tzinfo is not None or local.second or local.microsecond:
                    raise ValueError("expected naive minute timestamp")
                if local.year != 2026 or local.month != int(month):
                    raise ValueError("timestamp outside file month")
                measured_at = local.replace(tzinfo=KST).astimezone(UTC)
                values = tuple(float(row[name]) for name in METRICS)
                if not all(math.isfinite(value) for value in values):
                    raise ValueError("non-finite number")
            except (TypeError, ValueError) as error:
                raise ValueError(f"{path}:{line}: {error}") from error
            if previous is not None and measured_at <= previous:
                raise ValueError(f"{path}:{line}: timestamp not strictly increasing")
            previous = measured_at
            count += 1
            yield (pump, measured_at, row["run_status"], *values)
    if count == 0:
        raise ValueError(f"{path}: empty CSV")


async def check_signal_mapping(conn: asyncpg.Connection, pump: str) -> None:
    rows = await conn.fetch(
        """SELECT sig.source_column FROM sensor_signal sig
           JOIN sensor sn ON sn.sensor_id = sig.sensor_id
           WHERE sn.equipment_id = $1""",
        pump,
    )
    columns = [row["source_column"] for row in rows]
    if len(columns) != len(METRICS) or set(columns) != set(METRICS):
        raise ValueError(f"{pump}: signal mapping does not match the eight CSV metrics: {columns}")


async def import_file(conn: asyncpg.Connection, path: Path, batch_size: int) -> tuple[int, int]:
    count = 0
    async with conn.transaction():
        batch = []
        for record in csv_records(path):
            batch.append(record)
            if len(batch) >= batch_size:
                await conn.copy_records_to_table(
                    "cdu_import_stage", records=batch, columns=STAGE_COLUMNS
                )
                count += len(batch)
                batch.clear()
        if batch:
            await conn.copy_records_to_table(
                "cdu_import_stage", records=batch, columns=STAGE_COLUMNS
            )
            count += len(batch)

        state_conflicts = await conn.fetchval(
            """SELECT count(*) FROM cdu_import_stage s
               JOIN equipment_run_state_1m old USING (equipment_id, measured_at)
               WHERE old.run_status IS DISTINCT FROM s.run_status"""
        )
        signal_conflicts = await conn.fetchval(
            f"""SELECT count(*) {SIGNAL_ROWS_SQL}
                JOIN sensor_data_1m old ON old.signal_id = sig.signal_id
                    AND old.measured_at = s.measured_at
                WHERE old.value IS DISTINCT FROM v.value"""
        )
        if state_conflicts or signal_conflicts:
            raise ValueError(
                f"{path}: existing data differs "
                f"(states={state_conflicts}, signals={signal_conflicts}); file rolled back"
            )

        state_result = await conn.execute(
            """INSERT INTO equipment_run_state_1m
                   (equipment_id, measured_at, run_status)
               SELECT equipment_id, measured_at, run_status FROM cdu_import_stage
               WHERE true
               ON CONFLICT (equipment_id, measured_at) DO NOTHING"""
        )
        signal_result = await conn.execute(
            f"""INSERT INTO sensor_data_1m (signal_id, measured_at, value)
                SELECT sig.signal_id, s.measured_at, v.value {SIGNAL_ROWS_SQL}
                WHERE true
                ON CONFLICT (signal_id, measured_at) DO NOTHING"""
        )
    inserted_states = int(state_result.rsplit(" ", 1)[-1])
    inserted_signals = int(signal_result.rsplit(" ", 1)[-1])
    if inserted_states > count or inserted_signals > count * len(METRICS):
        raise RuntimeError(f"{path}: inserted row count exceeds parsed CSV rows")
    return inserted_states, inserted_signals


async def run(root: Path, batch_size: int) -> None:
    files = expected_files(root)
    url = make_url(get_settings().database_url)
    conn = await asyncpg.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        database=url.database,
    )
    try:
        await conn.execute("SELECT pg_advisory_lock(hashtext('cdu_2026_1m_import'))")
        await conn.execute(STAGE_SQL)
        for pump in range(1, 7):
            await check_signal_mapping(conn, f"P{pump}")
        total_states = total_signals = 0
        for index, path in enumerate(files, 1):
            states, signals = await import_file(conn, path, batch_size)
            total_states += states
            total_signals += signals
            print(f"[{index:02d}/72] {path.name}: +{states} states, +{signals} signals", flush=True)
        print(f"Done: +{total_states} states, +{total_signals} signals", flush=True)
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", type=Path, required=True, help="Directory containing P1 through P6"
    )
    parser.add_argument("--batch-size", type=int, default=5000)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    asyncio.run(run(args.data, args.batch_size))


if __name__ == "__main__":
    main()
