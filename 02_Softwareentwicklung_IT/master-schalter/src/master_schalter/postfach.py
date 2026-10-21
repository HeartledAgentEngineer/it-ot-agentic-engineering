"""Postfach des Wechselassistenten: eine kleine Datei je Nachricht an einen Claude-/Hermes-Chat.

Layout: `<datenordner>/postfach/<ziel>/<kennung>/<vorgang-id>.json` mit `ziel` ∈ claude|hermes
(Codex bekommt seine Nachricht über die Thread-Queue). Eingelegte Dateien wandern bei der
Abholung nach `erledigt/`, ungültige nach `verworfen/` (mit Grund).

Sicherheit (G6): Sitzungskennungen und Vorgangs-IDs nur nach Muster `^[A-Za-z0-9_-]{1,80}$`, die
Postfachwurzel ist fest und der aufgelöste Ordner muss unter ihr liegen; Dateien sind höchstens
4 KB groß und enthalten nur `{vorgang, thema, rolle, laufend, zeit}` – der Text der Nachricht
entsteht erst beim Abholen aus festen Satzbausteinen.

Gültigkeit (G5): Eine Nachricht `neu` gilt nur, solange die aktuelle Marke des Themas genau
`<ziel-rolle> … assistent <thema> <vorgang-id>` ist; eine Nachricht `abgabe` nur, solange die
Marke noch diesen Vorgang trägt. Jeder spätere Wechsel überschreibt die Marke und macht ältere
Aufträge damit ungültig (A→B→A: B erhält nichts mehr).

Abholung ist **keine** Übernahme: sie setzt den Vorgang nur auf `im_chat`. Die Übernahme
bestätigt der Zielchat selbst mit `masterwechsel quittieren`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from . import assistent_vorgaenge, besitz, modi, paare
from .signale import _atomar_schreiben, daten_ordner

ZIELE = ("claude", "hermes")
ARTEN = assistent_vorgaenge.ARTEN
MAX_BYTES = 4096
FELDER = {"vorgang", "thema", "rolle", "laufend", "zeit"}
ERLEDIGT, VERWORFEN = "erledigt", "verworfen"

TEXT_NEU = ("Du führst jetzt das Thema {thema}. Lies zuerst {laufend}, "
            "dann führe `masterwechsel quittieren {vorgang} neu` aus.")
TEXT_ABGABE = ("Du führst das Thema {thema} nicht mehr. Schließe den laufenden Schritt sauber ab, "
               "beginne keinen neuen und führe `masterwechsel quittieren {vorgang} abgabe` aus.")


class PostfachFehler(Exception):
    """Ziel, Kennung, Pfad oder Inhalt ist nicht zulässig."""


@dataclass(frozen=True)
class Nachricht:
    vorgang: str
    thema: str
    rolle: str                # "neu" | "abgabe"
    laufend: str
    text: str                 # fester Satzbaustein für den Chat


def wurzel() -> Path:
    return daten_ordner() / "postfach"


def _kennung(wert: object, was: str) -> str:
    if not isinstance(wert, str) or modi.VORGANG_ID_MUSTER.fullmatch(wert) is None:
        raise PostfachFehler(f"{was} unzulässig (erlaubt: {modi.VORGANG_ID_MUSTER.pattern}): {wert!r}")
    return wert


def ordner(ziel: str, kennung: str) -> Path:
    """Postfachordner einer Sitzung; Ziel und Kennung werden geprüft, `resolve()` muss unter der Wurzel liegen."""
    if not isinstance(ziel, str) or ziel not in ZIELE:
        raise PostfachFehler(f"Postfachziel unzulässig (erlaubt: {', '.join(ZIELE)}): {ziel!r}")
    pfad = wurzel() / ziel / _kennung(kennung, "Sitzungskennung")
    if not pfad.resolve().is_relative_to(wurzel().resolve()):
        raise PostfachFehler("Postfachordner liegt außerhalb der Postfachwurzel")
    return pfad


def _inhalt(vorgang_id: str, thema: str, rolle: str, laufend: str, zeit: str) -> dict[str, str]:
    return {"vorgang": vorgang_id, "thema": thema, "rolle": rolle, "laufend": laufend, "zeit": zeit}


def einlegen(ziel: str, kennung: str, vorgang_id: str, thema: str, rolle: str, laufend: str) -> Path:
    """Nachricht atomar einlegen (tmp + `os.replace`); dieselbe Vorgangs-ID ergibt genau eine Datei.

    Liegt die Nachricht schon im Postfach, bleibt sie unverändert; wurde sie bereits abgeholt
    (`erledigt/`) oder verworfen, wird sie nicht erneut eingelegt.
    """
    ziel_ordner = ordner(ziel, kennung)
    _kennung(vorgang_id, "Vorgangskennung")
    try:
        paare.thema_pruefen(thema)
        if laufend != paare.laufend_bilden(thema):
            raise PostfachFehler(f"laufender Pfad passt nicht zum Thema: {laufend!r}")
    except paare.PaarFehler as fehler:
        raise PostfachFehler(str(fehler)) from fehler
    if rolle not in ARTEN:
        raise PostfachFehler(f"Nachrichtenart unzulässig (erlaubt: {', '.join(ARTEN)}): {rolle!r}")
    ziel_datei = ziel_ordner / f"{vorgang_id}.json"
    for unterordner in (ERLEDIGT, VERWORFEN):
        if (ziel_ordner / unterordner / f"{vorgang_id}.json").exists():
            return ziel_ordner / unterordner / f"{vorgang_id}.json"
    inhalt = json.dumps(_inhalt(vorgang_id, thema, rolle, laufend, datetime.now(timezone.utc).isoformat()),
                        ensure_ascii=False)
    if len(inhalt.encode("utf-8")) > MAX_BYTES:
        raise PostfachFehler(f"Nachricht größer als {MAX_BYTES} Bytes")
    if ziel_datei.exists():
        alt, _ = _lesen(ziel_datei)
        if isinstance(alt, dict) and all(alt.get(k) == v for k, v in
                                         _inhalt(vorgang_id, thema, rolle, laufend, "").items() if k != "zeit"):
            return ziel_datei
    _atomar_schreiben(ziel_datei, inhalt)
    return ziel_datei


def _lesen(datei: Path) -> tuple[object, str | None]:
    """`(Inhalt, None)` oder `(None, Grund)`; zu große oder unlesbare Dateien werden nicht geparst."""
    try:
        if datei.stat().st_size > MAX_BYTES:
            return None, f"Datei größer als {MAX_BYTES} Bytes"
        return json.loads(datei.read_text(encoding="utf-8")), None
    except (OSError, ValueError):
        return None, "Datei nicht lesbar oder kein JSON"


def _pruefen(datei: Path, roh: object) -> tuple[dict[str, str] | None, str | None]:
    """Inhalt streng prüfen: `(Inhalt, None)` oder `(None, Grund)`."""
    if not isinstance(roh, dict) or set(roh) != FELDER or not all(isinstance(v, str) for v in roh.values()):
        return None, "Inhalt ist kein gültiger Postfachauftrag"
    try:
        _kennung(roh["vorgang"], "Vorgangskennung")
        paare.thema_pruefen(roh["thema"])
    except (PostfachFehler, paare.PaarFehler) as fehler:
        return None, str(fehler)
    if roh["vorgang"] != datei.stem:
        return None, "Vorgangskennung passt nicht zum Dateinamen"
    if roh["rolle"] not in ARTEN:
        return None, f"Nachrichtenart unzulässig: {roh['rolle']!r}"
    if roh["laufend"] != paare.laufend_bilden(roh["thema"]):
        return None, "laufender Pfad passt nicht zum Thema"
    return roh, None


def _verwerfen(datei: Path, roh: object, grund: str) -> None:
    """Nach `verworfen/` verschieben; der Grund steht in der neuen Datei dabei."""
    ziel = datei.parent / VERWORFEN / datei.name
    inhalt = dict(roh) if isinstance(roh, dict) else {"inhalt": None}
    inhalt["grund"] = grund
    _atomar_schreiben(ziel, json.dumps(inhalt, ensure_ascii=False))
    datei.unlink(missing_ok=True)


def _text(inhalt: dict[str, str]) -> str:
    vorlage = TEXT_NEU if inhalt["rolle"] == "neu" else TEXT_ABGABE
    return vorlage.format(thema=inhalt["thema"], laufend=inhalt["laufend"], vorgang=inhalt["vorgang"])


def abholen(ziel: str, kennung: str, repo: Path | None = None) -> list[Nachricht]:
    """Alle gültigen Nachrichten einer Sitzung abholen; ungültige wandern nach `verworfen/`.

    Nur der Ordner dieser Kennung wird gelesen. Gültige Dateien setzen den Vorgang auf `im_chat`
    und wandern nach `erledigt/` (Abbruch dazwischen = Nachricht kommt beim nächsten Mal erneut).
    Ist die Marke eines Themas nicht lesbar, bleibt die Datei unberührt liegen.
    """
    pfad = ordner(ziel, kennung)
    if not pfad.is_dir():
        return []
    nachrichten: list[Nachricht] = []
    for datei in sorted(pfad.glob("*.json")):
        if not datei.is_file() or modi.VORGANG_ID_MUSTER.fullmatch(datei.stem) is None:
            continue
        roh, grund = _lesen(datei)
        inhalt, grund = (None, grund) if grund is not None else _pruefen(datei, roh)
        if inhalt is not None:
            try:
                grund = _gueltigkeit(ziel, inhalt, repo)
            except modi.ModusFehler:
                continue          # Besitzstatus nicht lesbar: weder zustellen noch verwerfen
        if inhalt is None or grund is not None:
            _verwerfen(datei, roh, grund or "ungültig")
            continue
        _zustellen(datei, inhalt)
        nachrichten.append(Nachricht(inhalt["vorgang"], inhalt["thema"], inhalt["rolle"],
                                     inhalt["laufend"], _text(inhalt)))
    return nachrichten


def _gueltigkeit(ziel: str, inhalt: dict[str, str], repo: Path | None) -> str | None:
    """G5 gegen die aktuelle Marke; `None` = gültig, sonst der Grund."""
    vorgang = assistent_vorgaenge.finden(inhalt["vorgang"])
    if vorgang is None or vorgang.thema != inhalt["thema"]:
        return "Vorgang unbekannt"
    if vorgang.phase == "verworfen":
        return "Vorgang wurde verworfen"
    rolle = ziel if inhalt["rolle"] == "neu" else None
    return assistent_vorgaenge.marke_pruefen(inhalt["thema"], inhalt["vorgang"], rolle=rolle, repo=repo)


def _zustellen(datei: Path, inhalt: dict[str, str]) -> None:
    zeit = datetime.now(timezone.utc).isoformat()

    def im_chat(alt: list[assistent_vorgaenge.Vorgang]) -> list[assistent_vorgaenge.Vorgang]:
        return [replace(v, phase="im_chat", zeit=zeit)
                if v.id == inhalt["vorgang"] and v.phase not in (*assistent_vorgaenge.ENDGUELTIG, "im_chat")
                else v for v in alt]

    assistent_vorgaenge.aendern(im_chat)
    ziel = datei.parent / ERLEDIGT / datei.name
    ziel.parent.mkdir(parents=True, exist_ok=True)
    try:
        datei.replace(ziel)
    except FileNotFoundError:
        pass                      # ein zweiter Abholer war schneller
