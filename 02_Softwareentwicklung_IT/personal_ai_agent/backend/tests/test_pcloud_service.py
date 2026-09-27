"""Tests: pCloud-Anbindung (Service) — alles OHNE Netz.

httpx wird grundsaetzlich durch Attrappen ersetzt. Fuer Wege, auf denen
KEIN Aufruf passieren darf (fehlender Token, leerer Suchbegriff,
Groessen-Abbruch vor dem Download), steht die Stolperfalle `Stolperfalle`
im Weg: ein echter Aufruf wuerde den Test sofort auffliegen lassen.

Die Tests beruehren nie die echte pCloud — kein Verbrauch, kein Schreiben.
Der Test-Token ist erfunden; die echte Adresse kommt in dieser Datei nicht
vor (fuer den Maskentest dient eine erfundene Adresse).

Aufruf: cd backend && .venv/Scripts/python -m pytest tests/test_pcloud_service.py -q
"""

import base64
import json
import os
import sys

import httpx
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.config import settings  # noqa: E402
from app.services import pcloud_service as modul  # noqa: E402

TOKEN = "test-token-nicht-echt-39-zeichen-abcdefg"
HOST = "eapi.test.example"
EMAIL = "sebastian@example.com"          # erfundene Adresse fuer den Maskentest
MASK = "se" + "*" * (len(EMAIL) - 6) + ".com"

# Rohe JPEG-Bytes (Anfang wie ein echtes JPEG) und dieselben Bytes als
# base64 in der Textzeile, die pCloud live liefert (27.09.2026 geprueft):
#   fileid|ergebnis|masse|data:image/jpeg;base64,…
JPEG = b"\xff\xd8\xff\xe0" + b"x" * 20
THUMB_ZEILE = (
    f"42|0|86x120|data:image/jpeg;base64,{base64.b64encode(JPEG).decode()}"
).encode("utf-8")


# ── Attrappen (kein Netz) ──────────────────────────────────────────────────

class Antwort:
    """Attrappe einer httpx-Antwort (JSON oder Binaerdaten)."""

    def __init__(self, daten=None, *, content=b"", status_code=200,
                 content_type="application/json"):
        self._daten = daten
        self.content = content
        self.status_code = status_code
        self.headers = {"content-type": content_type} if content_type else {}

    def json(self):
        if self._daten is None:
            raise ValueError("keine JSON-Daten in dieser Attrappe")
        return self._daten


class FakeGet:
    """httpx.get-Attrappe: liefert Antworten der Reihe nach, merkt Aufrufe."""

    def __init__(self, *antworten):
        self._antworten = list(antworten)
        self.aufrufe = []

    def __call__(self, url, params=None, timeout=None):
        self.aufrufe.append(
            {"url": url, "params": dict(params or {}), "timeout": timeout}
        )
        if not self._antworten:
            raise AssertionError("Unerwarteter weiterer httpx.get-Aufruf")
        naechste = self._antworten.pop(0)
        if isinstance(naechste, Exception):
            raise naechste
        return naechste


class Stolperfalle:
    """Kein Aufruf erlaubt — jeder Versuch fliegt auf."""

    def __call__(self, *args, **kwargs):
        raise AssertionError(
            f"Unerlaubter Netz-Aufruf: args={args!r} kwargs={kwargs!r}"
        )


class FakeStrom:
    """httpx.stream-Attrappe (Kontextmanager) mit Datenstuecken."""

    def __init__(self, teile, *, status_code=200):
        self._teile = list(teile)
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_bytes(self):
        for teil in self._teile:
            yield teil


class FakeStreamAufruf:
    """httpx.stream-Attrappe: liefert Stroeme der Reihe nach, merkt Aufrufe."""

    def __init__(self, *stroeme):
        self._stroeme = list(stroeme)
        self.aufrufe = []

    def __call__(self, methode, url, timeout=None):
        self.aufrufe.append({"methode": methode, "url": url})
        if not self._stroeme:
            raise AssertionError("Unerwarteter weiterer httpx.stream-Aufruf")
        naechster = self._stroeme.pop(0)
        if isinstance(naechster, Exception):
            raise naechster
        return naechster


def mit_get(monkeypatch, *antworten) -> FakeGet:
    """httpx.get durch eine Attrappe ersetzen (nach dem Test automatisch zurueck)."""
    fake = FakeGet(*antworten)
    monkeypatch.setattr(modul.httpx, "get", fake)
    return fake


def mit_stream(monkeypatch, *stroeme) -> FakeStreamAufruf:
    """httpx.stream durch eine Attrappe ersetzen."""
    fake = FakeStreamAufruf(*stroeme)
    monkeypatch.setattr(modul.httpx, "stream", fake)
    return fake


# ── Fixtures und Bauhilfen ─────────────────────────────────────────────────

@pytest.fixture
def dienst() -> modul.PCloudService:
    """Dienst mit festem Test-Token — kein Einfluss aus .env/Umgebung."""
    return modul.PCloudService(token=TOKEN, host=HOST)


@pytest.fixture
def ohne_token(monkeypatch) -> modul.PCloudService:
    """Dienst ohne Token — weder in settings noch in der Umgebung."""
    monkeypatch.delenv("PCLOUD_TOKEN", raising=False)
    monkeypatch.setattr(settings, "pcloud_token", "")
    return modul.PCloudService()


def _userinfo(**felder):
    grundlage = {
        "result": 0,
        "email": EMAIL,
        "userid": 4738912,
        "premium": True,
        "emailverified": True,
        "quota": 2_199_023_255_552,
        "usedquota": 390_500_000_000,
    }
    grundlage.update(felder)
    return grundlage


def _liste(*eintraege):
    return {"result": 0, "metadata": {"contents": list(eintraege), "isfolder": True}}


def _ordner(name, folderid=1):
    return {"name": name, "isfolder": True, "folderid": folderid}


def _datei(name, fileid=1, size=100, modified="Fri, 26 Sep 2026 10:00:00 +0000"):
    return {
        "name": name,
        "isfolder": False,
        "fileid": fileid,
        "size": size,
        "modified": modified,
    }


# ── Konfiguration ──────────────────────────────────────────────────────────

def test_ist_konfiguriert_mit_und_ohne_token(dienst, ohne_token):
    assert dienst.ist_konfiguriert() is True
    assert ohne_token.ist_konfiguriert() is False


def test_token_und_host_aus_der_umgebung(monkeypatch):
    """Ohne settings-Werte zaehlen die Umgebungsvariablen; Host hat Standard."""
    monkeypatch.setattr(settings, "pcloud_token", "")
    monkeypatch.setattr(settings, "pcloud_host", "")
    monkeypatch.setenv("PCLOUD_TOKEN", TOKEN)
    monkeypatch.setenv("PCLOUD_HOST", "api.pcloud.com")
    dienst = modul.PCloudService()
    assert dienst.ist_konfiguriert() is True
    assert dienst.host == "api.pcloud.com"

    monkeypatch.delenv("PCLOUD_HOST")
    assert modul.PCloudService().host == modul.STANDARD_HOST == "eapi.pcloud.com"


def test_host_vertraegt_schema_und_schraegstrich(monkeypatch):
    """Ein versehentliches "https://…/" in der .env darf die URL nicht zerstoeren."""
    monkeypatch.setattr(settings, "pcloud_host", "https://eapi.pcloud.com/")
    assert modul.PCloudService().host == "eapi.pcloud.com"


def test_ohne_token_klarer_fehler_statt_netzaufruf(ohne_token, monkeypatch):
    """Fehlender Token: eigener Fehler mit Klartext, kein einziger HTTP-Aufruf."""
    monkeypatch.setattr(modul.httpx, "get", Stolperfalle())
    with pytest.raises(modul.PCloudNichtKonfiguriert) as fehler:
        ohne_token.status()
    text = str(fehler.value)
    assert "PCLOUD_TOKEN" in text
    assert "nicht konfiguriert" in text
    # Der Router unterscheidet 503 (nicht konfiguriert) von 502 (API-Fehler).
    assert isinstance(fehler.value, modul.PCloudFehler)


# ── Interner Aufruf-Helfer _api ────────────────────────────────────────────

def test_api_ergaenzt_auth_und_liefert_daten(dienst, monkeypatch):
    fake = mit_get(monkeypatch, Antwort(_userinfo()))
    daten = dienst._api("/userinfo")
    assert daten["result"] == 0
    assert len(fake.aufrufe) == 1
    aufruf = fake.aufrufe[0]
    assert aufruf["url"] == f"https://{HOST}/userinfo"
    assert aufruf["params"]["auth"] == TOKEN
    assert aufruf["timeout"] == dienst.timeout


def test_api_reicht_den_fehlertext_durch(dienst, monkeypatch):
    """result != 0: der Fehlertext der pCloud steht in der eigenen Ausnahme."""
    mit_get(monkeypatch, Antwort({"result": 2005, "error": "Directory does not exist."}))
    with pytest.raises(modul.PCloudFehler) as fehler:
        dienst._api("/listfolder", folderid=7)
    assert "Directory does not exist." in str(fehler.value)
    assert "2005" in str(fehler.value)


def test_api_http_fehlerstatus_wird_klarer_text(dienst, monkeypatch):
    mit_get(monkeypatch, Antwort(None, status_code=503, content_type="text/html"))
    with pytest.raises(modul.PCloudFehler) as fehler:
        dienst._api("/userinfo")
    assert "HTTP 503" in str(fehler.value)


def test_api_unlesbares_json_wird_klarer_text(dienst, monkeypatch):
    antwort = Antwort(None)
    antwort.content = b"<html>kaputt</html>"
    mit_get(monkeypatch, antwort)
    with pytest.raises(modul.PCloudFehler) as fehler:
        dienst._api("/userinfo")
    assert "keine lesbare JSON-Antwort" in str(fehler.value)


def test_netzfehler_nennt_die_klasse_aber_nie_den_token(dienst, monkeypatch):
    """Transportfehler: nur der Klassenname. Fremde Meldungen koennen die
    volle URL samt Token enthalten und werden bewusst verworfen."""
    mit_get(monkeypatch, httpx.ConnectError(f"kaputt bei auth={TOKEN}"))
    with pytest.raises(modul.PCloudFehler) as fehler:
        dienst.status()
    text = str(fehler.value)
    assert "ConnectError" in text
    assert TOKEN not in text


def test_token_taucht_in_keinem_log_auf(dienst, monkeypatch, caplog):
    mit_get(monkeypatch, httpx.ConnectError(f"kaputt bei auth={TOKEN}"))
    with caplog.at_level("DEBUG"):
        with pytest.raises(modul.PCloudFehler):
            dienst.status()
    assert TOKEN not in caplog.text


def test_geheimnis_filter_entfernt_den_token():
    """Letzte Verteidigungslinie: auch ein durchgereichter Fehlertext wird
    vom Token befreit, bevor er sichtbar wird."""
    assert modul._ohne_geheimnis(f"x auth={TOKEN} y", TOKEN) == "x auth=*** y"
    assert modul._ohne_geheimnis("ohne geheimnis", TOKEN) == "ohne geheimnis"


# ── status() ───────────────────────────────────────────────────────────────

def test_email_maske_verdeckt_kurze_werte_komplett():
    assert modul._maskiere_email("abc") == "***"
    assert modul._maskiere_email("a@b.c") == "*****"
    assert modul._maskiere_email("") == ""


def test_status_maskiert_die_email(dienst, monkeypatch):
    """Nur erste 2 und letzte 4 Zeichen bleiben — die echte Adresse nirgends."""
    mit_get(monkeypatch, Antwort(_userinfo()))
    ergebnis = dienst.status()
    assert ergebnis["email"] == MASK
    assert ergebnis["email"].startswith("se")
    assert ergebnis["email"].endswith(".com")
    # Die vollstaendige Adresse darf in KEINER Zeile der Antwort stehen.
    assert EMAIL not in json.dumps(ergebnis, ensure_ascii=False)


def test_status_rechnet_quota_und_belegung_in_gb(dienst, monkeypatch):
    mit_get(monkeypatch, Antwort(_userinfo()))
    ergebnis = dienst.status()
    assert ergebnis["quota_gb"] == 2199.0
    assert ergebnis["belegt_gb"] == 390.5
    assert ergebnis["frei_gb"] == 1808.5
    assert ergebnis["premium"] is True
    assert ergebnis["email_verifiziert"] is True
    assert ergebnis["userid"] == 4738912
    assert ergebnis["host"] == HOST
    assert ergebnis["verbunden"] is True


def test_status_kaputte_zahlen_werden_ehrlich_null(dienst, monkeypatch):
    """Ein kaputter Zahlenwert darf keinen 500er ausloesen."""
    mit_get(monkeypatch, Antwort(_userinfo(quota="kaputt", usedquota=None)))
    ergebnis = dienst.status()
    assert ergebnis["quota_gb"] == 0.0
    assert ergebnis["belegt_gb"] == 0.0
    assert ergebnis["frei_gb"] == 0.0


# ── liste() ────────────────────────────────────────────────────────────────

def test_liste_ordnet_ordner_zuerst_dann_namen(dienst, monkeypatch):
    fake = mit_get(
        monkeypatch,
        Antwort(
            _liste(
                _datei("zebra.jpg", fileid=11),
                _ordner("Urlaub", folderid=5),
                _datei("Apfel.png", fileid=12),
                _ordner("arbeit", folderid=6),
            )
        ),
    )
    eintraege = dienst.liste(0)
    assert fake.aufrufe[0]["url"] == f"https://{HOST}/listfolder"
    assert fake.aufrufe[0]["params"]["folderid"] == 0
    assert [e["name"] for e in eintraege] == [
        "arbeit", "Urlaub", "Apfel.png", "zebra.jpg",
    ]
    assert [e["ist_ordner"] for e in eintraege] == [True, True, False, False]


def test_liste_gibt_folderid_weiter_und_normalisiert_felder(dienst, monkeypatch):
    fake = mit_get(
        monkeypatch,
        Antwort(_liste(_ordner("Bilder", folderid=42), {"name": "ohne-zusatz.jpg"})),
    )
    eintraege = dienst.liste(42)
    assert fake.aufrufe[0]["params"]["folderid"] == 42
    ordner, datei = eintraege
    assert ordner["folderid"] == 42 and ordner["fileid"] is None
    assert datei["fileid"] is None and datei["groesse"] is None
    assert datei["geaendert"] is None


def test_liste_leerer_ordner_ergibt_leere_liste(dienst, monkeypatch):
    """Ein leerer Ordner kommt ohne metadata zurueck — gueltig, kein Fehler."""
    mit_get(monkeypatch, Antwort({"result": 0}))
    assert dienst.liste(0) == []


def test_liste_unbekannter_ordner_wirft_den_fehlertext(dienst, monkeypatch):
    mit_get(
        monkeypatch,
        Antwort({"result": 2005, "error": "Directory does not exist."}),
    )
    with pytest.raises(modul.PCloudFehler) as fehler:
        dienst.liste(999)
    assert "Directory does not exist." in str(fehler.value)


# ── suche() ────────────────────────────────────────────────────────────────

def test_suche_ignoriert_gross_und_kleinschreibung(dienst, monkeypatch):
    mit_get(
        monkeypatch,
        Antwort(
            _liste(
                _ordner("Urlaub 2024", folderid=1),
                _datei("urlaub-alt.jpg", fileid=2),
                _datei("Arbeit.pdf", fileid=3),
            )
        ),
    )
    treffer = dienst.suche("URLAUB")
    assert [t["name"] for t in treffer] == ["Urlaub 2024", "urlaub-alt.jpg"]


def test_suche_begrenzt_auf_50_treffer(dienst, monkeypatch):
    viele = [_datei(f"bild-{i:03d}.jpg", fileid=i) for i in range(60)]
    mit_get(monkeypatch, Antwort(_liste(*viele)))
    treffer = dienst.suche("bild")
    assert modul.MAX_TREFFER == 50
    assert len(treffer) == 50
    assert treffer[0]["name"] == "bild-000.jpg"  # dieselbe Reihenfolge wie liste()


def test_suche_ohne_begriff_kein_netzaufruf(dienst, monkeypatch):
    monkeypatch.setattr(modul.httpx, "get", Stolperfalle())
    assert dienst.suche("") == []
    assert dienst.suche("   ") == []


def test_suche_ist_nicht_rekursiv(dienst, monkeypatch):
    """Genau EIN listfolder — Unterordner werden nicht durchsucht."""
    fake = mit_get(
        monkeypatch,
        Antwort(_liste(_ordner("Unterordner", folderid=7), _datei("treffer.jpg", fileid=2))),
    )
    treffer = dienst.suche("treffer")
    assert [t["name"] for t in treffer] == ["treffer.jpg"]
    assert len(fake.aufrufe) == 1


# ── thumb() ────────────────────────────────────────────────────────────────

def test_thumb_liest_das_textformat_mit_base64(dienst, monkeypatch):
    """Live-Format: fileid|0|masse|data:image/jpeg;base64,… -> Bildbytes."""
    fake = mit_get(
        monkeypatch, Antwort(None, content=THUMB_ZEILE, content_type="text/plain")
    )
    daten = dienst.thumb(42)
    assert daten == JPEG
    assert daten[:3] == b"\xff\xd8\xff"
    aufruf = fake.aufrufe[0]
    assert aufruf["url"] == f"https://{HOST}/getthumbs"
    assert aufruf["params"]["fileids"] == 42
    assert aufruf["params"]["size"] == "120x120"
    assert aufruf["params"]["type"] == "jgp"   # png antwortet live mit Fehler 5002
    assert aufruf["params"]["auth"] == TOKEN


def test_thumb_meldet_die_fehlerzeile_mit_code(dienst, monkeypatch):
    """type=png-Variante live: fileid|5002|0 -> klare Meldung statt Textbytes."""
    mit_get(
        monkeypatch,
        Antwort(None, content=b"42|5002|0\n", content_type="text/plain"),
    )
    with pytest.raises(modul.PCloudFehler) as fehler:
        dienst.thumb(42)
    text = str(fehler.value)
    assert "5002" in text
    assert "42" in text


def test_thumb_rohe_bildbytes_bleiben_unveraendert(dienst, monkeypatch):
    """Andere pCloud-Versionen koennten rohe Bytes liefern — dann unveraendert."""
    mit_get(monkeypatch, Antwort(None, content=JPEG, content_type="image/jpeg"))
    assert dienst.thumb(7) == JPEG


def test_thumb_gibt_die_groesse_weiter(dienst, monkeypatch):
    fake = mit_get(
        monkeypatch, Antwort(None, content=THUMB_ZEILE, content_type="text/plain")
    )
    dienst.thumb(7, "32x32")
    assert fake.aufrufe[0]["params"]["size"] == "32x32"


def test_thumb_groessere_vorschauen_sind_erlaubt(dienst, monkeypatch):
    """480x480/800x800 sind live geprueft (27.09.2026) — noetig fuer Screenshots,
    weil Text bei 120x120 nicht lesbar ist (Messung screenshots_triage.py)."""
    fake = mit_get(
        monkeypatch, Antwort(None, content=THUMB_ZEILE, content_type="text/plain")
    )
    assert dienst.thumb(7, "800x800") == JPEG
    assert fake.aufrufe[0]["params"]["size"] == "800x800"
    assert modul.ERLAUBTE_THUMB_GROESSEN == ("32x32", "120x120", "480x480", "800x800")


def test_thumb_json_fehlerantwort_wird_zur_ausnahme(dienst, monkeypatch):
    """Falls pCloud statt Bilddaten JSON liefert: Fehlertext statt Rohbytes."""
    roh = b'{"result": 2009, "error": "File not found."}'
    mit_get(
        monkeypatch,
        Antwort({"result": 2009, "error": "File not found."}, content=roh,
                content_type="application/json"),
    )
    with pytest.raises(modul.PCloudFehler) as fehler:
        dienst.thumb(99)
    assert "File not found." in str(fehler.value)


def test_thumb_leere_antwort_wird_klarer_fehler(dienst, monkeypatch):
    mit_get(monkeypatch, Antwort(None, content=b"", content_type="text/plain"))
    with pytest.raises(modul.PCloudFehler) as fehler:
        dienst.thumb(5)
    assert "keine Bilddaten" in str(fehler.value)


def test_thumb_verbotene_groesse_ohne_netzaufruf(dienst, monkeypatch):
    monkeypatch.setattr(modul.httpx, "get", Stolperfalle())
    with pytest.raises(modul.PCloudFehler) as fehler:
        dienst.thumb(1, "9999x9999")
    text = str(fehler.value)
    assert "32x32" in text and "120x120" in text


def test_medientyp_aus_den_ersten_bytes():
    """Der Router setzt den richtigen Content-Type aus den Bild-Bytes."""
    assert modul.media_typ_fuer_bild(b"\x89PNG\r\n\x1a\n" + b"x") == "image/png"
    assert modul.media_typ_fuer_bild(JPEG) == "image/jpeg"
    assert modul.media_typ_fuer_bild(b"GIF89a" + b"x") == "image/gif"
    assert modul.media_typ_fuer_bild(b"irgendwas") == "application/octet-stream"


# ── datei_bytes() ──────────────────────────────────────────────────────────

def test_datei_bytes_laedt_ueber_getfilelink(dienst, monkeypatch):
    fake_get = mit_get(
        monkeypatch,
        Antwort({"result": 0, "hosts": ["c1.pcloud.com", "c2.pcloud.com"],
                 "path": "/abc/unterlagen.pdf", "size": 1000}),
    )
    fake_stream = mit_stream(monkeypatch, FakeStrom([b"AAA", b"BBB"]))
    daten = dienst.datei_bytes(17)
    assert daten == b"AAABBB"
    assert fake_get.aufrufe[0]["url"] == f"https://{HOST}/getfilelink"
    assert fake_get.aufrufe[0]["params"]["fileid"] == 17
    assert fake_stream.aufrufe[0]["methode"] == "GET"
    assert fake_stream.aufrufe[0]["url"] == "https://c1.pcloud.com/abc/unterlagen.pdf"


def test_datei_bytes_zu_gross_laut_link_ohne_download(dienst, monkeypatch):
    """Ist die Datei laut Link schon zu gross, wird gar nicht erst geladen."""
    mit_get(
        monkeypatch,
        Antwort({"result": 0, "hosts": ["c1.pcloud.com"], "path": "/gross.zip",
                 "size": 26 * 1024 * 1024}),
    )
    monkeypatch.setattr(modul.httpx, "stream", Stolperfalle())
    with pytest.raises(modul.PCloudZuGross) as fehler:
        dienst.datei_bytes(1)
    text = str(fehler.value)
    assert "Obergrenze" in text
    assert "26.2 MB" in text  # die 25-MB-Grenze selbst
    assert "27.3 MB" in text  # die zu grosse Datei


def test_datei_bytes_obergrenze_greift_beim_laden(dienst, monkeypatch):
    """Auch ohne size-Angabe wird beim Laden gekappt (hier mit kleiner Grenze)."""
    mit_get(monkeypatch, Antwort({"result": 0, "hosts": ["c1.pcloud.com"],
                                  "path": "/x.bin"}))
    mit_stream(monkeypatch, FakeStrom([b"123456", b"789012"]))
    with pytest.raises(modul.PCloudZuGross):
        dienst.datei_bytes(1, max_bytes=10)


def test_datei_bytes_faellt_auf_den_zweiten_host_zurueck(dienst, monkeypatch):
    mit_get(
        monkeypatch,
        Antwort({"result": 0, "hosts": ["tot.pcloud.com", "c2.pcloud.com"],
                 "path": "/x.bin", "size": 3}),
    )
    fake_stream = mit_stream(
        monkeypatch, httpx.ConnectError("host tot"), FakeStrom([b"ok!"])
    )
    daten = dienst.datei_bytes(2)
    assert daten == b"ok!"
    assert [a["url"] for a in fake_stream.aufrufe] == [
        "https://tot.pcloud.com/x.bin",
        "https://c2.pcloud.com/x.bin",
    ]


def test_datei_bytes_ohne_link_wird_klarer_fehler(dienst, monkeypatch):
    mit_get(monkeypatch, Antwort({"result": 0, "hosts": [], "path": ""}))
    with pytest.raises(modul.PCloudFehler) as fehler:
        dienst.datei_bytes(3)
    assert "keinen Download-Link" in str(fehler.value)


def test_fehlerklassen_erben_von_pcloud_fehler():
    """Damit der Router sauber 503/413/502 unterscheiden kann."""
    assert issubclass(modul.PCloudNichtKonfiguriert, modul.PCloudFehler)
    assert issubclass(modul.PCloudZuGross, modul.PCloudFehler)
