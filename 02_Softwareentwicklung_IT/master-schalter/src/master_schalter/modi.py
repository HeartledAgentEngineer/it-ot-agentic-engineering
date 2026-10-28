"""Persistente Themenprofile (v2) und sichere Rollenwechsel.

Die Auswahl ist eine Routing-/Rollenregel. Sie startet weder eine Sitzung noch einen Transport
und niemals einen Workerprozess: `worker` ist eine gespeicherte Ausführervorgabe für den
NÄCHSTEN bereinigten Coding-Auftrag; `master` ist die Soll-Masterrolle des Themas.

Format in `themenmodi.json`:

    {"version": 2, "themen": {"<thema>": {"master": "...", "worker": "...", "modell": ...}}}

* ``master``  – ``kontingent|claude|codex|hermes``
* ``worker``  – ``workflow|claude|codex|hermes`` (``workflow`` nur mit ``modell: null``)
* ``modell``  – Kennung oder ``None`` (Standard des Werkzeugs); bei ``hermes`` genau
  ``deepseek/deepseek-v4.1-flash``

Unbekannte Werte, Schlüssel und Versionen werden strikt abgelehnt; eine fehlende Datei oder ein
fehlendes Thema ergibt ``kontingent/workflow/None``. Version-1-Dateien (Textwerte
``kontingent|hermes-codex``) werden **nur lesend** als v2-Profil gedeutet; migriert wird erst
beim ersten ausdrücklich angeforderten Schreibvorgang – atomar unter der kurzen globalen
Sperre, andere Themen bleiben erhalten.

Der Schutz eines Themas bleibt aktiv, solange die Masterrolle fest ist, seine geprüfte
Besitzdatei Hermes nennt oder eine eigene Modus-Zwischenmarke steht. Jeder echte Masterwechsel
läuft unter der Themensperre in fester Reihenfolge: eigene Zwischenmarke
``reserviert modus <thema> <ziel> <zeit>`` schreiben, offene Mastervorgänge entwerten, Profil
speichern, zuletzt den Zielbesitz schreiben. Die Zwischenmarke schützt auch festen
Claude-Besitz vor einem Profilspeicher-Fehler, wird in allen Versand-/ACK-/Rückgabewegen
fail-closed behandelt und nie als Übergabe-Reservierung gedeutet. Worker- und Modell-Setter
lassen Masterfeld und `.master`-Marke exakt unverändert.

Arbeitsweise `vibe` (Datei `arbeitsweise.json`, Modul `arbeitsweise`) gibt es nur mit Ausführer Claude. Die Prüfung
(`_vibe_pruefen`) sitzt zentral im einzigen Profilschreiber `_speichern` und – vor der ersten Besitzmarke – in
`_umschalten_gesperrt`; ein Profil mit anderem Ausführer wird bei `vibe` abgelehnt, ohne Profil oder Besitzdatei zu
ändern. `vibe_setzen` schaltet die Arbeitsweise (nur von Hand) und lehnt jeden anderen Ausführer als Claude ab.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

from . import arbeitsweise, besitz, modelle, paare, uebergabe, vorgaenge, zustand
from .signale import _atomar_schreiben, _iso, daten_ordner

KONTINGENT = "kontingent"
HERMES_CODEX = "hermes-codex"
WERTE = (KONTINGENT, HERMES_CODEX)                       # Legacy-Werte von CLI und Menü
MASTER_WERTE = ("kontingent", "claude", "codex", "hermes")
WORKER_WERTE = ("workflow", "claude", "codex", "hermes")
WORKFLOW = "workflow"
ZIEL_ROLLEN = ("claude", "codex", "hermes")
VORGANG_ID_MUSTER = re.compile(r"[A-Za-z0-9_-]{1,80}")   # Vorgangs- und Sitzungskennungen des Assistenten
HERMES_MODELL = "deepseek/deepseek-v4.1-flash"
VERSION = 2
VERSION_ALT = 1
GLOBALE_FRIST = 1.0
_E = TypeVar("_E")
ANZEIGE = {"claude": "Claude", "codex": "Codex", "hermes": "Hermes"}


class ModusFehler(Exception):
    """Profil, Thema, Sperre oder Besitzwechsel ist ungültig."""


@dataclass(frozen=True)
class Profil:
    master: str = KONTINGENT
    worker: str = WORKFLOW
    modell: str | None = None


# Nur-Lese-Migration der Version-1-Werte; geschrieben wird ausschließlich Version 2.
LEGACY: dict[str, Profil] = {
    KONTINGENT: Profil(KONTINGENT, WORKFLOW, None),
    HERMES_CODEX: Profil("hermes", "codex", "gpt-6-luna"),
}
_ZIEL_ROLLE = {KONTINGENT: besitz.CLAUDE, "claude": besitz.CLAUDE,
               "codex": besitz.CODEX, "hermes": besitz.HERMES}
_ERWARTETE_BESITZER = {
    KONTINGENT: (besitz.CLAUDE, besitz.CODEX),   # eine laufende Codex-Übernahme bleibt gültig
    "claude": (besitz.CLAUDE,),
    "codex": (besitz.CODEX,),
    "hermes": (besitz.HERMES,),
}


def datei() -> Path:
    return daten_ordner() / "themenmodi.json"


# --- Lesen und strenge Prüfung -------------------------------------------------

def _modell_pruefen(modell: object) -> str:
    """Saubere Modellkennung (Text, ohne Kontrollzeichen, begrenzt) – sonst ModusFehler."""
    if not isinstance(modell, str):
        raise ModusFehler(f"Modellkennung ist kein Text: {modell!r}")
    text = modell.strip()
    if (not text or text != modell or len(text) > modelle.MAX_FELD
            or any(ord(zeichen) < 32 or ord(zeichen) == 127 for zeichen in text)):
        raise ModusFehler(f"Modellkennung unzulässig: {modell!r}")
    return text


def _profil_pruefen(thema: str, roh: object) -> Profil:
    """Ein v2-Profil streng prüfen: genau die drei Felder, gültige Werte, gültige Kombination."""
    if not isinstance(roh, dict) or set(roh) != {"master", "worker", "modell"}:
        raise ModusFehler(f"Modusdatei enthält ein ungültiges Profil für {thema!r}")
    master, worker, modell = roh["master"], roh["worker"], roh["modell"]
    if not isinstance(master, str) or master not in MASTER_WERTE:
        raise ModusFehler(f"Unbekannte Masterrolle für {thema!r}: {master!r}")
    if not isinstance(worker, str) or worker not in WORKER_WERTE:
        raise ModusFehler(f"Unbekannter Ausführerprovider für {thema!r}: {worker!r}")
    if modell is not None:
        modell = _modell_pruefen(modell)
    if worker == WORKFLOW and modell is not None:
        raise ModusFehler(f"„Nach Workflow“ erlaubt kein festes Modell für {thema!r}")
    if worker == "hermes" and modell != HERMES_MODELL:
        raise ModusFehler(f"Hermes nutzt genau {HERMES_MODELL!r}; {thema!r} nennt {modell!r}")
    return Profil(master, worker, modell)


def _lesen(datei_pfad: Path | None = None) -> dict[str, Profil]:
    pfad = datei_pfad or datei()
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as fehler:
        raise ModusFehler(f"Modusdatei nicht lesbar: {fehler}") from fehler
    if (not isinstance(roh, dict) or not isinstance(roh.get("themen"), dict)
            or set(roh) - {"version", "themen"}):
        raise ModusFehler("Modusdatei hat ein ungültiges Format oder eine unbekannte Version")
    version = roh.get("version")
    if version not in (VERSION_ALT, VERSION):
        raise ModusFehler("Modusdatei hat ein ungültiges Format oder eine unbekannte Version")
    result: dict[str, Profil] = {}
    for thema, wert in roh["themen"].items():
        try:
            paare.thema_pruefen(thema)
        except paare.PaarFehler as fehler:
            raise ModusFehler(f"Modusdatei enthält ein ungültiges Thema: {fehler}") from fehler
        if version == VERSION_ALT:
            if not isinstance(wert, str) or wert not in LEGACY:
                raise ModusFehler(f"Modusdatei enthält einen unbekannten Modus für {thema!r}")
            result[thema] = LEGACY[wert]
        else:
            result[thema] = _profil_pruefen(thema, wert)
    return result


def lesen(datei_pfad: Path | None = None) -> dict[str, Profil]:
    return _lesen(datei_pfad)


def profil(thema: str, datei_pfad: Path | None = None) -> Profil:
    try:
        paare.thema_pruefen(thema)
    except paare.PaarFehler as fehler:
        raise ModusFehler(str(fehler)) from fehler
    return _lesen(datei_pfad).get(thema, Profil())


def als_profil(wert: str | Profil) -> Profil:
    """Alt-Wert oder Profil vereinheitlichen; unbekannte Texte bedeuten Kontingentbetrieb."""
    if isinstance(wert, Profil):
        return wert
    return LEGACY.get(wert, Profil())


def _anzeige(wert: Profil) -> str:
    """Legacy-Sicht für CLI/Menü: `kontingent` bzw. `hermes-codex`, sonst die feste Masterrolle."""
    if wert.master == KONTINGENT:
        return KONTINGENT
    if wert.master == "hermes" and wert.worker == "codex":
        return HERMES_CODEX
    return wert.master


def modus(thema: str, datei_pfad: Path | None = None) -> str:
    """Arbeitsmodus-Anzeige eines Themas (Legacy-Sicht, aus dem Profil abgeleitet)."""
    return _anzeige(profil(thema, datei_pfad))


# --- Besitz und Pfade ----------------------------------------------------------

def _besitz_text_lesen(master_datei: Path) -> str:
    """Nur eine fehlende Datei bedeutet Claude; ein echter Lesefehler sperrt fail-closed."""
    try:
        return master_datei.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""
    except OSError as fehler:
        raise ModusFehler(f"Besitzstatus nicht lesbar; Thema bleibt geschützt ({fehler})") from fehler


def _besitzer_lesen(master_datei: Path) -> str:
    return besitz.besitzer(_besitz_text_lesen(master_datei))


def _pfad_teile(pfad: Path) -> tuple[str, ...]:
    """Pfadkomponenten ohne Windows-Längenpräfix; unter Windows ohne Groß-/Kleinschreibung."""
    text = os.fspath(pfad)
    if text.startswith("\\\\?\\UNC\\"):
        text = "\\\\" + text[len("\\\\?\\UNC\\"):]
    elif text.startswith("\\\\?\\"):
        text = text[len("\\\\?\\"):]
    text = os.path.normcase(os.path.normpath(text))
    return tuple(teil for teil in re.split(r"[\\/]+", text) if teil)


def _enthalten(master: Path, wurzel: Path) -> bool:
    """Komponentenweise Enthaltensein – robust gegen `\\\\?\\`-Präfixe (Windows-Race)."""
    a, b = _pfad_teile(master), _pfad_teile(wurzel)
    return len(b) <= len(a) and a[: len(b)] == b


def _paar_pruefen(thema: str, repo: Path | None, *, laufend: str | None = None,
                  erforderlich: bool = True) -> tuple[paare.Paar | None, Path | None]:
    try:
        paare.thema_pruefen(thema)
    except paare.PaarFehler as fehler:
        raise ModusFehler(str(fehler)) from fehler
    paar = next((p for p in paare.lesen() if p.thema == thema), None)
    if paar is None and laufend is None and erforderlich:
        raise ModusFehler(f"Thema unbekannt (kein vorhandenes Paar): {thema}")
    if paar is None and laufend is None:
        return None, None
    if repo is None:
        try:
            wurzel = uebergabe.repo_wurzel()
        except uebergabe.UebergabeFehler as fehler:
            raise ModusFehler(str(fehler)) from fehler
    else:
        wurzel = Path(repo).resolve()
        if not wurzel.is_dir() or not (wurzel / ".git").exists():
            raise ModusFehler("Repository-Wurzel ist nicht geprüft")
    laufend = paare.laufend_pruefen(thema, paar.laufend if paar is not None else laufend or "")
    master = besitz.pfad(wurzel, laufend)
    if not _enthalten(master.resolve(), wurzel.resolve()):
        raise ModusFehler("Besitzpfad liegt außerhalb des geprüften Repositorys")
    return paar, master


# --- Eigene Modus-Zwischenmarke ------------------------------------------------

def zwischenmarke(thema: str, ziel: str, zeit: str) -> str:
    """Eigene Modus-Zwischenmarke `reserviert modus <thema> <ziel> <zeit>` bauen."""
    if ziel not in ZIEL_ROLLEN:
        raise ModusFehler(f"Zwischenmarke braucht eine Zielrolle, nicht {ziel!r}")
    return f"reserviert modus {thema} {ziel} {zeit}"


def ist_zwischenmarke(text: str, thema: str) -> bool:
    """Nur die eigene Marke in strengem Format UND mit demselben Thema wird erkannt."""
    teile = text.split()
    if len(teile) != 5 or teile[0] != besitz.RESERVIERT or teile[1] != "modus":
        return False
    if teile[2] != thema or teile[3] not in ZIEL_ROLLEN:
        return False
    return _iso(teile[4]) is not None


# --- Schutz und Anzeige --------------------------------------------------------

def fuehrt(thema: str, *, repo: Path | None = None, datei_pfad: Path | None = None,
           laufend: str | None = None) -> str | None:
    """Wer das Thema führt – feste Masterrolle, echter Hermes-Besitz oder eigene Zwischenmarke.

    `None` heißt Kontingentbetrieb ohne Besitz. Für Aufruf unter der Themensperre gedacht;
    ein unlesbarer Besitzstatus sperrt fail-closed.
    """
    wert = profil(thema, datei_pfad)
    if wert.master != KONTINGENT:
        return ANZEIGE[wert.master]
    paar, master_datei = _paar_pruefen(thema, repo, laufend=laufend, erforderlich=False)
    if paar is None and master_datei is None:
        return None
    text = _besitz_text_lesen(master_datei)
    if ist_zwischenmarke(text, thema):
        return "Modusumschaltung"
    return ANZEIGE["hermes"] if besitz.besitzer(text) == besitz.HERMES else None


def geschuetzt(thema: str, *, repo: Path | None = None, datei_pfad: Path | None = None,
               laufend: str | None = None) -> bool:
    """Frische Schutzprüfung; für Aufruf unter der Themensperre vorgesehen."""
    return fuehrt(thema, repo=repo, datei_pfad=datei_pfad, laufend=laufend) is not None


def snapshot(themen: list[str], *, repo: Path | None = None,
             datei_pfad: Path | None = None) -> dict[str, tuple[str, str, bool]]:
    """Einmaliger technischer UI-Snapshot: (Modus-Anzeige, Besitz, effektiv geschützt) je Thema."""
    mapping = _lesen(datei_pfad)
    wurzel: Path | None = repo
    if wurzel is None:
        try:
            wurzel = uebergabe.repo_wurzel()
        except uebergabe.UebergabeFehler as fehler:
            raise ModusFehler(str(fehler)) from fehler
    result: dict[str, tuple[str, str, bool]] = {}
    for thema in themen:
        wert = mapping.get(thema, Profil())
        _, master_datei = _paar_pruefen(thema, wurzel)
        text = _besitz_text_lesen(master_datei)
        owner = besitz.besitzer(text)
        if owner not in (besitz.CLAUDE, besitz.CODEX, besitz.RESERVIERT, besitz.HERMES):
            raise ModusFehler(f"Besitzstatus von {thema!r} ist unbekannt")
        sicher = (wert.master != KONTINGENT or owner == besitz.HERMES
                  or ist_zwischenmarke(text, thema))
        result[thema] = (_anzeige(wert), owner, sicher)
    return result


# --- Schreiben -----------------------------------------------------------------

def _speichern(datei_pfad: Path, thema: str, profil_wert: Profil | str) -> None:
    """Atomar unter kurzer globaler Sperre schreiben; andere Themen bleiben erhalten.

    Nimmt auch einen Legacy-Textwert an: der erste ausdrückliche Schreibvorgang migriert eine
    Version-1-Datei damit vollständig auf Version 2.
    """
    ziel = profil_wert
    if isinstance(ziel, str):
        if ziel not in LEGACY:
            raise ModusFehler(f"Unbekannter Arbeitsmodus: {ziel!r}")
        ziel = LEGACY[ziel]
    if not isinstance(ziel, Profil):
        raise ModusFehler("Arbeitsprofil ist ungeeignet")
    _vibe_pruefen(thema, ziel, arbeitsweise.neben(datei_pfad))
    with zustand.sperre(GLOBALE_FRIST):
        aktuell = _lesen(datei_pfad)
        aktuell[thema] = ziel
        _atomar_schreiben(datei_pfad, json.dumps(
            {"version": VERSION,
             "themen": {t: {"master": p.master, "worker": p.worker, "modell": p.modell}
                        for t, p in aktuell.items()}},
            ensure_ascii=False, indent=2))


def _vibe_pruefen(thema: str, ziel: Profil, vibe_pfad: Path) -> None:
    """Vorrangregel: Vibe gibt es nur mit Ausführer Claude – vor jeder Nebenwirkung des Profilschreibens.

    Nur ein Profil mit anderem Ausführer wird geprüft. Ist die Arbeitsweise-Datei dann nicht lesbar, ist unbekannt, ob
    Vibe gilt: Das Profil bleibt fail-closed unverändert (die Meldung nennt den Grund).
    """
    if ziel.worker == "claude":
        return
    try:
        weise = arbeitsweise.arbeitsweise(thema, vibe_pfad)
    except arbeitsweise.ArbeitsweiseFehler as fehler:
        raise ModusFehler(f"Arbeitsweise von {thema!r} nicht prüfbar ({fehler}); Profil wurde nicht geändert") from fehler
    if weise == arbeitsweise.VIBE:
        raise ModusFehler(f"{thema!r} steht auf Vibe und braucht Ausführer Claude – erst `masterwechsel vibe {thema} "
                          "aus`; Profil wurde nicht geändert")


def _offene_entwerten(thema: str, zeit: str) -> None:
    def entwerten(alt: list[vorgaenge.Vorgang]) -> list[vorgaenge.Vorgang]:
        return [
            replace(v, phase="entwertet", zeit=zeit)
            if v.thema == thema and v.phase in vorgaenge.OFFEN else v
            for v in alt
        ]

    vorgaenge.aendern(entwerten, frist=GLOBALE_FRIST)


def _ziel_marke(ziel: Profil, zeit: str, thema: str) -> str:
    if ziel.master == KONTINGENT:
        return besitz.zeile(besitz.CLAUDE, zeit, "modus-reset", thema)
    return besitz.zeile(_ZIEL_ROLLE[ziel.master], zeit, "modus", thema)


def _besitz_meldung(ziel: Profil, owner: str) -> str:
    if ziel.master == KONTINGENT and owner != besitz.CLAUDE:
        return "Besitzmarke noch nicht zurückgesetzt"
    return f"{ANZEIGE[_ZIEL_ROLLE[ziel.master]]}-Besitzmarke nicht gespeichert"


def vorgang_id_pruefen(vorgang_id: object) -> str:
    """Kennung nur nach Muster (`re.fullmatch`, kein abschließendes LF) – sonst ModusFehler."""
    if not isinstance(vorgang_id, str) or VORGANG_ID_MUSTER.fullmatch(vorgang_id) is None:
        raise ModusFehler(f"Vorgangskennung unzulässig (erlaubt: {VORGANG_ID_MUSTER.pattern}): {vorgang_id!r}")
    return vorgang_id


def _umschalten_gesperrt(thema: str, ziel: Profil, datei_pfad: Path | None, *,
                         repo: Path | None, vorgang_id: str | None = None) -> Profil:
    """Einen echten Masterwechsel unter der bereits gehaltenen Themensperre vollziehen.

    Reihenfolge: eigene Zwischenmarke → offene Mastervorgänge entwerten → Profil speichern →
    Zielbesitz schreiben. Jeder Teilfehler nennt den erreichten Zustand; die Wiederholung
    derselben Wahl erkennt die eigene Zwischenmarke und vervollständigt sicher.

    Mit `vorgang_id` (Wechselassistent) schreibt der einzige abschließende Zielschreibvorgang
    direkt `<rolle> <zeit> assistent <thema> <vorgang-id>` – auch wenn die Zielrolle schon
    besitzt. Es gibt also nie eine fertige Modusmarke ohne Vorgangs-ID. Ohne `vorgang_id`
    bleibt das Verhalten exakt wie in v0.4.0.
    """
    try:
        paare.thema_pruefen(thema)
    except paare.PaarFehler as fehler:
        raise ModusFehler(str(fehler)) from fehler
    if vorgang_id is not None:
        vorgang_id_pruefen(vorgang_id)
        if ziel.master not in ZIEL_ROLLEN:
            raise ModusFehler(f"Übergabe braucht eine Zielrolle (claude|codex|hermes), nicht {ziel.master!r}")
    pfad = datei_pfad or datei()
    alt = _lesen(pfad).get(thema, Profil())
    _vibe_pruefen(thema, ziel, arbeitsweise.neben(pfad))    # vor der ersten Besitzmarke
    # Vor jeder Nebenwirkung: Thema, Paar, Repository-Pfade und fremde Reservierung prüfen.
    _, master_datei = _paar_pruefen(thema, repo)
    text = _besitz_text_lesen(master_datei)
    eigene_marke = ist_zwischenmarke(text, thema)
    owner = besitz.besitzer(text)
    if not eigene_marke:
        if owner == besitz.RESERVIERT:
            raise ModusFehler("Thema ist gerade fremd reserviert; Arbeitsmodus wurde nicht geändert")
        if owner not in (besitz.CLAUDE, besitz.CODEX, besitz.HERMES):
            raise ModusFehler("Besitzstatus ist unbekannt; Arbeitsmodus wurde nicht geändert")
    ziel_rolle = _ZIEL_ROLLE[ziel.master]
    if vorgang_id is not None:
        if (alt == ziel and not eigene_marke
                and besitz.assistent_marke(text) == (ziel_rolle, thema, vorgang_id)):
            return alt     # derselbe Vorgang ist schon fertig übergeben: keine zweite Marke
    elif alt == ziel and owner in _ERWARTETE_BESITZER[ziel.master] and not eigene_marke:
        return alt     # konsistente gleiche Masterwahl: keine Nebenwirkung, Marke bleibt bytegleich

    zeit = datetime.now(timezone.utc).isoformat()
    marke = zwischenmarke(thema, ziel_rolle, zeit)
    if not eigene_marke:
        try:
            geschrieben = besitz.vergleiche_und_schreibe(master_datei, text, marke)
        except OSError as fehler:
            raise ModusFehler(f"Besitzdatei nicht schreibbar; Arbeitsmodus wurde nicht geändert ({fehler})") from fehler
        if not geschrieben:
            raise ModusFehler("Besitzdatei wurde gleichzeitig geändert; Arbeitsmodus wurde nicht geändert")
        steht = marke           # ab jetzt steht die frische eigene Zwischenmarke in der Datei
    else:
        steht = text            # aus einem abgebrochenen eigenen Wechsel übernommene Marke
    try:
        _offene_entwerten(thema, zeit)
    except (OSError, zustand.SperrFehler) as fehler:
        raise ModusFehler("Umschaltung unvollständig – Modus erneut wählen: offene Vorgänge nicht "
                          f"entwertet; eigene Zwischenmarke steht ({fehler})") from fehler
    if alt != ziel:
        try:
            _speichern(pfad, thema, ziel)
        except (OSError, zustand.SperrFehler, ModusFehler) as fehler:
            raise ModusFehler("Umschaltung unvollständig – Modus erneut wählen: offene Vorgänge "
                              f"entwertet; eigene Modusmarke steht, Modusdatei nicht aktualisiert "
                              f"(vorheriges Profil {alt}) ({fehler})") from fehler
    if vorgang_id is not None:
        neu = besitz.assistent_zeile(ziel_rolle, zeit, thema, vorgang_id)
    elif owner == ziel_rolle and not eigene_marke:
        neu = text      # bestehende echte Ziel-Mastermarke wörtlich erhalten
    else:
        neu = _ziel_marke(ziel, zeit, thema)
    try:
        geschrieben = besitz.vergleiche_und_schreibe(master_datei, steht, neu)
    except OSError as fehler:
        raise ModusFehler("Umschaltung unvollständig – Modus erneut wählen: offene Vorgänge "
                          f"entwertet; {_besitz_meldung(ziel, owner)}, eigene Modusmarke steht "
                          f"noch ({fehler})") from fehler
    if not geschrieben:
        raise ModusFehler("Umschaltung unvollständig – Modus erneut wählen: offene Vorgänge "
                          f"entwertet; {_besitz_meldung(ziel, owner)}, eigene Modusmarke steht noch")
    return ziel


def _unter_sperre(thema: str, arbeit: Callable[[], _E]) -> _E:
    try:
        paare.thema_pruefen(thema)
    except paare.PaarFehler as fehler:
        raise ModusFehler(str(fehler)) from fehler
    try:
        with zustand.thema_sperre(thema, blockierend=True, frist=GLOBALE_FRIST) as frei:
            if not frei:
                raise zustand.SperrFehler("Themenwechsel ist gerade belegt")
            return arbeit()
    except zustand.SperrFehler as fehler:
        raise ModusFehler(f"Übergabe läuft – Modus gleich erneut wählen: {fehler}") from fehler


# --- Öffentliche Setter ---------------------------------------------------------

def vibe_setzen(thema: str, an: bool, datei_pfad: Path | None = None) -> bool:
    """Arbeitsweise Vibe ein- oder ausschalten (nur von Hand); `True`, wenn sich etwas geändert hat.

    Unter der Themensperre, das Profil wird dazu frisch gelesen. Das Thema muss existieren (Profil oder Paar). `an`
    braucht Ausführer Claude (Vorrang vor der Workerwahl); bei jedem Fehler bleibt die Datei unverändert.
    """
    def arbeit() -> bool:
        pfad = datei_pfad or datei()
        profile = _lesen(pfad)
        if thema not in profile and not any(p.thema == thema for p in paare.lesen()):
            raise ModusFehler(f"Thema unbekannt (weder Profil noch Paar): {thema}")
        if an and profile.get(thema, Profil()).worker != "claude":
            raise ModusFehler("Vibe braucht Ausführer Claude – erst `masterwechsel worker-setzen "
                              f"{thema} claude`")
        try:
            return arbeitsweise.setzen(thema, an, arbeitsweise.neben(pfad))
        except arbeitsweise.ArbeitsweiseFehler as fehler:
            raise ModusFehler(str(fehler)) from fehler

    return _unter_sperre(thema, arbeit)


def _setzen_gesperrt(thema: str, wert: str, datei_pfad: Path | None = None, *,
                     repo: Path | None = None) -> None:
    """Interner Legacy-Setter für Aufrufer, die die Themensperre bereits halten."""
    if wert not in WERTE:
        raise ModusFehler(f"Unbekannter Arbeitsmodus: {wert!r}")
    _umschalten_gesperrt(thema, LEGACY[wert], datei_pfad, repo=repo)


def setzen(thema: str, wert: str, datei_pfad: Path | None = None, *,
           repo: Path | None = None) -> None:
    """Legacy-Setter der CLI/des Menüs (`kontingent`|`hermes-codex`) – migriert nach v2."""
    try:
        paare.thema_pruefen(thema)
    except paare.PaarFehler as fehler:
        raise ModusFehler(str(fehler)) from fehler
    if wert not in WERTE:
        raise ModusFehler(f"Unbekannter Arbeitsmodus: {wert!r}")
    _unter_sperre(thema, lambda: _umschalten_gesperrt(thema, LEGACY[wert], datei_pfad, repo=repo))


def master_setzen(thema: str, master: str, datei_pfad: Path | None = None, *,
                  repo: Path | None = None) -> Profil:
    """Nur die Masterrolle eines Themas setzen – Worker- und Modellwahl bleiben erhalten.

    Eine konsistente gleiche Masterwahl ist ein No-op und erhält eine bestehende echte
    Ziel-Mastermarke bytegleich; jeder echte Wechsel entwertet offene Mastervorgänge.
    """
    if not isinstance(master, str) or master not in MASTER_WERTE:
        raise ModusFehler(f"Unbekannte Masterrolle: {master!r}")

    def arbeit() -> Profil:
        pfad = datei_pfad or datei()
        alt = _lesen(pfad).get(thema, Profil())
        return _umschalten_gesperrt(thema, replace(alt, master=master), pfad, repo=repo)

    return _unter_sperre(thema, arbeit)


def master_setzen_wenn(thema: str, master: str, pruefung: Callable[[Profil, str, str | None], bool],
                       datei_pfad: Path | None = None, *, repo: Path | None = None) -> Profil | None:
    """Masterrolle nur setzen, wenn `pruefung` den frisch gelesenen Zustand erlaubt (Sammelbefehl `alle`).

    Unter derselben Themensperre wie `master_setzen` werden Profil und Besitzdatei (fail-closed) gelesen und
    `pruefung(alt, besitzer, zwischenziel)` aufgerufen; `zwischenziel` ist die Zielrolle einer eigenen
    Modus-Zwischenmarke, sonst `None`. `False` ⇒ `None`, nichts geschrieben. Eine Ausnahme aus `pruefung`
    ⇒ `ModusFehler`, nichts umgeschaltet. `True` ⇒ derselbe Wechsel wie `master_setzen`.
    """
    if not isinstance(master, str) or master not in MASTER_WERTE:
        raise ModusFehler(f"Unbekannte Masterrolle: {master!r}")

    def arbeit() -> Profil | None:
        pfad = datei_pfad or datei()
        alt = _lesen(pfad).get(thema, Profil())
        _, master_datei = _paar_pruefen(thema, repo)
        text = _besitz_text_lesen(master_datei)
        zwischenziel = text.split()[3] if ist_zwischenmarke(text, thema) else None
        try:
            erlaubt = pruefung(alt, besitz.besitzer(text), zwischenziel)
        except Exception as fehler:   # bewusst breit: jede Panne in Prüfung/Merken verhindert das Umschalten
            raise ModusFehler(f"Vorprüfung gescheitert; Arbeitsmodus wurde nicht geändert ({fehler})") from fehler
        if not erlaubt:
            return None
        return _umschalten_gesperrt(thema, replace(alt, master=master), pfad, repo=repo)

    return _unter_sperre(thema, arbeit)


def master_uebergeben_gesperrt(thema: str, master: str, *, vorgang_id: str,
                               datei_pfad: Path | None = None, repo: Path | None = None) -> Profil:
    """Masterrolle für den Wechselassistenten setzen – **die Themensperre muss der Aufrufer halten**.

    Wie `master_setzen` (Worker und Modell bleiben erhalten, offene Mastervorgänge werden
    entwertet), nimmt die Sperre aber nicht selbst. Die Zielmarke trägt die Vorgangs-ID
    (`<rolle> <zeit> assistent <thema> <vorgang-id>`); nur Zielrollen claude|codex|hermes.
    """
    if not isinstance(master, str) or master not in ZIEL_ROLLEN:
        raise ModusFehler(f"Unbekannte Zielrolle: {master!r} (erlaubt: {', '.join(ZIEL_ROLLEN)})")
    vorgang_id_pruefen(vorgang_id)
    pfad = datei_pfad or datei()
    alt = _lesen(pfad).get(thema, Profil())
    return _umschalten_gesperrt(thema, replace(alt, master=master), pfad, repo=repo, vorgang_id=vorgang_id)


def worker_setzen(thema: str, worker: str, datei_pfad: Path | None = None, *,
                  repo: Path | None = None) -> Profil:
    """Ausführervorgabe setzen; Masterfeld und `.master`-Marke bleiben exakt unverändert.

    Ein Providerwechsel setzt das Modell ausdrücklich auf den Standard des Werkzeugs
    (`None`; bei Hermes die fest freigegebene Kennung) – der Aufrufer meldet das.
    """
    if not isinstance(worker, str) or worker not in WORKER_WERTE:
        raise ModusFehler(f"Unbekannter Ausführerprovider: {worker!r}")

    def arbeit() -> Profil:
        pfad = datei_pfad or datei()
        alt = _lesen(pfad).get(thema, Profil())
        _paar_pruefen(thema, repo)
        if worker == alt.worker:
            return alt
        neu = replace(alt, worker=worker,
                      modell=HERMES_MODELL if worker == "hermes" else None)
        _speichern(pfad, thema, neu)
        return neu

    return _unter_sperre(thema, arbeit)


def _katalog_pruefen(provider: str, modell: str, katalog: modelle.Katalog | None,
                     jetzt: datetime | None) -> None:
    """Die Modellwahl nur gegen einen sichtbaren, erfolgreich ermittelten Katalog zulassen."""
    sichtbar = katalog if katalog is not None else modelle.lesen(provider, jetzt=jetzt)
    if not isinstance(sichtbar, modelle.Katalog):
        raise ModusFehler("Modellkatalog ist nicht geprüft; Modell wurde nicht gespeichert")
    if sichtbar.provider != provider:
        raise ModusFehler(f"Modellkatalog gehört zu {sichtbar.provider!r}, nicht zu {provider!r}")
    if sichtbar.fehler is not None:
        raise ModusFehler(f"Modellkatalog von {provider} wurde nicht erfolgreich ermittelt "
                          f"({sichtbar.fehler}); Modell wurde nicht gespeichert")
    if sichtbar.veraltet:
        raise ModusFehler(f"Modellkatalog von {provider} ist veraltet – erst Modelle aktualisieren")
    if not any(m.id == modell for m in sichtbar.modelle):
        raise ModusFehler(f"Modell {modell!r} steht nicht im erfolgreich ermittelten Katalog "
                          f"von {provider}")


def modell_setzen(thema: str, modell: str | None, datei_pfad: Path | None = None, *,
                  repo: Path | None = None, katalog: modelle.Katalog | None = None,
                  jetzt: datetime | None = None) -> Profil:
    """Ausführermodell setzen; Masterfeld und `.master`-Marke bleiben exakt unverändert.

    `None` ist die ausdrückliche Standardvorgabe des Werkzeugs. Feste Kennungen der Werkzeuge
    werden gegen den sichtbaren, erfolgreich ermittelten Katalog geprüft; ein veralteter oder
    fehlerhafter Katalog lehnt ab, ohne irgendetwas zu ändern. Das Hermes-Modell ist
    ausdrücklich fest freigegeben.
    """
    geprueft = None if modell is None else _modell_pruefen(modell)

    def arbeit() -> Profil:
        pfad = datei_pfad or datei()
        alt = _lesen(pfad).get(thema, Profil())
        _paar_pruefen(thema, repo)
        if alt.worker == WORKFLOW:
            if geprueft is not None:
                raise ModusFehler("„Nach Workflow“ erlaubt kein festes Modell")
            return alt
        if alt.worker == "hermes":
            if geprueft != HERMES_MODELL:
                raise ModusFehler(f"Hermes nutzt genau {HERMES_MODELL!r}")
        elif geprueft is not None:
            _katalog_pruefen(alt.worker, geprueft, katalog, jetzt)
        neu = replace(alt, modell=geprueft)
        if neu != alt:
            _speichern(pfad, thema, neu)
        return neu

    return _unter_sperre(thema, arbeit)
