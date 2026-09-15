"""Tests: Daemon trennt ANTWORT von internem Denken (`_CliAusgabe`).

Regression (Sebastian 2026-09-15: „alles wieder in einer Blase … warum sehe ich
das jetzt wieder so kryptisch?"): `hermes_inbox_daemon.py` behandelte JEDE
Ausgabezeile von `hermes chat -q` als Antwort. Die CLI rahmt aber jeden
Abschnitt in einen Kasten:

    ┌─ Reasoning ─…┐  …englisches Modell-Reasoning, mitten im Wort umgebrochen…
    └──────────────┘
    ╭─⚕ Hermes …────╮  …die eigentliche Antwort (Markdown, Code-Blöcke)…
    ╰──────────────╯

Dadurch standen die Reasoning-Fragmente als 💬-Blasen im Chat und am Ende ALLES
zusammen in EINER riesigen Antwort-Blase. Diese Tests halten fest: nur der
Antwort-Kasten wird Antwort, der Gedanken-Kasten höchstens zu EINEM kurzen
Hinweis, Werkzeug-/Abschlusszeilen fallen weg.
"""
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

import hermes_inbox_daemon as d  # noqa: E402


# Der Rahmen, wie ihn die CLI schreibt (Kastenbreite gekürzt).
DENKEN_AUF = "┌─ Reasoning ─────────────────────────────┐"
DENKEN_ZU = "└─────────────────────────────────────────┘"
ANTWORT_AUF = "╭─⚕ Hermes ───────────────────────────────╮"
ANTWORT_ZU = "╰─────────────────────────────────────────╯"


def _lauf(zeilen):
    """Zeilen durch den Filter schicken → (antwort, gedanken, gemeldet)."""
    f = d._CliAusgabe()
    antwort, gedanken = [], []
    for z in zeilen:
        art, text = f.zeile(z)
        if art == "antwort":
            antwort.append(text)
        elif art == "gedanke":
            gedanken.append(text)
    return antwort, gedanken


def test_reasoning_landet_nicht_in_der_antwort():
    antwort, gedanken = _lauf([
        ANTWORT_AUF,          # Antwort-Kasten VOR dem Denken (wie real: Text, dann Reasoning)
        "Schon gut, ich sehe es.",
        ANTWORT_ZU,
        DENKEN_AUF,
        "Let me look at the image first.",
        "Also, should I check whether the same flat-list flaw exists in the conv_code",
        "es live rendering path?",
        DENKEN_ZU,
        ANTWORT_AUF,
        "Erledigt und belegt (Commit 24a71c3, lokal).",
        ANTWORT_ZU,
    ])
    gesamt = "\n".join(antwort)
    assert "Let me look at the image" not in gesamt
    assert "flat-list flaw" not in gesamt
    assert "Erledigt und belegt" in gesamt
    assert "Schon gut, ich sehe es." in gesamt
    # Der Gedanke wird genau EINMAL und nur als kurzer Hinweis gemeldet.
    assert len(gedanken) == 1
    assert gedanken[0].startswith("🧠 Hermes denkt nach")


def test_code_block_bleibt_erhalten():
    antwort, _ = _lauf([
        ANTWORT_AUF,
        "```diff",
        "- alt",
        "+ neu",
        "```",
        ANTWORT_ZU,
    ])
    assert antwort == ["```diff", "- alt", "+ neu", "```"]


def test_rahmen_und_werkzeugzeilen_fallen_weg():
    antwort, gedanken = _lauf([
        ANTWORT_AUF,
        "  ┊ ░ preparing read_file…",
        "Antwortzeile",
        ANTWORT_ZU,
        "Resume this session with:",
        "session_id: abc",
    ])
    assert antwort == ["Antwortzeile"]
    assert gedanken == []


def test_ohne_kaesten_bleibt_alles_antwort():
    """Andere CLI-Fassung ohne Rahmen: nichts geht verloren (Rückfall)."""
    antwort, _ = _lauf(["Zeile eins", "Zeile zwei"])
    assert antwort == ["Zeile eins", "Zeile zwei"]


def test_gedanke_gemeldet_wird_nach_antwort_kasten_wieder_frei():
    """Nach einer Antwort darf das nächste Reasoning wieder gemeldet werden."""
    f = d._CliAusgabe()
    abfolge = [DENKEN_AUF, "denken 1", DENKEN_ZU,
               ANTWORT_AUF, "Antwort 1", ANTWORT_ZU,
               DENKEN_AUF, "denken 2", DENKEN_ZU]
    gemeldet = [t for art, t in (f.zeile(z) for z in abfolge) if art == "gedanke"]
    assert len(gemeldet) == 2


def test_formularzeilen_halten_den_puffer():
    """Frage + '❯ 1. …'-Optionen bleiben EINE Meldung (klickbare Abfrage)."""
    puffer = [("💬", "Welchen Weg?"), ("💬", "❯ 1. Token")]
    assert d._formular_haelt_puffer(puffer) is True
    # Umbruch einer Optionszeile hält ebenfalls …
    assert d._formular_haelt_puffer(
        [("💬", "❯ 2. Sehr langer Optionstext ohne Satzende der erst"), ]
    ) is True
    # … ein normaler langer Absatz aber NICHT (Flush bleibt zügig).
    assert d._formular_haelt_puffer(
        [("💬", "Ein ganz normaler, langer Absatz ohne Punkt am Ende der genau so"),
         ("💬", "geht es weiter und weiter und weiter und weiter und weiter und weiter"),
         ]
    ) is False
