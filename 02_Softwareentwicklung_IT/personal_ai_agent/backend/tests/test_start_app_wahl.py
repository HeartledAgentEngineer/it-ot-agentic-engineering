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


def test_heyagent_kommt_vor_webapk_und_browser():
    block = _oeffnen_block()
    pos_hey = block.index(ADRESSE)
    pos_webapk = block.index("org.chromium.webapk")
    pos_browser = block.index('-d "http://localhost:$PORT"')
    assert pos_hey < pos_webapk < pos_browser, (
        "Reihenfolge muss sein: Hey Agent -> Web-App -> Browser"
    )


def test_webapk_und_browser_bleiben_als_rueckfall():
    block = _oeffnen_block()
    assert "H2OOpaqueMainActivity" in block, "Rueckfall Web-App fehlt"
    assert 'http://localhost:$PORT' in block, "Rueckfall Browser fehlt"
