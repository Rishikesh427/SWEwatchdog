from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_granola_export(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text())
    notes = payload if isinstance(payload, list) else payload.get("notes", [])
    return [granola_note_to_source(note) for note in notes]


def granola_note_to_source(note: dict[str, Any]) -> dict[str, Any]:
    text = note.get("text") or note.get("markdown") or note.get("summary") or ""
    note_id = note.get("id", "unknown")
    return {
        "kind": "granola_note",
        "system": "granola",
        "text": text,
        "url": note.get("url") or f"granola://note/{note_id}",
        "created_at": note.get("created_at") or note.get("start_time"),
        "meeting_id": note_id,
    }
