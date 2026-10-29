"""Rollen eines Themas aufgelöst und mit Modell – für Master-Status (Text) und Übersichtsfenster (Tabelle).

`aufloesen` ist eine **reine Funktion** (kein Dateizugriff): aus Profil, Lage, Besitz, Prüferwahl und Arbeitsweise macht sie
drei Texte „Werkzeug · Modell“. Modellnamen stammen ausschließlich aus `rollen.BESETZUNG` (Matrix aus `AGENTS.md`), dem
Profil des Themas oder festen Konstanten (`App-Standard`, `DeepSeek V4.1 Flash`); was dort nicht steht, ist „?“ oder
„Standard“ – nichts wird erfunden.

* **Master:** `kontingent` ⇒ Thinker der aktuellen Lage („Claude · Opus 5.5 (nach Kontingent)“; Lage unbekannt ⇒
  „nach Kontingent · Lage ?“); fester Master ⇒ dessen Werkzeug (Modell nur, wenn der Thinker der Lage dasselbe Werkzeug
  ist). Hat ein anderer den Besitz (Hermes, Antigravity, Zwischenmarke, …), steht der Besitz dabei.
* **Prüfer:** wie `pruefkreis.py`, **ausgehend vom Besitz** (`kurz.pruefkreis_master`): Besitz Codex ⇒ Hermes, Besitz
  Claude/Hermes/Antigravity ⇒ Codex; ist der Besitz unklar (Datei fehlt, unlesbar, ungültig, Zwischenmarke), bricht `pruefkreis` ohne
  `--master` ab – dann steht „?“, **auch bei gesetzter Prüferwahl**. Eine Wahl (`pruefer.json`) gilt frei, auch für die
  Familie des Masters (dann `gleiche_familie` ⇒ Hinweis). Vibe ⇒ „Master-Kurzprüfung“.
* **Ausführer:** Werkzeug + Profilmodell oder „Standard“; `workflow` ⇒ „Workflow → <Worker der Lage>“.
"""
from __future__ import annotations

import re

from . import anzeige, arbeitsweise, modi, pruefer_wahl, rollen

FAMILIEN = {"claude": "Claude", "codex": "Codex", "hermes": "Hermes", "agy": "Antigravity"}
APP_STANDARD = "App-Standard"                                  # pruefkreis ruft Codex ohne `-m`
HERMES_ANZEIGE = anzeige.HERMES_MODELL_ANZEIGE                 # „DeepSeek V4.1 Flash“ (fest freigegeben)
VIBE_PRUEFER_TEXT = "Master-Kurzprüfung (Vibe, keine Codex-/Hermes-Gegenprüfung)"
BESITZ_UNKLAR = "? (Besitz unklar – pruefkreis bricht ohne --master ab)"
FAMILIEN_HINWEIS = "gleiche Familie wie Master"
STANDARD = "Standard"
BESITZ_NAMEN = {**FAMILIEN, "reserviert": "reserviert (Zwischenmarke)"}
_FAMILIE_NACH_ANFANG = (
    ("Claude", "claude"),
    ("GPT", "codex"),
    ("DeepSeek", "hermes"),
    ("Antigravity", "agy"),
    ("Gemini", "agy"),
)


def ohne_klammern(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", text).strip()


def _familie_modell(text: str) -> tuple[str | None, str]:
    """Werkzeug und Modell aus einer Matrixzelle: „Claude Opus 5.5 (Claude Pro)“ ⇒ („claude“, „Opus 5.5“)."""
    kern = ohne_klammern(text)
    for anfang, familie in _FAMILIE_NACH_ANFANG:
        if kern.startswith(anfang):
            return familie, kern[len(anfang):].strip() if familie == "claude" else kern
    return None, kern


def _besitz_name(besitzer: str) -> str:
    return BESITZ_NAMEN.get(besitzer, besitzer)


def master_text(profil: modi.Profil, lage: str | None, besitzer: str | None) -> str:
    """Master mit Modell; ein abweichender (oder unbekannter) Besitz steht dahinter."""
    besetzung = rollen.besetzung(lage)
    thinker_familie, thinker_modell = (None, "") if besetzung is None else _familie_modell(besetzung.thinker)
    if profil.master == modi.KONTINGENT:
        if besetzung is None:
            familie, basis = None, "nach Kontingent · Lage ?"
        elif thinker_familie is None:
            familie, basis = None, f"{thinker_modell} (nach Kontingent)"
        else:
            familie = thinker_familie
            basis = f"{FAMILIEN[familie]} · {thinker_modell} (nach Kontingent)"
    else:
        familie = profil.master if profil.master in FAMILIEN else None
        if familie is None:
            basis = "?"
        elif familie == "hermes":
            basis = f"Hermes · {HERMES_ANZEIGE}"
        elif thinker_familie == familie:
            basis = f"{FAMILIEN[familie]} · {thinker_modell} (fest)"
        else:
            basis = f"{FAMILIEN[familie]} (fest)"
    if besitzer is None:
        return f"{basis} · Besitz unbekannt"
    if familie is None or besitzer != familie:
        return f"{basis} · Besitz {_besitz_name(besitzer)}"
    return basis


def _regel_pruefer(pk_master: str) -> str:
    return "hermes" if pk_master == "codex" else "codex"


def _pruefer_name(wer: str) -> str:
    return f"Codex · {APP_STANDARD}" if wer == "codex" else f"Hermes · {HERMES_ANZEIGE}"


def pruefer_werkzeug(pk_master: str | None, wahl: str, weise: str) -> str | None:
    """Wer `pruefkreis` heute starten würde: `codex` | `hermes`; `None` bei Vibe, unklarem Besitz oder ungültiger Wahl-Datei."""
    if weise == arbeitsweise.VIBE or pk_master is None or wahl == pruefer_wahl.UNBEKANNT:
        return None
    return wahl if wahl in pruefer_wahl.GESPEICHERT else _regel_pruefer(pk_master)


def gleiche_familie(pk_master: str | None, wahl: str, weise: str) -> bool:
    """Prüfer aus derselben Familie wie der Master (nur durch eine ausdrückliche Wahl möglich)."""
    wer = pruefer_werkzeug(pk_master, wahl, weise)
    return wer is not None and wer == pk_master


def pruefer_text(pk_master: str | None, wahl: str, weise: str) -> str:
    """Prüfer wie `pruefkreis` ihn ermittelt (Besitz zuerst, dann Wahl, sonst Regel)."""
    if weise == arbeitsweise.VIBE:
        return VIBE_PRUEFER_TEXT
    if pk_master is None:
        return BESITZ_UNKLAR
    if wahl == pruefer_wahl.UNBEKANNT:
        return (f"? (pruefer.json ungültig – pruefkreis nutzt die Regel: "
                f"{_pruefer_name(_regel_pruefer(pk_master))})")
    if wahl in pruefer_wahl.GESPEICHERT:
        text = f"{_pruefer_name(wahl)} (gewählt)"
        return f"{text} – {FAMILIEN_HINWEIS}" if wahl == pk_master else text
    return _pruefer_name(_regel_pruefer(pk_master))


def ausfuehrer_text(profil: modi.Profil, lage: str | None, weise: str) -> str:
    if profil.worker == modi.WORKFLOW:
        besetzung = rollen.besetzung(lage)
        return "Workflow → " + (ohne_klammern(besetzung.worker) if besetzung is not None else "Lage ?")
    if profil.worker not in FAMILIEN:
        return "?"
    if profil.worker == "hermes":
        modell = HERMES_ANZEIGE if profil.modell in (None, modi.HERMES_MODELL) else profil.modell
    elif profil.modell:
        modell = profil.modell
    elif profil.worker == "claude" and weise == arbeitsweise.VIBE:
        modell = f"{STANDARD} (Vibe: Sonnet oder Haiku)"
    else:
        modell = STANDARD
    return f"{FAMILIEN[profil.worker]} · {modell}"


def aufloesen(profil: modi.Profil, lage: str | None, besitzer: str | None, pruefer_wahl_wert: str,
              arbeitsweise_wert: str, pk_master: str | None = None) -> tuple[str, str, str]:
    """(Master, Prüfer, Ausführer) als Texte mit Modell.

    `besitzer` ist der Besitz wie die Anzeige ihn liest (fehlende Datei = claude); `pk_master` der Master, den
    `pruefkreis` liest (`kurz.pruefkreis_master`, `None` = pruefkreis bricht ab). `pruefer_wahl_wert` ist
    `automatisch|codex|hermes|?`, `arbeitsweise_wert` `protokoll|vibe|?`.
    """
    return (master_text(profil, lage, besitzer),
            pruefer_text(pk_master, pruefer_wahl_wert, arbeitsweise_wert),
            ausfuehrer_text(profil, lage, arbeitsweise_wert))
