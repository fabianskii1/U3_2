"""Resolve short replies against the choices already offered to the user."""

import re

from skadi_agents.equipment_status import matching_sensors, sensor_signal
from skadi_agents.inspection_evidence import markdown_text
from skadi_agents.language import close_spelling
from skadi_agents.reflector import normalize


def _keys(text: str) -> set[str]:
    value = re.sub(r"[?!.。]+$", "", text.strip())
    keys = {normalize(value)}
    value = re.sub(
        r"(?:보여\s*줘|보여\s*주세요|열어\s*줘|조회해\s*줘|"
        r"선택할게요?|선택해\s*줘|볼게요?|할게요?)$",
        "",
        value,
    ).strip()
    keys.add(normalize(value))
    for _ in range(2):
        value = re.sub(r"(?:으로|로|요)$", "", value).strip()
        keys.add(normalize(value))
    return keys - {""}


async def matching_equipment_choices(
    tools, text: str, candidates: list[dict]
) -> tuple[list[int], bool]:
    """Return indices and whether a spelling suggestion needs confirmation."""
    keys = _keys(text)
    names = [[candidate["id"], candidate["name"]] for candidate in candidates]
    exact = [i for i, values in enumerate(names) if keys.intersection(map(normalize, values))]
    if exact:
        return exact, False

    lookup = getattr(tools, "lookup_alias", None)
    if lookup:
        for candidate, values in zip(candidates, names, strict=True):
            result = await lookup(candidate["id"], entity_type="equipment")
            if not isinstance(result, dict):
                continue
            for item in result.get("candidates", []):
                if item.get("id") != candidate["id"]:
                    continue
                values.extend(alias["alias_name"] for alias in item.get("aliases", []))
    exact = [i for i, values in enumerate(names) if keys.intersection(map(normalize, values))]
    if exact:
        return exact, False

    def descriptive(value: str) -> str:
        return normalize(value).replace("펌프", "").replace("설비", "")

    partial_keys = {descriptive(key) for key in keys if len(descriptive(key)) >= 2}
    partial = [
        i
        for i, values in enumerate(names)
        if any(key in descriptive(name) for key in partial_keys for name in values[1:])
    ]
    if partial:
        return partial, False

    suggestions = []
    for i, values in enumerate(names):
        variants = set()
        for value in values[1:]:
            words = re.findall(r"[가-힣]+", value.replace("펌프", "").replace("설비", ""))
            variants.update(
                "".join(words[start:end])
                for start in range(len(words))
                for end in range(start + 1, len(words) + 1)
            )
        if any(close_spelling(key, variant) for key in partial_keys for variant in variants):
            suggestions.append(i)
    return suggestions, bool(suggestions)


def matching_sensor_choices(text: str, candidates: list[dict]) -> list[dict]:
    value = re.sub(r"^(?:그중에서|그중|이중에서|이중)\s*", "", text.strip())
    keys = _keys(value)
    for key in list(keys):
        for _ in range(3):
            key = re.sub(r"(?:센서|측|쪽|값|을|를|만|도)$", "", key)
            if key:
                keys.add(key)
    ids = {
        row["sensor_id"]
        for key in keys
        for row in matching_sensors(candidates, key, sensor_signal(key))
    }
    return [row for row in candidates if row["sensor_id"] in ids]


def selection_reply(pending: dict, previous: dict, body: str):
    from skadi_agents.executor import Reply

    candidates = pending["candidates"]
    labels = [
        f"{i}. {markdown_text(c.get('measurement_name') or c['name'])} "
        f"({markdown_text(c.get('sensor_id') or c['id'])})"
        for i, c in enumerate(candidates, 1)
    ]
    choices = [
        {
            "label": f"{c.get('sensor_id') or c['id']} · {c.get('measurement_name') or c['name']}",
            "message": f"{i}번",
        }
        for i, c in enumerate(candidates, 1)
    ]
    if pending.get("allow_all") and len(candidates) > 1:
        labels.append(f"{len(candidates) + 1}. 전체 펌프 비교")
        choices.append({"label": "전체 펌프 비교", "message": "전체 비교"})
    return Reply(
        body + "\n\n" + "\n".join(labels),
        context={**previous, "workspace_pending": pending},
        choices=choices,
    )
