"""Pruefungen fuer das pCloud-Bewegungs-Sicherheitsnetz — alles OHNE Netz.

httpx wird grundsaetzlich durch Attrappen ersetzt. Fuer Wege, auf denen KEIN
Aufruf passieren darf (Trockenlauf, fehlender Name, Namenskonflikt, fehlender
Token), steht die Stolperfalle im Weg: ein echter Aufruf wuerde den Test
sofort auffliegen lassen.

Zusaetzlich geprueft: im Quelltext der eigenen Werkzeuge kommt kein
Entfernungs-Befehl vor (Suchtest), und der Token taucht in keiner Ausgabe,
keiner Fehlermeldung und keiner Manifest-Zeile auf. Der Test-Token ist
erfunden.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_pcloud_bewegungen.py -q
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import httpx
import pytest

PROJEKT = Path(__file__).resolve().parents[2]
BEWEGUNGEN_PFAD = PROJEKT / "tools" / "pcloud" / "pcloud_bewegungen.py"
RUCKROLL_PFAD = PROJEKT / "tools" / "pcloud" / "pcloud_rueckrollen.py"


def _laden(name: str, pfad: Path):
    """Ein Werkzeug als Modul laden und unter seinem Namen registrieren.

    Die Registrierung in ``sys.modules`` sorgt dafuer, dass
    ``pcloud_rueckrollen.py`` beim Import dieselbe Instanz findet.
    """
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"Werkzeug nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    sys.modules[name] = modul
    spez.loader.exec_module(modul)
    return modul


modul = _laden("pcloud_bewegungen", BEWEGUNGEN_PFAD)

TOKEN = "test-token-nicht-echt-39-zeichen-abcdefg"
HOST = "eapi.test.example"


# ── Attrappen (kein Netz) ──────────────────────────────────────────────────

class Antwort:
    """Attrappe einer httpx-Antwort mit JSON-Daten."""

    def __init__(self, daten=None, *, status_code=200):
        self._daten = daten
        self.status_code = status_code

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
        raise AssertionError(f"Unerlaubter Netz-Aufruf: args={args!r} kwargs={kwargs!r}")


def mit_get(monkeypatch, *antworten) -> FakeGet:
    """httpx.get durch eine Attrappe ersetzen (nach dem Test automatisch zurueck)."""
    fake = FakeGet(*antworten)
    monkeypatch.setattr(httpx, "get", fake)
    return fake


# ── Bauhilfen ─────────────────────────────────────────────────────────────

def _ok(**felder) -> Antwort:
    """Erfolgs-Antwort der pCloud (result = 0)."""
    return Antwort({"result": 0, **felder})


def _liste(*eintraege) -> Antwort:
    """listfolder-Antwort mit den gegebenen Eintraegen im Ordner."""
    return _ok(metadata={"contents": list(eintraege)})


def _eintrag(name: str, kennung: int, *, ist_ordner: bool = False) -> dict:
    """Ein Eintrag, wie ihn listfolder liefert (Datei oder Ordner)."""
    roh = {"name": name, "isfolder": ist_ordner}
    if ist_ordner:
        roh["folderid"] = kennung
    else:
        roh["fileid"] = kennung
    return roh


def _zeilen(pfad: Path) -> list:
    """Die JSON-Zeilen einer Manifest-Datei (leer, wenn es sie nicht gibt)."""
    if not pfad.exists():
        return []
    return [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]


@pytest.fixture
def mfad(tmp_path) -> Path:
    """Manifest-Pfad im Testverzeichnis (ausserhalb jedes Repos)."""
    return tmp_path / "manifest.jsonl"


@pytest.fixture
def ohne_env(monkeypatch, tmp_path):
    """Weder Token noch Pfade aus der Umgebung, keine .env-Datei vorhanden."""
    for name in ("PCLOUD_TOKEN", "PCLOUD_HOST", "PCLOUD_MANIFEST"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(modul, "ENV_DATEI", tmp_path / "keine.env")


# ── Manifest: anhaengen ────────────────────────────────────────────────────

def test_manifest_anhaengen_haengt_nur_an(mfad):
    """Zwei Eintraege = zwei Zeilen — nichts wird ueberschrieben."""
    modul.manifest_anhaengen({"art": "movefile", "name": "a.jpg"}, pfad=mfad)
    modul.manifest_anhaengen({"art": "movefile", "name": "b.jpg"}, pfad=mfad)

    zeilen = _zeilen(mfad)
    assert [z["name"] for z in zeilen] == ["a.jpg", "b.jpg"]
    assert mfad.read_text(encoding="utf-8").count("\n") == 2


def test_manifest_ueberschreibt_vorhandenes_nicht(mfad):
    """Was schon im Manifest steht, bleibt unangetastet."""
    mfad.write_text('{"art": "movefile", "name": "alt.jpg"}\n', encoding="utf-8")
    modul.manifest_anhaengen({"art": "movefile", "name": "neu.jpg"}, pfad=mfad)

    zeilen = _zeilen(mfad)
    assert len(zeilen) == 2
    assert zeilen[0] == {"art": "movefile", "name": "alt.jpg"}
    assert zeilen[1]["name"] == "neu.jpg"


def test_manifest_eintrag_hat_alle_felder_und_iso_zeit(mfad):
    """Jede Zeile traegt die neun Pflichtfelder; die Zeit hat einen Zonenversatz."""
    modul.manifest_anhaengen(
        {"art": "movefile", "name": "a.jpg", "fileid": 7, "von_folderid": 1,
         "nach_folderid": 2}, pfad=mfad)
    z = _zeilen(mfad)[0]

    assert list(z.keys()) == list(modul.MANIFEST_FELDER)
    assert z["art"] == "movefile" and z["fileid"] == 7
    assert z["folderid"] is None and z["von_pfad"] is None  # Unbekanntes ehrlich None
    zeit = datetime.fromisoformat(z["zeit"])
    assert zeit.tzinfo is not None


def test_manifest_lehnt_unbekannte_art_ab(mfad):
    """Nur die erlaubten Arten kommen ins Manifest."""
    with pytest.raises(modul.PCloudBewegungsFehler) as fehler:
        modul.manifest_anhaengen({"art": "schraeg", "name": "x"}, pfad=mfad)
    assert "schraeg" in str(fehler.value)
    assert not mfad.exists()


def test_manifest_standardpfad_und_umgebungsvariable(ohne_env, monkeypatch, tmp_path):
    """Standard ist ~/foto_sortierung/manifest.jsonl; die Umgebung schlaegt ihn."""
    standard = modul.manifest_datei()
    assert standard.name == "manifest.jsonl"
    assert "foto_sortierung" in str(standard)

    monkeypatch.setenv("PCLOUD_MANIFEST", str(tmp_path / "woanders.jsonl"))
    assert modul.manifest_datei() == tmp_path / "woanders.jsonl"


def test_manifest_im_repo_wird_abgelehnt(tmp_path):
    """Ein Manifest-Pfad in einem Git-Repo wird verweigert — nichts entsteht."""
    (tmp_path / ".git").mkdir()
    pfad = tmp_path / "unter" / "manifest.jsonl"

    with pytest.raises(modul.PCloudBewegungsFehler) as fehler:
        modul.manifest_anhaengen({"art": "movefile", "name": "x"}, pfad=pfad)
    assert "Repo" in str(fehler.value)
    assert not pfad.exists()


# ── ordner_anlegen ─────────────────────────────────────────────────────────

def test_ordner_anlegen_trocken_sendet_nichts(mfad, monkeypatch):
    """Trockenlauf ist Standard: kein Aufruf, keine Manifest-Zeile."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    eintrag = modul.ordner_anlegen(222, "2025", manifest_pfad=mfad)

    assert eintrag["art"] == "createfolder"
    assert eintrag["name"] == "2025"
    assert eintrag["nach_folderid"] == 222
    assert eintrag["folderid"] is None
    assert eintrag["trocken"] is True
    assert not mfad.exists()


def test_ordner_anlegen_echt_ruft_createfolder_und_bucht(mfad, monkeypatch):
    """Echt: createfolder mit folderid+name, danach genau eine Manifest-Zeile."""
    fake = mit_get(
        monkeypatch,
        _ok(metadata={"folderid": 555, "path": "/Agent/Fotos/2025"}),
    )
    eintrag = modul.ordner_anlegen(
        222, "2025", trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)

    assert fake.aufrufe[0]["url"] == f"https://{HOST}/createfolder"
    assert fake.aufrufe[0]["params"] == {"folderid": 222, "name": "2025", "auth": TOKEN}
    assert eintrag["folderid"] == 555
    assert eintrag["nach_pfad"] == "/Agent/Fotos/2025"
    assert eintrag == _zeilen(mfad)[0]


# ── datei_verschieben ──────────────────────────────────────────────────────

def test_datei_verschieben_trocken_sendet_nichts(mfad, monkeypatch):
    """Trockenlauf: geplanter Eintrag, kein Aufruf, keine Zeile."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    eintrag = modul.datei_verschieben(
        777, 222, name="IMG_1.jpg", von_folderid=111, manifest_pfad=mfad)

    assert eintrag["art"] == "movefile"
    assert eintrag["fileid"] == 777
    assert eintrag["von_folderid"] == 111 and eintrag["nach_folderid"] == 222
    assert eintrag["trocken"] is True
    assert not mfad.exists()


def test_datei_verschieben_echt_ruft_renamefile_und_bucht(mfad, monkeypatch):
    """Echt: erst Zielordner lesen, dann renamefile, dann buchen."""
    fake = mit_get(
        monkeypatch,
        _liste(),                                                  # Ziel ist frei
        _ok(metadata={"path": "/Agent/Fotos/2025/IMG_1.jpg"}),     # renamefile
    )
    eintrag = modul.datei_verschieben(
        777, 222, name="IMG_1.jpg", von_folderid=111,
        trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)

    assert fake.aufrufe[0]["url"] == f"https://{HOST}/listfolder"
    assert fake.aufrufe[0]["params"] == {"folderid": 222, "auth": TOKEN}
    assert fake.aufrufe[1]["url"] == f"https://{HOST}/renamefile"
    assert fake.aufrufe[1]["params"] == {"fileid": 777, "tofolderid": 222, "auth": TOKEN}
    assert eintrag["nach_pfad"] == "/Agent/Fotos/2025/IMG_1.jpg"
    assert eintrag == _zeilen(mfad)[0]


def test_verschieben_verweigert_ohne_namen(mfad, monkeypatch):
    """Ohne Namen waere der Namenskonflikt am Ziel nicht pruefbar — kein Lauf."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    with pytest.raises(modul.PCloudBewegungsFehler) as fehler:
        modul.datei_verschieben(
            777, 222, von_folderid=111, trocken=False,
            manifest_pfad=mfad, token=TOKEN, host=HOST)
    assert "Namen" in str(fehler.value)
    assert not mfad.exists()


def test_verschieben_verweigert_ohne_quellordner(mfad, monkeypatch):
    """Ohne Quellordner-Id waere die Aktion nicht rueckholbar — kein Lauf."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    with pytest.raises(modul.PCloudBewegungsFehler) as fehler:
        modul.datei_verschieben(
            777, 222, name="a.jpg", trocken=False,
            manifest_pfad=mfad, token=TOKEN, host=HOST)
    assert "von_folderid" in str(fehler.value)
    assert not mfad.exists()


def test_verschieben_verweigert_gleiche_quelle_und_ziel(mfad, monkeypatch):
    """Ziel = Quelle ist keine Bewegung — nichts gesendet."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    with pytest.raises(modul.PCloudBewegungsFehler) as fehler:
        modul.datei_verschieben(
            777, 111, name="a.jpg", von_folderid=111, trocken=False,
            manifest_pfad=mfad, token=TOKEN, host=HOST)
    assert "derselbe Ordner" in str(fehler.value)
    assert not mfad.exists()


def test_verschieben_haelt_bei_gleichnamigem_ziel_an(mfad, monkeypatch):
    """Liegt am Ziel ein gleichnamiges fremdes Element, wird NICHTS verschoben."""
    fake = mit_get(monkeypatch, _liste(_eintrag("img_1.jpg", 999)))  # andere Datei!
    with pytest.raises(modul.PCloudBewegungsFehler) as fehler:
        modul.datei_verschieben(
            777, 222, name="IMG_1.jpg", von_folderid=111,
            trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)

    assert "IMG_1.jpg" in str(fehler.value)
    assert len(fake.aufrufe) == 1          # nur die Lesepruefung, kein renamefile
    assert not mfad.exists()


def test_verschieben_ueberspringt_wenn_schon_am_ziel(mfad, monkeypatch):
    """Liegt DIESELBE Datei schon am Ziel, ist die Aktion erledigt — nichts tun."""
    fake = mit_get(monkeypatch, _liste(_eintrag("IMG_1.jpg", 777)))
    ergebnis = modul.datei_verschieben(
        777, 222, name="IMG_1.jpg", von_folderid=111,
        trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)

    assert ergebnis["uebersprungen"] is True
    assert "bereits" in ergebnis["grund"]
    assert len(fake.aufrufe) == 1          # kein renamefile
    assert not mfad.exists()


def test_verschieben_meldet_ersetzte_datei_und_bucht_trotzdem(mfad, monkeypatch):
    """Ersetzt pCloud doch eine Zieldatei: Eintrag mit Hinweis + lauter Fehler."""
    fake = mit_get(
        monkeypatch,
        _liste(),
        _ok(metadata={"deletedfileid": 4242, "path": "/Agent/Fotos/IMG_1.jpg"}),
    )
    with pytest.raises(modul.PCloudBewegungsFehler) as fehler:
        modul.datei_verschieben(
            777, 222, name="IMG_1.jpg", von_folderid=111,
            trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)

    assert "4242" in str(fehler.value)
    zeilen = _zeilen(mfad)
    assert len(zeilen) == 1
    assert "hinweis" in zeilen[0]          # der Fall steht so im Manifest


def test_ordner_verschieben_echt_ruft_renamefolder_und_bucht(mfad, monkeypatch):
    """Ordner-Verschieben: renamefolder mit folderid+tofolderid."""
    fake = mit_get(
        monkeypatch,
        _liste(),
        _ok(metadata={"path": "/Agent/Fotos/2025/Motiv"}),
    )
    eintrag = modul.ordner_verschieben(
        555, 222, name="Motiv", von_folderid=111,
        trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)

    assert fake.aufrufe[1]["url"] == f"https://{HOST}/renamefolder"
    assert fake.aufrufe[1]["params"] == {"folderid": 555, "tofolderid": 222, "auth": TOKEN}
    assert eintrag["art"] == "movefolder"
    assert eintrag["folderid"] == 555
    assert _zeilen(mfad)[0] == eintrag


# ── Fehlerwege ─────────────────────────────────────────────────────────────

def test_api_fehler_wird_klartext_und_nichts_gebucht(mfad, monkeypatch):
    """pCloud-Fehler kommen als Klartext — und das Manifest bleibt leer."""
    mit_get(
        monkeypatch,
        _liste(),
        Antwort({"result": 2005, "error": "Directory does not exist."}),
    )
    with pytest.raises(modul.PCloudBewegungsFehler) as fehler:
        modul.datei_verschieben(
            777, 222, name="a.jpg", von_folderid=111,
            trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)
    assert "2005" in str(fehler.value)
    assert "Directory does not exist." in str(fehler.value)
    assert not mfad.exists()


def test_netzfehler_nennt_nur_die_klasse_und_nie_den_token(mfad, monkeypatch):
    """Transportfehler melden nur den Klassen-Namen — der Token bleibt geheim."""
    mit_get(monkeypatch, _liste(), httpx.ConnectError(f"kaputt bei auth={TOKEN}"))
    with pytest.raises(modul.PCloudBewegungsFehler) as fehler:
        modul.datei_verschieben(
            777, 222, name="a.jpg", von_folderid=111,
            trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)

    text = str(fehler.value)
    assert "ConnectError" in text
    assert TOKEN not in text
    assert not mfad.exists()


def test_fehlertext_mit_token_wird_maskiert(mfad, monkeypatch):
    """Selbst ein Fehlertext, der den Token enthielte, kommt maskiert an."""
    mit_get(
        monkeypatch,
        _liste(),
        Antwort({"result": 2005, "error": f"kaputt {TOKEN}"}),
    )
    with pytest.raises(modul.PCloudBewegungsFehler) as fehler:
        modul.datei_verschieben(
            777, 222, name="a.jpg", von_folderid=111,
            trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)

    text = str(fehler.value)
    assert TOKEN not in text
    assert "***" in text


def test_token_steht_in_keiner_manifest_zeile(mfad, monkeypatch):
    """Ein gelungener Lauf schreibt den Token nirgends hin."""
    mit_get(monkeypatch, _liste(), _ok(metadata={}))
    modul.datei_verschieben(
        777, 222, name="a.jpg", von_folderid=111,
        trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)

    text = mfad.read_text(encoding="utf-8")
    assert TOKEN not in text


def test_ohne_token_klarer_fehler_statt_netzaufruf(ohne_env, mfad, monkeypatch):
    """Ohne Token: klarer Text und KEIN Netzaufruf."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    with pytest.raises(modul.PCloudBewegungsFehler) as fehler:
        modul.datei_verschieben(
            777, 222, name="a.jpg", von_folderid=111,
            trocken=False, manifest_pfad=mfad)
    assert "PCLOUD_TOKEN" in str(fehler.value)


# ── zielordner_finden_oder_bauen ───────────────────────────────────────────

def test_zielordner_finden_oder_bauen_findet_vorhandenen(mfad, monkeypatch):
    """Vorhandener Ordner wird genommen — kein createfolder, keine Buchung."""
    fake = mit_get(monkeypatch, _liste(_eintrag("2025", 555, ist_ordner=True)))
    ergebnis = modul.zielordner_finden_oder_bauen(
        222, "2025", trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)

    assert ergebnis["folderid"] == 555
    assert ergebnis["angelegt"] is False
    assert [a["url"] for a in fake.aufrufe] == [f"https://{HOST}/listfolder"]
    assert not mfad.exists()


def test_zielordner_wird_nicht_doppelt_angelegt(mfad, monkeypatch):
    """Zweiter Lauf findet den angelegten Ordner — createfolder laeuft EINMAL."""
    fake = mit_get(
        monkeypatch,
        _liste(),
        _ok(metadata={"folderid": 555, "path": "/Agent/Fotos/2025"}),
        _liste(_eintrag("2025", 555, ist_ordner=True)),
    )
    erst = modul.zielordner_finden_oder_bauen(
        222, "2025", trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)
    zweit = modul.zielordner_finden_oder_bauen(
        222, "2025", trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)

    assert erst["angelegt"] is True and erst["folderid"] == 555
    assert zweit["angelegt"] is False and zweit["folderid"] == 555
    arten = [a["url"].rsplit("/", 1)[-1] for a in fake.aufrufe]
    assert arten == ["listfolder", "createfolder", "listfolder"]
    assert len(_zeilen(mfad)) == 1          # nur EINE Buchung


def test_zielordner_finden_oder_bauen_trocken_sendet_nichts(mfad, monkeypatch):
    """Trockenlauf baut nichts und liest nichts — nur der geplante Eintrag."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    ergebnis = modul.zielordner_finden_oder_bauen(222, "2025", manifest_pfad=mfad)

    assert ergebnis["art"] == "createfolder"
    assert ergebnis["trocken"] is True
    assert not mfad.exists()


def test_zielordner_finden_oder_bauen_konflikt_mit_datei(mfad, monkeypatch):
    """Gleichnamige DATEI im Elternordner: Klartextfehler statt Ordneranlage."""
    fake = mit_get(monkeypatch, _liste(_eintrag("2025", 999)))  # Datei, kein Ordner
    with pytest.raises(modul.PCloudBewegungsFehler) as fehler:
        modul.zielordner_finden_oder_bauen(
            222, "2025", trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)

    assert "DATEI" in str(fehler.value)
    assert [a["url"] for a in fake.aufrufe] == [f"https://{HOST}/listfolder"]
    assert not mfad.exists()


# ── archiv_entpacken (Papas Amazon-Fotos, 10.10.2026) ──────────────────────

def test_entpacken_trocken_sendet_nichts(mfad, monkeypatch):
    """Trockenlauf ist Standard: kein Aufruf, keine Manifest-Zeile."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    eintrag = modul.archiv_entpacken(
        108721897936, 4242, name="AmazonPhotos (11).zip", manifest_pfad=mfad)

    assert eintrag["art"] == "extractarchive"
    assert eintrag["fileid"] == 108721897936
    assert eintrag["nach_folderid"] == 4242
    assert eintrag["trocken"] is True
    assert not mfad.exists()


def test_entpacken_leerer_ordner_entpackt_und_bucht(mfad, monkeypatch):
    """Leerer Zielordner: erst lesen, dann entpacken, dann EINE Manifest-Zeile."""
    fake = mit_get(
        monkeypatch,
        _liste(),
        _ok(metadata={"path": "/Bilder & Videos/Papa (Amazon)/AmazonPhotos (11)"}, taskid=77),
    )
    eintrag = modul.archiv_entpacken(
        108721897936, 4242, name="AmazonPhotos (11).zip",
        trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)

    assert len(fake.aufrufe) == 2
    assert fake.aufrufe[0]["params"]["folderid"] == 4242          # Vorpruefung: lesen
    letzter = fake.aufrufe[-1]
    assert letzter["url"].endswith("/extractarchive")
    assert letzter["params"]["fileid"] == 108721897936
    assert letzter["params"]["tofolderid"] == 4242
    zeilen = _zeilen(mfad)
    assert len(zeilen) == 1
    assert zeilen[0]["art"] == "extractarchive"
    assert zeilen[0]["taskid"] == 77
    assert zeilen[0]["nach_pfad"] == "/Bilder & Videos/Papa (Amazon)/AmazonPhotos (11)"
    assert eintrag["name"] == "AmazonPhotos (11).zip"


def test_entpacken_voller_ordner_entpackt_nicht(mfad, monkeypatch):
    """Zielordner nicht leer: kein Entpacken, keine Buchung — so ist es idempotent."""
    fake = mit_get(monkeypatch, _liste(_eintrag("IMG_1.jpg", 5)))
    z = modul.archiv_entpacken(
        108721897936, 4242, trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)

    assert z["uebersprungen"] is True
    assert z["grund"] == "ziel_nicht_leer"
    assert z["anzahl_vorhanden"] == 1
    assert len(fake.aufrufe) == 1                                 # nur gelesen
    assert not mfad.exists()


def test_entpacken_ohne_token_klartext_ohne_netz(ohne_env, mfad):
    """Ohne Token gibt es einen Klartextfehler — und keinen Netz-Aufruf."""
    with pytest.raises(modul.PCloudBewegungsFehler) as fehler:
        modul.archiv_entpacken(1, 2, trocken=False, manifest_pfad=mfad)
    assert "PCLOUD_TOKEN" in str(fehler.value)


def test_entpacken_token_taucht_nicht_in_der_buchung_auf(mfad, monkeypatch):
    """Der Geheimwert steht in keiner Manifest-Zeile."""
    mit_get(monkeypatch, _liste(), _ok(metadata={"path": "/x"}))
    modul.archiv_entpacken(1, 2, trocken=False, manifest_pfad=mfad, token=TOKEN, host=HOST)
    assert TOKEN not in mfad.read_text(encoding="utf-8")


# ── Positivliste und Quelltext ─────────────────────────────────────────────

def test_positivliste_enthaelt_nur_lesen_und_die_schreibwege():
    """Die Positivliste ist exakt: lesen + die Schreibwege, sonst nichts."""
    assert set(modul.ERLAUBTE_METHODEN) == {
        "createfolder", "renamefile", "renamefolder", "listfolder", "extractarchive"}


def test_positivliste_weist_fremde_methoden_ab(monkeypatch):
    """Eine fremde Methode wird abgewiesen, BEVOR etwas gesendet wird.

    Der Methodenname wird zusammengesetzt, damit die verbotenen Namen
    nirgends im Quelltext stehen (siehe Suchtest darunter).
    """
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    fremd = "del" + "ete" + "file"
    with pytest.raises(modul.PCloudBewegungsFehler) as fehler:
        modul._api_senden(fremd, {}, token=TOKEN, host=HOST)
    assert "Positivliste" in str(fehler.value)


def test_keine_loeschbefehle_in_den_eigenen_dateien():
    """Suchtest: die verbotenen Namen kommen in keiner eigenen Datei vor."""
    # Zusammengesetzt, damit dieser Test sie nicht selbst in die Datei traegt.
    verboten = ("del" + "ete" + "file", "del" + "ete" + "folder", "un" + "link")
    eigene = (
        BEWEGUNGEN_PFAD,
        RUCKROLL_PFAD,
        Path(__file__),
        PROJEKT / "backend" / "tests" / "test_pcloud_rueckrollen.py",
    )
    for pfad in eigene:
        text = pfad.read_text(encoding="utf-8").lower()
        for wort in verboten:
            assert wort not in text, f"{pfad.name} enthaelt {wort!r}"
