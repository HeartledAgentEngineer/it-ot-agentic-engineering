"""Tests: pCloud-Schluessel-Uebernahme in ALLEN Startwegen (Issue #3 Befund 1, 02.10.2026).

Befund: Die Uebernahme stand nur in start-termux.sh. Das Widget "agent" startet
termux/agent-start, die App termux/agent-ensure.sh — beide kamen nie daran
vorbei; der Schluessel lag seit 27.09. unbenutzt im Download-Ordner, die
Gesichter-Kacheln im Quiz blieben leer. Jetzt ein Skript
(termux/pcloud-schluessel-uebernehmen.sh), alle drei Startwege rufen es auf.

Funktionstests laufen das echte Skript mit bash gegen Dateien in tmp_path
(erfundene Werte, nie ein echter Schluessel).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PROJEKT = Path(__file__).resolve().parents[2]
SKRIPT = PROJEKT / "termux" / "pcloud-schluessel-uebernehmen.sh"
STARTWEGE = {
    "start-termux.sh": PROJEKT / "start-termux.sh",
    "agent-start": PROJEKT / "termux" / "agent-start",
    "agent-ensure.sh": PROJEKT / "termux" / "agent-ensure.sh",
}
WERT = "erfundenerTestwert/mit+Sonder=zeichen&und|strich"


def _lauf(env: Path, quelle: Path):
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash nicht vorhanden")
    return subprocess.run([bash, str(SKRIPT).replace("\\", "/"),
                           str(env).replace("\\", "/"), str(quelle).replace("\\", "/")],
                          capture_output=True, text=True, encoding="utf-8")


# ── Alle Startwege rufen das eine Skript auf ────────────────────────────────

@pytest.mark.parametrize("name", sorted(STARTWEGE))
def test_jeder_startweg_ruft_die_uebernahme_auf(name):
    text = STARTWEGE[name].read_text(encoding="utf-8")
    zeilen = [z for z in text.splitlines()
              if "pcloud-schluessel-uebernehmen.sh" in z and not z.lstrip().startswith("#")]
    assert len(zeilen) == 1, f"{name}: genau ein Aufruf erwartet"
    assert zeilen[0].rstrip().endswith("|| true"), f"{name}: darf den Start nie verhindern"
    aufruf = text.index(zeilen[0])
    assert aufruf < text.index("python -m uvicorn app.main:app"), f"{name}: Uebernahme vor dem Serverstart"
    assert text.index("pull --ff-only") < aufruf, f"{name}: erst den neuesten Stand holen"


def test_der_alte_block_steht_nirgends_mehr_doppelt():
    for name, pfad in STARTWEGE.items():
        assert "done < \"$QUELLE_TOKEN\"" not in pfad.read_text(encoding="utf-8"), \
            f"{name}: Uebernahme-Logik gehoert nur ins gemeinsame Skript"


def test_skript_gibt_keine_werte_aus():
    text = SKRIPT.read_text(encoding="utf-8")
    for zeile in text.splitlines():
        if "echo" in zeile:
            assert "$wert" not in zeile and "$ersatz" not in zeile


# ── Funktion (echtes Skript, erfundene Werte) ───────────────────────────────

def test_uebernahme_haengt_an_ersetzt_und_loescht_die_uebergabe(tmp_path):
    env = tmp_path / ".env"
    env.write_text("OPENROUTER_API_KEY=bleibt\nPCLOUD_HOST=alt.example\n", encoding="utf-8")
    quelle = tmp_path / "pcloud_token.txt"
    quelle.write_bytes(f'PCLOUD_TOKEN="{WERT}"\r\nPCLOUD_HOST=eapi.example\r\nANDERES=nein\r\n'.encode())
    lauf = _lauf(env, quelle)
    assert lauf.returncode == 0
    inhalt = env.read_text(encoding="utf-8").splitlines()
    assert "OPENROUTER_API_KEY=bleibt" in inhalt
    assert "PCLOUD_HOST=eapi.example" in inhalt and "PCLOUD_HOST=alt.example" not in inhalt
    assert f"PCLOUD_TOKEN={WERT}" in inhalt
    assert not any(z.startswith("ANDERES") for z in inhalt)
    assert not quelle.exists(), "Geheimnis darf nicht im Download-Ordner liegen bleiben"
    assert (tmp_path / ".env.vorher").read_text(encoding="utf-8").startswith("OPENROUTER_API_KEY=bleibt")
    assert WERT not in lauf.stdout and "eapi.example" not in lauf.stdout


def test_ersetzt_vorhandenen_schluessel_mit_sonderzeichen(tmp_path):
    env = tmp_path / ".env"
    env.write_text("PCLOUD_TOKEN=alt\n", encoding="utf-8")
    quelle = tmp_path / "pcloud_token.txt"
    quelle.write_text(f"PCLOUD_TOKEN={WERT}\n", encoding="utf-8")
    assert _lauf(env, quelle).returncode == 0
    assert env.read_text(encoding="utf-8").splitlines() == [f"PCLOUD_TOKEN={WERT}"]


def test_ohne_uebergabedatei_passiert_nichts(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A=1\n", encoding="utf-8")
    lauf = _lauf(env, tmp_path / "gibtsnicht.txt")
    assert lauf.returncode == 0 and lauf.stdout == ""
    assert env.read_text(encoding="utf-8") == "A=1\n"
    assert not (tmp_path / ".env.vorher").exists()


def test_ohne_token_zeile_bleibt_die_datei_liegen(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A=1\n", encoding="utf-8")
    quelle = tmp_path / "pcloud_token.txt"
    quelle.write_text("PCLOUD_TOKEN=\nIRGENDWAS=x\n", encoding="utf-8")
    lauf = _lauf(env, quelle)
    assert lauf.returncode == 0 and "fehlgeschlagen" in lauf.stdout
    assert quelle.exists(), "ohne gueltigen Schluessel nichts loeschen"
    assert "PCLOUD_TOKEN" not in env.read_text(encoding="utf-8")
