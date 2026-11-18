"""Align sensor metadata and seeded tags with the CDU sensor register.

Revision ID: 4b8e6f1c2a90
Revises: 86d9e2184a37

Source: data/CDU_펌프_계측기_태그대장_제안사양.xlsx, 센서 대장!A7:K49.
The register has seven instrument tags per pump; IT and ET are one UT instrument.
"""

import sqlalchemy as sa
from alembic import op

revision = "4b8e6f1c2a90"
down_revision = "86d9e2184a37"
branch_labels = None
depends_on = None

METADATA_COLUMNS = (
    "installation_location",
    "manufacturer",
    "model_name",
    "measurement_range",
    "pid_drawing_number",
    "management_grade",
)

# tag prefix, loop suffix, measurement, location, unit, manufacturer, model, range
REGISTER = (
    ("TT", "01", "유체 온도", "펌프 흡입측 공정 배관", "°C", "Endress+Hauser", "iTHERM TM131 (Pt100 WW)", "0~400 °C"),
    ("TT", "02", "베어링 온도", "펌프 베어링부", "°C", "WIKA", "TR55 (Pt100) + T32", "0~150 °C"),
    ("ST", "03", "회전수", "모터 회전축", "rpm", "Pepperl+Fuchs", "NJ4-12GM-N-V1 + KFD2-UFC-Ex1.D", "0~2,400 rpm"),
    ("UT", "04", "전류·전압", "모터 전원 회로", "A RMS / V RMS", "Schneider Electric", "PM5560 + CT METSECT5CC010", "1~100 A RMS / 20~600 V L-L"),
    ("VT", "05", "진동 속도 RMS", "펌프 베어링 하우징", "mm/s RMS", "Metrix", "ST5484E (AAA 151)", "0~25.4 mm/s RMS"),
    ("PT", "06", "흡입압", "펌프 흡입측 배관", "kPa(g)", "Endress+Hauser", "Cerabar PMP51B (4 bar g 셀)", "−50~400 kPa(g)"),
    ("PT", "07", "토출압", "펌프 토출측 배관", "kPa(g)", "Endress+Hauser", "Cerabar PMP51B (10 bar g 셀)", "0~1,000 kPa(g)"),
)

REFERENCING_TABLES = (
    "sensor_alias",
    "alarm",
    "report_symptoms",
    "report_chart_attachments",
    "session_detail",
    "chat_request_log",
)


def upgrade() -> None:
    for column in METADATA_COLUMNS:
        op.add_column("sensor", sa.Column(column, sa.Text(), nullable=True))

    conn = op.get_bind()
    # An IT/ET signal reference cannot be reduced to the shared UT instrument
    # without losing which measured quantity was used.
    retired_ids = [f"10-{tag}-1{pump}04" for pump in range(1, 7) for tag in ("IT", "ET")]
    for table in REFERENCING_TABLES:
        count = conn.execute(
            sa.text(f'SELECT count(*) FROM "{table}" WHERE sensor_id = ANY(CAST(:ids AS varchar[]))'),
            {"ids": retired_ids},
        ).scalar_one()
        if count:
            raise RuntimeError(
                f"Cannot replace IT/ET sensor IDs: {table} has {count} references. "
                "Preserve signal identity before migrating these rows."
            )

    update = sa.text(
        """UPDATE sensor SET measurement_name=:measurement_name,
            installation_location=:installation_location, unit=:unit,
            manufacturer=:manufacturer, model_name=:model_name,
            measurement_range=:measurement_range,
            pid_drawing_number=NULL, management_grade=NULL
            WHERE sensor_id=:sensor_id AND equipment_id=:equipment_id"""
    )
    insert = sa.text(
        """INSERT INTO sensor (sensor_id, equipment_id, measurement_name,
            installation_location, unit, manufacturer, model_name,
            measurement_range, pid_drawing_number, management_grade)
            VALUES (:sensor_id, :equipment_id, :measurement_name,
            :installation_location, :unit, :manufacturer, :model_name,
            :measurement_range, NULL, NULL)"""
    )
    for pump in range(1, 7):
        for tag, suffix, name, location, unit, maker, model, span in REGISTER:
            row = {
                "sensor_id": f"10-{tag}-1{pump}{suffix}",
                "equipment_id": f"P{pump}",
                "measurement_name": name,
                "installation_location": location,
                "unit": unit,
                "manufacturer": maker,
                "model_name": model,
                "measurement_range": span,
            }
            if tag == "UT":
                conn.execute(insert, row)
            else:
                result = conn.execute(update, row)
                if result.rowcount != 1:
                    raise RuntimeError(f"Expected exactly one existing sensor: {row['sensor_id']}")
    conn.execute(
        sa.text("DELETE FROM sensor WHERE sensor_id = ANY(CAST(:ids AS varchar[]))"),
        {"ids": retired_ids},
    )


def downgrade() -> None:
    raise RuntimeError("The UT instrument merge cannot be safely reversed")
