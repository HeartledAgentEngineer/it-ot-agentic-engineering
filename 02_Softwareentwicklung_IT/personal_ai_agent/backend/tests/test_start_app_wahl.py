"""Waechter: welche App start-termux.sh nach dem Serverstart oeffnet.

Weg zur App: eigene Adresse heyagent://start (siehe Test unten).

Seit es die native Android-App "Hey Agent" (de.sebastian.heyagent) gibt, soll
der Widget-Tipp DIESE App nach vorne holen - nicht mehr die alte Chrome-Web-App
(org.chromium.webapk...). Reihenfolge: Hey Agent -> Web-App -> Browser.
Offline, liest nur den Skripttext.
"""
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STARTTERMUX = REPO / "start-termux.sh"
HEYAGENT = "de.sebastian.heyagent"


def _oeffnen_block() -> str:
    text = STARTTERMUX.read_text(encoding="utf-8")
    start = text.index("# ── App statt Browser öffnen")
    return text[start:]


MANIFEST = REPO / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
ADRESSE = "heyagent://start"


def test_heyagent_wird_ueber_eigene_adresse_gestartet():
    """Termux (targetSdk 37) sieht fremde Pakete nicht: `pm list packages` und
    `am start -n` finden Hey Agent dort nicht. Eine eigene Adresse loest Android
    dagegen immer auf - wie http:// beim Browser."""
    block = _oeffnen_block()
    assert f'am start -a android.intent.action.VIEW -d "{ADRESSE}"' in block, (
        "Startbefehl ueber heyagent://start fehlt"
    )
    assert "pm list packages" not in block.split(ADRESSE)[0], (
        "vor dem App-Start darf keine Paketliste stehen - Termux sieht die App darin nicht"
    )


def test_app_nimmt_die_eigene_adresse_an():
    manifest = MANIFEST.read_text(encoding="utf-8")
    assert 'android:scheme="heyagent"' in manifest, "Manifest: Adresse heyagent:// fehlt"
    assert 'android:launchMode="singleTask"' in manifest, (
        "ohne singleTask oeffnet jeder Widget-Tipp eine zweite App-Instanz"
    )


def test_widget_oeffnet_keinen_browser_mehr():
    """Sebastians Wunsch 29.09.2026: das Widget oeffnet nur noch Hey Agent."""
    block = _oeffnen_block()
    assert 'http://localhost:$PORT"' not in block.split("wait $SERVER_PID")[0].split(ADRESSE)[1], (
        "nach dem Hey-Agent-Start darf kein Browser-Rueckfall mehr kommen"
    )
    assert "org.chromium.webapk" not in block, "Web-App-Rueckfall ist entfernt"


def test_fehler_von_android_wird_angezeigt():
    block = _oeffnen_block()
    assert 'AM_AUSGABE="$(am start' in block and "$AM_AUSGABE" in block, (
        "scheitert der App-Start, muss die Meldung von Android sichtbar sein"
    )


STARTTEXT = STARTTERMUX.read_text(encoding="utf-8")


def test_widget_richtet_app_start_selbst_ein():
    """Keine Eingabe in Termux: jeder Widget-Tipp legt den profile.d-Eintrag an."""
    assert 'sh "$PROJEKT/termux/hey-agent-einrichten.sh"' in STARTTEXT
    pos_sync = STARTTEXT.index("── Aktualisieren")
    pos_einr = STARTTEXT.index("hey-agent-einrichten.sh\" 2>&1")
    assert pos_sync < pos_einr, "Einrichtung erst nach dem Git-Abgleich (neueste Fassung)"


def test_widget_zeigt_stand_und_pull_fehler():
    assert 'echo "Stand jetzt: $(git log --oneline -1' in STARTTEXT
    assert "Pull fehlgeschlagen" in STARTTEXT, "ein gescheiterter Pull darf nicht still bleiben"
