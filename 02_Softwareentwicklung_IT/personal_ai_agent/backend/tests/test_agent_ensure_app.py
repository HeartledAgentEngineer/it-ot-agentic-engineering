"""Waechter: agent-ensure.sh als Startweg der Hey-Agent-App (Play-Store-Termux).

Die App kann das Play-Store-Termux nicht fernsteuern (kein RUN_COMMAND). Sie oeffnet
Termux sichtbar; der Eintrag in ~/.bashrc ruft dann `agent-ensure.sh --app-zurueck`.
Das Skript zieht den neuesten Stand (nur Vorspulen), startet das Backend, wartet auf
/health und holt die App ueber heyagent://start zurueck.
Offline, liest nur den Skripttext.
"""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKRIPT = REPO / "termux" / "agent-ensure.sh"
ANDROID = REPO / "android" / "app" / "src" / "main" / "java" / "de" / "sebastian" / "heyagent"


def _text() -> str:
    return SKRIPT.read_text(encoding="utf-8")


def test_schalter_app_zurueck_und_ruecksprung():
    text = _text()
    assert "--app-zurueck" in text, "Schalter --app-zurueck fehlt"
    assert 'am start -a android.intent.action.VIEW -d "heyagent://start"' in text, (
        "Ruecksprung zur App ueber heyagent://start fehlt"
    )


def test_laufendes_backend_bleibt_unberuehrt():
    """Laeuft das Backend, endet das Skript sofort - vor Pull und Start, und ohne
    Ruecksprung (sonst springt jedes manuelle Termux-Oeffnen in die App)."""
    text = _text()
    pos_ok = text.index("if health_ok; then")
    assert pos_ok < text.index("git -C") < text.index("nohup python -m uvicorn"), (
        "Reihenfolge muss sein: Health-Check -> Pull -> Start"
    )


def test_pull_nur_vorspulen_nie_ueberschreiben():
    text = _text()
    assert "pull --ff-only" in text, "Pull muss --ff-only sein"
    assert "merge-base --is-ancestor HEAD origin/main" in text, (
        "Pull nur, wenn das Handy wirklich hinter origin liegt"
    )
    for verboten in ("reset --hard", "push", "--force", "rm -rf", "clean -f"):
        assert verboten not in text, f"verbotener Befehl im Startskript: {verboten}"


def test_wartet_auf_health_vor_ruecksprung():
    text = _text()
    pos_start = text.index("nohup python -m uvicorn")
    pos_warten = text.index("WARTEN_S")
    pos_zurueck = text.index('-d "heyagent://start"')
    assert pos_start < pos_zurueck and pos_warten < pos_zurueck, (
        "erst Backend starten und auf /health warten, dann zur App zurueck"
    )


def test_app_oeffnet_termux_als_rueckfall():
    launcher = (ANDROID / "TermuxLauncher.kt").read_text(encoding="utf-8")
    assert "perRunCommand() || termuxOeffnen()" in launcher, (
        "ohne RUN_COMMAND muss die App Termux sichtbar oeffnen"
    )
    assert "komponente != null" in launcher, (
        "startForegroundService liefert null, wenn der Termux-Dienst fehlt - das muss zaehlen"
    )


EINRICHTEN = REPO / "termux" / "hey-agent-einrichten.sh"


def test_einrichtung_nutzt_profile_d_statt_bashrc():
    """Termux startet Sitzungen als Login-Shell (`bash -l`, am Handy gemessen) - die
    liest ~/.bashrc nicht. $PREFIX/etc/profile.d/*.sh liest jede Login-Shell."""
    text = EINRICHTEN.read_text(encoding="utf-8")
    assert "$PREFIX/etc/profile.d/hey-agent.sh" in text, "Hook muss nach profile.d"
    assert "--app-zurueck" in text, "Hook muss agent-ensure.sh --app-zurueck rufen"
    assert ".bashrc" not in text.split("# ---")[-1], "kein Schreiben in ~/.bashrc"
    for verboten in ("rm ", "reset --hard", "push", "--force"):
        assert verboten not in text, f"verbotener Befehl in der Einrichtung: {verboten}"


def test_einrichtung_ist_wiederholbar():
    """Mehrfach ausfuehren darf nichts doppeln: die Hook-Datei wird ganz neu
    geschrieben (>), nie angehaengt (>>)."""
    text = EINRICHTEN.read_text(encoding="utf-8")
    assert '> "$HOOK"' in text and '>> "$HOOK"' not in text
