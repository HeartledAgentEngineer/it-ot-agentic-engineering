"""Pruefungen fuer das pCloud-Rueckroll-Werkzeug — alles OHNE Netz.

Geprueft werden: die Anzeige (--zeigen), der Trockenlauf (sendet NICHTS),
die umgekehrte Reihenfolge, das echte Rueckwaertsfahren (httpx durch
Attrappen ersetzt), das Verhalten bei angelegten Ordnern (bleiben bestehen),
die Lesepruefung vor jeder Rueckrollung, Fehlerwege und der Suchtest ueber
den eigenen Quelltext (kein Entfernungs-Befehl). Der Test-Token ist erfunden.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_pcloud_rueckrollen.py -q
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

PROJEKT = Path(__file__).resolve().parents[2]
TOOLS = PROJEKT / "tools" / "pcloud"
BEWEGUNGEN_PFAD = TOOLS / "pcloud_bewegungen.py"
RUCKROLL_PFAD = TOOLS / "pcloud_rueckrollen.py"


def _laden(name: str, pfad: Path):
    """Ein Werkzeug als Modul laden und unter seinem Namen registrieren."""
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"Werkzeug nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    sys.modules[name] = modul
    spez.loader.exec_module(modul)
    return modul


# Erst das Bewegungs-Modul (die CLI importiert es beim Laden ueber sys.modules).
bewegen = _laden("pcloud_bewegungen", BEWEGUNGEN_PFAD)
cli = _laden("pcloud_rueckrollen", RUCKROLL_PFAD)

TOKEN = "test-token-nicht-echt-39-zeichen-abcdefg"
HOST = "eapi.test.example"
ZEIT = "2026-09-27T05:00:00+02:00"


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
    return Antwort({"result": 0, **felder})


def _liste(*eintraege) -> Antwort:
    return _ok(metadata={"contents": list(eintraege)})


def _datei(name: str, kennung: int) -> dict:
    return {"name": name, "isfolder": False, "fileid": kennung}


def _eintrag(art, name="x", *, fileid=None, folderid=None, von: "int | None" = 111,
             nach: "int | None" = 222) -> dict:
    """Ein vollstaendiger Manifest-Eintrag, wie ihn das Sicherheitsnetz schreibt."""
    return {
        "zeit": ZEIT, "art": art, "name": name,
        "fileid": fileid, "folderid": folderid,
        "von_folderid": von, "nach_folderid": nach,
        "von_pfad": None, "nach_pfad": None,
    }


def _schreibe(pfad: Path, eintraege) -> None:
    """Manifest-Zeilen direkt schreiben (unabhaengig vom Werkzeug)."""
    pfad.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in eintraege) + "\n",
        encoding="utf-8",
    )


def _zeilen(pfad: Path) -> list:
    if not pfad.exists():
        return []
    return [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]


@pytest.fixture
def mit_env(monkeypatch):
    """Token und Host fuer echte Laeufe aus der Umgebung (Testwerte, kein Netz)."""
    monkeypatch.setenv("PCLOUD_TOKEN", TOKEN)
    monkeypatch.setenv("PCLOUD_HOST", HOST)


# ── --zeigen ───────────────────────────────────────────────────────────────

def test_zeigen_listet_nummeriert_und_zaehlt(tmp_path, capsys):
    """Nummerierte Liste (Zeit, Art, Name, von -> nach) + Zaehlung am Ende."""
    mfad = tmp_path / "manifest.jsonl"
    _schreibe(mfad, [
        _eintrag("createfolder", "2025", folderid=333, von=None),
        _eintrag("movefile", "a.jpg", fileid=11),
        _eintrag("movefile", "b.jpg", fileid=12),
        _eintrag("rueckroll", "a.jpg", fileid=11, von=222, nach=111),
    ])

    code = cli.main(["--zeigen", "--manifest", str(mfad)])
    aus = capsys.readouterr().out

    assert code == 0
    assert "   1  " in aus and "   4  " in aus          # nummeriert
    assert "2026-09-27T05:00:00+02:00" in aus            # Zeit
    assert "a.jpg" in aus and "b.jpg" in aus and "2025" in aus
    assert "->" in aus
    assert "Eintraege gesamt: 4" in aus
    assert "noch offen/rueckholbar: 1" in aus            # b.jpg; a.jpg ist zurueck
    assert "Angelegte Ordner: 1" in aus
    assert "Rueckrollungen im Manifest: 1" in aus


def test_zeigen_ohne_manifest_ist_kein_fehler(tmp_path, capsys):
    """Ohne Manifest gibt es eine klare Meldung — kein Absturz."""
    code = cli.main(["--zeigen", "--manifest", str(tmp_path / "fehlt.jsonl")])
    aus = capsys.readouterr().out
    assert code == 0
    assert "Keine Eintraege" in aus


def test_rueckwaerts_ohne_manifest_exit_2(tmp_path, capsys):
    """--rueckwaerts auf ein fehlendes Manifest ist ein Bedienfehler."""
    code = cli.main(["--rueckwaerts", "1", "--manifest", str(tmp_path / "fehlt.jsonl")])
    assert code == 2
    assert "Kein Manifest" in capsys.readouterr().out


# ── Trockenlauf und Reihenfolge ────────────────────────────────────────────

def test_rueckwaerts_trockenlauf_sendet_nichts(tmp_path, capsys, monkeypatch):
    """Ohne --wirklich: kein einziger Netzaufruf, Manifest unveraendert."""
    mfad = tmp_path / "manifest.jsonl"
    _schreibe(mfad, [
        _eintrag("movefile", "a.jpg", fileid=1),
        _eintrag("movefile", "b.jpg", fileid=2),
    ])
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    vorher = mfad.read_text(encoding="utf-8")

    code = cli.main(["--rueckwaerts", "2", "--manifest", str(mfad)])
    aus = capsys.readouterr().out

    assert code == 0
    assert "Trockenlauf" in aus
    assert aus.count("WUERDE ZURUECK") == 2
    assert mfad.read_text(encoding="utf-8") == vorher


def test_rueckroll_reihenfolge_ist_umgekehrt():
    """Der Plan faehrt die Aktionen in umgekehrter Reihenfolge (neueste zuerst)."""
    eintraege = [
        _eintrag("movefile", "alt.jpg", fileid=1),
        _eintrag("createfolder", "2025", folderid=333, von=None),
        _eintrag("movefile", "neu.jpg", fileid=2),
    ]
    schritte = cli.rueckroll_plan(eintraege, 3)

    assert [s["art"] for s in schritte] == ["movefile", "createfolder", "movefile"]
    assert [s["kennung"] for s in schritte if s["machbar"]] == [2, 1]


def test_wirklich_faehrt_in_umgekehrter_reihenfolge_und_bucht_rueckroll(
        tmp_path, capsys, monkeypatch, mit_env):
    """Echt: renamefile je Verschiebung, neueste zuerst, art=rueckroll gebucht."""
    mfad = tmp_path / "manifest.jsonl"
    _schreibe(mfad, [
        _eintrag("movefile", "a.jpg", fileid=1),
        _eintrag("movefile", "b.jpg", fileid=2),
    ])
    fake = mit_get(
        monkeypatch,
        _liste(_datei("b.jpg", 2)), _liste(), _ok(metadata={}),   # Schritt b.jpg
        _liste(_datei("a.jpg", 1)), _liste(), _ok(metadata={}),   # Schritt a.jpg
    )

    code = cli.main(["--rueckwaerts", "2", "--wirklich", "--manifest", str(mfad)])
    aus = capsys.readouterr().out

    assert code == 0
    assert "2 rueckwaerts gefahren" in aus
    renamefile = [a for a in fake.aufrufe if a["url"].endswith("/renamefile")]
    assert [a["params"]["fileid"] for a in renamefile] == [2, 1]   # neueste zuerst
    assert [a["params"]["tofolderid"] for a in renamefile] == [111, 111]

    zeilen = _zeilen(mfad)
    assert len(zeilen) == 4                                       # 2 + 2 Rueckrollungen
    neu = zeilen[2:]
    assert all(z["art"] == "rueckroll" for z in neu)
    assert neu[0]["fileid"] == 2 and neu[0]["von_folderid"] == 222 and neu[0]["nach_folderid"] == 111
    assert neu[1]["fileid"] == 1


# ── Ordner bleiben bestehen, Lesepruefung, Randfaelle ──────────────────────

def test_angelegter_ordner_bleibt_bestehen(tmp_path, capsys, monkeypatch):
    """createfolder ist nicht rueckholbar: nur melden, nichts senden."""
    mfad = tmp_path / "manifest.jsonl"
    _schreibe(mfad, [_eintrag("createfolder", "2025", folderid=333, von=None)])
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    vorher = mfad.read_text(encoding="utf-8")

    code = cli.main(["--rueckwaerts", "1", "--wirklich", "--manifest", str(mfad)])
    aus = capsys.readouterr().out

    assert code == 0
    assert "bleibt bestehen" in aus
    assert "1 nur gemeldet" in aus
    assert mfad.read_text(encoding="utf-8") == vorher


def test_ueberspringt_wenn_nicht_mehr_im_ordner(tmp_path, capsys, monkeypatch, mit_env):
    """Lesepruefung: liegt das Element nicht (mehr) im Zielordner, nichts tun."""
    mfad = tmp_path / "manifest.jsonl"
    _schreibe(mfad, [_eintrag("movefile", "a.jpg", fileid=1)])
    fake = mit_get(monkeypatch, _liste())                          # Zielordner leer
    vorher = mfad.read_text(encoding="utf-8")

    code = cli.main(["--rueckwaerts", "1", "--wirklich", "--manifest", str(mfad)])
    aus = capsys.readouterr().out

    assert code == 0
    assert "UEBERSPRUNGEN" in aus
    assert len(fake.aufrufe) == 1                                  # nur die Lesepruefung
    assert mfad.read_text(encoding="utf-8") == vorher


def test_bereits_zurueckgeholt_wird_gemeldet(tmp_path, capsys, monkeypatch):
    """Eine schon gebuchte Rueckrollung wird erkannt und nicht doppelt gefahren."""
    mfad = tmp_path / "manifest.jsonl"
    _schreibe(mfad, [
        _eintrag("movefile", "a.jpg", fileid=1),
        _eintrag("rueckroll", "a.jpg", fileid=1, von=222, nach=111),
    ])
    monkeypatch.setattr(httpx, "get", Stolperfalle())

    assert cli.main(["--zeigen", "--manifest", str(mfad)]) == 0
    assert "noch offen/rueckholbar: 0" in capsys.readouterr().out

    code = cli.main(["--rueckwaerts", "1", "--wirklich", "--manifest", str(mfad)])
    aus = capsys.readouterr().out
    assert code == 0
    assert "bereits zurueckgeholt" in aus


def test_unvollstaendiger_eintrag_wird_nicht_angefasst(tmp_path, capsys, monkeypatch):
    """Ohne Quellordner-Id ist keine Rueckrollung moeglich — nur melden."""
    mfad = tmp_path / "manifest.jsonl"
    _schreibe(mfad, [_eintrag("movefile", "a.jpg", fileid=1, von=None)])
    monkeypatch.setattr(httpx, "get", Stolperfalle())

    code = cli.main(["--rueckwaerts", "1", "--wirklich", "--manifest", str(mfad)])
    aus = capsys.readouterr().out

    assert code == 0
    assert "NICHT ANGEFASST" in aus
    assert "unvollstaendig" in aus


def test_zu_viele_angefordert_nimmt_die_vorhandenen(tmp_path, capsys, monkeypatch):
    """N groesser als der Bestand: alle nehmen, mit Hinweis."""
    mfad = tmp_path / "manifest.jsonl"
    _schreibe(mfad, [
        _eintrag("movefile", "a.jpg", fileid=1),
        _eintrag("movefile", "b.jpg", fileid=2),
    ])
    monkeypatch.setattr(httpx, "get", Stolperfalle())

    code = cli.main(["--rueckwaerts", "5", "--manifest", str(mfad)])
    aus = capsys.readouterr().out

    assert code == 0
    assert "es gibt nur 2 Aktionen" in aus
    assert aus.count("WUERDE ZURUECK") == 2


def test_kaputte_manifest_zeile_klarer_fehler(tmp_path, capsys):
    """Eine kaputte Zeile stoppt ehrlich (mit Zeilennummer) statt zu raten."""
    mfad = tmp_path / "manifest.jsonl"
    mfad.write_text('{"art": "movefile"}\nKEIN JSON\n', encoding="utf-8")

    code = cli.main(["--zeigen", "--manifest", str(mfad)])
    assert code == 2
    assert "Zeile 2" in capsys.readouterr().out


# ── Fehlerwege ─────────────────────────────────────────────────────────────

def test_fehler_bricht_nicht_ab_und_ergibt_exit_3(tmp_path, capsys, monkeypatch, mit_env):
    """Ein Fehler stoppt den Rest nicht; am Ende steht Exit 3 und die Zaehlung."""
    mfad = tmp_path / "manifest.jsonl"
    _schreibe(mfad, [
        _eintrag("movefile", "a.jpg", fileid=1),
        _eintrag("movefile", "b.jpg", fileid=2),
    ])
    mit_get(
        monkeypatch,
        _liste(_datei("b.jpg", 2)), _liste(),                          # Schritt b.jpg
        Antwort({"result": 2005, "error": "Directory does not exist."}),
        _liste(_datei("a.jpg", 1)), _liste(), _ok(metadata={}),        # Schritt a.jpg
    )

    code = cli.main(["--rueckwaerts", "2", "--wirklich", "--manifest", str(mfad)])
    aus = capsys.readouterr().out

    assert code == 3
    assert "FEHLER" in aus
    assert "1 rueckwaerts gefahren" in aus and "1 fehlgeschlagen" in aus
    neu = _zeilen(mfad)[2:]
    assert [z["fileid"] for z in neu] == [1]                           # nur a.jpg gebucht


def test_token_taucht_in_keiner_ausgabe_auf(tmp_path, capsys, monkeypatch, mit_env):
    """Auch ein Transportfehler mit Token im fremden Text gibt ihn nicht aus."""
    mfad = tmp_path / "manifest.jsonl"
    _schreibe(mfad, [_eintrag("movefile", "a.jpg", fileid=1)])
    mit_get(
        monkeypatch,
        _liste(_datei("a.jpg", 1)), _liste(),
        httpx.ConnectError(f"kaputt bei auth={TOKEN}"),
    )

    code = cli.main(["--rueckwaerts", "1", "--wirklich", "--manifest", str(mfad)])
    aus = capsys.readouterr().out

    assert code == 3
    assert TOKEN not in aus
    assert "ConnectError" in aus
    assert len(_zeilen(mfad)) == 1                                     # nichts gebucht


# ── Quelltextpruefung ──────────────────────────────────────────────────────

def test_rueckroll_cli_ohne_loeschbefehl_im_quelltext():
    """Suchtest: die verbotenen Namen kommen im Werkzeug nicht vor."""
    # Zusammengesetzt, damit dieser Test sie nicht selbst in die Datei traegt.
    verboten = ("del" + "ete" + "file", "del" + "ete" + "folder", "un" + "link")
    text = RUCKROLL_PFAD.read_text(encoding="utf-8").lower()
    for wort in verboten:
        assert wort not in text
