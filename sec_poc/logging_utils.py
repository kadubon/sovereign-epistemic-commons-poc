from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from sec_poc.schemas import Event


def ensure_dir(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def write_jsonl(path: str | Path, events: Iterable[dict]) -> None:
    output_path = Path(path)
    ensure_dir(output_path.parent)
    with output_path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True) + "\n")


def append_jsonl(path: str | Path, event: Event | dict) -> None:
    output_path = Path(path)
    ensure_dir(output_path.parent)
    payload = event.to_dict() if isinstance(event, Event) else event
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def dump_json(path: str | Path, payload: dict) -> None:
    output_path = Path(path)
    ensure_dir(output_path.parent)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)

