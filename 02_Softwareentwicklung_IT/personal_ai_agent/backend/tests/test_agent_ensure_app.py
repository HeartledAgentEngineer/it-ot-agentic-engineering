"""Waechter: agent-ensure.sh als Startweg der Hey-Agent-App.

Der App-Weg ruft die GEMEINSAME Start-Vorbereitung (termux/start-vorbereiten.sh:
git pull + Uebernahmen inkl. Wissensdatei memory.db) - auch wenn das Backend schon
laeuft - und startet uvicorn nur, wenn /health nicht antwortet. Die App oeffnet bei
Bedarf Termux sichtbar; der Eintrag in $PREFIX/etc/profile.d ruft dann
`agent-ensure.sh --app-zurueck`, das wartet auf /health und holt die App ueber
heyagent://start zurueck.
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


def test_laufendes_backend_wird_vorbereitet_aber_nicht_neu_gestartet():
    """10.10.2026: Der App-Weg bereitet AUCH vor, wenn das Backend schon laeuft
    (git pull + Wissensdatei-Uebernahme ueber die gemeinsame Vorbereitung - bei
    dauerhaft laufendem Server liefen sie sonst nie). Neu gestartet wird nichts:
    kein Kill, kein Ruecksprung; nur der Serverstart entfaellt."""
    text = _text()
    pos_check = text.index("if health_ok; then")
    pos_prep = text.index('bash "$PROJEKT/termux/start-vorbereiten.sh"')
    pos_skip = text.index("Serverstart uebersprungen")
    pos_start = text.index("nohup python -m uvicorn")
    assert pos_check < pos_prep < pos_skip < pos_start, (
        "Reihenfolge: Health-Check -> Vorbereitung -> (bei laufendem Backend Ende) -> Start"
    )
    assert '"--laufend"' in text and "_VORBEREITUNG_MODUS" in text
    assert text.rindex("heyagent://start") > pos_start, (
        "kein Ruecksprung zur App, wenn nichts gestartet wurde"
    )
    for verboten in ("pkill", "kill -9"):
        assert verboten not in text, f"der App-Weg beendet nichts: {verboten}"


def test_pull_nur_vorspulen_nie_ueberschreiben():
    """Die Pull-Regel steht seit 10.10.2026 EINMAL in der gemeinsamen Vorbereitung
    (termux/start-vorbereiten.sh); App-Weg und Widget rufen nur noch sie auf."""
    vorbereitung = (REPO / "termux" / "start-vorbereiten.sh").read_text(encoding="utf-8")
    assert "pull --ff-only" in vorbereitung, "Pull muss --ff-only sein"
    assert "merge-base --is-ancestor HEAD origin/main" in vorbereitung, (
        "Pull nur, wenn das Handy wirklich hinter origin liegt"
    )
    for name in ("agent-ensure.sh", "agent-start"):
        text = (REPO / "termux" / name).read_text(encoding="utf-8")
        assert "start-vorbereiten.sh" in text, f"{name}: ruft die gemeinsame Vorbereitung"
        for verboten in ("reset --hard", "push", "--force", "clean -f"):
            assert verboten not in text, f"verbotener Befehl in {name}: {verboten}"
    for verboten in ("reset --hard", "push", "--force", "rm -rf", "clean -f"):
        assert verboten not in vorbereitung, f"verbotener Befehl in der Vorbereitung: {verboten}"


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
