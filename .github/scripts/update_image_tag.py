"""Edit one image alias in this repository's Kustomize format without reformatting it."""

import re
import sys
from pathlib import Path


def tag_span(text: str, alias: str) -> tuple[int, int]:
    headers = list(re.finditer(r"^images:[ \t]*(?:#.*)?$", text, re.MULTILINE))
    if len(headers) != 1:
        raise ValueError("Expected exactly one images section")
    offset = headers[0].end()
    tail = text[offset:]
    next_section = re.search(r"^[A-Za-z_][A-Za-z0-9_-]*:", tail, re.MULTILINE)
    section = tail[:next_section.start()] if next_section else tail
    entries = list(re.finditer(r"^  - name: ([A-Za-z0-9_.-]+)[ \t]*$", section, re.MULTILINE))
    if len(entries) != len(re.findall(r"^[ \t]*-[ \t]+", section, re.MULTILINE)):
        raise ValueError("Image entries must use the repository's unquoted '- name: alias' format")
    matches = [i for i, entry in enumerate(entries) if entry.group(1) == alias]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one image alias: {alias}")
    index = matches[0]
    start = entries[index].end()
    end = entries[index + 1].start() if index + 1 < len(entries) else len(section)
    block = section[start:end]
    pattern = r'''^    newTag: (?P<tag>"[^"\n]*"|'[^'\n]*'|[^ \t\n#]+)([ \t]*(?:#.*)?)$'''
    tags = list(re.finditer(pattern, block, flags=re.MULTILINE))
    if len(tags) != 1:
        raise ValueError(f"Expected exactly one newTag for {alias}")
    return offset + start + tags[0].start("tag"), offset + start + tags[0].end("tag")


def image_tag(text: str, alias: str) -> str:
    start, end = tag_span(text, alias)
    return text[start:end].strip("\"'")


def update_tag(text: str, alias: str, sha: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Image tag must be a full lowercase commit SHA")
    start, end = tag_span(text, alias)
    return text[:start] + f'"{sha}"' + text[end:]


if __name__ == "__main__":
    try:
        manifest, alias, sha = sys.argv[1:]
        path = Path(manifest)
        updated = update_tag(path.read_text(), alias, sha)
        path.write_text(updated)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
