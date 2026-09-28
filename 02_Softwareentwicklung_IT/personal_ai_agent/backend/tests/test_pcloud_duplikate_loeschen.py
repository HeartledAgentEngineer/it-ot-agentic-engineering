"""Pruefungen fuer das pCloud-Loesch-Werkzeug (Duplikate) — alles OHNE Netz.

httpx wird grundsaetzlich durch Attrappen ersetzt. Fuer Wege, auf denen KEIN
Aufruf passieren darf (Trockenlauf, Abbruch wegen Abweichung, verweigerte
Kennung, Manifest im Repo, fehlender Token), steht die Stolperfalle im Weg:
ein echter Aufruf wuerde den Test sofort auffliegen lassen. Der Attrappen-
Sender protokolliert ausserdem die Methodennamen — so ist belegt, dass im
Trockenlauf **kein** ``deletefile`` abgeht.

Zusaetzlich geprueft: die Positivliste der API-Methoden (und dass im Quelltext
kein anderer Methodenname auftaucht), die Abwesenheit von Verschiebe-,
Download- und Ordner-Entfernungs-Aufrufen, die Manifest-Pflicht (anhaengend,
nur ueber das Nachbarmodul) und dass der Token in keiner Ausgabe, keiner
Fehlermeldung und keiner Zeile steht.

Alle Kennungen, Namen und Groessen hier sind ERFUNDEN — nichts stammt aus dem
echten Bericht. Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_pcloud_duplikate_loeschen.py -q
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

PROJEKT = Path(__file__).resolve().parents[2]
TOOLS = PROJEKT / "tools" / "pcloud"
WERKZEUG_PFAD = TOOLS / "pcloud_duplikate_loeschen.py"
BEWEGUNGEN_PFAD = TOOLS / "pcloud_bewegungen.py"


def _laden(name: str, pfad: Path):
    """Ein Werkzeug als Modul laden und unter seinem Namen registrieren.

    Die Registrierung in ``sys.modules`` sorgt dafuer, dass das Loesch-Werkzeug
    beim Import dieselbe ``pcloud_bewegungen``-Instanz findet.
    """
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"Werkzeug nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    sys.modules[name] = modul
    spez.loader.exec_module(modul)
    return modul


# Erst das Nachbarmodul (das Loesch-Werkzeug importiert es beim Laden), dann es selbst.
bewegen = _laden("pcloud_bewegungen", BEWEGUNGEN_PFAD)
modul = _laden("pcloud_duplikate_loeschen", WERKZEUG_PFAD)

TOKEN = "test-token-nicht-echt-39-zeichen-abcdefg"
HOST = "eapi.test.example"
STAND = "2026-09-27T05:00:00+02:00"

# Erfundene Ordnerkennungen der Attrappe (nicht aus dem echten Konto).
UPLOAD_ID = 4001
SAMMLUNG_ID = 4002
UNTER_ID = 4100


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
    """httpx.get-Attrappe: beantwortet listfolder aus einem Ordner-Buch.

    ``ordner`` bildet folderid -> Inhalt ab (Liste von Roheintraegen, ein
    fertiges JSON-Objekt oder eine Ausnahme). ``deletefile`` und ``trash_list``
    werden als Erfolg beantwortet — jede andere Methode fliegt auf.
    """

    def __init__(self, ordner=None, *, papierkorb=None, loeschen_fehler=None):
        self.ordner = {int(k): v for k, v in (ordner or {}).items()}
        self.papierkorb = papierkorb
        self.loeschen_fehler = loeschen_fehler
        self.aufrufe = []

    def __call__(self, url, params=None, timeout=None):
        params = dict(params or {})
        methode = url.rsplit("/", 1)[-1]
        self.aufrufe.append({"methode": methode, "url": url, "params": params, "timeout": timeout})
        if methode == "listfolder":
            kennung = params.get("folderid")
            if kennung not in self.ordner:
                raise AssertionError(f"Unerwarteter listfolder-Aufruf: folderid={kennung!r}")
            inhalt = self.ordner[kennung]
            if isinstance(inhalt, Exception):
                raise inhalt
            if isinstance(inhalt, dict):
                return Antwort(inhalt)
            return Antwort({"result": 0, "metadata": {"contents": list(inhalt)}})
        if methode == "deletefile":
            if self.loeschen_fehler is not None:
                if isinstance(self.loeschen_fehler, Exception):
                    raise self.loeschen_fehler
                return self.loeschen_fehler
            return Antwort({"result": 0})
        if methode == "trash_list":
            if self.papierkorb is None:
                raise AssertionError("trash_list war hier nicht erwartet")
            if isinstance(self.papierkorb, dict):
                return Antwort(self.papierkorb)
            return Antwort({"result": 0, "metadata": {"contents": list(self.papierkorb)}})
        raise AssertionError(f"Unerwartete Methode: {methode}")

    @property
    def methoden(self) -> list:
        """Die Methodennamen aller Aufrufe, in Reihenfolge."""
        return [a["methode"] for a in self.aufrufe]

    @property
    def loeschungen(self) -> list:
        """Die fileids aller deletefile-Aufrufe, in Reihenfolge."""
        return [a["params"].get("fileid") for a in self.aufrufe if a["methode"] == "deletefile"]


class Stolperfalle:
    """Kein Aufruf erlaubt — jeder Versuch fliegt auf."""

    def __call__(self, *args, **kwargs):
        raise AssertionError(f"Unerlaubter Netz-Aufruf: args={args!r} kwargs={kwargs!r}")


def mit_get(monkeypatch, *antworten, **kwargs) -> FakeGet:
    """httpx.get durch die Attrappe ersetzen (nach dem Test automatisch zurueck)."""
    fake = FakeGet(*antworten, **kwargs)
    monkeypatch.setattr(httpx, "get", fake)
    return fake


# ── Bauhilfen fuer Bericht und Ordner-Buch ────────────────────────────────

def _d(fileid, name, pfad, *, size=None, hashwert=None, baum="upload"):
    """Ein Datei-Eintrag im Bericht (Mitglied oder Kandidat)."""
    eintrag = {"fileid": fileid, "name": name, "pfad": pfad, "baum": baum}
    if size is not None:
        eintrag["size"] = size
    if hashwert is not None:
        eintrag["hash"] = hashwert
    return eintrag


def _bericht(gruppen, *, baeume=None) -> dict:
    """Einen Bericht wie aus ``pcloud_duplikate.py`` bauen (Gruppen -> Kandidaten)."""
    gebaute = []
    kandidaten = []
    for gruppe in gruppen:
        mitglieder = [dict(m) for m in gruppe["mitglieder"]]
        kandidaten_der_gruppe = [dict(k) for k in gruppe["kandidaten"]]
        gebaute.append(
            {
                "size": gruppe["size"],
                "hash": gruppe["hash"],
                "hash_text": str(gruppe["hash"]),
                "anzahl": len(mitglieder),
                "baeume": sorted({m["baum"] for m in mitglieder}),
                "art": gruppe.get("art", "innerhalb_upload"),
                "mitglieder": [
                    {"fileid": m["fileid"], "name": m["name"], "pfad": m["pfad"], "baum": m["baum"]}
                    for m in mitglieder
                ],
                "loesch_kandidaten": [
                    {"fileid": k["fileid"], "name": k["name"], "pfad": k["pfad"], "baum": k["baum"]}
                    for k in kandidaten_der_gruppe
                ],
            }
        )
        for k in kandidaten_der_gruppe:
            kandidaten.append(
                {
                    "fileid": k["fileid"],
                    "name": k["name"],
                    "pfad": k["pfad"],
                    "baum": k["baum"],
                    "size": gruppe["size"],
                    "hash": gruppe["hash"],
                    "gruppe_hash_text": str(gruppe["hash"]),
                }
            )
    return {
        "stand": STAND,
        "trocken": True,
        "werkzeug": "tools/pcloud/pcloud_duplikate.py",
        "baeume": baeume
        if baeume is not None
        else {
            "upload": {"gelesen": True, "name": "Automatic Upload", "folderid": UPLOAD_ID},
            "sammlung": {"gelesen": True, "name": "Bilder & Videos", "folderid": SAMMLUNG_ID},
        },
        "gruppen": gebaute,
        "loesch_kandidaten": {
            "dateien": len(kandidaten),
            "mb": round(sum(k["size"] for k in kandidaten) / 1_000_000, 1),
            "liste": kandidaten,
        },
        "zusammenfassung": {"duplikatgruppen": len(gebaute), "betroffene_dateien": len(kandidaten)},
    }


def _kandidaten_und_buch(anzahl, *, size=1_500_000):
    """N einfache Kandidaten (je eine Gruppe) samt passendem Ordner-Buch.

    Rueckgabe: (Bericht, ordner-Buch) — die Dateien liegen direkt im Baum-Ordner.
    """
    gruppen = []
    roh = []
    for i in range(anzahl):
        fileid = 7_000_000 + i
        name = f"kopie_{i:03d}.jpg"
        pfad = f"Automatic Upload/{name}"
        groesse = size + i
        hashwert = 5_500_000 + i
        gruppen.append(
            {
                "size": groesse,
                "hash": hashwert,
                "art": "innerhalb_upload",
                "mitglieder": [
                    _d(fileid, name, pfad, size=groesse, hashwert=hashwert),
                    _d(7_100_000 + i, f"original_{i:03d}.jpg", f"Automatic Upload/original_{i:03d}.jpg",
                       size=groesse, hashwert=hashwert),
                ],
                "kandidaten": [_d(fileid, name, pfad, size=groesse, hashwert=hashwert)],
            }
        )
        roh.append(_datei_roh(name, fileid, groesse, hashwert))
    return _bericht(gruppen), {UPLOAD_ID: roh}


def _datei_roh(name, fileid, size, hashwert, *, ordner_id=UPLOAD_ID):
    """Ein Datei-Eintrag, wie ihn ``listfolder`` liefert (Hash als Zahl)."""
    return {
        "name": name,
        "isfolder": False,
        "fileid": fileid,
        "folderid": ordner_id,
        "size": size,
        "hash": hashwert,
    }


def _ordner_roh(name, folderid):
    """Ein Ordner-Eintrag, wie ihn ``listfolder`` liefert."""
    return {"name": name, "isfolder": True, "folderid": folderid}


def _bericht_schreiben(tmp_path, bericht) -> Path:
    """Den Bericht als JSON-Datei ablegen (ausserhalb jedes Repos)."""
    ziel = tmp_path / "duplikate.json"
    ziel.write_text(json.dumps(bericht, ensure_ascii=False), encoding="utf-8")
    return ziel


def _zeilen(pfad: Path) -> list:
    """Die JSON-Zeilen einer Manifest-Datei (leer, wenn es sie nicht gibt)."""
    if not Path(pfad).exists():
        return []
    return [json.loads(z) for z in Path(pfad).read_text(encoding="utf-8").splitlines() if z.strip()]


@pytest.fixture
def umgebung(monkeypatch, tmp_path):
    """Token/Host aus der Umgebung; keine .env, kein Manifest aus der Umgebung."""
    monkeypatch.setenv("PCLOUD_TOKEN", TOKEN)
    monkeypatch.setenv("PCLOUD_HOST", HOST)
    monkeypatch.delenv("PCLOUD_MANIFEST", raising=False)
    monkeypatch.delenv("PCLOUD_DUPLIKATE_ZIEL", raising=False)
    monkeypatch.setattr(bewegen, "ENV_DATEI", tmp_path / "keine.env")


@pytest.fixture
def ohne_env(monkeypatch, tmp_path):
    """Weder Token noch Host gesetzt, keine .env-Datei vorhanden."""
    monkeypatch.delenv("PCLOUD_TOKEN", raising=False)
    monkeypatch.delenv("PCLOUD_HOST", raising=False)
    monkeypatch.delenv("PCLOUD_MANIFEST", raising=False)
    monkeypatch.delenv("PCLOUD_DUPLIKATE_ZIEL", raising=False)
    monkeypatch.setattr(bewegen, "ENV_DATEI", tmp_path / "keine.env")


@pytest.fixture
def mfad(tmp_path) -> Path:
    """Manifest-Pfad im Testverzeichnis (ausserhalb jedes Repos)."""
    return tmp_path / "manifest.jsonl"


def _lauf(bericht, tmp_path, mfad, *schalter):
    """Kurzweg: Bericht schreiben und main() mit Schaltern fahren."""
    pfad = _bericht_schreiben(tmp_path, bericht)
    return modul.main(["--bericht", str(pfad), "--manifest", str(mfad), *schalter])


# ── Reine Funktionen: Rueckweg, MB, Manifest-Zeile, Gegenprobe ────────────

def test_rueckweg_text_nennt_papierkorb_und_zuruecklegen():
    """Der Rueckweg steht im Klartext: Papierkorb, trash_list, trash_restore."""
    text = modul.rueckweg_text()
    assert "Papierkorb" in text
    assert "trash_list" in text and "trash_restore" in text
    assert "endgueltig" in text


def test_freigabe_mb_zwei_nachkommastellen():
    """1,5 MB + 0,5 MB = 2,0 MB — zwei Nachkommastellen, aufgerundet wird nicht."""
    kandidaten = [{"size": 1_500_000}, {"size": 500_000}, {"size": 1234}]
    assert modul.freigabe_mb(kandidaten) == round(2_001_234 / 1_000_000, 2)
    assert modul.freigabe_mb([{"size": 1_000}]) == 0.0
    assert modul.freigabe_mb([{"size": 1_500_000}, {"size": 500_000}]) == 2.0


def test_freigabe_mb_ohne_groesse_zaehlt_null():
    """Kaputte oder fehlende Groessen zaehlen als 0 — es wird nicht geschaetzt."""
    assert modul.freigabe_mb([{}, {"size": "viel"}, {"size": None}]) == 0.0
    assert modul.freigabe_mb([]) == 0.0


def test_manifest_zeile_hat_genau_die_sieben_felder():
    """Eine Manifest-Zeile traegt genau art, fileid, name, pfad, size, hash, zeit."""
    zeile = modul.manifest_zeile(
        {"fileid": 7, "name": "a.jpg", "pfad": "Automatic Upload/a.jpg", "size": 10, "hash": 99},
        "2026-09-28T05:00:00+02:00",
    )
    assert list(zeile) == ["art", "fileid", "name", "pfad", "size", "hash", "zeit"]
    assert zeile["art"] == "loeschen"
    assert zeile["fileid"] == 7 and zeile["size"] == 10 and zeile["hash"] == "99"
    assert zeile["zeit"] == "2026-09-28T05:00:00+02:00"


def test_manifest_zeile_mit_leeren_werten_wirft_nicht():
    """Ein leerer Kandidat ergibt eine harmlose Zeile (None/leer), keinen Absturz."""
    zeile = modul.manifest_zeile({}, "")
    assert zeile["fileid"] is None and zeile["size"] is None and zeile["hash"] is None
    assert zeile["name"] == "" and zeile["pfad"] == ""
    assert zeile["art"] == "loeschen"


def test_pruefe_kandidat_stimmt():
    """Gleiche Groesse UND gleiche Pruefsumme => ok."""
    urteil = modul.pruefe_kandidat({"size": 1000, "hash": 5}, {"size": 1000, "hash": 5})
    assert urteil["ok"] is True
    assert "stimmen" in urteil["grund"]


def test_pruefe_kandidat_abweichende_groesse():
    """Andere Groesse => nicht ok, mit beiden Zahlen im Klartext."""
    urteil = modul.pruefe_kandidat({"size": 1000, "hash": 5}, {"size": 1001, "hash": 5})
    assert urteil["ok"] is False
    assert "1000" in urteil["grund"] and "1001" in urteil["grund"]


def test_pruefe_kandidat_abweichender_hash():
    """Gleiche Groesse, andere Pruefsumme => nicht ok (kein Inhaltsbeweis)."""
    urteil = modul.pruefe_kandidat({"size": 1000, "hash": 5}, {"size": 1000, "hash": 6})
    assert urteil["ok"] is False
    assert "Pruefsumme" in urteil["grund"]


def test_pruefe_kandidat_nicht_auffindbar():
    """Keine live gelesenen Metadaten => nicht loeschen."""
    for seite in (None, {}, "kaputt"):
        urteil = modul.pruefe_kandidat({"size": 1000, "hash": 5}, seite)
        assert urteil["ok"] is False
    assert "nicht mehr auffindbar" in modul.pruefe_kandidat({"size": 1000, "hash": 5}, None)["grund"]


def test_pruefe_kandidat_ohne_berichtswerte():
    """Fehlt im Bericht Groesse oder Hash, wird nicht geloescht."""
    ohne_groesse = modul.pruefe_kandidat({"hash": 5}, {"size": 1, "hash": 5})
    ohne_hash = modul.pruefe_kandidat({"size": 1}, {"size": 1, "hash": 5})
    assert ohne_groesse["ok"] is False and "Groesse" in ohne_groesse["grund"]
    assert ohne_hash["ok"] is False and "Pruefsumme" in ohne_hash["grund"]


def test_grenze_klemmen():
    """Die Grenze ist hart auf 1…200 geklemmt."""
    assert modul.grenze_klemmen(25) == 25
    assert modul.grenze_klemmen(0) == 1
    assert modul.grenze_klemmen(-5) == 1
    assert modul.grenze_klemmen(10_000) == 200
    assert modul.grenze_klemmen("viel") == modul.GRENZE_STANDARD


# ── kandidaten_waehlen ────────────────────────────────────────────────────

def test_kandidaten_waehlen_alle_nimmt_nur_upload_kandidaten():
    """Gewaehlt werden nur die Kandidaten der Kandidatenliste (Upload)."""
    bericht = _bericht(
        [
            {
                "size": 1000,
                "hash": 5,
                "art": "innerhalb_upload",
                "mitglieder": [
                    _d(1, "a.jpg", "Automatic Upload/a.jpg", size=1000, hashwert=5),
                    _d(2, "b.jpg", "Automatic Upload/b.jpg", size=1000, hashwert=5),
                ],
                "kandidaten": [_d(2, "b.jpg", "Automatic Upload/b.jpg", size=1000, hashwert=5)],
            }
        ]
    )
    auswahl = modul.kandidaten_waehlen(bericht)
    assert [k["fileid"] for k in auswahl["kandidaten"]] == [2]
    assert auswahl["verweigert"] == [] and auswahl["uebersprungen"] == []
    assert auswahl["rest"] == 0


def test_kandidaten_waehlen_art_filter_und_uebersprungene():
    """--art engt ein; die anderen kommen ehrlich unter uebersprungen."""
    bericht = _bericht(
        [
            {
                "size": 1000,
                "hash": 5,
                "art": "ueber_baeume",
                "mitglieder": [
                    _d(1, "a.jpg", "Automatic Upload/a.jpg", size=1000, hashwert=5),
                    _d(2, "a.jpg", "Bilder & Videos/a.jpg", size=1000, hashwert=5, baum="sammlung"),
                ],
                "kandidaten": [_d(1, "a.jpg", "Automatic Upload/a.jpg", size=1000, hashwert=5)],
            },
            {
                "size": 2000,
                "hash": 6,
                "art": "innerhalb_upload",
                "mitglieder": [
                    _d(3, "c.jpg", "Automatic Upload/c.jpg", size=2000, hashwert=6),
                    _d(4, "c.jpg", "Automatic Upload/c2.jpg", size=2000, hashwert=6),
                ],
                "kandidaten": [_d(4, "c2.jpg", "Automatic Upload/c2.jpg", size=2000, hashwert=6)],
            },
        ]
    )
    nur_ueber = modul.kandidaten_waehlen(bericht, art="ueber_baeume")
    assert [k["fileid"] for k in nur_ueber["kandidaten"]] == [1]
    assert [e["fileid"] for e in nur_ueber["uebersprungen"]] == [4]
    assert "art ist ueber_baeume" in nur_ueber["uebersprungen"][0]["grund"]

    nur_innerhalb = modul.kandidaten_waehlen(bericht, art="innerhalb_upload")
    assert [k["fileid"] for k in nur_innerhalb["kandidaten"]] == [4]
    assert len(modul.kandidaten_waehlen(bericht, art="alle")["kandidaten"]) == 2


def test_kandidaten_waehlen_unbekannte_art_wird_abgewiesen():
    """Eine unbekannte Art ist ein Bedienfehler (Klartext)."""
    with pytest.raises(modul.DuplikateLoeschFehler) as fehler:
        modul.kandidaten_waehlen(_bericht([]), art="alles")
    assert "alles" in str(fehler.value)
    assert "alle" in str(fehler.value)


def test_kandidaten_waehlen_grenze_und_rest():
    """30 Kandidaten, Grenze 25 => 25 gewaehlt, rest = 5."""
    bericht, _ = _kandidaten_und_buch(30)
    auswahl = modul.kandidaten_waehlen(bericht, grenze=25)
    assert len(auswahl["kandidaten"]) == 25
    assert auswahl["rest"] == 5
    assert [k["fileid"] for k in auswahl["kandidaten"]] == [7_000_000 + i for i in range(25)]


def test_kandidaten_waehlen_grenze_wird_geklemmt():
    """Grenze 0 => 1, Grenze 10.000 => 200, kaputter Wert => Standard."""
    bericht, _ = _kandidaten_und_buch(3)
    assert len(modul.kandidaten_waehlen(bericht, grenze=0)["kandidaten"]) == 1
    assert modul.kandidaten_waehlen(bericht, grenze=0)["rest"] == 2
    assert len(modul.kandidaten_waehlen(bericht, grenze=10_000)["kandidaten"]) == 3
    assert modul.kandidaten_waehlen(_bericht([]), grenze="viel")["kandidaten"] == []


def test_kandidaten_waehlen_nur_dateien_engt_ein():
    """--nur-dateien: nur die genannten Kennungen kommen in Frage."""
    bericht, _ = _kandidaten_und_buch(3)
    auswahl = modul.kandidaten_waehlen(bericht, nur_dateien=[7_000_002, 7_000_000])
    assert [k["fileid"] for k in auswahl["kandidaten"]] == [7_000_002, 7_000_000]
    assert auswahl["verweigert"] == [] and auswahl["rest"] == 0


def test_kandidaten_waehlen_nur_dateien_unbekannte_kennung_verweigert():
    """Eine Kennung, die nicht im Bericht steht, wird verweigert."""
    bericht, _ = _kandidaten_und_buch(2)
    auswahl = modul.kandidaten_waehlen(bericht, nur_dateien=[999_999])
    assert auswahl["kandidaten"] == []
    assert len(auswahl["verweigert"]) == 1
    assert "steht nicht im Bericht" in auswahl["verweigert"][0]["grund"]


def test_kandidaten_waehlen_nur_dateien_sammlung_verweigert():
    """Ein Sammlungs-Original wird auch per --nur-dateien verweigert."""
    bericht = _bericht(
        [
            {
                "size": 1000,
                "hash": 5,
                "art": "ueber_baeume",
                "mitglieder": [
                    _d(1, "a.jpg", "Automatic Upload/a.jpg", size=1000, hashwert=5),
                    _d(2, "a.jpg", "Bilder & Videos/a.jpg", size=1000, hashwert=5, baum="sammlung"),
                ],
                "kandidaten": [_d(1, "a.jpg", "Automatic Upload/a.jpg", size=1000, hashwert=5)],
            }
        ]
    )
    auswahl = modul.kandidaten_waehlen(bericht, nur_dateien=[2])
    assert auswahl["kandidaten"] == []
    assert len(auswahl["verweigert"]) == 1
    assert auswahl["verweigert"][0]["baum"] == "sammlung"
    assert "Sammlung" in auswahl["verweigert"][0]["grund"] or "Kandidat" in auswahl["verweigert"][0]["grund"]


def test_kandidaten_waehlen_ueberspringt_ohne_hash_oder_groesse():
    """Kandidaten ohne Groesse/Pruefsumme sind nicht loeschbar (uebersprungen)."""
    bericht = _bericht(
        [
            {
                "size": 1000,
                "hash": 5,
                "art": "innerhalb_upload",
                "mitglieder": [
                    _d(1, "a.jpg", "Automatic Upload/a.jpg", size=1000, hashwert=5),
                    _d(2, "b.jpg", "Automatic Upload/b.jpg", size=1000, hashwert=5),
                ],
                "kandidaten": [_d(2, "b.jpg", "Automatic Upload/b.jpg", size=1000, hashwert=5)],
            }
        ]
    )
    # Kandidat ohne Hash direkt in der Liste (so kaeme er aus einem kaputten Bericht).
    bericht["loesch_kandidaten"]["liste"].append(
        {"fileid": 3, "name": "c.jpg", "pfad": "Automatic Upload/c.jpg", "baum": "upload", "size": 10}
    )
    auswahl = modul.kandidaten_waehlen(bericht)
    assert [k["fileid"] for k in auswahl["kandidaten"]] == [2]
    assert [e["fileid"] for e in auswahl["uebersprungen"]] == [3]
    assert "Pruefsumme" in auswahl["uebersprungen"][0]["grund"]


def test_kandidaten_waehlen_verweigert_kandidaten_aus_der_sammlung():
    """Steht ein Sammlungs-Eintrag in der Kandidatenliste, wird verweigert."""
    bericht = _bericht([])
    bericht["loesch_kandidaten"]["liste"].append(
        {"fileid": 9, "name": "x.jpg", "pfad": "Bilder & Videos/x.jpg", "baum": "sammlung",
         "size": 1000, "hash": 5}
    )
    auswahl = modul.kandidaten_waehlen(bericht)
    assert auswahl["kandidaten"] == []
    assert len(auswahl["verweigert"]) == 1


# ── Bericht laden, Kennungsdatei lesen ────────────────────────────────────

def test_bericht_laden_fehlt_klare_meldung(tmp_path):
    """Ein fehlender Bericht ist Klartext, kein Traceback."""
    with pytest.raises(modul.DuplikateLoeschFehler) as fehler:
        modul.bericht_laden(str(tmp_path / "gibtsnicht.json"))
    assert "nicht gefunden" in str(fehler.value)
    assert "pcloud_duplikate.py" in str(fehler.value)


def test_bericht_laden_kaputt_oder_kein_objekt(tmp_path):
    """Kaputtes JSON und eine blanke Liste werden abgewiesen."""
    kaputt = tmp_path / "kaputt.json"
    kaputt.write_text("{das ist kein json", encoding="utf-8")
    with pytest.raises(modul.DuplikateLoeschFehler) as fehler:
        modul.bericht_laden(str(kaputt))
    assert "kein gueltiges JSON" in str(fehler.value)

    liste = tmp_path / "liste.json"
    liste.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(modul.DuplikateLoeschFehler) as fehler:
        modul.bericht_laden(str(liste))
    assert "kein Objekt" in str(fehler.value)

    gut = tmp_path / "gut.json"
    gut.write_text('{"stand": "2026-09-27"}', encoding="utf-8")
    daten, pfad = modul.bericht_laden(str(gut))
    assert daten["stand"] == "2026-09-27" and Path(pfad).is_absolute()


def test_kennungen_aus_datei_liest_zahlen_und_kommentare(tmp_path):
    """Eine Kennung je Zeile; '#'-Kommentar und Leerzeilen sind erlaubt."""
    datei = tmp_path / "nur.txt"
    datei.write_text(
        "# Freigabe vom 28.09.2026\n7000000\n\n  7000001  # zweite Kopie\n7000000\n",
        encoding="utf-8",
    )
    assert modul.kennungen_aus_datei(str(datei)) == [7_000_000, 7_000_001]


def test_kennungen_aus_datei_kaputte_zeile_und_leere_datei(tmp_path):
    """Unbrauchbare Zeilen brechen mit Zeilennummer ab; leer heisst Abbruch."""
    kaputt = tmp_path / "kaputt.txt"
    kaputt.write_text("7000000\nkeine-zahl\n", encoding="utf-8")
    with pytest.raises(modul.DuplikateLoeschFehler) as fehler:
        modul.kennungen_aus_datei(str(kaputt))
    assert "Zeile 2" in str(fehler.value)

    leer = tmp_path / "leer.txt"
    leer.write_text("# nichts\n\n", encoding="utf-8")
    with pytest.raises(modul.DuplikateLoeschFehler) as fehler:
        modul.kennungen_aus_datei(str(leer))
    assert "keine Kennung" in str(fehler.value)

    fehlt = tmp_path / "fehlt.txt"
    with pytest.raises(modul.DuplikateLoeschFehler) as fehler:
        modul.kennungen_aus_datei(str(fehlt))
    assert "nicht lesbar" in str(fehler.value)


# ── Positivliste, Quelltext, Geheimnis ────────────────────────────────────

def test_positivliste_ist_exakt():
    """Erlaubt sind genau drei Methoden — das Entfernen ganzer Ordner nicht."""
    assert modul.ERLAUBTE_METHODEN == ("listfolder", "deletefile", "trash_list")
    verboten = "del" + "ete" + "folder"
    assert verboten not in modul.ERLAUBTE_METHODEN


def test_positivliste_weist_fremde_methode_ab(umgebung, monkeypatch):
    """Eine fremde Methode wird abgewiesen, BEVOR etwas gesendet wird."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    for fremd in ("del" + "ete" + "folder", "move" + "file", "trash" + "_restore", "copy" + "file"):
        with pytest.raises(modul.DuplikateLoeschFehler) as fehler:
            modul._api_senden(fremd, {}, token=TOKEN, host=HOST)
        assert "Positivliste" in str(fehler.value)


def test_nur_methoden_der_positivliste_im_quelltext():
    """Jeder gesendete Methodenname steht als fester Text auf der Positivliste."""
    baum = ast.parse(WERKZEUG_PFAD.read_text(encoding="utf-8"))
    gefunden = set()
    for knoten in ast.walk(baum):
        if (
            isinstance(knoten, ast.Call)
            and isinstance(knoten.func, ast.Name)
            and knoten.func.id == "_api_senden"
        ):
            erster = knoten.args[0] if knoten.args else None
            assert isinstance(erster, ast.Constant) and isinstance(erster.value, str), (
                "Der Methodenname muss ein fester Text sein (kein Zusammensetzen zur Laufzeit)."
            )
            gefunden.add(erster.value)
    assert gefunden == set(modul.ERLAUBTE_METHODEN)


def _verbotene_namen() -> tuple:
    """Verbotene Aufrufe — zusammengesetzt, damit dieser Test sie nicht selbst traegt."""
    return (
        "del" + "ete" + "folder",
        "move" + "file",
        "move" + "folder",
        "rename" + "file",
        "rename" + "folder",
        "copy" + "file",
        "un" + "link",
        "rm" + "tree",
    )


def test_keine_verbotenen_befehle_im_quelltext():
    """Suchtest: nichts loeschen/verschieben/umbenennen ausser deletefile."""
    for pfad in (WERKZEUG_PFAD, Path(__file__)):
        text = pfad.read_text(encoding="utf-8").lower()
        for wort in _verbotene_namen():
            assert wort not in text, f"{pfad.name} enthaelt {wort!r}"


def test_kein_download_im_quelltext():
    """Suchtest: kein Herunterladen von Inhalten — nur Metadaten."""
    text = WERKZEUG_PFAD.read_text(encoding="utf-8").lower()
    verboten = (
        "get" + "filelink",
        "get" + "thumbs",
        "datei" + "_bytes",
        "iter_bytes",
        "content=",
        "'wb'",
        '"wb"',
        ".write(b",
    )
    for wort in verboten:
        assert wort not in text, f"Werkzeug enthaelt {wort!r}"
    # Kein Rueckholen: trash_restore darf nur als Text im Rueckweg-Satz stehen.
    assert "_api_senden(\"trash" + "_restore\"" not in text


def test_manifest_art_loeschen_ist_beim_nachbarn_erlaubt():
    """Die Art 'loeschen' ist dem Nachbarmodul bekannt (sonst gaebe es keine Zeile)."""
    assert modul.MANIFEST_ART == "loeschen"
    assert modul.MANIFEST_ART in bewegen.ERLAUBTE_ARTEN


def test_manifest_anhaengen_akzeptiert_die_loeschzeile(umgebung, mfad):
    """Das Nachbarmodul nimmt die Zeile an — genau EINE Zeile, anhaengend."""
    modul.manifest_buchen(
        {"fileid": 7, "name": "a.jpg", "pfad": "Automatic Upload/a.jpg", "size": 10, "hash": 99},
        zeit=STAND,
        pfad=mfad,
    )
    modul.manifest_buchen(
        {"fileid": 8, "name": "b.jpg", "pfad": "Automatic Upload/b.jpg", "size": 20, "hash": 98},
        zeit=STAND,
        pfad=mfad,
    )
    zeilen = _zeilen(mfad)
    assert [z["art"] for z in zeilen] == ["loeschen", "loeschen"]
    assert zeilen[0]["fileid"] == 7 and zeilen[0]["hash"] == "99"
    assert mfad.read_text(encoding="utf-8").count("\n") == 2


def test_manifest_im_repo_wird_abgelehnt(tmp_path):
    """Ein Manifest-Pfad in einem Git-Repo wird verweigert — nichts entsteht."""
    (tmp_path / ".git").mkdir()
    pfad = tmp_path / "unter" / "manifest.jsonl"
    with pytest.raises(modul.DuplikateLoeschFehler) as fehler:
        modul.manifest_ort_pruefen(str(pfad))
    assert "Repo" in str(fehler.value)
    assert not pfad.exists()


# ── Trockenlauf (CLI) ─────────────────────────────────────────────────────

def test_trockenlauf_sendet_ueberhaupt_nichts(umgebung, monkeypatch, mfad, tmp_path):
    """Trockenlauf: kein einziger Netz-Aufruf (Stolperfalle im Weg), Exit 0."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    bericht, _ = _kandidaten_und_buch(3)
    assert _lauf(bericht, tmp_path, mfad) == 0
    assert not mfad.exists()


def test_trockenlauf_zeigt_zahlen_modus_und_kandidaten(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """Die Konsole nennt Zahlen, Modus, Beispiele (Name+Pfad) und den Rueckweg."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    bericht, _ = _kandidaten_und_buch(2)
    assert _lauf(bericht, tmp_path, mfad, "--beispiele", "2") == 0
    aus = capsys.readouterr().out
    assert "Modus: TROCKENLAUF" in aus
    assert "Geloescht: 0" in aus
    assert "Geprueft (gewaehlte Kandidaten): 2" in aus
    assert "kopie_000.jpg" in aus and "Automatic Upload/kopie_000.jpg" in aus
    assert "Rest: 0" in aus
    assert "trash_restore" in aus and "Papierkorb" in aus
    assert "Trockenlauf beendet" in aus


def test_trockenlauf_beispiele_begrenzt_und_rest_genannt(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """--beispiele 5 zeigt 5 Kandidaten, nennt aber die Gesamtzahl."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    bericht, _ = _kandidaten_und_buch(30)
    assert _lauf(bericht, tmp_path, mfad, "--grenze", "25", "--beispiele", "5") == 0
    aus = capsys.readouterr().out
    assert "Erste 5 Kandidaten von 25:" in aus
    assert "und 20 weitere" in aus
    assert "Rest: 5" in aus
    assert not mfad.exists()


def test_keine_kandidaten_ist_nichts_zu_tun(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """Leerer Bericht: geloescht 0, Exit 0, nichts gesendet."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    assert _lauf(_bericht([]), tmp_path, mfad) == 0
    aus = capsys.readouterr().out
    assert "nichts zu tun" in aus and "geloescht: 0" in aus
    assert not mfad.exists()


def test_bericht_fehlt_exit2(umgebung, mfad, tmp_path, capsys):
    """Fehlender Bericht: Exit 2 mit Klartext."""
    code = modul.main(["--bericht", str(tmp_path / "nix.json"), "--manifest", str(mfad)])
    assert code == 2
    assert "nicht gefunden" in capsys.readouterr().err
    assert not mfad.exists()


def test_unbekannte_art_exit2(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """--art mit falschem Wert: Exit 2, nichts gesendet."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    bericht, _ = _kandidaten_und_buch(2)
    assert _lauf(bericht, tmp_path, mfad, "--art", "irgendwas") == 2
    assert "irgendwas" in capsys.readouterr().err


def test_sammlung_kandidat_per_nur_dateien_exit2(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """Ein Sammlungs-Original per --nur-dateien: verweigert, Exit 2, nichts gesendet."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    bericht = _bericht(
        [
            {
                "size": 1000,
                "hash": 5,
                "art": "ueber_baeume",
                "mitglieder": [
                    _d(1, "a.jpg", "Automatic Upload/a.jpg", size=1000, hashwert=5),
                    _d(2, "a.jpg", "Bilder & Videos/a.jpg", size=1000, hashwert=5, baum="sammlung"),
                ],
                "kandidaten": [_d(1, "a.jpg", "Automatic Upload/a.jpg", size=1000, hashwert=5)],
            }
        ]
    )
    liste = tmp_path / "nur.txt"
    liste.write_text("2\n", encoding="utf-8")
    pfad = _bericht_schreiben(tmp_path, bericht)
    code = modul.main(
        ["--bericht", str(pfad), "--manifest", str(mfad), "--nur-dateien", str(liste)]
    )
    assert code == 2
    err = capsys.readouterr().err
    assert "VERWEIGERT" in err and "2" in err
    assert not mfad.exists()


def test_nur_dateien_unbekannte_kennung_exit2(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """Eine Kennung, die nicht im Bericht steht: verweigert, Exit 2."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    bericht, _ = _kandidaten_und_buch(2)
    liste = tmp_path / "nur.txt"
    liste.write_text("4711\n", encoding="utf-8")
    pfad = _bericht_schreiben(tmp_path, bericht)
    code = modul.main(["--bericht", str(pfad), "--manifest", str(mfad), "--nur-dateien", str(liste)])
    assert code == 2
    assert "VERWEIGERT" in capsys.readouterr().err


def test_papierkorb_im_trockenlauf_liest_nur(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """--papierkorb ruft im Trockenlauf NUR trash_list auf (lesend) und nennt die Zahl."""
    fake = mit_get(monkeypatch, papierkorb=[{}, {}, {}])
    bericht, _ = _kandidaten_und_buch(2)
    assert _lauf(bericht, tmp_path, mfad, "--papierkorb") == 0
    assert fake.methoden == ["trash_list"]
    aus = capsys.readouterr().out
    assert "Papierkorb: 3 Eintraege" in aus
    assert not mfad.exists()


def test_meldung_wenn_papierkorb_ohne_token(ohne_env, monkeypatch, mfad, tmp_path, capsys):
    """Ohne Token gibt es fuer den Papierkorb-Blick Klartext statt Netzaufruf."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    bericht, _ = _kandidaten_und_buch(2)
    assert _lauf(bericht, tmp_path, mfad, "--papierkorb") == 2
    assert "PCLOUD_TOKEN" in capsys.readouterr().err


def test_manifest_pfad_im_repo_exit2(umgebung, monkeypatch, tmp_path, capsys):
    """Manifest im Repo: Exit 2 VOR jedem Aufruf (nichts geloescht, nichts gebucht)."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    (tmp_path / ".git").mkdir()
    man = tmp_path / "unter" / "manifest.jsonl"
    bericht, _ = _kandidaten_und_buch(2)
    pfad = _bericht_schreiben(tmp_path, bericht)
    code = modul.main(["--bericht", str(pfad), "--manifest", str(man), "--wirklich"])
    assert code == 2
    assert "Repo" in capsys.readouterr().err
    assert not man.exists()


# ── Wirklicher Lauf ───────────────────────────────────────────────────────

def test_wirklich_loescht_und_bucht_genau_eine_zeile_je_datei(
    umgebung, monkeypatch, mfad, tmp_path
):
    """--wirklich: Gegenprobe stimmt => deletefile und genau eine Manifest-Zeile."""
    bericht, buch = _kandidaten_und_buch(2)
    fake = mit_get(monkeypatch, buch)
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 0

    assert fake.loeschungen == [7_000_000, 7_000_001]
    zeilen = _zeilen(mfad)
    assert len(zeilen) == 2
    # Die Pflichtfelder aus §3.4 sind da; die leeren Standardfelder des
    # Nachbarmoduls (folderid, von_pfad, ...) kommen beim Anhaengen dazu.
    assert {"art", "fileid", "name", "pfad", "size", "hash", "zeit"} <= set(zeilen[0])
    assert zeilen[0]["art"] == "loeschen"
    assert zeilen[0]["fileid"] == 7_000_000
    assert zeilen[0]["name"] == "kopie_000.jpg"
    assert zeilen[0]["pfad"] == "Automatic Upload/kopie_000.jpg"
    assert zeilen[0]["size"] == 1_500_000
    assert zeilen[0]["hash"] == "5500000"
    assert zeilen[0]["zeit"]
    assert zeilen[1]["fileid"] == 7_000_001


def test_wirklich_liest_zuerst_und_loescht_dann(umgebung, monkeypatch, mfad, tmp_path):
    """Reihenfolge je Datei: erst listfolder (Gegenprobe), dann deletefile."""
    bericht, buch = _kandidaten_und_buch(1)
    fake = mit_get(monkeypatch, buch)
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 0
    assert fake.methoden == ["listfolder", "deletefile"]
    assert fake.aufrufe[0]["params"]["folderid"] == UPLOAD_ID
    assert fake.aufrufe[1]["params"]["fileid"] == 7_000_000


def test_wirklich_meldet_zahlen_und_manifest(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """Die Abschlusszeile nennt geprueft, geloescht, MB, Fehler, Rest und das Manifest."""
    bericht, buch = _kandidaten_und_buch(2, size=1_500_000)
    mit_get(monkeypatch, buch)
    assert _lauf(bericht, tmp_path, mfad, "--wirklich", "--grenze", "25") == 0
    aus = capsys.readouterr().out
    assert "Modus: WIRKLICH" in aus
    assert "geloescht 2" in aus and "geprueft 2" in aus
    assert "freigegeben 3,00 MB" in aus
    assert f"Manifest: {mfad}" in aus
    assert "GELOESCHT (Papierkorb)" in aus


def test_wirklich_mit_unterordner_geht_den_pfad_nach(umgebung, monkeypatch, mfad, tmp_path):
    """Die Gegenprobe findet die Datei auch in einem Unterordner des Baums."""
    datei = _datei_roh("tief.jpg", 7_000_000, 1000, 5, ordner_id=UNTER_ID)
    bericht = _bericht(
        [
            {
                "size": 1000,
                "hash": 5,
                "art": "innerhalb_upload",
                "mitglieder": [
                    _d(7_000_000, "tief.jpg", "Automatic Upload/Duplikate/tief.jpg", size=1000, hashwert=5)
                ],
                "kandidaten": [
                    _d(7_000_000, "tief.jpg", "Automatic Upload/Duplikate/tief.jpg", size=1000, hashwert=5)
                ],
            }
        ]
    )
    buch = {UPLOAD_ID: [_ordner_roh("Duplikate", UNTER_ID)], UNTER_ID: [datei]}
    fake = mit_get(monkeypatch, buch)
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 0
    assert fake.loeschungen == [7_000_000]
    assert len(_zeilen(mfad)) == 1


def test_wirklich_abbruch_bei_abweichender_groesse(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """Andere Groesse als im Bericht: kein deletefile, keine Zeile, Exit 2."""
    bericht, buch = _kandidaten_und_buch(1)
    buch[UPLOAD_ID][0]["size"] = 1_500_001        # Bericht sagt 1.500.000
    fake = mit_get(monkeypatch, buch)
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 2
    assert fake.loeschungen == []
    assert not mfad.exists()
    aus = capsys.readouterr().out
    assert "ABBRUCH" in aus and "Groesse weicht ab" in aus


def test_wirklich_abbruch_bei_abweichendem_hash(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """Andere Pruefsumme als im Bericht: kein deletefile, keine Zeile, Exit 2."""
    bericht, buch = _kandidaten_und_buch(1)
    buch[UPLOAD_ID][0]["hash"] = 5_500_099
    fake = mit_get(monkeypatch, buch)
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 2
    assert fake.loeschungen == []
    assert not mfad.exists()
    assert "Pruefsumme weicht ab" in capsys.readouterr().out


def test_wirklich_abbruch_wenn_datei_nicht_mehr_auffindbar(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """Ist die Datei weg, wird abgebrochen — es wird nicht 'trotzdem' geloescht."""
    bericht, buch = _kandidaten_und_buch(1)
    buch[UPLOAD_ID] = []                          # Datei nicht mehr da
    fake = mit_get(monkeypatch, buch)
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 2
    assert fake.loeschungen == []
    assert not mfad.exists()
    assert "nicht mehr in ihrem Ordner" in capsys.readouterr().out


def test_wirklich_bricht_beim_zweiten_kandidaten_ab_behaelt_aber_die_erste_buchung(
    umgebung, monkeypatch, mfad, tmp_path, capsys
):
    """Der Abbruch stoppt den Rest — die vorherige Loeschung bleibt gebucht."""
    bericht, buch = _kandidaten_und_buch(3)
    buch[UPLOAD_ID][1]["size"] = 1_500_999        # Bericht sagt 1.500.001
    fake = mit_get(monkeypatch, buch)
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 2
    assert fake.loeschungen == [7_000_000]        # nur die erste, geprüfte Datei
    zeilen = _zeilen(mfad)
    assert len(zeilen) == 1 and zeilen[0]["fileid"] == 7_000_000
    aus = capsys.readouterr().out
    assert "Es wird nichts weiter geloescht." in aus


def test_wirklich_grenze_30_25_loescht_genau_25(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """30 Kandidaten, --grenze 25: genau 25 Loeschungen, rest = 5."""
    bericht, buch = _kandidaten_und_buch(30)
    fake = mit_get(monkeypatch, buch)
    assert _lauf(bericht, tmp_path, mfad, "--wirklich", "--grenze", "25") == 0
    assert len(fake.loeschungen) == 25
    assert len(_zeilen(mfad)) == 25
    assert 7_000_025 not in fake.loeschungen
    aus = capsys.readouterr().out
    assert "geloescht 25" in aus and "Rest 5" in aus


def test_grenze_wird_auch_beim_aufruf_geklemmt(umgebung, monkeypatch, mfad, tmp_path):
    """--grenze 100000 wird auf 200 geklemmt (hier: alle 3 Kandidaten)."""
    bericht, buch = _kandidaten_und_buch(3)
    fake = mit_get(monkeypatch, buch)
    assert _lauf(bericht, tmp_path, mfad, "--wirklich", "--grenze", "100000") == 0
    assert len(fake.loeschungen) == 3


def test_zweiter_lauf_ist_idempotent(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """Zweiter Lauf am selben Stand: 0 Loeschungen, 0 neue Zeilen, Exit 0."""
    bericht, buch = _kandidaten_und_buch(2)
    mit_get(monkeypatch, buch)
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 0
    vorher = mfad.read_text(encoding="utf-8")
    capsys.readouterr()

    monkeypatch.setattr(httpx, "get", Stolperfalle())      # nichts darf mehr gesendet werden
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 0
    assert mfad.read_text(encoding="utf-8") == vorher
    aus = capsys.readouterr().out
    assert "geloescht 0" in aus and "uebersprungen 2" in aus


def test_manifest_wird_nur_angehaengt(umgebung, monkeypatch, mfad, tmp_path):
    """Bestehende Manifest-Zeilen bleiben Zeichen fuer Zeichen unveraendert."""
    alt = '{"art": "move' + 'file", "name": "alt.jpg"}'
    mfad.write_text(alt + "\n", encoding="utf-8")
    bericht, buch = _kandidaten_und_buch(1)
    mit_get(monkeypatch, buch)
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 0
    zeilen = mfad.read_text(encoding="utf-8").splitlines()
    assert zeilen[0] == alt
    assert len(zeilen) == 2
    assert json.loads(zeilen[1])["art"] == "loeschen"


def test_manifest_kaputte_zeile_haelt_den_lauf_an(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """Ein unlesbares Manifest ist Grund zum Anhalten — nichts wird geloescht."""
    mfad.write_text("{kaputt\n", encoding="utf-8")
    bericht, buch = _kandidaten_und_buch(1)
    fake = mit_get(monkeypatch, buch)
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 2
    assert fake.loeschungen == []
    assert "kein gueltiges JSON" in capsys.readouterr().out


def test_pcloud_lehnt_deletefile_ab(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """Lehnt pCloud das Loeschen ab: Fehler zaehlen, anhalten, keine Zeile."""
    bericht, buch = _kandidaten_und_buch(2)
    fake = mit_get(
        monkeypatch, buch, loeschen_fehler=Antwort({"result": 2005, "error": "no permission"})
    )
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 2
    assert len(fake.loeschungen) == 1
    assert not mfad.exists()
    aus = capsys.readouterr().out
    assert "ABBRUCH" in aus and "abgelehnt" in aus and "2005" in aus


def test_ohne_token_klarer_fehler_ohne_netzaufruf(ohne_env, monkeypatch, mfad, tmp_path, capsys):
    """Ohne Token wird nichts gesendet und nichts geloescht — Klartext, Exit 2."""
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    bericht, _ = _kandidaten_und_buch(2)
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 2
    aus = capsys.readouterr().out
    assert "PCLOUD_TOKEN" in aus
    assert not mfad.exists()


# ── Geheimnis ─────────────────────────────────────────────────────────────

def test_token_taucht_nirgends_auf(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """Der Token steht in keiner Ausgabe, keiner Manifest-Zeile und keiner Datei."""
    bericht, buch = _kandidaten_und_buch(2)
    mit_get(monkeypatch, buch)
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 0
    aus = capsys.readouterr()
    assert TOKEN not in aus.out and TOKEN not in aus.err
    assert TOKEN not in mfad.read_text(encoding="utf-8")
    assert TOKEN not in WERKZEUG_PFAD.read_text(encoding="utf-8")


def test_fehlertext_mit_token_wird_maskiert(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """Ein Anbieter-Fehlertext mit Token kommt maskiert an — nie im Klartext."""
    bericht, buch = _kandidaten_und_buch(1)
    mit_get(
        monkeypatch,
        buch,
        loeschen_fehler=Antwort({"result": 2005, "error": f"kaputt {TOKEN}"}),
    )
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 2
    aus = capsys.readouterr()
    gesamt = aus.out + aus.err
    assert TOKEN not in gesamt
    assert "***" in gesamt


def test_netzfehler_nennt_nur_die_klasse(umgebung, monkeypatch, mfad, tmp_path, capsys):
    """Ein Transportfehler nennt nur den Klassen-Namen, nie die volle URL."""
    bericht, buch = _kandidaten_und_buch(1)
    mit_get(monkeypatch, buch, loeschen_fehler=httpx.ConnectError(f"kaputt bei auth={TOKEN}"))
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 2
    gesamt = "".join(capsys.readouterr())
    assert "ConnectError" in gesamt and TOKEN not in gesamt


# ── Frische der Gegenprobe (Pruefer-Beanstandung Runde 1, behoben) ────────

class FrischWechsel:
    """Attrappe, die bei jedem ``listfolder`` einen ANDEREN Ordnerinhalt liefert.

    Damit laesst sich beweisen, dass die Gegenprobe wirklich frisch liest:
    ein Zwischenspeicher wuerde den zweiten Inhalt nie sehen.
    """

    def __init__(self, *inhalte):
        self.inhalte = [list(inhalt) for inhalt in inhalte]
        self.aufrufe = []

    def __call__(self, url, params=None, timeout=None):
        methode = url.rsplit("/", 1)[-1]
        self.aufrufe.append({"methode": methode, "params": dict(params or {})})
        if methode == "listfolder":
            inhalt = self.inhalte.pop(0) if len(self.inhalte) > 1 else self.inhalte[0]
            return Antwort({"result": 0, "metadata": {"contents": list(inhalt)}})
        if methode == "deletefile":
            return Antwort({"result": 0})
        raise AssertionError(f"Unerwartete Methode: {methode}")

    @property
    def anzahl(self) -> int:
        return sum(1 for a in self.aufrufe if a["methode"] == "listfolder")


def test_livepruefer_liest_jeden_ordner_frisch(umgebung, monkeypatch):
    """Zwei Kandidaten im selben Ordner ⇒ zwei listfolder-Aufrufe (kein Zwischenspeicher)."""
    bericht, buch = _kandidaten_und_buch(2)
    fake = mit_get(monkeypatch, buch)
    pruefer = modul.LivePruefer(bericht)
    kandidaten = modul.kandidaten_waehlen(bericht)["kandidaten"]
    assert len(kandidaten) == 2
    for kandidat in kandidaten:
        lage = pruefer.stand(kandidat)
        assert lage["gefunden"] is True
    assert fake.methoden.count("listfolder") == 2


def test_zweite_gegenprobe_sieht_geaenderten_hash_und_bricht_ab(
    umgebung, monkeypatch, mfad, tmp_path, capsys
):
    """Aendert sich der Hash zwischen zwei Kandidaten, haelt der Lauf an.

    Erst der frische zweite Blick deckt das auf: mit einem Zwischenspeicher
    waere die Aenderung unsichtbar und die zweite Datei trotzdem geloescht
    worden — genau die Beanstandung, die dieser Test festnagelt.
    """
    bericht, buch = _kandidaten_und_buch(2)
    roh = buch[UPLOAD_ID]
    erster = list(roh)
    zweiter = [dict(roh[0]), dict(roh[1], hash=roh[1]["hash"] + 1)]
    fake = FrischWechsel(erster, zweiter)
    monkeypatch.setattr(httpx, "get", fake)
    assert _lauf(bericht, tmp_path, mfad, "--wirklich") == 2
    assert fake.anzahl == 2, "die zweite Gegenprobe muss frisch gelesen werden"
    geloescht = [a["params"].get("fileid") for a in fake.aufrufe if a["methode"] == "deletefile"]
    assert geloescht == [7_000_000], "nur die erste Datei darf geloescht sein"
    assert len(_zeilen(mfad)) == 1, "nur die erste Loeschung darf gebucht sein"
    gesamt = "".join(capsys.readouterr())
    assert "ABBRUCH" in gesamt or "Abweichung" in gesamt
