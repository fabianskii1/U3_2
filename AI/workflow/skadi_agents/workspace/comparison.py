"""Links to the existing multi-pump overlay chart with fixed query conditions."""

from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo


def comparison_kind(name: str) -> str | None:
    if "진동" in name:
        return "VIB"
    if "베어링" in name and "온도" in name:
        return "TB"
    if "유체" in name and "온도" in name:
        return "TF"
    for term, kind in (
        ("흡입", "PS"),
        ("토출", "PD"),
        ("전류", "AMP"),
        ("전압", "VOLT"),
        ("회전수", "RPM"),
    ):
        if term in name:
            return kind
    return None


def comparison_href(entities, selected, series, interval):
    kinds = {comparison_kind(sensor["measurement_name"]) for _, sensor in selected}
    if len(kinds) != 1 or None in kinds:
        return None
    windows = {(item["start"], item["end"]) for item in series}
    if len(windows) != 1:
        return None
    start, end = next(iter(windows))
    start, end = (
        datetime.fromisoformat(value)
        .astimezone(ZoneInfo("Asia/Seoul"))
        .replace(tzinfo=None)
        .isoformat(timespec="seconds")
        for value in (start, end)
    )
    params = [
        ("plant_id", entities[0].plant_id),
        ("unit_id", entities[0].unit_id),
        ("compare", "all"),
        ("compare_sensor", next(iter(kinds))),
        ("from", start),
        ("to", end),
        ("interval", interval or "1h"),
    ]
    params.extend(("compare_equipment_id", entity.id) for entity in entities)
    return "/trend?" + urlencode(params)
