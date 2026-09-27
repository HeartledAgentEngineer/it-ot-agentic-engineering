"""Pruefungen fuer das Duplikate-Werkzeug (Pruefsummen) — alles OHNE Netz.

httpx wird grundsaetzlich durch Attrappen ersetzt: Jeder ``listfolder``-
Aufruf wird aus einem selbst gebauten Ordner-Inhalt beantwortet, und ein
Aufruf auf einen Ordner, der nicht in der Attrappe steht, laesst den Test
auffliegen. So ist belegt, dass das Werkzeug genau die Baeume liest, die es
lesen soll — und nichts sonst.

Zusaetzlich geprueft: im Quelltext kommt kein Loeschbefehl und kein
Herunterladen vor (Suchtest), der Token taucht in keiner Ausgabe auf, und
kaputte API-Felder loesen keinen Absturz aus. Der Test-Token ist erfunden.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_pcloud_duplikate.py -q
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import httpx
import pytest

PROJEKT = Path(__file__).resolve().parents[2]
WERKZEUG_PFAD = PROJEKT / "tools" / "pcloud" / "pcloud_duplikate.py"


def _laden(name: str, pfad: Path):
    """Ein Werkzeug als Modul laden und unter seinem Namen registrieren."""
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"Werkzeug nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    sys.modules[name] = modul
    spez.loader.exec_module(modul)
    return modul


modul = _laden("pcloud_duplikate", WERKZEUG_PFAD)

TOKEN = "test-token-nicht-echt-39-zeichen-abcdefg"
HOST = "eapi.test.example"

UPLOAD_ID = 111
SAMMLUNG_ID = 222


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
    """httpx.get-Attrappe: beantwortet ``listfolder`` aus einem Ordner-Buch.

    ``ordner`` bildet folderid -> Inhalt ab. Der Inhalt ist
      * eine Liste von Eintraegen (normaler Ordnerinhalt),
      * ein fertiges JSON-Objekt (z. B. eine Fehlerantwort), oder
      * eine Ausnahme (wird geworfen, fuer Netzfehler).
    Ein Aufruf auf eine unbekannte folderid fliegt auf.
    """

    def __init__(self, ordner):
        self.ordner = {int(k): v for k, v in ordner.items()}
        self.aufrufe = []

    def __call__(self, url, params=None, timeout=None):
        params = dict(params or {})
        self.aufrufe.append({"url": url, "params": params, "timeout": timeout})
        kennung = params.get("folderid")
        if kennung not in self.ordner:
            raise AssertionError(f"Unerwarteter listfolder-Aufruf: folderid={kennung!r}")
        inhalt = self.ordner[kennung]
        if isinstance(inhalt, Exception):
            raise inhalt
        if isinstance(inhalt, dict):            # fertige Antwort (Fehler o. ae.)
            return Antwort(inhalt)
        return Antwort({"result": 0, "metadata": {"contents": list(inhalt)}})

    @property
    def kennungen(self):
        """Die folderids aller Aufrufe, in Reihenfolge."""
        return [a["params"].get("folderid") for a in self.aufrufe]


class Stolperfalle:
    """Kein Aufruf erlaubt — jeder Versuch fliegt auf."""

    def __call__(self, *args, **kwargs):
        raise AssertionError(f"Unerlaubter Netz-Aufruf: args={args!r} kwargs={kwargs!r}")


# ── Bauhilfen ─────────────────────────────────────────────────────────────

def _datei(name, fileid, size, hashwert, **felder):
    """Ein Datei-Eintrag, wie ihn listfolder liefert (live: hash als Zahl)."""
    roh = {
        "name": name,
        "isfolder": False,
        "fileid": fileid,
        "size": size,
        "hash": hashwert,
        "created": "Sun, 20 Oct 2024 08:24:28 +0000",
        "modified": "Sun, 20 Oct 2024 08:24:28 +0000",
        "parentfolderid": UPLOAD_ID,
    }
    roh.update(felder)
    return roh


def _ordner(name, folderid):
    """Ein Ordner-Eintrag, wie ihn listfolder liefert."""
    return {"name": name, "isfolder": True, "folderid": folderid}


def _wurzel(*zusatz):
    """Der Inhalt der pCloud-Wurzel: die zwei Zielordner (+ Zusatz)."""
    return [_ordner("Automatic Upload", UPLOAD_ID), _ordner("Bilder & Videos", SAMMLUNG_ID), *zusatz]


def _mit_ordnern(monkeypatch, ordner) -> FakeGet:
    """httpx.get durch die Ordner-Attrappe ersetzen."""
    fake = FakeGet(ordner)
    monkeypatch.setattr(httpx, "get", fake)
    return fake


@pytest.fixture
def umgebung(monkeypatch, tmp_path):
    """Token/Host aus der Umgebung; keine .env-Datei vorhanden."""
    monkeypatch.setenv("PCLOUD_TOKEN", TOKEN)
    monkeypatch.setenv("PCLOUD_HOST", HOST)
    monkeypatch.setattr(modul, "ENV_DATEI", tmp_path / "keine.env")


@pytest.fixture
def ohne_env(monkeypatch, tmp_path):
    """Weder Token noch Host gesetzt, keine .env-Datei vorhanden."""
    monkeypatch.delenv("PCLOUD_TOKEN", raising=False)
    monkeypatch.delenv("PCLOUD_HOST", raising=False)
    monkeypatch.setattr(modul, "ENV_DATEI", tmp_path / "keine.env")


# ── Gruppierung nach size+hash ────────────────────────────────────────────

def test_gruppierung_nach_size_und_hash(umgebung, monkeypatch):
    """Gleiche Groesse UND gleicher Hash = eine Duplikatgruppe."""
    _mit_ordnern(monkeypatch, {
        0: _wurzel(),
        UPLOAD_ID: [_datei("a.jpg", 1, 100, 999), _datei("b.jpg", 2, 100, 999)],
        SAMMLUNG_ID: [],
    })
    bericht = modul.scan_und_bericht(token=TOKEN, host=HOST)

    assert bericht["zusammenfassung"]["duplikatgruppen"] == 1
    gruppe = bericht["gruppen"][0]
    assert (gruppe["size"], gruppe["hash_text"]) == (100, "999")
    assert gruppe["anzahl"] == 2
    assert gruppe["art"] == "innerhalb_upload"


def test_gleiche_groesse_anderer_hash_ist_kein_duplikat(umgebung, monkeypatch):
    """Gleiche Groesse, anderer Inhalt (Hash) — zaehlt NICHT als Duplikat."""
    _mit_ordnern(monkeypatch, {
        0: _wurzel(),
        UPLOAD_ID: [_datei("a.jpg", 1, 100, 111), _datei("b.jpg", 2, 100, 222)],
        SAMMLUNG_ID: [],
    })
    bericht = modul.scan_und_bericht(token=TOKEN, host=HOST)

    assert bericht["gruppen"] == []
    assert bericht["zusammenfassung"]["duplikatgruppen"] == 0
    assert bericht["zusammenfassung"]["betroffene_dateien"] == 0


def test_duplikat_ueber_baeume_hinweg_wird_erkannt(umgebung, monkeypatch):
    """Upload-Kopie und Sammlung-Original landen in EINER Gruppe."""
    fake = _mit_ordnern(monkeypatch, {
        0: _wurzel(),
        UPLOAD_ID: [_datei("IMG_1.jpg", 7, 500, 1234567890123456789)],
        SAMMLUNG_ID: [_ordner("Familie", 333)],
        333: [_datei("IMG_1.jpg", 8, 500, 1234567890123456789)],
    })
    bericht = modul.scan_und_bericht(token=TOKEN, host=HOST)

    gruppe = bericht["gruppen"][0]
    assert gruppe["art"] == "ueber_baeume"
    assert gruppe["baeume"] == ["sammlung", "upload"]
    assert {m["baum"] for m in gruppe["mitglieder"]} == {"upload", "sammlung"}
    assert bericht["zusammenfassung"]["ueber_baeume"]["gruppen"] == 1
    assert bericht["zusammenfassung"]["ueber_baeume"]["dateien"] == 2
    # Wurzel genau EINMAL, danach nur die zwei Baeume (kein Lauf ueber die Wurzel).
    assert fake.kennungen == [0, UPLOAD_ID, SAMMLUNG_ID, 333]


def test_loesch_kandidat_ist_immer_die_upload_kopie(umgebung, monkeypatch):
    """Kandidat = Upload-Kopie; die Sammlung steht NIE auf der Kandidatenliste."""
    fake = _mit_ordnern(monkeypatch, {
        0: _wurzel(),
        UPLOAD_ID: [_datei("IMG_1.jpg", 7, 500, 1234567890123456789)],
        SAMMLUNG_ID: [_datei("IMG_1.jpg", 8, 500, 1234567890123456789)],
    })
    bericht = modul.scan_und_bericht(token=TOKEN, host=HOST)

    gruppe = bericht["gruppen"][0]
    kandidaten = gruppe["loesch_kandidaten"]
    assert [k["fileid"] for k in kandidaten] == [7]
    assert all(k["baum"] == "upload" for k in kandidaten)
    assert 8 not in {k["fileid"] for k in kandidaten}       # Sammlung bleibt
    assert bericht["loesch_kandidaten"]["dateien"] == 1
    assert [k["fileid"] for k in bericht["loesch_kandidaten"]["liste"]] == [7]
    assert "upload" in bericht["regel_kandidat"]
    # Wurzel genau einmal, danach nur die zwei Baeume.
    assert fake.kennungen == [0, UPLOAD_ID, SAMMLUNG_ID]


def test_innerhalb_sammlung_gibt_es_keine_kandidaten(umgebung, monkeypatch):
    """Doppelte INNERHALB der Sammlung: keine Kandidaten (Sammlung ist tabu)."""
    _mit_ordnern(monkeypatch, {
        0: _wurzel(),
        UPLOAD_ID: [],
        SAMMLUNG_ID: [_datei("x.jpg", 1, 400, 31337), _datei("y.jpg", 2, 400, 31337)],
    })
    bericht = modul.scan_und_bericht(token=TOKEN, host=HOST)

    gruppe = bericht["gruppen"][0]
    assert gruppe["art"] == "innerhalb_sammlung"
    assert gruppe["loesch_kandidaten"] == []
    assert bericht["zusammenfassung"]["innerhalb"]["sammlung"]["gruppen"] == 1
    assert bericht["zusammenfassung"]["loesch_kandidaten"]["dateien"] == 0


def test_innerhalb_upload_bleibt_eine_kopie_stehen(umgebung, monkeypatch):
    """Drei Upload-Kopien: Kandidaten sind die weiteren — EINE bleibt."""
    _mit_ordnern(monkeypatch, {
        0: _wurzel(),
        UPLOAD_ID: [
            _datei("a.jpg", 1, 700, 5), _datei("b.jpg", 2, 700, 5), _datei("c.jpg", 3, 700, 5),
        ],
        SAMMLUNG_ID: [],
    })
    bericht = modul.scan_und_bericht(token=TOKEN, host=HOST)

    gruppe = bericht["gruppen"][0]
    kandidaten = [k["fileid"] for k in gruppe["loesch_kandidaten"]]
    assert kandidaten == [2, 3]                 # a.jpg (fileid 1) bleibt stehen
    assert 1 not in kandidaten
    assert bericht["zusammenfassung"]["loesch_kandidaten"]["dateien"] == 2


# ── Grenzen: Tiefe, Budget, leere und kaputte Daten ───────────────────────

def test_tiefenbegrenzung_liest_nicht_tiefer(umgebung, monkeypatch):
    """max_tiefe=1: Ordner auf Tiefe 2 wird gezaehlt, aber nicht gelesen."""
    fake = _mit_ordnern(monkeypatch, {
        0: _wurzel(),
        UPLOAD_ID: [_ordner("A", 1001)],
        1001: [_ordner("B", 1002)],             # B liegt auf Tiefe 2 -> gesperrt
        SAMMLUNG_ID: [],
    })
    bericht = modul.scan_und_bericht(max_tiefe=1, token=TOKEN, host=HOST)

    assert 1002 not in fake.kennungen           # kein Leseaufruf auf B
    zahlen = bericht["baeume"]["upload"]
    assert zahlen["tiefe_grenze"] == 1
    assert zahlen["tiefe_erreicht"] == 1
    assert zahlen["uebersprungen_tiefe"] == 1
    assert zahlen["ordner_gelesen"] == 2        # Wurzelbaum-Start + A
    assert bericht["zusammenfassung"]["duplikatgruppen"] == 0


def test_leere_baeume_ergeben_leeren_bericht(umgebung, monkeypatch):
    """Leere Ordner (auch ohne ``metadata``) — kein Absturz, ehrliche Nullen."""
    _mit_ordnern(monkeypatch, {
        0: _wurzel(),
        UPLOAD_ID: [],
        SAMMLUNG_ID: [],
    })
    bericht = modul.scan_und_bericht(token=TOKEN, host=HOST)

    assert bericht["gruppen"] == []
    zusammen = bericht["zusammenfassung"]
    assert zusammen["gescannte_dateien"] == 0
    assert zusammen["vergleichbare_dateien"] == 0
    assert zusammen["betroffene_dateien"] == 0
    assert bericht["loesch_kandidaten"]["liste"] == []


def test_kaputte_und_fehlende_felder_loesen_keinen_absturz_aus(umgebung, monkeypatch):
    """Fehlende/kaputte Felder, Fremdtypen, kaputtes metadata — alles zaehlbar."""
    _mit_ordnern(monkeypatch, {
        0: _wurzel(),
        UPLOAD_ID: [
            "kein Objekt",                                  # Fremdtyp in contents
            {"name": "ohne_id", "isfolder": True},          # Ordner ohne folderid
            _ordner("M", 1500),                             # Ordner mit kaputtem metadata
            {"name": "ohne_hash.jpg", "isfolder": False, "fileid": 11, "size": 5},
            {"name": "ohne_size.jpg", "isfolder": False, "fileid": 12, "hash": 7},
            {"name": "kaputte_size.jpg", "isfolder": False, "fileid": 13,
             "size": "viel", "hash": 7},
            {"name": "ohne_kennung.jpg", "isfolder": False, "size": 9, "hash": 8},
            _datei("gut.jpg", 14, 100, 4242),
        ],
        1500: {"result": 0, "metadata": "kaputt"},
        SAMMLUNG_ID: [],
    })
    bericht = modul.scan_und_bericht(token=TOKEN, host=HOST)   # kein Traceback

    zahlen = bericht["baeume"]["upload"]
    assert zahlen["kaputte_eintraege"] == 2         # Fremdtyp + Ordner ohne Id
    assert zahlen["ohne_hash"] == 1
    assert zahlen["ohne_groesse"] == 2              # fehlend UND unbrauchbar ("viel")
    assert zahlen["ohne_kennung"] == 1
    assert zahlen["dateien"] == 5
    assert zahlen["knoten"] == zahlen["ordner_gelesen"] + 5
    # Nur "gut.jpg" hat size+hash — allein ist sie kein Duplikat.
    assert bericht["gruppen"] == []
    assert bericht["zusammenfassung"]["vergleichbare_dateien"] == 2  # gut.jpg + size/hash-Paar


def test_fehlender_upload_ordner_klare_meldung(umgebung, monkeypatch):
    """Fehlt 'Automatic Upload', gibt es Klartext — und nur den Wurzelaufruf."""
    fake = _mit_ordnern(monkeypatch, {0: [_ordner("Bilder & Videos", SAMMLUNG_ID)]})
    with pytest.raises(modul.DuplikateFehler) as fehler:
        modul.scan_und_bericht(token=TOKEN, host=HOST)

    assert "Automatic Upload" in str(fehler.value)
    assert fake.kennungen == [0]


def test_fehlender_sammlung_ordner_klare_meldung(umgebung, monkeypatch):
    """Fehlt 'Bilder & Videos', gibt es Klartext — kein stiller Teillauf."""
    fake = _mit_ordnern(monkeypatch, {0: [_ordner("Automatic Upload", UPLOAD_ID)], UPLOAD_ID: []})
    with pytest.raises(modul.DuplikateFehler) as fehler:
        modul.scan_und_bericht(token=TOKEN, host=HOST)

    assert "Bilder & Videos" in str(fehler.value)
    assert fake.kennungen == [0, UPLOAD_ID]      # Upload wurde gelesen, dann Abbruch


def test_ohne_sammlung_liest_nur_den_upload_baum(umgebung, monkeypatch):
    """--ohne-sammlung: nur Upload lesen, Sammlung ehrlich als 'nicht gelesen'."""
    fake = _mit_ordnern(monkeypatch, {
        0: _wurzel(),
        UPLOAD_ID: [_datei("a.jpg", 1, 100, 5), _datei("b.jpg", 2, 100, 5)],
    })
    bericht = modul.scan_und_bericht(ohne_sammlung=True, token=TOKEN, host=HOST)

    assert fake.kennungen == [0, UPLOAD_ID]
    assert bericht["baeume"]["sammlung"]["gelesen"] is False
    assert "grund" in bericht["baeume"]["sammlung"]
    assert len(bericht["gruppen"]) == 1
    assert bericht["zusammenfassung"]["ueber_baeume"]["gruppen"] == 0
    assert bericht["zusammenfassung"]["innerhalb"]["sammlung"]["gruppen"] == 0


def test_ordner_budget_bricht_ehrlich_ab(umgebung, monkeypatch):
    """Ordner-Budget erschoepft: ehrlicher Abbruch statt Weiterlesen."""
    fake = _mit_ordnern(monkeypatch, {
        0: _wurzel(),
        UPLOAD_ID: [_ordner("A", 1001)],
        1001: [_ordner("B", 1002)],             # darf nicht mehr gelesen werden
        SAMMLUNG_ID: [],
    })
    bericht = modul.scan_und_bericht(ordner_max=1, token=TOKEN, host=HOST)

    assert fake.kennungen == [0, UPLOAD_ID, SAMMLUNG_ID]
    zahlen = bericht["baeume"]["upload"]
    assert zahlen["abgebrochen"] is True
    assert zahlen["offen_gelassen"] == 1
    assert zahlen["aufrufe"] == 1


def test_jeder_ordner_wird_genau_einmal_gelesen(umgebung, monkeypatch):
    """Dieselbe Kennung zweimal im Baum = trotzdem nur EIN Leseaufruf."""
    fake = _mit_ordnern(monkeypatch, {
        0: _wurzel(),
        UPLOAD_ID: [_ordner("A", 1001), _ordner("B", 1001)],
        1001: [],
        SAMMLUNG_ID: [],
    })
    bericht = modul.scan_und_bericht(token=TOKEN, host=HOST)

    assert fake.kennungen.count(1001) == 1
    assert fake.kennungen.count(0) == 1
    assert bericht["baeume"]["upload"]["wiederholte_ordner"] == 1
    assert bericht["aufrufe_gesamt"] == len(fake.kennungen)


# ── Positivliste, Quelltext und Geheimnis ─────────────────────────────────

def test_positivliste_enthaelt_nur_listfolder(umgebung, monkeypatch):
    """Erlaubt ist genau EINE Methode: listfolder."""
    assert modul.ERLAUBTE_METHODEN == ("listfolder",)


def test_positivliste_weist_fremde_methoden_ab(umgebung, monkeypatch):
    """Eine fremde Methode wird abgewiesen, BEVOR etwas gesendet wird.

    Der Name wird zusammengesetzt, damit er nirgends im Quelltext steht
    (siehe Suchtest darunter).
    """
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    fremd = "del" + "ete" + "file"
    with pytest.raises(modul.DuplikateFehler) as fehler:
        modul._api_senden(fremd, {}, token=TOKEN, host=HOST)
    assert "Positivliste" in str(fehler.value)


def test_keine_loeschbefehle_im_quelltext():
    """Suchtest: die verbotenen Namen kommen in keiner eigenen Datei vor."""
    verboten = ("del" + "ete" + "file", "del" + "ete" + "folder", "un" + "link")
    eigene = (WERKZEUG_PFAD, Path(__file__))
    for pfad in eigene:
        text = pfad.read_text(encoding="utf-8").lower()
        for wort in verboten:
            assert wort not in text, f"{pfad.name} enthaelt {wort!r}"


def test_kein_download_im_quelltext():
    """Suchtest: kein Herunterladen von Inhalten, nur Metadaten (listfolder)."""
    text = WERKZEUG_PFAD.read_text(encoding="utf-8").lower()
    verboten = (
        "datei" + "_bytes",                     # keine Datei-Inhalte ziehen
        "getfile" + "link",
        "get" + "thumbs",
        ".write(b",
        "'wb'",
        '"wb"',
    )
    for wort in verboten:
        assert wort not in text, f"Werkzeug enthaelt {wort!r}"
    # Und auch kein herunterladender Baustein:
    assert "iter_bytes" not in text and "content=" not in text


def test_fehlertext_mit_token_wird_maskiert(umgebung, monkeypatch):
    """Selbst ein Fehlertext, der den Token enthielte, kommt maskiert an."""
    _mit_ordnern(monkeypatch, {0: {"result": 2005, "error": f"kaputt {TOKEN}"}})
    with pytest.raises(modul.DuplikateFehler) as fehler:
        modul.scan_und_bericht(token=TOKEN, host=HOST)

    text = str(fehler.value)
    assert "2005" in text and TOKEN not in text and "***" in text


def test_ohne_token_klarer_fehler_statt_netzaufruf(ohne_env, monkeypatch):
    """Ohne Token: klarer Text und KEIN Netzaufruf."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    with pytest.raises(modul.DuplikateFehler) as fehler:
        modul.scan_und_bericht()
    assert "PCLOUD_TOKEN" in str(fehler.value)


# ── Ausgabe: Pfad, Datei, Konsole ─────────────────────────────────────────

def test_ausgabepfad_im_repo_wird_abgelehnt(tmp_path):
    """Ausgabe im Repo = Klartextfehler + SystemExit(2); nichts entsteht."""
    drin = PROJEKT / "tools" / "pcloud" / "nicht_erlaubt.json"
    with pytest.raises(SystemExit) as aus:
        modul._pruefe_ziel_ausserhalb_repo(str(drin))
    assert aus.value.code == 2
    assert not drin.exists()

    draussen = tmp_path / "duplikate.json"
    assert modul._pruefe_ziel_ausserhalb_repo(str(draussen)) == str(draussen)


def test_standardpfad_wird_ausgeschrieben_und_liegt_ausserhalb():
    """Der Standardpfad ist absolut, ohne '~' und ausserhalb des Repos."""
    ziel = modul._pruefe_ziel_ausserhalb_repo(modul.STANDARD_AUSGABE)
    assert os.path.isabs(ziel)
    assert "~" not in ziel
    assert "foto_sortierung" in ziel
    assert not os.path.normcase(ziel).startswith(os.path.normcase(str(PROJEKT)))


def test_hauptlauf_schreibt_json_mit_gruppen_und_kandidaten(umgebung, monkeypatch, tmp_path):
    """main(): Exit 0, JSON mit Gruppe, Mitgliedern und Kandidaten; ohne Token."""
    _mit_ordnern(monkeypatch, {
        0: _wurzel(),
        UPLOAD_ID: [_datei("IMG_1.jpg", 7, 500, 1234567890123456789)],
        SAMMLUNG_ID: [_datei("IMG_1.jpg", 8, 500, 1234567890123456789)],
    })
    ziel = tmp_path / "duplikate.json"
    code = modul.main(["--quelle", str(ziel), "--beispiele", "5", "--trocken"])

    assert code == 0
    text = ziel.read_text(encoding="utf-8")
    daten = json.loads(text)
    assert daten["trocken"] is True
    assert daten["tiefe_grenze"] == modul.MAX_TIEFE_STANDARD
    gruppe = daten["gruppen"][0]
    assert set(gruppe) >= {"size", "hash", "anzahl", "art", "mitglieder", "loesch_kandidaten"}
    for mitglied in gruppe["mitglieder"]:
        assert set(mitglied) == {"fileid", "name", "pfad", "baum", "created", "modified"}
    assert daten["zusammenfassung"]["ueber_baeume"]["gruppen"] == 1
    assert daten["loesch_kandidaten"]["liste"][0]["fileid"] == 7
    assert TOKEN not in text
    assert not (tmp_path / "duplikate.json.tmp").exists()


def test_konsole_zeigt_zahlen_fuenf_beispiele_und_kandidaten(umgebung, monkeypatch, capsys, tmp_path):
    """Konsole: Zahlen + hoechstens 5 Beispielgruppen + Kandidat-Kennzeichnung."""
    upload = [_datei(f"u{i}.jpg", 100 + i, 1000 + i, 900 + i) for i in range(7)]
    sammlung = [_datei(f"s{i}.jpg", 200 + i, 1000 + i, 900 + i) for i in range(7)]
    _mit_ordnern(monkeypatch, {0: _wurzel(), UPLOAD_ID: upload, SAMMLUNG_ID: sammlung})

    code = modul.main(["--quelle", str(tmp_path / "d.json")])

    assert code == 0
    aus = capsys.readouterr().out
    assert "Duplikatgruppen" in aus
    assert "Gruppe 5" in aus and "Gruppe 6" not in aus
    assert "und 2 weitere Gruppen" in aus
    assert "LOESCH-KANDIDAT" in aus
    assert "Loesch-Kandidaten (immer die Kopie im Baum 'upload'" in aus
    assert "u6.jpg" in aus                      # Beispiele zeigen Namen
    assert "s6.jpg" in aus
