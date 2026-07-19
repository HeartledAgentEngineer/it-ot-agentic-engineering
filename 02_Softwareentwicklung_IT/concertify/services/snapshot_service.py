"""
services/snapshot_service.py
============================
Logik fuer Setlist-Schnappschuesse.

Reine Funktionen (kein IO, 100% unit-testbar):
    - diff_setlists       Vergleich alt/neu fuer die Uebernehmen-Ansicht
    - is_list_saved       Sicherheits-Check "schon gesichert?"
    - build_snapshot_payload / apply_snapshot_payload   Payload <-> setlist_data

Klasse SnapshotService (Orchestrierung, Repository per DI) folgt in einem spaeteren Task.
"""

# Vollstaendiger Setlist-Zustand pro Kuenstler (Spec Abschnitt 3).
PAYLOAD_KEYS = [
    "setlist_titles",
    "new_titles",
    "spotify_uris",
    "scores",
    "badges",
    "positions",
    "is_encore",
    "set_type",
    "play_counts",
    "total_concerts_analyzed",
    "positions_hist",
    "manual_order",
    "excluded_songs",
    "show_elements",
]


def diff_setlists(old_titles: list[str], new_titles: list[str]) -> dict:
    """Vergleicht zwei Songlisten.

    Returns dict mit 'added' (nur in neu), 'removed' (nur in alt),
    'unchanged' (in beiden) — jeweils in der Reihenfolge der neuen/alten Liste.
    """
    old_set = set(old_titles)
    new_set = set(new_titles)
    return {
        "added": [t for t in new_titles if t not in old_set],
        "removed": [t for t in old_titles if t not in new_set],
        "unchanged": [t for t in new_titles if t in old_set],
    }


def is_list_saved(current_titles: list[str], snapshots: list[dict]) -> bool:
    """True, wenn die aktuelle Songliste EXAKT (Inhalt + Reihenfolge) als
    Schnappschuss existiert. snapshots = Liste von Repo-Dicts mit payload."""
    current = list(current_titles)
    for snap in snapshots:
        if snap.get("payload", {}).get("setlist_titles", []) == current:
            return True
    return False


def build_snapshot_payload(artist_entry: dict) -> dict:
    """Extrahiert den sicherbaren Setlist-Zustand aus setlist_data[artist]."""
    return {k: artist_entry[k] for k in PAYLOAD_KEYS if k in artist_entry}


def apply_snapshot_payload(artist_entry: dict, payload: dict) -> None:
    """Schreibt einen Snapshot-Payload zurueck in setlist_data[artist] (mutiert)."""
    for key in PAYLOAD_KEYS:
        if key in payload:
            artist_entry[key] = payload[key]


class SnapshotService:
    """Orchestriert Snapshot-Operationen. Repository per Dependency Injection."""

    def __init__(self, repository):
        self._repo = repository

    def create_snapshot(
        self, artist: str, name: str, artist_entry: dict, user_id: str = "local"
    ) -> "tuple[int | None, str | None]":
        if not name.strip():
            return None, "missing name"
        payload = build_snapshot_payload(artist_entry)
        sid = self._repo.create(artist, name.strip(), payload, user_id=user_id)
        return sid, None

    def list_snapshots(self, artist: str, user_id: str = "local") -> list[dict]:
        return [
            {"id": s["id"], "name": s["name"], "created_at": s["created_at"]}
            for s in self._repo.list(artist, user_id=user_id)
        ]

    def get_restore_payload(
        self, snapshot_id: int
    ) -> "tuple[str | None, dict | None, str | None]":
        snap = self._repo.get(snapshot_id)
        if not snap:
            return None, None, "unknown snapshot"
        return snap["artist"], snap["payload"], None

    def is_current_saved(
        self, artist: str, current_titles: list[str], user_id: str = "local"
    ) -> bool:
        return is_list_saved(
            current_titles, self._repo.list(artist, user_id=user_id)
        )

    def delete_snapshot(self, snapshot_id: int) -> bool:
        return self._repo.delete(snapshot_id)

    def rename_snapshot(self, snapshot_id: int, new_name: str) -> bool:
        if not new_name.strip():
            return False
        return self._repo.rename(snapshot_id, new_name.strip())
