"""Waechter: welche App start-termux.sh nach dem Serverstart oeffnet.

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


def test_heyagent_wird_gesucht_und_gestartet():
    block = _oeffnen_block()
    assert f'HEYAGENT_PKG="{HEYAGENT}"' in block, "start-termux.sh kennt die Hey-Agent-App nicht"
    assert 'am start -n "$HEYAGENT_PKG/.MainActivity"' in block, (
        "Startbefehl fuer die Hey-Agent-Activity fehlt"
    )


def test_heyagent_kommt_vor_webapk_und_browser():
    block = _oeffnen_block()
    pos_hey = block.index(HEYAGENT)
    pos_webapk = block.index("org.chromium.webapk")
    pos_browser = block.index("android.intent.action.VIEW")
    assert pos_hey < pos_webapk < pos_browser, (
        "Reihenfolge muss sein: Hey Agent -> Web-App -> Browser"
    )


def test_webapk_und_browser_bleiben_als_rueckfall():
    block = _oeffnen_block()
    assert "H2OOpaqueMainActivity" in block, "Rueckfall Web-App fehlt"
    assert 'http://localhost:$PORT' in block, "Rueckfall Browser fehlt"
