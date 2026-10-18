"""S7: Auch der Stream-Weg (`/api/chat/stream`) behauptet keinen Lauf mehr.

Der Stream-Weg ist eine ZWEITE, nicht in `chat_routing` ausgelagerte Kopie der
Weiche. Dort stand dieselbe unwahre Meldung wie im Nicht-Stream-Weg
(„🧩 Hermes-Aufgabe erkannt – wird übernommen." / „Hermes nimmt sich der Aufgabe
an"), obwohl weder PC-Hermes noch lokaler Hermes liefen. Dieser Test fährt den
echten Endpunkt, sammelt die Server-Sent-Events und prüft, dass die Meldung
ehrlich ist, den Grund nennt und eine ehrliche Statuszeile geschrieben wird.

Gepatcht wird über die Globals der ECHTEN Endpunktfunktion (`__globals__`) — so
trifft der Patch dasselbe Modulobjekt, auch wenn ein anderer Test
`app.router.chat` zwischendurch aus `sys.modules` geworfen und neu geladen hat.
"""
import asyncio
import os
import sys
from unittest import mock

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.models import ChatRequest  # noqa: E402
from app.router.chat import chat_stream  # noqa: E402
from app.services import chat_routing  # noqa: E402
from app.services.hermes_gateway import hermes_gateway as hg_instanz  # noqa: E402


def _stream_text(req) -> str:
    """Fährt den Endpunkt und sammelt alle SSE-Stücke zu Text."""
    antwort = asyncio.run(chat_stream(req))

    async def _sammeln():
        teile = []
        async for stueck in antwort.body_iterator:
            teile.append(stueck if isinstance(stueck, str) else stueck.decode("utf-8"))
        return "".join(teile)

    return asyncio.run(_sammeln())


def test_stream_weg_meldet_ehrlich_wenn_kein_hermes_laeuft():
    statuszeilen = []
    gebucht = {}

    def _anlegen(auftrag, hinweis=None, kategorie=None, komplexitaet=None):
        gebucht["auftrag"] = auftrag
        return {"id": "s7-stream-1"}

    class _FakeBuch:
        @staticmethod
        def anlegen(*a, **k):
            return _anlegen(*a, **k)

        @staticmethod
        def setze_chat_verknuepfung(*a, **k):
            return None

    ersatz = {
        "hermes_gateway": mock.Mock(sende_auftrag=lambda _a: None,
                                    letzter_fehler="Verbindung abgelehnt"),
        "hermes_local_ist_verfuegbar": lambda: False,
        "auftrag_service": _FakeBuch(),
        "verlauf_nachricht_anhaengen": lambda *a, **k: None,
        "_finish_exchange": lambda *a, **k: None,
        "_get_or_create_conversation": lambda _c: "conv-s7-stream",
    }
    with mock.patch.dict(chat_stream.__globals__, ersatz), \
         mock.patch.object(chat_routing, "statusmeldung_bereit",
                           side_effect=lambda i, g: statuszeilen.append((i, g))):
        req = ChatRequest(message="Baue einen /health-Endpoint in der FastAPI-App",
                          conversation_id="conv_code",
                          model="deepseek/deepseek-v4-flash", web_search="off")
        text = _stream_text(req)

    assert "niemand daran" in text            # ehrlicher Zustand
    assert "Grund:" in text                   # warum
    assert "benachrichtigt" not in text       # alte Behauptung
    assert "wird übernommen" not in text
    # Die Aufgabe wird weiterhin vorgemerkt und die Statuszeile ist ehrlich.
    assert gebucht.get("auftrag")
    assert statuszeilen and statuszeilen[0][0] == "s7-stream-1"
    assert "lokale Hermes" in statuszeilen[0][1]


def test_beide_wege_benutzen_dieselbe_meldung():
    """Quelltext-Wächter: es gibt keine zweite Kopie der Wartemeldung mehr.

    Geprüft werden die ehemaligen CODE-Zeichenketten (mit Gedankenstrich und
    Fettdruck bzw. dem Folgesatz). Die bloße Wortfolge steht weiterhin in
    Kommentaren, die den Befund erklären — Kommentare sind kein Verhalten.
    """
    pfad = os.path.join(BACKEND, "app", "router", "chat.py")
    quelle = open(pfad, "r", encoding="utf-8").read()
    assert "– wird übernommen.**" not in quelle
    assert "Hermes nimmt sich der Aufgabe an. Sobald" not in quelle
    assert "bereit_reply_text" in quelle
