"""Resolve equipment identities from BE-supplied database candidates."""

import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher


def normalize_name(value: str) -> str:
    """Ignore width, case and whitespace differences without fuzzy guessing."""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(normalized.split())


@dataclass(frozen=True)
class Equipment:
    equipment_id: str
    equipment_name: str
    aliases: tuple[str, ...]
    source: str


@dataclass(frozen=True)
class Match:
    equipment: Equipment
    matched_name: str
    match_type: str


class EquipmentCatalog:
    def __init__(self, equipment: tuple[Equipment, ...]):
        self.equipment = equipment
        self._names: dict[str, list[Match]] = {}
        for item in equipment:
            for name, match_type in (
                (item.equipment_id, "id"),
                (item.equipment_name, "name"),
                *((alias, "alias") for alias in item.aliases),
            ):
                key = normalize_name(name)
                if not key:
                    continue
                matches = self._names.setdefault(key, [])
                if all(match.equipment.equipment_id != item.equipment_id for match in matches):
                    matches.append(Match(item, name, match_type))

    @classmethod
    def from_candidates(cls, candidates: list[dict]) -> "EquipmentCatalog":
        equipment: list[Equipment] = []
        seen_ids: set[str] = set()
        for data in candidates:
            equipment_id = data.get("equipment_id")
            name = data.get("equipment_name")
            aliases = data.get("aliases")
            if (
                not isinstance(equipment_id, str)
                or not equipment_id.strip()
                or not isinstance(name, str)
                or not name.strip()
                or not isinstance(aliases, (list, tuple))
                or any(not isinstance(alias, str) or not alias.strip() for alias in aliases)
            ):
                raise ValueError("Invalid equipment identity or aliases")
            if equipment_id in seen_ids:
                raise ValueError(f"Duplicate equipment_id: {equipment_id}")
            seen_ids.add(equipment_id)
            equipment.append(Equipment(equipment_id, name, tuple(aliases), "database"))
        return cls(tuple(equipment))

    def find(self, name: str) -> tuple[Match, ...]:
        return tuple(self._names.get(normalize_name(name), ()))

    def has_similar_name(self, normalized_name: str) -> bool:
        """Recognize plausible typos in equipment names and aliases."""
        if len(normalized_name) < 4:
            return False
        return any(
            len(candidate) >= 4
            and SequenceMatcher(None, normalized_name, candidate).ratio() >= 0.72
            for candidate in self._names
        )

    def rank(self, name: str, limit: int = 3) -> tuple[Equipment, ...]:
        """Return the closest catalog entries without treating similarity as a match."""
        query = normalize_name(name)
        if not query:
            return ()

        def score(item: Equipment) -> float:
            names = (item.equipment_id, item.equipment_name, *item.aliases)
            return max(
                SequenceMatcher(None, query, normalize_name(candidate)).ratio()
                for candidate in names
            )

        return tuple(
            sorted(self.equipment, key=lambda item: (-score(item), item.equipment_id))[:limit]
        )
