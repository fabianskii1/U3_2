"""Validate and install the November CDU alarm fixture in a migrated database."""

import argparse
import asyncio
import csv
import math
from datetime import UTC, datetime, timedelta
from itertools import islice
from pathlib import Path

import asyncpg
from sqlalchemy.engine import make_url

from app.config import get_settings
from scripts.import_cdu_1m import KST, METRICS, SIGNAL_ROWS_SQL, STAGE_COLUMNS, STAGE_SQL

PUMPS = [f"P{number}" for number in range(1, 7)]
START = datetime(2026, 11, 1, tzinfo=KST)
MINUTES = 30 * 24 * 60
LEVELS = {"주의": 1, "경고": 2, "위험": 3, "비상": 4}
EVENT_TYPES = {"예측", "임계치 초과"}
CALCULATIONS = {"FIXED", "BASELINE_RATIO", "BASELINE_OFFSET", "EXPECTED_OFFSET"}
PREFIX = "CDU_2026-11_P1-P6_Priority_"


def timestamp(value: str) -> datetime:
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        raise ValueError(f"Timezone required: {value}")
    return moment.astimezone(UTC)


def finite(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Non-finite value: {value}")
    return number


def telemetry(path: Path, pump: str):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {
            "timestamp",
            "plant_id",
            "unit_id",
            "equipment_id",
            "pump_id",
            "run_status",
            *METRICS,
        }
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"{path}: missing telemetry columns")
        count = 0
        for count, row in enumerate(reader, 1):
            moment = datetime.fromisoformat(row["timestamp"])
            expected = START + timedelta(minutes=count - 1)
            if (
                count > MINUTES
                or moment != expected.replace(tzinfo=None)
                or row["pump_id"] != pump
                or row["equipment_id"] != pump
                or (row["plant_id"], row["unit_id"]) != ("REF-01", "CDU-01")
                or row["run_status"] not in {"RUNNING", "STOPPED"}
            ):
                raise ValueError(f"{path}:{count + 1}: invalid pump, minute or run status")
            yield (
                pump,
                expected.astimezone(UTC),
                row["run_status"],
                *(finite(row[metric]) for metric in METRICS),
            )
        if count != MINUTES:
            raise ValueError(f"{path}: expected {MINUTES} rows, found {count}")


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        yield from csv.DictReader(stream)


def pump_id(row: dict) -> str:
    pump = row["equipment_id"].replace("-", "")
    if (
        pump not in PUMPS
        or row["equipment_id"] != f"P-{pump[1:]}"
        or row["plant_id"] != "PLANT-01"
        or row["equipment_group_id"] not in {"CDU", "CDU-01"}
    ):
        raise ValueError(f"Unexpected CDU asset: {row}")
    return pump


async def read_assets(conn):
    rows = await conn.fetch(
        """SELECT eq.equipment_id, s.sensor_id, sig.signal_id, sig.source_column,
                  sig.unit, s.unit AS sensor_unit
           FROM equipment eq JOIN sensor s USING (equipment_id)
           JOIN sensor_signal sig USING (sensor_id)
           WHERE eq.equipment_id = ANY($1::text[]) AND eq.plant_id = 'PLANT-01'
             AND eq.equipment_group_id = 'CDU-01'""",
        PUMPS,
    )
    mapping = {(row["equipment_id"], row["source_column"]): row for row in rows}
    if len(mapping) != len(rows) or set(mapping) != {(p, m) for p in PUMPS for m in METRICS}:
        raise ValueError("CDU signal mapping does not match the six pumps and eight CSV metrics")
    return mapping


def read_fixture(root: Path, assets: dict) -> tuple[dict, dict]:
    setpoints = {}
    for row in read_csv(root / f"{PREFIX}Setpoints.csv"):
        pump = pump_id(row)
        asset = assets[pump, row["sensor_column"]]
        key = row["setpoint_id"]
        start = timestamp(row["effective_from"])
        end = timestamp(row["effective_to"]) if row["effective_to"] else None
        calculation = row["calculation_type"]
        reference = row["reference"] or None
        duration = int(row["filter_minutes"])
        if (
            not key
            or key in setpoints
            or len(key) > 128
            or asset["sensor_id"] != row["sensor_id"]
            or row["unit"] not in {asset["unit"], asset["sensor_unit"]}
            or calculation not in CALCULATIONS
            or (calculation == "FIXED") != (reference is None)
            or {"HIGH": ">=", "LOW": "<="}.get(row["direction"]) != row["operator"]
            or duration <= 0
            or (end is not None and end <= start)
        ):
            raise ValueError(f"Invalid setpoint: {key}")
        setpoints[key] = {
            "equipment_id": pump,
            "sensor_id": asset["sensor_id"],
            "signal_id": asset["signal_id"],
            "alarm_level": LEVELS[row["alarm_level"]],
            "direction": row["direction"],
            "operator": row["operator"],
            "calculation_type": calculation,
            "parameter": finite(row["parameter"]),
            "reference": reference,
            "unit": row["unit"],
            "filter_minutes": duration,
            "effective_from": start,
            "effective_to": end,
        }

    alarms = {}
    for row in read_csv(root / f"{PREFIX}Alarms.csv"):
        key = row["alarm_id"]
        setpoint_id = row["setpoint_id"]
        rule = setpoints[setpoint_id]
        pump = pump_id(row)
        event_type = row["alarm_type"]
        start = timestamp(row["alarm_start_time"])
        end = timestamp(row["alarm_end_time"])
        sensor_start = timestamp(row["sensor_start_time"]) if row["sensor_start_time"] else None
        sensor_end = timestamp(row["sensor_end_time"]) if row["sensor_end_time"] else None
        level = LEVELS[row["alarm_level"]]
        if (
            not key
            or key in alarms
            or len(key) > 128
            or pump != rule["equipment_id"]
            or row["sensor_id"] != rule["sensor_id"]
            or level != rule["alarm_level"]
            or event_type not in EVENT_TYPES
            or start < rule["effective_from"]
            or (rule["effective_to"] is not None and start >= rule["effective_to"])
            or end < start
            or (sensor_start is None) != (sensor_end is None)
            or (sensor_start is not None and not start <= sensor_start <= sensor_end)
            or (event_type == "임계치 초과" and sensor_start != start)
        ):
            raise ValueError(f"Invalid alarm: {key}")
        alarms[key] = {
            "equipment_id": pump,
            "sensor_id": rule["sensor_id"],
            "alarm_level": level,
            "alarm_type": "Setpoint",
            "event_type": event_type,
            "setpoint_id": setpoint_id,
            "alarm_start_time": start,
            "alarm_end_time": end,
            "sensor_start_time": sensor_start,
            "sensor_end_time": sensor_end,
            "cof_score": finite(row["alarm_score"]),
            "unit": rule["unit"],
            "user_message": f"{event_type} · {rule['sensor_id']} · {row['alarm_level']}",
        }
    if len(alarms) != 10 or any(
        sum(rule["equipment_id"] == pump for rule in setpoints.values()) != 44 for pump in PUMPS
    ):
        raise ValueError("Expected 10 alarms and 44 setpoints per pump")
    return setpoints, alarms


async def insert_fixture_rows(
    conn, table: str, id_column: str, records: dict, *, insert: bool = True
) -> None:
    # Table, key and column names come from this module, never from CSV headers.
    columns = ", ".join((id_column, *next(iter(records.values()))))
    slots = ", ".join(f"${i}" for i in range(1, len(next(iter(records.values()))) + 2))
    for key, fields in records.items():
        query = f"SELECT {columns} FROM {table} WHERE {id_column} = $1"
        saved = await conn.fetchrow(query, key)
        if saved is not None:
            if any(saved[field] != value for field, value in fields.items()):
                raise ValueError(f"{table}: existing record differs: {key}")
            continue
        if not insert:
            continue
        await conn.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({slots})",
            key,
            *fields.values(),
        )


async def run(root: Path, apply: bool) -> None:
    url = make_url(get_settings().database_url)
    conn = await asyncpg.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        database=url.database,
    )
    try:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext('cdu_2026_1m_import'))")
            assets = await read_assets(conn)
            setpoints, alarms = read_fixture(root, assets)
            await conn.execute(STAGE_SQL)
            for pump in PUMPS:
                rows = telemetry(root / f"{pump}_2026-11.csv", pump)
                while batch := list(islice(rows, 5000)):
                    await conn.copy_records_to_table(
                        "cdu_import_stage", records=batch, columns=STAGE_COLUMNS
                    )
            state_count = len(PUMPS) * MINUTES
            signal_count = state_count * len(METRICS)
            await insert_fixture_rows(conn, "setpoint", "setpoint_id", setpoints)
            await insert_fixture_rows(conn, "alarm", "source_alarm_id", alarms, insert=apply)
            if not apply:
                print(
                    f"Validated: {state_count} state rows, {signal_count} samples, "
                    f"{len(setpoints)} setpoints, {len(alarms)} alarms"
                )
                # Roll back temporary setpoint inserts used to validate range constraints.
                raise PreviewComplete

            old_states = await conn.execute(
                "DELETE FROM equipment_run_state_1m WHERE equipment_id = ANY($1::text[])", PUMPS
            )
            old_signals = await conn.execute(
                """DELETE FROM sensor_data_1m AS d USING sensor_signal AS sig, sensor AS s
                   WHERE d.signal_id = sig.signal_id AND sig.sensor_id = s.sensor_id
                     AND s.equipment_id = ANY($1::text[])""",
                PUMPS,
            )
            state_result = await conn.execute(
                """INSERT INTO equipment_run_state_1m (equipment_id, measured_at, run_status)
                   SELECT equipment_id, measured_at, run_status FROM cdu_import_stage"""
            )
            signal_result = await conn.execute(
                f"""INSERT INTO sensor_data_1m (signal_id, measured_at, value)
                    SELECT sig.signal_id, s.measured_at, v.value {SIGNAL_ROWS_SQL}"""
            )
            if (
                state_result != f"INSERT 0 {state_count}"
                or signal_result != f"INSERT 0 {signal_count}"
            ):
                raise RuntimeError(
                    "Unexpected telemetry row counts. Fixture replacement rolled back."
                )
        print(
            f"Committed: replaced {old_states} state rows and {old_signals} samples "
            f"with {state_count} state rows and {signal_count} samples."
        )
    except PreviewComplete:
        pass
    finally:
        await conn.close()


class PreviewComplete(Exception):
    """Roll back after the dry run."""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", type=Path, required=True, help="Directory containing the CSV files"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Commit scoped CDU fixture replacement"
    )
    args = parser.parse_args()
    asyncio.run(run(args.data, args.apply))


if __name__ == "__main__":
    main()
