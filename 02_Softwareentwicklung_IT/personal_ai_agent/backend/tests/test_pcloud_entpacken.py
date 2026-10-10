"""Pruefungen fuer das Entpack-Werkzeug (Papas Amazon-Fotos) — alles OHNE Netz.

``httpx`` wird durch eine Attrappe ersetzt, die nach Methode antwortet und
jeden Aufruf mitschreibt. Damit laesst sich belegen, was der Trockenlauf NICHT
sendet und was der Schreiblauf genau sendet.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_pcloud_entpacken.py -q
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import httpx
import pytest

PROJEKT = Path(__file__).resolve().parents[2]
PC_ORDNER = PROJEKT / "tools" / "pcloud"


def _laden(name: str, pfad: Path):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"Werkzeug nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    sys.modules[name] = modul
    spez.loader.exec_module(modul)
    return modul


bewegungen = _laden("pcloud_bewegungen", PC_ORDNER / "pcloud_bewegungen.py")
entpacken = _laden("pcloud_entpacken", PC_ORDNER / "pcloud_entpacken.py")

TOKEN = "test-token-nicht-echt-39-zeichen-abcdefg"
HOST = "eapi.test.example"


# ── Attrappen ──────────────────────────────────────────────────────────────

class Antwort:
    def __init__(self, daten=None, *, status_code=200):
        self._daten = daten
        self.status_code = status_code

    def json(self):
        if self._daten is None:
            raise ValueError("keine JSON-Daten in dieser Attrappe")
        return self._daten


class Server:
    """Antwortet auf listfolder/createfolder/extractarchive und schreibt mit."""

    def __init__(self, *, ordner_vorhanden=(), kinder_vorhanden=0, naechste_ordnerid=5000):
        self.aufrufe = []
        self._ordner_vorhanden = set(ordner_vorhanden)
        self._kinder_vorhanden = kinder_vorhanden
        self._naechste = naechste_ordnerid

    def __call__(self, url, params=None, timeout=None):
        p = dict(params or {})
        methode = url.rsplit("/", 1)[-1]
        self.aufrufe.append({"methode": methode, "params": p, "timeout": timeout})

        if methode == "listfolder":
            if "path" in p:
                pfad = str(p["path"])
                return Antwort({"result": 0, "metadata": {
                    "folderid": 0 if pfad.strip() == "/" else 700,
                    "name": pfad.rsplit("/", 1)[-1] or "/",
                    "path": pfad,
                }})
            # Ein Zielordner: leer oder mit Kindern.
            if self._kinder_vorhanden:
                kinder = [{"name": f"bild{i}.jpg", "isfolder": False, "fileid": 9000 + i}
                          for i in range(self._kinder_vorhanden)]
            else:
                kinder = []
            return Antwort({"result": 0, "metadata": {"folderid": p.get("folderid"), "contents": kinder}})

        if methode == "createfolder":
            self._naechste += 1
            return Antwort({"result": 0, "metadata": {
                "folderid": self._naechste, "name": p.get("name"),
                "path": f"/Bilder & Videos/Papa (Amazon)/{p.get('name')}",
            }})

        if methode == "extractarchive":
            return Antwort({"result": 0, "metadata": {
                "folderid": p.get("tofolderid"), "path": "/Bilder & Videos/Papa (Amazon)/x",
            }, "taskid": 4242})

        raise AssertionError(f"Unerwartete Methode: {methode}")


def _mit_server(monkeypatch, server: Server) -> Server:
    monkeypatch.setattr(httpx, "get", server)
    return server


def _quelle_mit_archiven(*namen):
    """Ein listfolder-Ergebnis fuer den Quellordner bauen."""
    return [
        {"name": n, "ist_ordner": False, "fileid": 1000 + i, "folderid": None, "path": f"/AmazonPhotosvonPapa/{n}"}
        for i, n in enumerate(namen)
    ]


@pytest.fixture(autouse=True)
def _token_und_manifest(monkeypatch, tmp_path):
    """Token/Host aus der Umgebung, Manifest im Testverzeichnis (nicht im Repo)."""
    monkeypatch.setenv("PCLOUD_TOKEN", TOKEN)
    monkeypatch.setenv("PCLOUD_HOST", HOST)
    monkeypatch.setenv("PCLOUD_MANIFEST", str(tmp_path / "manifest.jsonl"))
    return tmp_path / "manifest.jsonl"


def _zeilen(pfad: Path):
    import json
    if not pfad.exists():
        return []
    return [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]


# ── Kleine Bausteine ───────────────────────────────────────────────────────

def test_ziel_name_ohne_endung():
    assert entpacken.ziel_name("AmazonPhotos (11).zip") == "AmazonPhotos (11)"
    assert entpacken.ziel_name("AmazonPhotos.zip") == "AmazonPhotos"
    assert entpacken.ziel_name("ohne_endung") == "ohne_endung"


def test_archiv_liste_nimmt_nur_archive_und_sortiert(monkeypatch):
    monkeypatch.setattr(bewegungen, "ordner_inhalt", lambda *a, **k: [
        {"name": "notiz.txt", "ist_ordner": False, "fileid": 1, "folderid": None, "path": None},
        {"name": "AmazonPhotos (10).zip", "ist_ordner": False, "fileid": 2, "folderid": None, "path": None},
        {"name": "AmazonPhotos (2).zip", "ist_ordner": False, "fileid": 3, "folderid": None, "path": None},
        {"name": "Unterordner", "ist_ordner": True, "fileid": None, "folderid": 9, "path": None},
    ])
    namen = [a["name"] for a in entpacken.archiv_liste(1, None, None)]
    assert namen == ["AmazonPhotos (10).zip", "AmazonPhotos (2).zip"]


# ── Trockenlauf ────────────────────────────────────────────────────────────

def test_trockenlauf_sendet_kein_entpacken(monkeypatch, capsys, _token_und_manifest):
    server = _mit_server(monkeypatch, Server())
    monkeypatch.setattr(entpacken, "archiv_liste", lambda *a, **k: _quelle_mit_archiven("A.zip", "B.zip"))

    assert entpacken.main([]) == 0
    ausgabe = capsys.readouterr().out

    assert "TROCKENLAUF" in ausgabe
    assert "Geplant: 2 Archive" in ausgabe
    assert all(a["methode"] == "listfolder" for a in server.aufrufe)
    assert not _zeilen(_token_und_manifest)


# ── Schreiben ──────────────────────────────────────────────────────────────

def test_schreiben_legt_ordner_an_und_entpackt(monkeypatch, capsys, _token_und_manifest):
    server = _mit_server(monkeypatch, Server())
    monkeypatch.setattr(entpacken, "archiv_liste", lambda *a, **k: _quelle_mit_archiven("A.zip"))

    assert entpacken.main(["--schreiben"]) == 0
    methoden = [a["methode"] for a in server.aufrufe]
    ausgabe = capsys.readouterr().out

    assert "entpackt:            1" in ausgabe
    assert methoden.count("extractarchive") == 1
    # Zielordner "Papa (Amazon)" + Unterordner "A" = zwei createfolder
    assert methoden.count("createfolder") == 2
    entpackt = [a for a in server.aufrufe if a["methode"] == "extractarchive"][0]
    assert entpackt["params"]["fileid"] == 1000
    assert entpackt["params"]["tofolderid"] == 5002
    zeilen = _zeilen(_token_und_manifest)
    assert [z["art"] for z in zeilen] == ["createfolder", "createfolder", "extractarchive"]
    assert TOKEN not in _token_und_manifest.read_text(encoding="utf-8")


def test_schreiben_ueberspringt_gefuelle_zielordner(monkeypatch, capsys, _token_und_manifest):
    """Idempotent: liegt im Zielordner schon etwas, wird nicht entpackt."""
    server = _mit_server(monkeypatch, Server(kinder_vorhanden=2))
    monkeypatch.setattr(entpacken, "archiv_liste", lambda *a, **k: _quelle_mit_archiven("A.zip"))

    assert entpacken.main(["--schreiben"]) == 0
    ausgabe = capsys.readouterr().out

    assert "uebersprungen:       1" in ausgabe
    assert "entpackt:            0" in ausgabe
    assert "extractarchive" not in [a["methode"] for a in server.aufrufe]


def test_nur_grenzt_auf_ein_archiv_ein(monkeypatch, capsys, _token_und_manifest):
    server = _mit_server(monkeypatch, Server())
    monkeypatch.setattr(
        entpacken, "archiv_liste",
        lambda *a, **k: _quelle_mit_archiven("AmazonPhotos (1).zip", "AmazonPhotos (35).zip"))

    assert entpacken.main(["--nur", "35", "--schreiben"]) == 0
    ausgabe = capsys.readouterr().out
    assert "Archive gesamt:      1" in ausgabe
    assert "entpackt:            1" in ausgabe
    assert [a["methode"] for a in server.aufrufe].count("extractarchive") == 1


def test_abbruch_wenn_quelle_fehlt(monkeypatch, capsys):
    class Kaputt(Server):
        def __call__(self, url, params=None, timeout=None):
            return Antwort({"result": 2055, "error": "Directory does not exist."})

    _mit_server(monkeypatch, Kaputt())
    assert entpacken.main([]) == 2
    assert "Abbruch" in capsys.readouterr().out


def test_pause_wartet_zwischen_den_archiven(monkeypatch, capsys, _token_und_manifest):
    """pCloud bricht bei einem Schwall mit Fehler 3006 ab (10.10.2026 gemessen:
    15 von 32). --pause legt zwischen zwei Archiven eine Wartezeit ein, aber
    NICHT nach dem letzten (sonst wartet der Lauf am Ende sinnlos)."""
    _mit_server(monkeypatch, Server())
    monkeypatch.setattr(
        entpacken, "archiv_liste",
        lambda *a, **k: _quelle_mit_archiven("A.zip", "B.zip", "C.zip"))

    gewartet = []
    monkeypatch.setattr(entpacken.time, "sleep", lambda s: gewartet.append(s))

    assert entpacken.main(["--schreiben", "--pause", "7.5"]) == 0
    assert gewartet == [7.5, 7.5]          # zwischen 1-2 und 2-3, nicht danach
    assert "entpackt:            3" in capsys.readouterr().out


def test_ohne_pause_kein_warteaufruf(monkeypatch, capsys, _token_und_manifest):
    """Standard bleibt ohne Wartezeit — der Probelauf soll schnell sein."""
    _mit_server(monkeypatch, Server())
    monkeypatch.setattr(entpacken, "archiv_liste", lambda *a, **k: _quelle_mit_archiven("A.zip"))

    gerufen = []
    monkeypatch.setattr(entpacken.time, "sleep", lambda s: gerufen.append(s))

    assert entpacken.main(["--schreiben"]) == 0
    assert gerufen == []
