"""Use asset codes as IDs and load the supplied Ulsan CUD reference data.

Revision ID: 6f4c2a91b730
Revises: c061aa305efa
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "6f4c2a91b730"
down_revision = "c061aa305efa"
branch_labels = None
depends_on = None

CODE_COLUMNS = ("plant_id", "equipment_group_id", "equipment_id", "sensor_id")
CODE_TABLES = {"plant", "equipment_group", "equipment", "sensor"}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()
    foreign_keys = [
        (table, fk)
        for table in tables
        for fk in inspector.get_foreign_keys(table)
        if fk["referred_table"] in CODE_TABLES
    ]
    for table, fk in foreign_keys:
        op.drop_constraint(fk["name"], table, type_="foreignkey")

    for table in tables:
        for column in inspector.get_columns(table):
            name = column["name"]
            if name not in CODE_COLUMNS:
                continue
            if table in CODE_TABLES and name == f"{table}_id":
                op.execute(
                    sa.text(f'ALTER TABLE "{table}" ALTER COLUMN "{name}" DROP IDENTITY IF EXISTS')
                )
            op.alter_column(
                table,
                name,
                existing_type=column["type"],
                type_=sa.String(30),
                existing_nullable=column["nullable"],
                postgresql_using=f'"{name}"::varchar(30)',
            )

    for table, fk in foreign_keys:
        op.create_foreign_key(
            fk["name"],
            table,
            fk["referred_table"],
            fk["constrained_columns"],
            fk["referred_columns"],
            ondelete=fk.get("options", {}).get("ondelete"),
        )

    op.add_column("plant", sa.Column("location", sa.Text(), nullable=False, server_default=""))
    op.alter_column("plant", "location", server_default=None)
    op.alter_column(
        "sensor",
        "sensor_name",
        new_column_name="measurement_name",
        existing_type=sa.Text(),
        type_=sa.String(100),
        existing_nullable=False,
    )
    op.alter_column(
        "sensor",
        "out_unit",
        new_column_name="unit",
        existing_type=sa.Text(),
        type_=sa.String(30),
        existing_nullable=False,
    )
    op.drop_column("sensor", "sensor_type")
    op.drop_column("sensor", "level")

    plant = sa.table("plant", sa.column("plant_id"), sa.column("plant_name"), sa.column("location"))
    op.bulk_insert(
        plant,
        [{"plant_id": "PLANT-01", "plant_name": "울산CLX", "location": "울산광역시 남구 신정동"}],
    )
    plant_alias = sa.table(
        "plant_alias",
        sa.column("plant_alias_id"),
        sa.column("plant_id"),
        sa.column("plant_alias_name"),
    )
    op.bulk_insert(
        plant_alias,
        [
            {"plant_alias_id": i, "plant_id": "PLANT-01", "plant_alias_name": name}
            for i, name in enumerate(("울산", "CLX", "남구", "신정동"), 1)
        ],
    )
    group = sa.table(
        "equipment_group",
        sa.column("equipment_group_id"),
        sa.column("plant_id"),
        sa.column("equipment_group_name"),
    )
    op.bulk_insert(
        group,
        [
            {
                "equipment_group_id": "CUD-01",
                "plant_id": "PLANT-01",
                "equipment_group_name": "상압증류(CUD) 1호기",
            }
        ],
    )
    group_alias = sa.table(
        "equipment_group_alias",
        sa.column("equipment_group_alias_id"),
        sa.column("equipment_group_id"),
        sa.column("equipment_group_alias_name"),
    )
    op.bulk_insert(
        group_alias,
        [
            {
                "equipment_group_alias_id": 1,
                "equipment_group_id": "CUD-01",
                "equipment_group_alias_name": "CUD 1호기",
            },
            {
                "equipment_group_alias_id": 2,
                "equipment_group_id": "CUD-01",
                "equipment_group_alias_name": "상압증류 1호",
            },
        ],
    )
    equipment = sa.table(
        "equipment",
        sa.column("equipment_id"),
        sa.column("plant_id"),
        sa.column("equipment_group_id"),
        sa.column("equipment_name"),
        sa.column("equipment_type"),
        sa.column("equipment_status"),
        sa.column("equipment_level"),
    )
    names = (
        "원유 공급 펌프",
        "나프타 제품 이송 펌프",
        "등유 측류 이송 펌프",
        "경유 측류 이송 펌프",
        "펌프어라운드 순환 펌프",
        "상압잔사유 이송 펌프",
    )
    op.bulk_insert(
        equipment,
        [
            {
                "equipment_id": f"P{i}",
                "plant_id": "PLANT-01",
                "equipment_group_id": "CUD-01",
                "equipment_name": name,
                "equipment_type": "펌프",
                "equipment_status": 0,
                "equipment_level": 1,
            }
            for i, name in enumerate(names, 1)
        ],
    )
    sensor = sa.table(
        "sensor",
        sa.column("sensor_id"),
        sa.column("equipment_id"),
        sa.column("measurement_name"),
        sa.column("unit"),
    )
    measurements = (
        ("TT", "01", "유체 온도", "°C"),
        ("TT", "02", "모터 온도", "°C"),
        ("ST", "03", "회전수", "rpm"),
        ("IT", "04", "모터 전류", "A RMS"),
        ("ET", "04", "모터 선간전압", "V RMS"),
        ("VT", "05", "진동 속도 RMS", "mm/s RMS"),
        ("PT", "06", "흡입압", "kPa(g)"),
        ("PT", "07", "토출압", "kPa(g)"),
    )
    op.bulk_insert(
        sensor,
        [
            {
                "sensor_id": f"10-{tag}-1{i}{suffix}",
                "equipment_id": f"P{i}",
                "measurement_name": name,
                "unit": unit,
            }
            for i in range(1, 7)
            for tag, suffix, name, unit in measurements
        ],
    )
    for table, key in (
        ("plant_alias", "plant_alias_id"),
        ("equipment_group_alias", "equipment_group_alias_id"),
    ):
        op.execute(
            sa.text(
                f"SELECT setval(pg_get_serial_sequence('{table}', '{key}'), (SELECT MAX({key}) FROM {table}), true)"
            )
        )


def downgrade() -> None:
    raise RuntimeError("Asset code IDs cannot be safely converted back to integer IDs")
