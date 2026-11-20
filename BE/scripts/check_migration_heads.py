"""Reject an ambiguous Alembic migration graph before deployment."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def main() -> int:
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(heads) != 1:
        print(f"Expected exactly one Alembic head; found {len(heads)}: {', '.join(heads)}")
        print("Merge migration branches before building or deploying the backend.")
        return 1
    print(f"Alembic migration head: {heads[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
