"""Pruefungen fuer die kabellose Uebergabe ans Handy ueber pCloud (10.10.2026).

Alles OHNE Netz: httpx wird durch Attrappen ersetzt, das Shell-Skript laeuft in
einem Sandkasten mit einem Attrappen-``python`` (das die "geholten" Dateien
erzeugt). Es gibt keine Zugangsdaten und keine echten Dateien — nur erfundene
Daten in ``tmp_path``.

Abgedeckt:
  * Hochladen (PC): Trockenlauf sendet nichts, Schreiben ruft uploadfile und
    bucht eine Manifest-Zeile, gleiche Pruefsumme -> uebersprungen, Netzfehler
    -> klare Meldung ohne Absturz, Ziel nur unter /Agent/, Token nie ausgegeben.
  * Holen (Handy): listfolder + getfilelink + Download in ein Staging, leerer
    Ordner und fehlender Token -> keine Ausnahme.
  * Uebernehmen (Shell): gleiche Pruefsumme -> nichts, abweichend -> erst
    Sicherung, dann Kopie, Quelle fehlt -> Exit 0 mit Meldung, Reihenfolge der
    Protokollzeilen, Kollision der Sicherung (_2).
  * Einbindung in termux/start-vorbereiten.sh, `bash -n` und reine LF.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_pcloud_uebergabe.py -q
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import httpx
import pytest

PROJEKT = Path(__file__).resolve().parents[2]
HOCHLADEN_PFAD = PROJEKT / "tools" / "pcloud" / "uebergabe_hochladen.py"
HOLEN_PFAD = PROJEKT / "tools" / "handy" / "pcloud_dateien_holen.py"
TERMUX = PROJEKT / "termux"
UEBERNEHMEN = TERMUX / "pcloud-uebernehmen.sh"
SHARED = TERMUX / "start-vorbereiten.sh"
WIDGET = TERMUX / "agent-start"
APP = TERMUX / "agent-ensure.sh"


def _laden(name: str, pfad: Path):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"Werkzeug nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    sys.modules[name] = modul
    spez.loader.exec_module(modul)
    return modul


hochladen = _laden("uebergabe_hochladen", HOCHLADEN_PFAD)
holen = _laden("pcloud_dateien_holen", HOLEN_PFAD)

TOKEN = "test-token-nicht-echt-39-zeichen-abcdefg"
HOST = "eapi.test.example"


# ── Attrappen (kein Netz) ──────────────────────────────────────────────────

class Antwort:
    """Attrappe einer httpx-Antwort mit JSON-Daten (GET-Aufrufe)."""

    def __init__(self, daten=None, *, status_code=200, content=b""):
        self._daten = daten
        self.status_code = status_code
        self.content = content
        self.headers = {}

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
        self.aufrufe.append({"url": url, "params": dict(params or {}), "timeout": timeout})
        if not self._antworten:
            raise AssertionError("Unerwarteter weiterer httpx.get-Aufruf")
        naechste = self._antworten.pop(0)
        if isinstance(naechste, Exception):
            raise naechste
        return naechste


class FakePost:
    """httpx.post-Attrappe: liefert Antworten der Reihe nach, merkt Aufrufe."""

    def __init__(self, *antworten):
        self._antworten = list(antworten)
        self.aufrufe = []

    def __call__(self, url, params=None, files=None, timeout=None):
        self.aufrufe.append({"url": url, "params": dict(params or {}),
                             "files": files, "timeout": timeout})
        if not self._antworten:
            raise AssertionError("Unerwarteter weiterer httpx.post-Aufruf")
        naechste = self._antworten.pop(0)
        if isinstance(naechste, Exception):
            raise naechste
        return naechste


class Stolperfalle:
    """Kein Aufruf erlaubt — jeder Versuch fliegt auf."""

    def __call__(self, *args, **kwargs):
        raise AssertionError(f"Unerlaubter Netz-Aufruf: args={args!r} kwargs={kwargs!r}")


def _ok(**felder) -> Antwort:
    return Antwort({"result": 0, **felder})


def _ordnung(**felder) -> Antwort:
    return _ok(metadata={"folderid": 4242, "path": "/Agent/uebergabe", **felder})


def _manifest_zeilen(pfad: Path) -> list:
    if not pfad.exists():
        return []
    return [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]


@pytest.fixture
def ohne_env(monkeypatch, tmp_path):
    for name in ("PCLOUD_TOKEN", "PCLOUD_HOST", "PCLOUD_UEBERGABE_MANIFEST"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(hochladen, "ENV_DATEI", tmp_path / "keine.env")
    monkeypatch.setattr(holen, "ENV_DATEI", tmp_path / "keine.env")


# ── Hochladen (PC): Plan und Idempotenz ────────────────────────────────────

def test_plan_ohne_manifest_ist_neu(tmp_path):
    datei = tmp_path / "a.json"
    datei.write_text("inhalt", encoding="utf-8")
    plan = hochladen.planen([str(datei)])
    assert len(plan) == 1
    assert plan[0]["name"] == "a.json"
    assert plan[0]["groesse"] == 6
    assert plan[0]["zustand"] == hochladen.ZUSTAND_NEU
    assert plan[0]["pruefsumme"] == hochladen.sha256_datei(str(datei))


def test_plan_gleiche_pruefsumme_ist_gleich(tmp_path):
    datei = tmp_path / "a.json"
    datei.write_text("inhalt", encoding="utf-8")
    eintrag = {"name": "a.json", "groesse": 6,
               "pruefsumme": hochladen.sha256_datei(str(datei))}
    plan = hochladen.planen([str(datei)], manifest_eintraege=[eintrag])
    assert plan[0]["zustand"] == hochladen.ZUSTAND_GLEICH


def test_plan_geaenderte_pruefsumme_ist_neu(tmp_path):
    datei = tmp_path / "a.json"
    datei.write_text("NEU", encoding="utf-8")
    eintrag = {"name": "a.json", "groesse": 6, "pruefsumme": "0" * 64}
    plan = hochladen.planen([str(datei)], manifest_eintraege=[eintrag])
    assert plan[0]["zustand"] == hochladen.ZUSTAND_NEU


def test_plan_alles_erzwingt_neu(tmp_path):
    datei = tmp_path / "a.json"
    datei.write_text("inhalt", encoding="utf-8")
    eintrag = {"name": "a.json", "groesse": 6,
               "pruefsumme": hochladen.sha256_datei(str(datei))}
    plan = hochladen.planen([str(datei)], manifest_eintraege=[eintrag], alles=True)
    assert plan[0]["zustand"] == hochladen.ZUSTAND_NEU


def test_dateien_sammeln_ordner_ist_nicht_rekursiv(tmp_path):
    (tmp_path / "unter").mkdir()
    (tmp_path / "unter" / "tief.txt").write_text("x", encoding="utf-8")
    (tmp_path / "b.json").write_text("b", encoding="utf-8")
    (tmp_path / "a.json").write_text("a", encoding="utf-8")
    gesammelt = [os.path.basename(p) for p in hochladen.dateien_sammeln(None, str(tmp_path))]
    assert gesammelt == ["a.json", "b.json"]           # sortiert, ohne Ordner


# ── Hochladen (PC): Trockenlauf und Schreiben ──────────────────────────────

def test_trockenlauf_sendet_nichts_und_bucht_nichts(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    datei = tmp_path / "a.json"
    datei.write_text("inhalt", encoding="utf-8")
    manifest = tmp_path / "manifest.jsonl"
    plan = hochladen.planen([str(datei)])
    ergebnis = hochladen.hochladen_lauf(plan, schreiben=False, ziel_liste=[],
                                        manifest=str(manifest))
    assert ergebnis["zaehler"]["hochgeladen"] == 1
    assert ergebnis["trocken"] is True
    assert not manifest.exists()


def test_schreiben_laedt_hoch_und_bucht_manifest(tmp_path, monkeypatch):
    datei = tmp_path / "a.json"
    datei.write_text("inhalt", encoding="utf-8")
    manifest = tmp_path / "manifest.jsonl"
    fake_get = FakeGet(_ordnung())
    fake_post = FakePost(_ok(fileids=[777]))
    monkeypatch.setattr(httpx, "get", fake_get)

    plan = hochladen.planen([str(datei)])
    ergebnis = hochladen.hochladen_lauf(plan, schreiben=True, ziel_liste=[],
                                        manifest=str(manifest), token=TOKEN, host=HOST,
                                        senden=fake_post)

    assert ergebnis["zaehler"]["hochgeladen"] == 1
    assert ergebnis["fehler"] is False
    # Ordner wurde geholt/angelegt (createfolderifnotexists mit auth).
    assert fake_get.aufrufe[0]["url"] == f"https://{HOST}/createfolderifnotexists"
    assert fake_get.aufrufe[0]["params"] == {"path": "/Agent/uebergabe", "auth": TOKEN}
    # Hochgeladen wurde per multipart (uploadfile) mit nopartial.
    assert fake_post.aufrufe[0]["url"] == f"https://{HOST}/uploadfile"
    assert fake_post.aufrufe[0]["params"]["folderid"] == 4242
    assert fake_post.aufrufe[0]["params"]["nopartial"] == 1
    assert "file" in fake_post.aufrufe[0]["files"]
    # Manifest-Zeile mit den verlangten Feldern.
    zeilen = _manifest_zeilen(manifest)
    assert len(zeilen) == 1
    z = zeilen[0]
    assert z["name"] == "a.json" and z["groesse"] == 6
    assert z["pruefsumme"] == hochladen.sha256_datei(str(datei))
    assert z["ziel"] == "/Agent/uebergabe/a.json"
    assert z["fileid"] == 777
    assert z["quelle"] and "zeit" in z
    assert TOKEN not in manifest.read_text(encoding="utf-8")


def test_gleiche_pruefsumme_wird_ohne_aufruf_uebersprungen(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    datei = tmp_path / "a.json"
    datei.write_text("inhalt", encoding="utf-8")
    eintrag = {"name": "a.json", "groesse": 6,
               "pruefsumme": hochladen.sha256_datei(str(datei))}
    plan = hochladen.planen([str(datei)], manifest_eintraege=[eintrag])
    ergebnis = hochladen.hochladen_lauf(plan, schreiben=True, ziel_liste=[eintrag],
                                        manifest=str(tmp_path / "m.jsonl"))
    assert ergebnis["zaehler"]["uebersprungen"] == 1
    assert ergebnis["zaehler"]["hochgeladen"] == 0
    assert "uebersprungen" in ergebnis["zeilen"][0]


def test_netzfehler_beim_hochladen_klare_meldung_kein_absturz(tmp_path, monkeypatch):
    datei = tmp_path / "a.json"
    datei.write_text("inhalt", encoding="utf-8")
    monkeypatch.setattr(httpx, "get", FakeGet(_ordnung()))
    fake_post = FakePost(httpx.ConnectError(f"kaputt bei auth={TOKEN}"))
    plan = hochladen.planen([str(datei)])
    ergebnis = hochladen.hochladen_lauf(plan, schreiben=True, ziel_liste=[],
                                        manifest=str(tmp_path / "m.jsonl"),
                                        token=TOKEN, host=HOST, senden=fake_post)
    assert ergebnis["fehler"] is True
    assert ergebnis["zaehler"]["fehler"] == 1
    assert "ConnectError" in ergebnis["zeilen"][0]
    assert TOKEN not in ergebnis["zeilen"][0]
    assert not (tmp_path / "m.jsonl").exists()          # nichts gebucht


def test_ziel_ausserhalb_agent_wird_abgelehnt():
    with pytest.raises(hochladen.UebergabeFehler) as fehler:
        hochladen.ziel_pfad_pruefen("/Privat/uebergabe")
    assert "/Agent/" in str(fehler.value)


def test_manifest_im_repo_wird_abgelehnt(tmp_path):
    (tmp_path / ".git").mkdir()
    with pytest.raises(hochladen.UebergabeFehler) as fehler:
        hochladen.manifest_anhaengen({"name": "x"}, pfad=str(tmp_path / "unter" / "m.jsonl"))
    assert "Repo" in str(fehler.value)


def test_ohne_token_klarer_text_kein_netzaufruf(ohne_env, tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    with pytest.raises(hochladen.UebergabeFehler) as fehler:
        hochladen.ordner_holen_oder_anlegen("/Agent/uebergabe")
    assert "PCLOUD_TOKEN" in str(fehler.value)


# ── Holen (Handy) ──────────────────────────────────────────────────────────

def test_holen_schreibt_dateien_und_liste(tmp_path, monkeypatch):
    ziel = tmp_path / "staging"
    liste = tmp_path / "liste.txt"
    fake = FakeGet(
        _ok(metadata={"contents": [
            {"name": "a.json", "fileid": 1, "size": 6, "isfolder": False},
            {"name": "b.jsonl", "fileid": 2, "size": 3, "isfolder": False},
            {"name": "ordner", "folderid": 9, "isfolder": True},
        ]}),
        _ok(hosts=["dl.example"], path="/get/1", size=6),   # getfilelink a
        Antwort(content=b"inhalt"),                          # Download a (6 Bytes)
        _ok(hosts=["dl.example"], path="/get/2", size=3),   # getfilelink b
        Antwort(content=b"abc"),                             # Download b (3 Bytes)
    )
    monkeypatch.setattr(httpx, "get", fake)
    bericht = holen.holen(ordner="/Agent/uebergabe", ziel=str(ziel), liste=str(liste),
                          token=TOKEN, host=HOST, protokoll=lambda *_: None)

    assert bericht["geholt"] == ["a.json", "b.jsonl"]
    assert (ziel / "a.json").read_bytes() == b"inhalt"
    assert (ziel / "b.jsonl").read_bytes() == b"abc"
    assert liste.read_text(encoding="utf-8").splitlines() == ["a.json", "b.jsonl"]
    # auth stand nur beim API-Aufruf, nicht in der Download-URL.
    assert fake.aufrufe[1]["url"] == f"https://{HOST}/getfilelink"
    assert fake.aufrufe[2]["url"] == "https://dl.example/get/1"
    assert "auth" not in fake.aufrufe[2]["url"]


def test_holen_leerer_ordner_ohne_fehler(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "get", FakeGet(_ok(metadata={"contents": []})))
    bericht = holen.holen(ordner="/Agent/uebergabe", ziel=str(tmp_path / "s"),
                          token=TOKEN, host=HOST, protokoll=lambda *_: None)
    assert bericht["geholt"] == [] and bericht["ordner_leer"] is True


def test_holen_ohne_token_kein_netzaufruf(ohne_env, tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "get", Stolperfalle())
    meldungen = []
    bericht = holen.holen(ordner="/Agent/uebergabe", ziel=str(tmp_path / "s"),
                          token=None, host=None, protokoll=meldungen.append)
    assert bericht["geholt"] == []
    assert any("PCLOUD_TOKEN" in z for z in meldungen)


def test_holen_groesse_abweichend_wird_nicht_uebernommen(tmp_path, monkeypatch):
    ziel = tmp_path / "s"
    fake = FakeGet(
        _ok(metadata={"contents": [{"name": "a.json", "fileid": 1, "size": 10, "isfolder": False}]}),
        _ok(hosts=["dl"], path="/g", size=10),
        Antwort(content=b"kurz"),                # nur 4 Bytes statt 10
    )
    monkeypatch.setattr(httpx, "get", fake)
    bericht = holen.holen(ordner="/Agent/uebergabe", ziel=str(ziel), token=TOKEN,
                          host=HOST, protokoll=lambda *_: None)
    assert bericht["geholt"] == [] and bericht["fehler"] == ["a.json"]
    assert not (ziel / "a.json").exists()


# ── Uebernehmen (Shell-Skript, echter Git-Bash-Lauf) ───────────────────────

def _bash() -> str:
    bash = shutil.which("bash")
    if not bash or "system32" in bash.lower():
        pytest.skip("Git Bash nicht vorhanden")
    assert bash is not None
    return bash


def _posix(pfad: Path) -> str:
    return str(pfad).replace("\\", "/")


def _ohne_msys(umgebung: dict) -> dict:
    for _v in ("MSYS2_ARG_CONV_EXCL", "MSYS_NO_PATHCONV"):
        umgebung.pop(_v, None)
    return umgebung


def _sandkasten(tmp_path: Path) -> Path:
    """Kopie des Shell-Skripts + Attrappen-python, das 'geholte' Dateien anlegt."""
    sb = tmp_path / "projekt"
    (sb / "termux").mkdir(parents=True)
    shutil.copy(UEBERNEHMEN, sb / "termux" / "pcloud-uebernehmen.sh")
    # Der Holer-Pfad muss existieren (die Attrappe-python ersetzt den Inhalt).
    (sb / "tools" / "handy").mkdir(parents=True)
    (sb / "tools" / "handy" / "pcloud_dateien_holen.py").write_text("# Attrappe\n", encoding="utf-8")
    bin_ordner = tmp_path / "bin"
    bin_ordner.mkdir()
    # Attrappen-python: kopiert $BH_VORLAGE/* nach --ziel, schreibt die Namen in
    # --liste und haengt 'fehlt.txt' an (Quelle-fehlt-Fall).
    stub = (
        "#!/bin/sh\n"
        "Z=\"\"; L=\"\"\n"
        "while [ $# -gt 0 ]; do case \"$1\" in --ziel) Z=\"$2\"; shift 2;; "
        "--liste) L=\"$2\"; shift 2;; --env) shift 2;; *) shift;; esac; done\n"
        "[ -n \"$Z\" ] && mkdir -p \"$Z\"\n"
        "if [ -n \"$BH_VORLAGE\" ] && [ -d \"$BH_VORLAGE\" ]; then\n"
        "  for f in \"$BH_VORLAGE\"/*; do [ -f \"$f\" ] && cp -f \"$f\" \"$Z/\"; done\n"
        "fi\n"
        "[ -n \"$L\" ] && { for f in \"$Z\"/*; do [ -f \"$f\" ] && basename \"$f\"; done > \"$L\"; "
        "echo fehlt.txt >> \"$L\"; }\n"
        "exit 0\n"
    )
    (bin_ordner / "python").write_bytes(stub.encode())
    os.chmod(bin_ordner / "python", 0o755)
    return sb


def _lauf(sb: Path, heim: Path, bin_ordner: Path, vorlage: Path, env_extra: dict):
    umgebung = dict(os.environ,
                    HOME=_posix(heim),
                    PCLOUD_UEBERGABE_ZIEL=_posix(heim / "foto_sortierung"),
                    PCLOUD_UEBERGABE_STAGING=_posix(heim / "staging"),
                    PCLOUD_UEBERGABE_PROTOKOLL=_posix(heim / "proto.log"),
                    BH_VORLAGE=_posix(vorlage),
                    PATH=_posix(bin_ordner) + os.pathsep + os.environ.get("PATH", ""))
    umgebung.pop("PROJEKT", None)
    umgebung.update(env_extra)
    return subprocess.run([_bash(), _posix(sb / "termux" / "pcloud-uebernehmen.sh"),
                           _posix(sb)],
                          env=_ohne_msys(umgebung), capture_output=True, text=True,
                          encoding="utf-8", timeout=120)


def test_uebernehmen_kopiert_neue_datei(tmp_path):
    sb = _sandkasten(tmp_path)
    heim = tmp_path / "heim"
    heim.mkdir()
    vorlage = tmp_path / "vorlage"
    vorlage.mkdir()
    (vorlage / "a.json").write_text("inhalt", encoding="utf-8")
    lauf = _lauf(sb, heim, tmp_path / "bin", vorlage, {})
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert (heim / "foto_sortierung" / "a.json").read_text(encoding="utf-8") == "inhalt"
    proto = (heim / "proto.log").read_text(encoding="utf-8")
    assert "uebernommen (kopiert)" in proto
    assert "fehlt.txt Quelle fehlt" in proto


def test_uebernehmen_gleiche_pruefsumme_tut_nichts(tmp_path):
    sb = _sandkasten(tmp_path)
    heim = tmp_path / "heim"
    (heim / "foto_sortierung").mkdir(parents=True)
    (heim / "foto_sortierung" / "a.json").write_text("inhalt", encoding="utf-8")
    vorlage = tmp_path / "vorlage"
    vorlage.mkdir()
    (vorlage / "a.json").write_text("inhalt", encoding="utf-8")   # identisch
    lauf = _lauf(sb, heim, tmp_path / "bin", vorlage, {})
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    proto = (heim / "proto.log").read_text(encoding="utf-8")
    assert "a.json uebersprungen (Pruefsumme gleich" in proto
    # Keine Sicherung, keine .teil-Reste.
    assert not list((heim / "foto_sortierung").glob("a.json.vor_*"))
    assert not list((heim / "foto_sortierung").glob("*.teil"))


def test_uebernehmen_sichert_vor_dem_kopieren_und_waehlt_kollision(tmp_path):
    sb = _sandkasten(tmp_path)
    heim = tmp_path / "heim"
    (heim / "foto_sortierung").mkdir(parents=True)
    ziel = heim / "foto_sortierung" / "a.json"
    ziel.write_text("ALt", encoding="utf-8")
    # Schon eine Sicherung von heute liegt da -> das Skript muss _2 nehmen.
    heute = datetime.now().strftime("%Y-%m-%d")
    (heim / "foto_sortierung" / f"a.json.vor_{heute}").write_text("noch aelter", encoding="utf-8")
    vorlage = tmp_path / "vorlage"
    vorlage.mkdir()
    (vorlage / "a.json").write_text("NEU", encoding="utf-8")
    lauf = _lauf(sb, heim, tmp_path / "bin", vorlage, {})
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert ziel.read_text(encoding="utf-8") == "NEU"
    kollision = heim / "foto_sortierung" / f"a.json.vor_{heute}_2"
    assert kollision.read_text(encoding="utf-8") == "ALt"
    # Reihenfolge im Protokoll: erst Sicherung, dann uebernommen.
    proto = (heim / "proto.log").read_text(encoding="utf-8").splitlines()
    i_sich = next(i for i, z in enumerate(proto) if "Sicherung angelegt" in z)
    i_ueb = next(i for i, z in enumerate(proto) if "uebernommen (kopiert)" in z)
    assert i_sich < i_ueb
    assert not list((heim / "foto_sortierung").glob("*.teil"))


def test_uebernehmen_ohne_liste_ist_exit0(tmp_path):
    sb = _sandkasten(tmp_path)
    heim = tmp_path / "heim"
    heim.mkdir()
    vorlage = tmp_path / "leer"
    vorlage.mkdir()
    bin_ordner = tmp_path / "bin2"
    bin_ordner.mkdir()
    # Attrappen-python, das gar nichts tut (kein Staging, keine Liste).
    (bin_ordner / "python").write_bytes(b"#!/bin/sh\nexit 0\n")
    os.chmod(bin_ordner / "python", 0o755)
    lauf = _lauf(sb, heim, bin_ordner, vorlage, {})
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    proto = (heim / "proto.log").read_text(encoding="utf-8")
    assert "keine Liste" in proto


# ── Einbindung, Syntax, Zeilenenden ────────────────────────────────────────

def test_uebernahme_ist_eigener_schritt_in_der_gemeinsamen_datei():
    text = SHARED.read_text(encoding="utf-8")
    assert 'bash "$HIER/pcloud-uebernehmen.sh" "$PROJEKT" || true' in text
    # Steht nach der Wissensdatei und vor dem Weckruf.
    assert (text.index("wissensdatei-uebernehmen.sh")
            < text.index("pcloud-uebernehmen.sh")
            < text.index("termux-wake-lock"))


def test_schritt_steht_nur_in_der_gemeinsamen_datei():
    for pfad in (WIDGET, APP):
        for zeile in pfad.read_text(encoding="utf-8").splitlines():
            if zeile.lstrip().startswith("#"):
                continue
            assert "pcloud-uebernehmen.sh" not in zeile


def test_skripte_sind_syntaxgeprueft_und_reine_lf():
    for pfad in (UEBERNEHMEN, SHARED):
        roh = pfad.read_bytes()
        assert b"\r" not in roh, f"{pfad.name}: reine LF verlangt (kein CR)"
        assert roh.startswith(b"#!"), f"{pfad.name}: Shebang fehlt"
    for pfad in (UEBERNEHMEN,):
        ergebnis = subprocess.run([_bash(), "-n", _posix(pfad)], capture_output=True, text=True)
        assert ergebnis.returncode == 0, f"bash -n {pfad.name}: {ergebnis.stderr}"
