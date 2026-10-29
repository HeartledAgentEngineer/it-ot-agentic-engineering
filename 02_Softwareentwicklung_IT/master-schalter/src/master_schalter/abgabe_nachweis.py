"""Lesender Nachweis, dass der alte Master seinen aktuellen Schritt abgegeben hat."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


class NachweisFehler(Exception):
    """Abgabe ist technisch nicht hinreichend nachgewiesen."""


Git = Callable[[Path, list[str]], str]


@dataclass(frozen=True)
class Nachweis:
    head: str
    kopfzeit: str
    datei_sha256: str
    geprueft_zeit: str

    def als_dict(self) -> dict[str, str]:
        return asdict(self)


def _utc(wert: datetime) -> datetime:
    return wert.replace(tzinfo=timezone.utc) if wert.tzinfo is None else wert.astimezone(timezone.utc)


def pruefen(thema: str, vorgang: object, repo: Path | None, jetzt: datetime, *, git: Git | None = None) -> Nachweis:
    """Prüft Kopfzeit, HEAD und Inhaltsfingerabdruck der registrierten laufenden Übergabe."""
    from . import automatik, modi, uebergabe

    try:
        _paar, laufend = modi._paar_pruefen(thema, repo)
        wurzel = Path(repo).resolve() if repo is not None else uebergabe.repo_wurzel()
        if laufend is None:
            raise NachweisFehler("Laufende Übergabe ist nicht registriert")
        daten = laufend.read_bytes()
        kopf = automatik.kopfzeile_lesen(laufend)
        if laufend.read_bytes() != daten:
            raise NachweisFehler("Laufende Übergabe änderte sich während der Prüfung")
        head = automatik.kopf_hash(wurzel, git)
    except NachweisFehler:
        raise
    except Exception as fehler:
        raise NachweisFehler("Laufende Übergabe oder Repository ist nicht prüfbar") from fehler
    if kopf is None:
        raise NachweisFehler("Übergabekopf fehlt oder ist ungültig")
    bereit, kopfzeit, kurz = kopf
    zeit = _utc(jetzt)
    kopfzeit = _utc(kopfzeit)
    if bereit != "ja":
        raise NachweisFehler("Übergabekopf bestätigt keine Abgabe")
    if kopfzeit > zeit or zeit - kopfzeit > automatik.FRIST_KOPFZEILE:
        raise NachweisFehler("Übergabekopf ist zeitlich nicht aktuell")
    seit_roh = getattr(vorgang, "abgabe_seit", None)
    try:
        seit = datetime.fromisoformat(str(seit_roh).replace("Z", "+00:00"))
    except (TypeError, ValueError) as fehler:
        raise NachweisFehler("Abgabeauftrag hat keine prüfbare Anfragezeit") from fehler
    if kopfzeit < _utc(seit):
        raise NachweisFehler("Übergabekopf wurde vor diesem Abgabeauftrag erstellt")
    if not head or not re.fullmatch(r"[0-9a-fA-F]{40,64}", head) or not automatik.head_passt(kurz, head):
        raise NachweisFehler("Übergabekopf gehört nicht zum aktuellen Repository-Stand")
    return Nachweis(head, kopfzeit.isoformat(), hashlib.sha256(daten).hexdigest(), zeit.isoformat())


def passt(vorgang: object, neu: Nachweis) -> bool:
    """Vergleicht den gespeicherten Beleg mit dem erneuten lesenden Prüfergebnis."""
    alt = getattr(vorgang, "abgabe_nachweis", None)
    neu_dict = neu.als_dict()
    return (isinstance(alt, dict)
            and all(alt.get(k) == neu_dict[k] for k in ("head", "kopfzeit", "datei_sha256")))
