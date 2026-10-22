"""Postfach des Wechselassistenten: eine kleine Datei je Nachricht an einen Claude-/Hermes-Chat.

Layout: `<datenordner>/postfach/<ziel>/<kennung>/<vorgang-id>_<art>.json` mit `ziel` ∈ claude|hermes
(Codex bekommt seine Nachricht über die Thread-Queue) und `art` ∈ `NACHRICHTEN`:
* `neu`            – Übernahme-Auftrag an den neuen Master
* `abgabe_auftrag` – Abgabe-Auftrag an den alten Master (er soll abschließen und quittieren)
* `abgabe_info`    – Info an den alten Master, dass er das Thema nicht mehr führt (ersetzt den Auftrag,
  wenn die Abgabe übersprungen wurde)
Auftrag und Info desselben Vorgangs liegen dank der Art im Dateinamen nebeneinander. Eingelegte
Dateien wandern bei der Abholung nach `erledigt/`, endgültig ungültige nach `verworfen/` (mit Grund).

Sicherheit (G6): Sitzungskennungen und Vorgangs-IDs nur nach Muster `^[A-Za-z0-9_-]{1,80}$`, die
Postfachwurzel ist fest und der aufgelöste Ordner muss unter ihr liegen; Dateien sind höchstens
4 KB groß und enthalten nur `{vorgang, thema, rolle, laufend, zeit}` (`rolle` = die Art) – der Text
der Nachricht entsteht erst beim Abholen aus festen Satzbausteinen.

Gültigkeit (G5/G8): Beim Abholen gibt es **drei** Ausgänge je Datei: zustellen, liegen lassen,
verwerfen. Verworfen wird nur bei endgültiger Ungültigkeit; im Zweifel bleibt die Datei liegen
(Vorgang noch nicht vermerkt, Phase noch nicht erreicht, Besitzstatus nicht lesbar, Themensperre belegt).
* `neu` gilt nur, solange die aktuelle Marke genau `<ziel-rolle> … assistent <thema> <vorgang-id>` ist
  (A→B→A: B erhält nichts mehr); vor `rolle_gesetzt` bleibt sie liegen.
* `abgabe_auftrag` gilt nur in einer offenen Abgabephase (`ABGABE_OFFEN`) und solange der Markentext
  noch dem Vorzustand des Vorgangs entspricht (während der Abgabe gehört die Marke noch dem alten
  Master); in `vorbereitet` bleibt er liegen (Datei steht vor dem Phasenwechsel), in jeder anderen
  Phase wird er verworfen.
* `abgabe_info` bleibt liegen, solange der Markentext noch dem Vorzustand entspricht (der alte Master
  führt noch); danach gilt sie, außer der Vorgang ist verworfen oder die Marke gehört – ohne genau diesen
  Wechsel zu tragen – wieder dem alten Master (späterer Wechsel zurück).
* Abgabe-Auftrag und -Info an eine andere Rolle als den alten Master (`vorgang.von`) werden verworfen.
Vor der Entscheidung wird die Datei unter der Sperre erneut gelesen; fehlt sie oder hat sie sich
geändert, war ein zweiter Abholer schneller und sie wird nicht noch einmal zurückgegeben.
Gültigkeitsprüfung und Zustellen/Verwerfen laufen je Datei unter der Themensperre (vor der Dateisperre
von `aendern`); ist sie belegt, bleibt die Datei liegen.

Den Text baut `text(art, …)` aus festen Satzbausteinen – auch für die Codex-Queue. Bei `neu` hängt er
den Zusatzsatz `ZUSATZ_ABGABE_FEHLTE` an, wenn der Vorgang `abgabe == "uebersprungen"` trägt; beim
Abholen wird das aus dem Vorgang abgeleitet (die Datei bekommt kein neues Inhaltsfeld).

Abholung ist **keine** Übernahme: `neu` setzt den Vorgang nur auf `im_chat`; die Übernahme bestätigt
der Zielchat selbst mit `masterwechsel quittieren`. Abgabe-Auftrag und -Info ändern die Phase **nie**,
sie setzen nur `abgabe_zugestellt`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from . import assistent_vorgaenge, besitz, modi, paare, zustand
from .signale import _atomar_schreiben, daten_ordner

ZIELE = ("claude", "hermes")
NACHRICHTEN = ("neu", "abgabe_auftrag", "abgabe_info")   # Werte des Inhaltsfeldes `rolle`
MAX_BYTES = 4096
FELDER = {"vorgang", "thema", "rolle", "laufend", "zeit"}
ERLEDIGT, VERWORFEN = "erledigt", "verworfen"
ZUSTELLEN, LIEGEN, VERWERFEN = "zustellen", "liegen", "verwerfen"      # Ausgänge der Gültigkeitsprüfung

TEXT_NEU = ("Du führst jetzt das Thema {thema}. Lies zuerst {laufend}, "
            "dann führe `masterwechsel quittieren {vorgang} neu` aus. "
            "Schlägt die Quittung fehl, beginne keinen Schritt – die Nachricht gilt dann nicht mehr.")
TEXT_ABGABE_AUFTRAG = ("Du gibst das Thema {thema} ab. Schließe den laufenden Schritt sauber ab, "
                       "aktualisiere {laufend} (Kopfzeile `Übergabebereit: ja`), beginne keinen neuen Schritt "
                       "und führe `masterwechsel quittieren {vorgang} abgabe` aus.")
TEXT_ABGABE_INFO = ("Du führst das Thema {thema} nicht mehr (Vorgang {vorgang}). Beginne dort keinen "
                    "neuen Schritt; die Übergabe übernimmt der neue Master. "
                    "Maßgeblich ist die Besitzmarke; prüfe im Zweifel `masterwechsel profil {thema}`.")
TEXTE = {"neu": TEXT_NEU, "abgabe_auftrag": TEXT_ABGABE_AUFTRAG, "abgabe_info": TEXT_ABGABE_INFO}
ZUSATZ_ABGABE_FEHLTE = ("Die Abgabe des alten Masters fehlte – prüfe zuerst `git status` und die Kopfzeile "
                        "der laufenden Übergabe.")


class PostfachFehler(Exception):
    """Ziel, Kennung, Pfad oder Inhalt ist nicht zulässig."""


@dataclass(frozen=True)
class Nachricht:
    vorgang: str
    thema: str
    rolle: str                # Art: "neu" | "abgabe_auftrag" | "abgabe_info"
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


def _dateiname(vorgang_id: str, art: str) -> str:
    return f"{vorgang_id}_{art}.json"


def _zerlegen(stem: str) -> tuple[str, str] | None:
    """`<vorgang-id>_<art>` → `(vorgang-id, art)`; `None`, wenn der Name nicht diesem Muster folgt."""
    for art in NACHRICHTEN:
        if stem.endswith(f"_{art}"):
            vorgang_id = stem[: -len(art) - 1]
            return (vorgang_id, art) if modi.VORGANG_ID_MUSTER.fullmatch(vorgang_id) else None
    return None


def _inhalt(vorgang_id: str, thema: str, rolle: str, laufend: str, zeit: str) -> dict[str, str]:
    return {"vorgang": vorgang_id, "thema": thema, "rolle": rolle, "laufend": laufend, "zeit": zeit}


def einlegen(ziel: str, kennung: str, vorgang_id: str, thema: str, rolle: str, laufend: str) -> Path:
    """Nachricht atomar einlegen (tmp + `os.replace`); dieselbe Vorgangs-ID und Art ergibt genau eine Datei.

    `rolle` ist die Nachrichtenart (`NACHRICHTEN`); die Datei heißt `<vorgang-id>_<art>.json`. Liegt die
    Nachricht schon im Postfach, bleibt sie unverändert; wurde sie bereits abgeholt (`erledigt/`) oder
    verworfen, wird sie nicht erneut eingelegt (zurückgegeben wird dann der Pfad der vorhandenen Datei).
    """
    ziel_ordner = ordner(ziel, kennung)
    _kennung(vorgang_id, "Vorgangskennung")
    try:
        paare.thema_pruefen(thema)
        if laufend != paare.laufend_bilden(thema):
            raise PostfachFehler(f"laufender Pfad passt nicht zum Thema: {laufend!r}")
    except paare.PaarFehler as fehler:
        raise PostfachFehler(str(fehler)) from fehler
    if rolle not in NACHRICHTEN:
        raise PostfachFehler(f"Nachrichtenart unzulässig (erlaubt: {', '.join(NACHRICHTEN)}): {rolle!r}")
    name = _dateiname(vorgang_id, rolle)
    ziel_datei = ziel_ordner / name
    for unterordner in (ERLEDIGT, VERWORFEN):
        if (ziel_ordner / unterordner / name).exists():
            return ziel_ordner / unterordner / name
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
    if roh["rolle"] not in NACHRICHTEN:
        return None, f"Nachrichtenart unzulässig: {roh['rolle']!r}"
    if datei.stem != f"{roh['vorgang']}_{roh['rolle']}":
        return None, "Vorgangskennung und Art passen nicht zum Dateinamen"
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


def text(art: str, thema: str, laufend: str, vorgang_id: str, abgabe_uebersprungen: bool = False) -> str:
    """Fester Nachrichtentext einer Art (auch für die Codex-Queue). Nie eine Chat-Kennung darin.

    Bei der Art `neu` hängt `abgabe_uebersprungen=True` den Zusatzsatz `ZUSATZ_ABGABE_FEHLTE` an: der alte
    Master hat nicht abgegeben, der neue soll zuerst den Stand prüfen.
    """
    satz = TEXTE[art].format(thema=thema, laufend=laufend, vorgang=vorgang_id)
    return f"{satz} {ZUSATZ_ABGABE_FEHLTE}" if art == "neu" and abgabe_uebersprungen else satz


def _text(inhalt: dict[str, str]) -> str:
    """Text zur Datei; den Zusatz bei übersprungener Abgabe leitet er aus dem Vorgang ab (kein Inhaltsfeld, G6)."""
    uebersprungen = False
    if inhalt["rolle"] == "neu":
        vorgang = assistent_vorgaenge.finden(inhalt["vorgang"])
        uebersprungen = vorgang is not None and vorgang.abgabe == "uebersprungen"
    return text(inhalt["rolle"], inhalt["thema"], inhalt["laufend"], inhalt["vorgang"], uebersprungen)


def abholen(ziel: str, kennung: str, repo: Path | None = None) -> list[Nachricht]:
    """Alle gültigen Nachrichten einer Sitzung abholen; endgültig ungültige wandern nach `verworfen/`.

    Nur der Ordner dieser Kennung wird gelesen, nur Dateien `<vorgang-id>_<art>.json`. Je Datei
    entscheidet `_entscheiden` unter der Themensperre zwischen zustellen, liegen lassen und verwerfen.
    Zugestellt wird nach `erledigt/` (Abbruch dazwischen = Nachricht kommt beim nächsten Mal erneut).
    `neu` setzt den Vorgang auf `im_chat`; `abgabe_auftrag`/`abgabe_info` ändern die Phase nie, sie
    setzen nur `abgabe_zugestellt`. Nicht lesbare Marke oder belegte Themensperre: Datei bleibt liegen.
    """
    pfad = ordner(ziel, kennung)
    if not pfad.is_dir():
        return []
    nachrichten: list[Nachricht] = []
    for datei in sorted(pfad.glob("*.json")):
        if not datei.is_file() or _zerlegen(datei.stem) is None:
            continue
        roh, grund = _lesen(datei)
        inhalt, grund = (None, grund) if grund is not None else _pruefen(datei, roh)
        if inhalt is None:
            _verwerfen(datei, roh, grund or "ungültig")
            continue
        with zustand.thema_sperre(inhalt["thema"], blockierend=True,
                                  frist=assistent_vorgaenge.THEMENSPERRE_FRIST) as frei:
            if not frei:
                continue          # Thema belegt: später erneut versuchen
            if _lesen(datei) != (roh, None):
                continue          # ein zweiter Abholer war schneller (oder die Datei wurde ersetzt)
            try:
                ausgang, grund = _entscheiden(ziel, inhalt, repo)
            except modi.ModusFehler:
                continue          # Besitzstatus nicht lesbar: weder zustellen noch verwerfen
            if ausgang == LIEGEN:
                continue
            if ausgang == VERWERFEN:
                _verwerfen(datei, roh, grund or "ungültig")
                continue
            if not _zustellen(datei, inhalt):
                continue
        nachrichten.append(Nachricht(inhalt["vorgang"], inhalt["thema"], inhalt["rolle"],
                                     inhalt["laufend"], _text(inhalt)))
    return nachrichten


def _markentext(thema: str, repo: Path | None) -> str:
    """Aktueller Markentext des Themas (gestrippt, fehlende Datei = leer); `ModusFehler` bei Lesefehlern."""
    _, master_datei = modi._paar_pruefen(thema, repo)
    return modi._besitz_text_lesen(master_datei)


def _entscheiden(ziel: str, inhalt: dict[str, str], repo: Path | None) -> tuple[str, str | None]:
    """Drei Ausgänge (G5/G8): `(ZUSTELLEN | LIEGEN | VERWERFEN, Grund)`; die Themensperre ist gehalten.

    Verworfen wird nur bei endgültiger Ungültigkeit, im Zweifel bleibt die Datei liegen.
    """
    vorgang = assistent_vorgaenge.finden(inhalt["vorgang"])
    if vorgang is None:
        return LIEGEN, None       # der Vermerk kann noch nachkommen
    if vorgang.thema != inhalt["thema"]:
        return VERWERFEN, "Vorgang gehört zu einem anderen Thema"
    art = inhalt["rolle"]
    offen = assistent_vorgaenge.ABGABE_OFFEN
    if art != "neu" and ziel != vorgang.von:
        return VERWERFEN, f"Empfänger {ziel} ist nicht der alte Master ({vorgang.von})"
    if art == "neu":
        if vorgang.phase == "verworfen":
            return VERWERFEN, "Vorgang wurde verworfen"
        if vorgang.phase in ("vorbereitet", *offen, "abgegeben", "abgabe_uebersprungen", "abgabe_fehler"):
            return LIEGEN, None   # Rolle noch nicht gesetzt
        grund = assistent_vorgaenge.marke_pruefen(vorgang.thema, vorgang.id, rolle=ziel, repo=repo)
        return (ZUSTELLEN, None) if grund is None else (VERWERFEN, grund)
    if art == "abgabe_auftrag":
        if vorgang.phase == "vorbereitet":
            return LIEGEN, None   # die Datei steht vor dem Phasenwechsel `abgabe_sende`
        if vorgang.phase not in offen:
            return VERWERFEN, "Abgabe nicht mehr offen"
        if _markentext(vorgang.thema, repo) != vorgang.vorzustand_marke.strip():
            return VERWERFEN, "Marke hat sich geändert"
        return ZUSTELLEN, None
    # abgabe_info
    if vorgang.phase == "verworfen":
        return VERWERFEN, "Vorgang wurde verworfen"
    text = _markentext(vorgang.thema, repo)
    if text == vorgang.vorzustand_marke.strip():
        return LIEGEN, None       # Rolle noch nicht gewechselt: der alte Master führt noch
    if besitz.assistent_marke(text) == (vorgang.ziel, vorgang.thema, vorgang.id):
        return ZUSTELLEN, None    # Marke trägt genau diesen Wechsel (auch bei gleicher Rolle, z. B. Claude → Claude)
    if besitz.besitzer(text) == vorgang.von:
        return VERWERFEN, "Marke gehört wieder dem alten Master (späterer Wechsel)"
    return ZUSTELLEN, None


def _zustellen(datei: Path, inhalt: dict[str, str]) -> bool:
    """Zustellung vermerken (Themensperre gehalten) und die Datei nach `erledigt/` verschieben.

    `False`, wenn die Datei beim Verschieben schon fehlte – dann wird die Nachricht nicht zurückgegeben.
    """
    zeit = datetime.now(timezone.utc).isoformat()
    neu = inhalt["rolle"] == "neu"

    def vermerken(alt: list[assistent_vorgaenge.Vorgang]) -> list[assistent_vorgaenge.Vorgang]:
        if neu:
            return [replace(v, phase="im_chat", zeit=zeit)
                    if v.id == inhalt["vorgang"] and v.phase not in (*assistent_vorgaenge.ENDGUELTIG, "im_chat")
                    else v for v in alt]
        return [replace(v, abgabe_zugestellt=zeit, zeit=zeit) if v.id == inhalt["vorgang"] else v for v in alt]

    assistent_vorgaenge.aendern(vermerken)
    ziel = datei.parent / ERLEDIGT / datei.name
    ziel.parent.mkdir(parents=True, exist_ok=True)
    try:
        datei.replace(ziel)
    except FileNotFoundError:
        return False              # ein zweiter Abholer war schneller
    return True


def info_statt_auftrag(ziel: str, kennung: str, vorgang_id: str, thema: str, laufend: str) -> Path:
    """Dem alten Master die Info statt des Abgabe-Auftrags geben (Abgabe übersprungen).

    Legt `<id>_abgabe_info.json` ein – immer, auch wenn der Auftrag schon abgeholt wurde – und
    verschiebt danach einen noch liegenden `<id>_abgabe_auftrag.json` mit dem Grund „durch Abgabe-Info
    ersetzt“ nach `verworfen/`. Der Aufrufer hält die Themensperre; ein Absturz zwischen beiden
    Schritten ist unschädlich, weil der Auftrag nach `abgabe_uebersprungen` beim Abholen ohnehin
    verworfen wird. Gibt den Pfad der Info-Datei zurück.
    """
    info = einlegen(ziel, kennung, vorgang_id, thema, "abgabe_info", laufend)
    auftrag = ordner(ziel, kennung) / _dateiname(vorgang_id, "abgabe_auftrag")
    if auftrag.is_file():
        roh, _ = _lesen(auftrag)
        _verwerfen(auftrag, roh, "durch Abgabe-Info ersetzt")
    return info
