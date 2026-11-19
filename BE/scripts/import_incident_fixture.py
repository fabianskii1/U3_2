"""Validate and install the November CDU incident fixture (plan/incidents/db.md).

Without --apply every write runs inside a transaction that is rolled back, so the
database constraints are exercised and the planned changes are printed.
"""

import argparse
import asyncio
import csv
import math
import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import asyncpg
from sqlalchemy.engine import make_url

from app.config import get_settings

INCIDENTS = "CDU_2026-11_incidents.csv"
CANDIDATES = "CDU_2026-11_incident_candidates.csv"
ALARMS = "CDU_2026-11_alarms.csv"
KST = timezone(timedelta(hours=9))
PLANT = "PLANT-01"
GROUP = "CDU-01"
PUMPS = {f"P{number}" for number in range(1, 7)}
LEVELS = {"주의": 1, "경고": 2, "위험": 3, "비상": 4}
EVENT_TYPES = {"예측", "임계치 초과"}
BOOLS = {"True": True, "False": False}
ALARM_FIELDS = (
    "alarm_start_time",
    "alarm_end_time",
    "sensor_start_time",
    "sensor_end_time",
    "cof_score",
    "peak_level",
    "incident_id",
)


class FixtureError(ValueError):
    pass


class PreviewComplete(Exception):
    """Roll back after the dry run."""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise FixtureError(message)


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def timestamp(value: str) -> datetime | None:
    if not value:
        return None
    moment = datetime.fromisoformat(value)
    check(moment.tzinfo is not None, f"Timezone required: {value}")
    return moment.astimezone(UTC)


def finite(value: str) -> float:
    number = float(value)
    check(math.isfinite(number), f"Non-finite value: {value}")
    return number


def flag(value: str) -> bool:
    check(value in BOOLS, f"Expected True/False: {value}")
    return BOOLS[value]


def equipment(row: dict) -> str:
    pump = row["equipment_id"].replace("-", "")
    check(
        pump in PUMPS
        and row.get("plant_id", PLANT) == PLANT
        and row.get("equipment_group_id", GROUP) in {"CDU", GROUP},
        f"Unexpected CDU asset: {row['equipment_id']}",
    )
    return pump


def incident_key(value: str) -> str:
    key = re.sub(r"^INC-P-(\d)-", r"INC-P\1-", value)
    check(re.fullmatch(r"INC-P\d-\d{12}", key) is not None, f"Invalid incident ID: {value}")
    return key


def read_fixture(root: Path):
    incidents: dict[str, dict] = {}
    linked_ids: dict[str, list[str]] = {}
    for row in read_csv(root / INCIDENTS):
        key = incident_key(row["incident_id"])
        check(key not in incidents, f"Duplicate incident: {key}")
        start = timestamp(row["incident_start_time"])
        end = timestamp(row["incident_end_time"])
        incidents[key] = {
            "plant_id": PLANT,
            "equipment_group_id": GROUP,
            "equipment_id": equipment(row),
            "incident_start_time": start,
            "detect_time": timestamp(row["detect_time"]),
            "first_alarm_time": timestamp(row["first_alarm_time"]),
            "incident_end_time": end,
            "peak_level": LEVELS[row["peak_level"]],
            "lead_sensor_id": row["lead_sensor_id"] or None,
            "diagnosis": row["diagnosis"],
            "top_risk_fault": row["top_risk_fault"],
            "top_cof": finite(row["top_cof"]),
            "top_pof": finite(row["top_pof"]),
            "incident_score": finite(row["incident_score"]),
            "alarm_grade": row["alarm_grade"],
            "grade_reason": row["grade_reason"],
            "response_time_h": finite(row["response_time_h"]),
            "actionable": flag(row["actionable"]),
            "alarm_count": int(row["alarm_count"]),
            "trend_count": int(row["trend_count"]),
            "source_file": INCIDENTS,
        }
        linked_ids[key] = [item for item in row["alarm_ids"].split(";") if item]

    candidates: dict[str, list[dict]] = {key: [] for key in incidents}
    for row in read_csv(root / CANDIDATES):
        key = incident_key(row["incident_id"])
        check(key in incidents, f"Candidate for unknown incident: {key}")
        check(
            equipment(row) == incidents[key]["equipment_id"], f"{key}: candidate equipment differs"
        )
        candidates[key].append(
            {
                "rank": int(row["rank"]),
                "fault": row["fault"],
                **{
                    name: finite(row[name])
                    for name in (
                        "rule_score_s",
                        "s_top3_sum",
                        "p",
                        "cof",
                        "p_trend",
                        "pf_hours",
                        "p_pf",
                        "pof",
                        "score",
                    )
                },
                **{name: int(row[name]) for name in ("speed", "impact", "w")},
                "is_diagnosis": flag(row["is_diagnosis"]),
                "is_top_risk": flag(row["is_top_risk"]),
                "evidence": row["evidence"],
            }
        )

    alarms: dict[str, dict] = {}
    for row in read_csv(root / ALARMS):
        key = row["alarm_id"]
        check(key and key not in alarms, f"Duplicate or empty alarm ID: {key}")
        check(row["alarm_type"] in EVENT_TYPES, f"{key}: unknown alarm type")
        alarms[key] = {
            "equipment_id": equipment(row),
            "sensor_id": row["sensor_id"],
            "setpoint_id": row["setpoint_id"],
            "alarm_level": LEVELS[row["alarm_level"]],
            "event_type": row["alarm_type"],
            "alarm_start_time": timestamp(row["alarm_start_time"]),
            "alarm_end_time": timestamp(row["alarm_end_time"]),
            "sensor_start_time": timestamp(row["sensor_start_time"]),
            "sensor_end_time": timestamp(row["sensor_end_time"]),
            "cof_score": finite(row["alarm_score"]),
            "peak_level": LEVELS[row["peak_level"]],
            "incident_id": incident_key(row["incident_id"]),
            "incident_score": finite(row["incident_score"]),
        }

    validate_fixture(incidents, linked_ids, candidates, alarms)
    return incidents, candidates, alarms


def validate_fixture(incidents, linked_ids, candidates, alarms) -> None:
    for key, item in incidents.items():
        linked = sorted(
            (a for a in alarms.values() if a["incident_id"] == key),
            key=lambda a: a["alarm_start_time"],
        )
        ids = sorted(k for k, a in alarms.items() if a["incident_id"] == key)
        check(linked, f"{key}: no linked alarms")
        check(sorted(linked_ids[key]) == ids, f"{key}: alarm_ids differ from alarm CSV links")
        check(item["alarm_count"] == len(linked), f"{key}: alarm_count differs")
        check(
            item["first_alarm_time"] == linked[0]["alarm_start_time"],
            f"{key}: first_alarm_time differs from earliest alarm",
        )
        check(
            item["peak_level"] == max(a["peak_level"] for a in linked),
            f"{key}: peak_level differs from linked alarms",
        )
        check(item["detect_time"] >= item["incident_start_time"], f"{key}: detect before start")
        for alarm in linked:
            check(alarm["equipment_id"] == item["equipment_id"], f"{key}: alarm equipment differs")
            check(
                item["incident_start_time"] <= alarm["alarm_start_time"]
                and alarm["alarm_end_time"] <= item["incident_end_time"]
                and (
                    alarm["sensor_end_time"] is None
                    or alarm["sensor_end_time"] <= item["incident_end_time"]
                ),
                f"{key}: alarm outside incident window",
            )
            check(alarm["cof_score"] == item["top_cof"], f"{key}: alarm score differs from top_cof")
            check(
                alarm["incident_score"] == item["incident_score"],
                f"{key}: alarm incident_score differs",
            )

        rows = sorted(candidates[key], key=lambda c: c["rank"])
        check([c["rank"] for c in rows] == list(range(1, len(rows) + 1)), f"{key}: rank gap")
        diagnosis = [c for c in rows if c["is_diagnosis"]]
        top_risk = [c for c in rows if c["is_top_risk"]]
        check(len(diagnosis) == 1 and len(top_risk) == 1, f"{key}: need one diagnosis/top risk")
        check(diagnosis[0]["fault"] == item["diagnosis"], f"{key}: diagnosis name differs")
        check(top_risk[0]["fault"] == item["top_risk_fault"], f"{key}: top risk name differs")
        check(
            (diagnosis[0]["cof"], diagnosis[0]["pof"], diagnosis[0]["score"])
            == (item["top_cof"], item["top_pof"], item["incident_score"]),
            f"{key}: diagnosis scores differ",
        )
    orphan = {a["incident_id"] for a in alarms.values()} - set(incidents)
    check(not orphan, f"Alarms link unknown incidents: {sorted(orphan)}")


async def validate_database(conn, incidents, alarms) -> dict[str, dict]:
    pumps = await conn.fetch(
        """SELECT equipment_id FROM equipment
           WHERE plant_id = $1 AND equipment_group_id = $2""",
        PLANT,
        GROUP,
    )
    known = {row["equipment_id"] for row in pumps}
    for key, item in incidents.items():
        check(item["equipment_id"] in known, f"{key}: equipment not in {GROUP}")
        if item["lead_sensor_id"]:
            owner = await conn.fetchval(
                "SELECT equipment_id FROM sensor WHERE sensor_id = $1", item["lead_sensor_id"]
            )
            check(owner == item["equipment_id"], f"{key}: lead sensor not on equipment")

    for key, alarm in alarms.items():
        rule = await conn.fetchrow(
            "SELECT equipment_id, sensor_id, alarm_level FROM setpoint WHERE setpoint_id = $1",
            alarm["setpoint_id"],
        )
        check(rule is not None, f"{key}: setpoint missing")
        check(
            (rule["equipment_id"], rule["sensor_id"], rule["alarm_level"])
            == (alarm["equipment_id"], alarm["sensor_id"], alarm["alarm_level"]),
            f"{key}: setpoint equipment/sensor/level differs",
        )

    saved = {
        row["source_alarm_id"]: dict(row)
        for row in await conn.fetch(
            f"""SELECT a.alarm_id, a.source_alarm_id, a.equipment_id, a.sensor_id, a.setpoint_id,
                       a.alarm_level, a.event_type, {", ".join(f"a.{f}" for f in ALARM_FIELDS)}
                FROM alarm a JOIN equipment e USING (equipment_id)
                WHERE e.plant_id = $1 AND e.equipment_group_id = $2""",
            PLANT,
            GROUP,
        )
    }
    check(
        set(saved) == set(alarms),
        f"Alarm IDs differ: CSV only {sorted(set(alarms) - set(saved))}, "
        f"DB only {sorted(set(saved) - set(alarms))}",
    )
    for key, alarm in alarms.items():
        row = saved[key]
        for field in ("equipment_id", "sensor_id", "setpoint_id", "alarm_level", "event_type"):
            check(row[field] == alarm[field], f"{key}: {field} differs from DB")
    return saved


async def upsert_error_types(conn, names: set[str]) -> dict[str, int]:
    await conn.executemany(
        """INSERT INTO error_type (error_type_name) VALUES ($1)
           ON CONFLICT (error_type_name) DO NOTHING""",
        [(name,) for name in sorted(names)],
    )
    rows = await conn.fetch(
        "SELECT error_type_id, error_type_name FROM error_type WHERE error_type_name = ANY($1)",
        sorted(names),
    )
    return {row["error_type_name"]: row["error_type_id"] for row in rows}


async def write(conn, incidents, candidates, alarms, saved) -> list[str]:
    changes: list[str] = []
    names = {c["fault"] for rows in candidates.values() for c in rows}
    names |= {i["diagnosis"] for i in incidents.values()}
    names |= {i["top_risk_fault"] for i in incidents.values()}
    existing_types = {
        row["error_type_name"] for row in await conn.fetch("SELECT error_type_name FROM error_type")
    }
    changes += [f"error_type + {name}" for name in sorted(names - existing_types)]
    type_ids = await upsert_error_types(conn, names)

    columns = (
        "plant_id",
        "equipment_group_id",
        "equipment_id",
        "incident_start_time",
        "detect_time",
        "first_alarm_time",
        "incident_end_time",
        "peak_level",
        "lead_sensor_id",
        "diagnosis_error_type_id",
        "top_risk_error_type_id",
        "top_cof",
        "top_pof",
        "incident_score",
        "alarm_grade",
        "grade_reason",
        "response_time_h",
        "actionable",
        "alarm_count",
        "trend_count",
        "source_file",
    )
    for key, item in incidents.items():
        record = {
            **item,
            "diagnosis_error_type_id": type_ids[item["diagnosis"]],
            "top_risk_error_type_id": type_ids[item["top_risk_fault"]],
        }
        values = [record[c] for c in columns]
        current = await conn.fetchrow(
            f"SELECT {', '.join(columns)} FROM incident WHERE incident_id = $1", key
        )
        if current is None:
            changes.append(f"incident + {key}")
        elif tuple(current) != tuple(values):
            diff = [c for c, v in zip(columns, values, strict=True) if current[c] != v]
            changes.append(f"incident ~ {key}: {', '.join(diff)}")
        else:
            continue
        slots = ", ".join(f"${n}" for n in range(1, len(columns) + 2))
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns)
        await conn.execute(
            f"""INSERT INTO incident (incident_id, {", ".join(columns)}) VALUES ({slots})
                ON CONFLICT (incident_id) DO UPDATE SET {updates}, loaded_at = now()""",
            key,
            *values,
        )

    cand_columns = (
        "rank",
        "error_type_id",
        "rule_score_s",
        "s_top3_sum",
        "p",
        "speed",
        "impact",
        "w",
        "cof",
        "p_trend",
        "pf_hours",
        "p_pf",
        "pof",
        "score",
        "is_diagnosis",
        "is_top_risk",
        "evidence",
    )
    for key, rows in candidates.items():
        wanted = sorted(
            tuple({**c, "error_type_id": type_ids[c["fault"]]}[col] for col in cand_columns)
            for c in rows
        )
        current = sorted(
            tuple(r)
            for r in await conn.fetch(
                f"SELECT {', '.join(cand_columns)} FROM incident_candidate WHERE incident_id = $1",
                key,
            )
        )
        if current == wanted:
            continue
        changes.append(f"incident_candidate ~ {key}: {len(current)} -> {len(wanted)} rows")
        await conn.execute("DELETE FROM incident_candidate WHERE incident_id = $1", key)
        slots = ", ".join(f"${n}" for n in range(1, len(cand_columns) + 2))
        await conn.executemany(
            f"INSERT INTO incident_candidate (incident_id, {', '.join(cand_columns)}) "
            f"VALUES ({slots})",
            [(key, *row) for row in wanted],
        )

    for key, alarm in alarms.items():
        row = saved[key]
        diff = [f for f in ALARM_FIELDS if row[f] != alarm[f]]
        if not diff:
            continue
        changes.append(
            f"alarm ~ {key}: " + ", ".join(f"{f} {fmt(row[f])} -> {fmt(alarm[f])}" for f in diff)
        )
        await conn.execute(
            f"""UPDATE alarm SET {", ".join(f"{f} = ${n}" for n, f in enumerate(ALARM_FIELDS, 2))}
                WHERE source_alarm_id = $1""",
            key,
            *(alarm[f] for f in ALARM_FIELDS),
        )

    alarm_ids = [saved[key]["alarm_id"] for key in alarms]
    snapshots = await conn.fetchval(
        """SELECT count(*) FROM alarm_intake
           WHERE alarm_id = ANY($1::bigint[]) OR selected_alarm_id = ANY($1::bigint[])""",
        alarm_ids,
    )
    if snapshots:
        print(f"WARNING: {snapshots} alarm_intake snapshots reference updated alarms (unchanged)")
    return changes


def fmt(value) -> str:
    if isinstance(value, datetime):
        return value.astimezone(KST).strftime("%m-%d %H:%M")
    return str(value)


async def run(root: Path, apply: bool) -> None:
    incidents, candidates, alarms = read_fixture(root)
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
            await conn.execute("SELECT pg_advisory_xact_lock(hashtext('cdu_incident_import'))")
            saved = await validate_database(conn, incidents, alarms)
            changes = await write(conn, incidents, candidates, alarms, saved)
            for line in changes:
                print(line)
            counts = await conn.fetchrow(
                """SELECT (SELECT count(*) FROM incident) AS incidents,
                          (SELECT count(*) FROM incident_candidate) AS candidates,
                          (SELECT count(*) FROM alarm WHERE incident_id IS NOT NULL) AS linked"""
            )
            summary = (
                f"{len(changes)} changes; incident {counts['incidents']}, "
                f"incident_candidate {counts['candidates']}, linked alarms {counts['linked']}"
            )
            if not apply:
                print(f"Validated (dry run, rolled back): {summary}")
                raise PreviewComplete
        print(f"Committed: {summary}")
    except PreviewComplete:
        pass
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", type=Path, required=True, help="Directory containing the incident CSV files"
    )
    parser.add_argument("--apply", action="store_true", help="Commit the incident fixture")
    args = parser.parse_args()
    asyncio.run(run(args.data, args.apply))


if __name__ == "__main__":
    main()
