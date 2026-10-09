"""Waechter: das ECHTE Widget-Skript termux/agent-start und die Hey-Agent-App.

Am Handy gemessen (30.09.2026, Screenshot der Widget-Sitzung): Das Widget "agent"
startet termux/agent-start (bindet termux/gemeinsam.sh ein) - NICHT start-termux.sh.
Die Aenderungen vom 29.09. abends lagen deshalb im falschen Skript, und der
Starteintrag riet den Projektordner falsch (Verknuepfung zeigt auf termux/agent-start,
dirname ist also termux/, nicht der Projektordner).
Offline, liest nur die Skripttexte.
"""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TERMUX = REPO / "termux"


def _lies(name: str) -> str:
    return (TERMUX / name).read_text(encoding="utf-8")


def _funktion(text: str, name: str) -> str:
    start = text.index(f"{name}() {{")
    return text[start:text.index("\n}", start)]


def test_widget_oeffnet_hey_agent_nicht_den_browser():
    koerper = _funktion(_lies("gemeinsam.sh"), "oberflaeche_oeffnen")
    assert 'am start -a android.intent.action.VIEW -d "heyagent://start"' in koerper
    assert "termux-open-url" not in koerper, "kein Browser mehr"
    assert '-d "$URL"' not in koerper, "kein Browser-Rueckfall auf http://localhost"


def test_widget_richtet_app_start_selbst_ein():
    text = _lies("agent-start")
    assert 'hey-agent-einrichten.sh' in text, "Widget muss die Einrichtung aufrufen"
    pos_pull = text.index("git pull --ff-only")
    pos_einr = text.index("hey-agent-einrichten.sh\"")
    pos_server = text.index("python -m uvicorn app.main:app --host")
    assert pos_pull < pos_einr < pos_server, "Einrichtung nach dem Pull, vor dem Serverstart"


def test_einrichtung_schreibt_festen_pfad():
    """Kein Raten ueber ~/.shortcuts/agent: der Eintrag bekommt den vollen Pfad
    von agent-ensure.sh, den die Einrichtung aus ihrem eigenen Ort kennt."""
    text = _lies("hey-agent-einrichten.sh")
    assert 'ENSURE="$HIER/agent-ensure.sh"' in text
    assert "readlink" not in text.split("cat >")[1], "Hook darf den Pfad nicht raten"


def test_agent_ensure_findet_projekt_ueber_eigenen_ort():
    text = _lies("agent-ensure.sh")
    pos_eigen = text.index('PROJEKT="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"')
    pos_verweis = text.index('verweis="$HOME/.shortcuts/agent"')
    assert pos_eigen < pos_verweis, "erst der eigene Ort, die Verknuepfung nur als Rueckfall"
    assert '*/termux) PROJEKT="$(dirname "$PROJEKT")"' in text, (
        "Verknuepfung auf termux/agent-start: Elternordner nehmen"
    )


# ── Abgeloeste Widget-Sitzung schliesst sich selbst (10.10.2026) ──────────────
#
# Am Handy: Jeder neue Widget-Tipp liess die vorige Sitzung durchgestrichen mit
# "Process completed (code 137) - press Enter" stehen. Termux schliesst Sitzungen
# nur bei Code 0 oder 130 selbst (TermuxTerminalSessionActivityClient). Der Schluss
# von agent-start laeuft hier ECHT in bash mit einem Platzhalter-Server.

import shutil
import subprocess

import pytest


def _schluss_ausfuehren(signal_oder_code: str) -> int:
    bash = shutil.which("bash")
    if not bash or "system32" in bash.lower():
        pytest.skip("Git Bash nicht vorhanden")
    text = _lies("agent-start")
    schluss = text[text.rindex('wait "$server"'):]
    if signal_oder_code == "kill9":
        vorlauf = 'sleep 30 & server=$!\nkill -9 "$server"\n'
    else:
        vorlauf = f'(exit {signal_oder_code}) & server=$!\n'
    return subprocess.run([bash, "-c", vorlauf + schluss], capture_output=True,
                          timeout=20).returncode


def test_von_neuerem_start_abgeloest_endet_mit_0_damit_termux_schliesst():
    assert _schluss_ausfuehren("kill9") == 0


def test_echter_absturz_bleibt_mit_seinem_code_stehen():
    assert _schluss_ausfuehren("3") == 3


def test_normales_ende_bleibt_0():
    assert _schluss_ausfuehren("0") == 0
