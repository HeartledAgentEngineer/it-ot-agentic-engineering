"""Pruefungen fuer W1: WhatsApp-Bilder vom Handy in die pCloud (21.10.2026).

Plan: ``.hermes/plans/2026-10-21_whatsapp-bilder.md`` (Fassung 5, Schritt W1).

Alles OHNE Netz und ohne echte Daten: ``httpx.get``/``httpx.post`` sind durch eine
Attrappe der pCloud-API ersetzt, die jeden Aufruf je Methode zaehlt. Der
"Medienordner" ist ein erfundener Baum in ``tmp_path``. Erfundene "sensible"
Datei-/Ordnernamen und ein erfundener Token duerfen nie in stdout, stderr oder
Ausnahmetexten auftauchen.

Abgedeckt (Pruefkriterien W1):
  * Trockenlauf schreibt nirgends (kein Cloud-Ordner, keine Sperre, kein Manifest).
  * Zweiter Lauf laedt 0 hoch; Datei in der Cloud entfernt -> ``fehlt_in_cloud``.
  * Genau ein Lesevorgang je Datei; Pruefsumme und Upload aus denselben Bytes.
  * Eigentumsbeleg (Ordner + Kennung + Pruefsumme) -> sonst ``unklar_begonnen``/``unklar``.
  * Abbruch nach / vor dem Upload, Verschieben, Umbenennen, fremde gleiche Datei.
  * Sperre (zweiter Lauf Exit 3), Ziel ausserhalb /Agent/ (Exit 2), falscher Host (Exit 3).
  * ``hochladen()`` bleibt unveraendert; die Erweiterungen in ``uebergabe_hochladen``.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_whatsapp_bilder_hochladen.py -q
"""

from __future__ import annotations

import ast
import builtins
import datetime
import hashlib
import importlib.util
import json
import os
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

PROJEKT = Path(__file__).resolve().parents[2]
HANDY = PROJEKT / "tools" / "handy"
PFAD_UEBERGABE = PROJEKT / "tools" / "pcloud" / "uebergabe_hochladen.py"
PFAD_EOB = PROJEKT / "tools" / "foto_sortierung" / "ereignisse_ordner_bauen.py"
PFAD_THEMEN = PROJEKT / "tools" / "foto_sortierung" / "foto_themen.py"

TOKEN = "tok-GEHEIMTOKEN-Zaunstein-0815-nicht-echt"
SENSIBEL = (
    "Zaunstein", "Anna-Zaunstein-Krankenhaus", "Familie_Zaunstein",
    "Bewerbung_Zaunstein", "Passwort", "GEHEIMTOKEN", "boesewicht",
)
ZIEL = "/Agent/whatsapp_bilder"
ENDUNGEN = (".jpg", ".jpeg", ".png", ".webp")


# ── Attrappe der pCloud-API (kein Netz, zaehlt jede Methode) ────────────────

class AbbruchWieKill(BaseException):
    """Hartes Ende des Prozesses (keine ``Exception``): laeuft an jedem except vorbei."""


class _Antwort:
    def __init__(self, daten, status_code=200):
        self._daten = daten
        self.status_code = status_code

    def json(self):
        return self._daten


class PCloudAttrappe:
    """Minimale, zustandsbehaftete pCloud: Ordner, Dateien, Zaehler je Methode."""

    SCHREIBEND = ("createfolderifnotexists", "uploadfile")
    BEKANNT = ("userinfo", "createfolderifnotexists", "listfolder", "stat",
               "checksumfile", "uploadfile")

    def __init__(self):
        self.aufrufe: Counter = Counter()
        self.hosts: Counter = Counter()
        self.parameter: list = []
        self.unerlaubt: list = []
        self.ordner_pfad = {0: "/"}
        self.ordner_id = {"/": 0}
        self.dateien: dict = {}
        self._id = 1000
        self.ersetzungen = 0
        # Schalter fuer Fehlerszenarien
        self.userinfo_status = 200
        self.userinfo_result = 0
        self.ohne_sha256 = False
        self.vor_upload = None            # callable(att, name, daten, folderid)
        self.nach_upload = None           # callable(att, fileid)
        self.upload_fehler = None         # Ausnahme NACH dem Speichern
        self.upload_ohne_fileid = False
        self.upload_fileid_ersatz = None
        self.upload_speichert = None      # bytes: gespeicherter Inhalt weicht ab
        self.beim_upload_umbenennen = False
        self.stat_fehler = None
        self.antwort_override = {}        # Methode -> fertige Antwort

    # -- Zaehler --------------------------------------------------------
    @property
    def schreibend(self) -> int:
        return sum(self.aufrufe[m] for m in self.SCHREIBEND)

    @property
    def gesamt(self) -> int:
        return sum(self.aufrufe.values())

    def installieren(self, monkeypatch):
        monkeypatch.setattr(httpx, "get", self.get)
        monkeypatch.setattr(httpx, "post", self.post)
        return self

    # -- Bestand fuer Tests ---------------------------------------------
    def _neue_id(self) -> int:
        self._id += 1
        return self._id

    def ordner_anlegen(self, pfad: str) -> int:
        akt = "/"
        for teil in [t for t in pfad.strip("/").split("/") if t]:
            nxt = akt.rstrip("/") + "/" + teil
            if nxt not in self.ordner_id:
                neu = self._neue_id()
                self.ordner_id[nxt] = neu
                self.ordner_pfad[neu] = nxt
            akt = nxt
        return self.ordner_id[akt]

    def datei_ablegen(self, ordner: str, name: str, daten: bytes) -> int:
        fid = self._neue_id()
        self.dateien[fid] = {"name": name, "parent": self.ordner_anlegen(ordner),
                             "daten": bytes(daten)}
        return fid

    def entfernen(self, fileid):
        del self.dateien[fileid]

    def verschieben(self, fileid, ordner):
        self.dateien[fileid]["parent"] = self.ordner_anlegen(ordner)

    def umbenennen(self, fileid, name):
        self.dateien[fileid]["name"] = name

    def inhalt_aendern(self, fileid, daten):
        self.dateien[fileid]["daten"] = bytes(daten)

    def in_ordner(self, ordner: str) -> list:
        fid = self.ordner_id.get(ordner)
        return sorted(f for f, d in self.dateien.items() if d["parent"] == fid)

    def namen(self) -> list:
        return sorted(d["name"] for d in self.dateien.values())

    # -- HTTP-Ersatz ----------------------------------------------------
    def _notieren(self, url, params):
        rest = url.split("://", 1)[1]
        host, methode = rest.split("/", 1)
        self.hosts[host] += 1
        self.aufrufe[methode] += 1
        self.parameter.append((methode, dict(params or {})))
        if methode not in self.BEKANNT:
            self.unerlaubt.append(methode)
            raise AssertionError(f"unerlaubte pCloud-Methode: {methode}")
        return methode

    def _meta_datei(self, fid):
        d = self.dateien[fid]
        return {"fileid": fid, "name": d["name"], "parentfolderid": d["parent"],
                "isfolder": False, "size": len(d["daten"])}

    def get(self, url, params=None, timeout=None):
        methode = self._notieren(url, params)
        if methode in self.antwort_override:
            return self.antwort_override[methode]
        p = dict(params or {})
        if methode == "userinfo":
            if self.userinfo_status != 200:
                return _Antwort({}, self.userinfo_status)
            if self.userinfo_result != 0:
                return _Antwort({"result": self.userinfo_result,
                                 "error": f"Log in required {p.get('auth')}"})
            return _Antwort({"result": 0, "userid": 7})
        if methode == "createfolderifnotexists":
            fid = self.ordner_anlegen(p["path"])
            return _Antwort({"result": 0, "metadata": {
                "folderid": fid, "isfolder": True, "path": p["path"]}})
        if methode == "listfolder":
            if "folderid" in p:
                fid = int(p["folderid"])
                if fid not in self.ordner_pfad:
                    return _Antwort({"result": 2005, "error": "Directory does not exist."})
            else:
                pfad = "/" + p["path"].strip("/")
                if pfad not in self.ordner_id:
                    return _Antwort({"result": 2005, "error": "Directory does not exist."})
                fid = self.ordner_id[pfad]
            inhalt = [self._meta_datei(f) for f in self.in_ordner(self.ordner_pfad[fid])]
            return _Antwort({"result": 0, "metadata": {
                "folderid": fid, "isfolder": True, "contents": inhalt}})
        if methode == "stat":
            if self.stat_fehler is not None:
                raise self.stat_fehler
            fid = int(p["fileid"])
            if fid not in self.dateien:
                return _Antwort({"result": 2009, "error": "File not found."})
            return _Antwort({"result": 0, "metadata": self._meta_datei(fid)})
        if methode == "checksumfile":
            fid = int(p["fileid"])
            if fid not in self.dateien:
                return _Antwort({"result": 2009, "error": "File not found."})
            daten = self.dateien[fid]["daten"]
            antwort = {"result": 0, "sha1": hashlib.sha1(daten).hexdigest()}
            if not self.ohne_sha256:
                antwort["sha256"] = hashlib.sha256(daten).hexdigest()
            return _Antwort(antwort)
        raise AssertionError(f"GET {methode} nicht vorgesehen")

    def post(self, url, params=None, files=None, timeout=None):
        methode = self._notieren(url, params)
        assert methode == "uploadfile"
        if methode in self.antwort_override:
            return self.antwort_override[methode]
        p = dict(params or {})
        name, daten = files["file"][0], files["file"][1]
        folderid = int(p["folderid"])
        if self.vor_upload is not None:
            self.vor_upload(self, name, daten, folderid)
        vorhanden = [d["name"] for d in self.dateien.values() if d["parent"] == folderid]
        if self.beim_upload_umbenennen:
            stamm, endung = os.path.splitext(name)
            name = f"{stamm} (1){endung}"
        if name in vorhanden:
            if p.get("renameifexists") == 1:
                stamm, endung = os.path.splitext(name)
                name = f"{stamm} (1){endung}"
            else:
                self.ersetzungen += 1
        fid = self._neue_id()
        self.dateien[fid] = {"name": name, "parent": folderid,
                             "daten": bytes(self.upload_speichert
                                            if self.upload_speichert is not None else daten)}
        if self.nach_upload is not None:
            self.nach_upload(self, fid)
        if self.upload_fehler is not None:
            raise self.upload_fehler
        if self.upload_ohne_fileid:
            return _Antwort({"result": 0})
        ausgeliefert = self.upload_fileid_ersatz or fid
        return _Antwort({"result": 0, "fileids": [ausgeliefert], "metadata": [
            {"fileid": ausgeliefert, "name": name, "parentfolderid": folderid}]})


# ── Hilfen ───────────────────────────────────────────────────────────────────

def _bild(pfad: Path, inhalt: str, jahr: int = 2019):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(b"\xff\xd8\xff" + inhalt.encode("utf-8") * 7)
    zeit = datetime.datetime(jahr, 5, 1, 12, 0).timestamp()
    os.utime(pfad, (zeit, zeit))


def baue_medien(basis: Path, voll: bool = True) -> Path:
    """Erfundener Medienbaum. voll=False: nur ein Bild."""
    wurzel = basis / "Bewerbung_Zaunstein" / "WhatsApp Images"
    wurzel.mkdir(parents=True)
    _bild(wurzel / "IMG-20200101-WA0001.jpg", "eins")
    if not voll:
        return wurzel
    _bild(wurzel / "IMG-20210615-WA0002.jpeg", "zwei")
    _bild(wurzel / "Anna-Zaunstein-Krankenhaus.png", "drei", jahr=2019)
    _bild(wurzel / "Sent" / "IMG-20220303-WA0004.jpg", "vier-gesendet")
    _bild(wurzel / "Sent" / "IMG-20220304-WA0005.webp", "fuenf-gesendet")
    # Ausgelassenes: versteckt, .nomedia, Private, fremder Unterordner, Nicht-Bild
    (wurzel / ".nomedia").write_bytes(b"")
    _bild(wurzel / ".versteckt.jpg", "versteckt")
    _bild(wurzel / "Private" / "IMG-20200202-WA0003.jpg", "privat")
    _bild(wurzel / "Familie_Zaunstein" / "foto.jpg", "fremder-ordner")
    (wurzel / "Passwort.txt").write_text("kein Bild", encoding="utf-8")
    return wurzel


def kennzahlen(text: str) -> dict:
    """Alle ``schluessel N | schluessel N``-Zeilen der Ausgabe zu einem dict."""
    ergebnis: dict = {}
    for zeile in text.splitlines():
        teile = zeile.split(" · ")
        if len(teile) < 2 and len(zeile.split(" ")) != 2:
            continue
        for teil in teile:
            stuecke = teil.strip().split(" ")
            if len(stuecke) == 2 and stuecke[0].replace("_", "").isalpha() \
                    and stuecke[1].replace(".", "").isdigit():
                ergebnis[stuecke[0]] = int(stuecke[1].replace(".", ""))
    return ergebnis


def manifest_zeilen(pfad: Path) -> list:
    if not pfad.exists():
        return []
    return [json.loads(z) for z in pfad.read_text(encoding="utf-8").splitlines() if z.strip()]


def _sha(daten: bytes) -> str:
    return hashlib.sha256(daten).hexdigest()


def _lade_modul(name: str, pfad: Path):
    spez = importlib.util.spec_from_file_location(name, pfad)
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


# ── Vorrichtungen ───────────────────────────────────────────────────────────

@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(HANDY))
    import whatsapp_bilder_gemeinsam as gemeinsam
    import whatsapp_bilder_hochladen as wa
    return SimpleNamespace(wa=wa, gemeinsam=gemeinsam, ug=gemeinsam.uebergabe_laden())


def _welt(tmp_path, monkeypatch, module, voll):
    for name in ("PCLOUD_TOKEN", "PCLOUD_HOST", "PCLOUD_UEBERGABE_MANIFEST"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(module.ug, "ENV_DATEI", tmp_path / "keine.env")
    monkeypatch.setenv("PCLOUD_TOKEN", TOKEN)
    att = PCloudAttrappe().installieren(monkeypatch)
    wurzel = baue_medien(tmp_path, voll=voll)
    ablage = tmp_path / "fs"                      # existiert absichtlich noch nicht
    welt = SimpleNamespace(
        att=att, wurzel=wurzel, tmp=tmp_path, ablage=ablage,
        manifest=ablage / "manifest.jsonl", sperre=ablage / "sperre",
        wa=module.wa, ug=module.ug, gemeinsam=module.gemeinsam)

    def argv(*zusatz):
        return ["--ordner", str(wurzel), "--manifest", str(welt.manifest),
                "--sperre", str(welt.sperre), *zusatz]

    def lauf(*zusatz):
        return module.wa.main(argv(*zusatz))

    welt.argv = argv
    welt.lauf = lauf
    return welt


@pytest.fixture
def welt(tmp_path, monkeypatch, module):
    return _welt(tmp_path, monkeypatch, module, voll=True)


@pytest.fixture
def eine(tmp_path, monkeypatch, module):
    return _welt(tmp_path, monkeypatch, module, voll=False)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Trockenlauf
# ═══════════════════════════════════════════════════════════════════════════

def test_trockenlauf_schreibt_nirgends(welt, capsys):
    assert welt.lauf() == 0
    z = kennzahlen(capsys.readouterr().out)
    assert z["neu"] == 5 and z["erledigt"] == 0
    assert welt.att.schreibend == 0                      # kein Ordner, kein Upload
    assert set(welt.att.ordner_id) == {"/"}              # nichts angelegt
    assert not welt.sperre.exists() and not welt.manifest.exists()
    assert not welt.ablage.exists()                      # nicht einmal der Ordner
    assert z["zielordner_neu"] == 4 and z["zielordner_vorhanden"] == 0
    assert welt.att.unerlaubt == []


def test_trockenlauf_zaehlt_bytes_und_ausgelassenes(welt, capsys):
    welt.lauf()
    z = kennzahlen(capsys.readouterr().out)
    erwartet = sum(p.stat().st_size for p in
                   [welt.wurzel / "IMG-20200101-WA0001.jpg",
                    welt.wurzel / "IMG-20210615-WA0002.jpeg",
                    welt.wurzel / "Anna-Zaunstein-Krankenhaus.png",
                    welt.wurzel / "Sent" / "IMG-20220303-WA0004.jpg",
                    welt.wurzel / "Sent" / "IMG-20220304-WA0005.webp"])
    assert z["bytes"] == erwartet
    assert z["nicht_bilder"] == 1                        # Passwort.txt
    # versteckt / .nomedia / Private / fremder Unterordner nie gelesen oder hochgeladen
    assert all("privat" not in str(a) for a in welt.att.parameter)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Schreiben, Idempotenz, Rueckweg
# ═══════════════════════════════════════════════════════════════════════════

def test_schreiblauf_laedt_hoch_und_bucht(welt, capsys):
    assert welt.lauf("--schreiben") == 0
    z = kennzahlen(capsys.readouterr().out)
    assert z["hochgeladen"] == 5 and z["fehler"] == 0
    assert len(welt.att.dateien) == 5 and welt.att.ersetzungen == 0
    for meth, p in welt.att.parameter:
        if meth == "uploadfile":
            assert p["nopartial"] == 1 and p["renameifexists"] == 1
    namen = welt.att.namen()
    assert all("_wa" in n and len(n.split("_wa")[-1].split(".")[0]) == 12 for n in namen)
    ordner = {welt.att.ordner_pfad[d["parent"]] for d in welt.att.dateien.values()}
    assert ordner == {f"{ZIEL}/empfangen/2020", f"{ZIEL}/empfangen/2021",
                      f"{ZIEL}/empfangen/2019", f"{ZIEL}/gesendet/2022"}
    zeilen = manifest_zeilen(welt.manifest)
    assert Counter(x["zustand"] for x in zeilen) == {"upload_begonnen": 5, "hochgeladen": 5}
    for x in zeilen:
        if x["zustand"] == "hochgeladen":
            assert x["fileid"] in welt.att.dateien
            assert x["cloud_name"] == welt.att.dateien[x["fileid"]]["name"]
    assert not welt.sperre.exists()                      # Sperre wieder frei


def test_zweiter_lauf_laedt_nichts_hoch(welt, capsys):
    welt.lauf("--schreiben")
    capsys.readouterr()
    vorher = welt.att.aufrufe["uploadfile"]
    assert welt.lauf("--schreiben") == 0
    z = kennzahlen(capsys.readouterr().out)
    assert z["erledigt"] == 5 and z["neu"] == 0 and z["hochgeladen"] == 0
    assert welt.att.aufrufe["uploadfile"] == vorher
    assert len(welt.att.dateien) == 5


def test_trockenlauf_nach_schreiblauf_zeigt_erledigt(welt, capsys):
    welt.lauf("--schreiben")
    capsys.readouterr()
    schreibend = welt.att.schreibend
    welt.lauf()
    z = kennzahlen(capsys.readouterr().out)
    assert z["erledigt"] == 5 and z["neu"] == 0
    assert welt.att.schreibend == schreibend


def test_datei_in_cloud_entfernt_fehlt_in_cloud_und_neuer_upload(welt, capsys):
    welt.lauf("--schreiben")
    capsys.readouterr()
    zeilen = manifest_zeilen(welt.manifest)
    alt = next(x for x in zeilen if x["zustand"] == "hochgeladen"
               and x["pfad"].endswith("WA0001.jpg"))
    welt.att.entfernen(alt["fileid"])
    assert welt.lauf("--schreiben") == 0
    z = kennzahlen(capsys.readouterr().out)
    assert z["fehlt_in_cloud"] == 1 and z["hochgeladen"] == 1
    zeilen = manifest_zeilen(welt.manifest)
    neu = [x for x in zeilen if x["zustand"] == "hochgeladen" and x["pfad"] == alt["pfad"]]
    assert len(neu) == 2 and neu[0]["kennung"] != neu[1]["kennung"]
    assert any(x["zustand"] == "fehlt_in_cloud" and x["kennung"] == alt["kennung"]
               for x in zeilen)
    # Danach ist wieder alles erledigt
    aufrufe = welt.att.aufrufe["uploadfile"]
    welt.lauf("--schreiben")
    z = kennzahlen(capsys.readouterr().out)
    assert z["erledigt"] == 5 and welt.att.aufrufe["uploadfile"] == aufrufe
    freigegeben = welt.wa.entfernbare_fileids(manifest_zeilen(welt.manifest))
    assert alt["fileid"] not in freigegeben and neu[1]["fileid"] in freigegeben


def test_max_begrenzt_den_lauf(welt, capsys):
    assert welt.lauf("--schreiben", "--max", "2") == 0
    z = kennzahlen(capsys.readouterr().out)
    assert welt.att.aufrufe["uploadfile"] == 2
    assert z["hochgeladen"] == 2 and z["zurueckgestellt"] == 3
    welt.lauf("--schreiben", "--max", "2")
    assert welt.att.aufrufe["uploadfile"] == 4


# ═══════════════════════════════════════════════════════════════════════════
# 3. Ein Lesevorgang je Datei, Pruefsumme und Upload aus denselben Bytes
# ═══════════════════════════════════════════════════════════════════════════

def test_genau_ein_lesevorgang_je_datei(welt, monkeypatch):
    echte = builtins.open
    zaehler: Counter = Counter()

    def zaehl_open(datei, *a, **k):
        try:
            pfad = os.fspath(datei)
        except TypeError:
            pfad = None
        if isinstance(pfad, str) and pfad.startswith(str(welt.wurzel)):
            zaehler[pfad] += 1
        return echte(datei, *a, **k)

    monkeypatch.setattr(builtins, "open", zaehl_open)
    assert welt.lauf("--schreiben") == 0
    bilder = [p for p in zaehler if p.lower().endswith(ENDUNGEN)]
    assert len(bilder) == 5 and all(zaehler[p] == 1 for p in bilder)
    # nichts Ausgelassenes (versteckt, Private, fremder Ordner, Nicht-Bild) wurde geoeffnet
    assert len(zaehler) == 5
    zaehler.clear()
    welt.lauf()                                           # auch der Trockenlauf: einmal
    assert len(zaehler) == 5 and all(v == 1 for v in zaehler.values())


def test_pruefsumme_und_upload_aus_denselben_bytes(welt):
    welt.lauf("--schreiben")
    hochgeladen = {x["fileid"]: x for x in manifest_zeilen(welt.manifest)
                   if x["zustand"] == "hochgeladen"}
    for fid, x in hochgeladen.items():
        assert _sha(welt.att.dateien[fid]["daten"]) == x["sha256"]
        assert x["groesse"] == len(welt.att.dateien[fid]["daten"])
        assert isinstance(x["mtime"], int)


def test_datei_aendert_sich_zwischen_lesen_und_upload(welt, capsys):
    ziel = welt.wurzel / "IMG-20200101-WA0001.jpg"
    original = ziel.read_bytes()
    geaendert = []

    def hook(att, name, daten, folderid):
        if name.startswith("IMG-20200101-WA0001") and not geaendert:
            ziel.write_bytes(original + b"NACHTRAEGLICH")
            geaendert.append(1)

    welt.att.vor_upload = hook
    assert welt.lauf("--schreiben") == 0
    capsys.readouterr()
    fid = next(x["fileid"] for x in manifest_zeilen(welt.manifest)
               if x["zustand"] == "hochgeladen" and x["pfad"].endswith("WA0001.jpg"))
    assert welt.att.dateien[fid]["daten"] == original
    zeile = next(x for x in manifest_zeilen(welt.manifest)
                 if x["zustand"] == "hochgeladen" and x["fileid"] == fid)
    assert zeile["sha256"] == _sha(original)
    welt.att.vor_upload = None
    welt.lauf()                                           # nur zaehlen
    z = kennzahlen(capsys.readouterr().out)
    assert z["neu"] == 1 and z["erledigt"] == 4          # neue sha256 = neu


# ═══════════════════════════════════════════════════════════════════════════
# 4. Eigentumsbeleg: kein "hochgeladen" ohne Beleg
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("variante", [
    "anderer_ordner", "name_ohne_kennung", "ohne_fileid", "andere_pruefsumme"])
def test_ohne_eigentumsbeleg_nur_unklar_begonnen(eine, capsys, variante):
    ordner = f"{ZIEL}/empfangen/2020"
    original = (eine.wurzel / "IMG-20200101-WA0001.jpg").read_bytes()
    if variante == "anderer_ordner":
        eine.att.upload_fileid_ersatz = eine.att.datei_ablegen(
            "/Agent/anderswo", "IMG-20200101-WA0001.jpg", original)
    elif variante == "name_ohne_kennung":
        eine.att.upload_fileid_ersatz = eine.att.datei_ablegen(
            ordner, "IMG-20200101-WA0001.jpg", original)
    elif variante == "ohne_fileid":
        eine.att.upload_ohne_fileid = True
    else:
        eine.att.upload_speichert = b"ein ganz anderer Inhalt"
    assert eine.lauf("--schreiben") == 0
    z = kennzahlen(capsys.readouterr().out)
    zeilen = manifest_zeilen(eine.manifest)
    assert not any(x["zustand"] == "hochgeladen" for x in zeilen)
    assert any(x["zustand"] == "unklar_begonnen" for x in zeilen)
    assert z["unklar_begonnen"] == 1 and z["hochgeladen"] == 0
    # Kein neuer Upload im Folgelauf (ohne --offene-neu)
    anzahl = eine.att.aufrufe["uploadfile"]
    eine.lauf("--schreiben")
    assert eine.att.aufrufe["uploadfile"] == anzahl
    assert eine.wa.entfernbare_fileids(manifest_zeilen(eine.manifest)) == set()


def test_treffer_mit_kennung_aber_anderer_pruefsumme_ist_unklar(eine, capsys):
    eine.lauf("--schreiben")
    capsys.readouterr()
    fid = next(x["fileid"] for x in manifest_zeilen(eine.manifest)
               if x["zustand"] == "hochgeladen")
    eine.att.inhalt_aendern(fid, b"veraendert")
    anzahl = eine.att.aufrufe["uploadfile"]
    assert eine.lauf("--schreiben") == 0
    z = kennzahlen(capsys.readouterr().out)
    assert z["unklar"] == 1 and eine.att.aufrufe["uploadfile"] == anzahl
    assert fid not in eine.wa.entfernbare_fileids(manifest_zeilen(eine.manifest))


@pytest.mark.parametrize("aenderung", ["umbenannt", "verschoben"])
def test_erledigte_datei_umbenannt_oder_verschoben_ist_unklar(eine, capsys, aenderung):
    eine.lauf("--schreiben")
    capsys.readouterr()
    fid = next(x["fileid"] for x in manifest_zeilen(eine.manifest)
               if x["zustand"] == "hochgeladen")
    assert fid in eine.wa.entfernbare_fileids(manifest_zeilen(eine.manifest))
    if aenderung == "umbenannt":
        eine.att.umbenennen(fid, "IMG-20200101-WA0001.jpg")      # Kennung entfernt
    else:
        eine.att.verschieben(fid, "/Agent/anderswo")
    anzahl = eine.att.aufrufe["uploadfile"]
    assert eine.lauf("--schreiben") == 0
    z = kennzahlen(capsys.readouterr().out)
    assert z["unklar"] == 1 and z["erledigt"] == 0
    assert eine.att.aufrufe["uploadfile"] == anzahl
    assert fid not in eine.wa.entfernbare_fileids(manifest_zeilen(eine.manifest))
    # Wiederholung bleibt unklar und haengt nicht endlos Zeilen an
    eine.lauf("--schreiben")
    z = kennzahlen(capsys.readouterr().out)
    assert z["unklar"] == 1 and eine.att.aufrufe["uploadfile"] == anzahl
    unklar_zeilen = [x for x in manifest_zeilen(eine.manifest) if x["zustand"] == "unklar"]
    assert len(unklar_zeilen) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 5. Abbrueche und Wiederaufnahme
# ═══════════════════════════════════════════════════════════════════════════

def test_abbruch_nach_upload_vor_ergebniszeile_wird_aufgenommen(eine, capsys):
    def nach(att, fileid):
        raise AbbruchWieKill()

    eine.att.nach_upload = nach
    with pytest.raises(AbbruchWieKill):
        eine.lauf("--schreiben")
    zeilen = manifest_zeilen(eine.manifest)
    assert [x["zustand"] for x in zeilen] == ["upload_begonnen"]
    assert len(eine.att.dateien) == 1
    fid = next(iter(eine.att.dateien))
    eine.att.nach_upload = None
    capsys.readouterr()
    assert eine.lauf("--schreiben") == 0
    z = kennzahlen(capsys.readouterr().out)
    assert z["erledigt"] == 1 and z["neu"] == 0
    assert eine.att.aufrufe["uploadfile"] == 1 and len(eine.att.dateien) == 1  # keine Dublette
    hoch = [x for x in manifest_zeilen(eine.manifest) if x["zustand"] == "hochgeladen"]
    assert len(hoch) == 1 and hoch[0]["fileid"] == fid


def test_verlorene_antwort_wird_im_folgelauf_gefunden(eine, capsys):
    eine.att.upload_fehler = httpx.ReadTimeout(f"Zeit abgelaufen {TOKEN} Anna-Zaunstein")
    assert eine.lauf("--schreiben") == 1                  # Fehler gezaehlt
    z = kennzahlen(capsys.readouterr().out)
    assert z["fehler"] == 1
    eine.att.upload_fehler = None
    assert eine.lauf("--schreiben") == 0
    assert eine.att.aufrufe["uploadfile"] == 1 and len(eine.att.dateien) == 1
    hoch = [x for x in manifest_zeilen(eine.manifest) if x["zustand"] == "hochgeladen"]
    assert len(hoch) == 1 and hoch[0]["fileid"] in eine.att.dateien


def test_abbruch_und_umbenennung_durch_pcloud(eine, capsys):
    eine.att.beim_upload_umbenennen = True

    def nach(att, fileid):
        raise AbbruchWieKill()

    eine.att.nach_upload = nach
    with pytest.raises(AbbruchWieKill):
        eine.lauf("--schreiben")
    eine.att.nach_upload = None
    eine.lauf("--schreiben")
    capsys.readouterr()
    hoch = [x for x in manifest_zeilen(eine.manifest) if x["zustand"] == "hochgeladen"]
    assert len(hoch) == 1 and "(1)" in hoch[0]["cloud_name"]
    assert f"_wa{hoch[0]['kennung']}" in hoch[0]["cloud_name"]
    assert len(eine.att.dateien) == 1 and eine.att.aufrufe["uploadfile"] == 1


def test_abbruch_vor_dem_upload_kein_neuer_upload_ohne_offene_neu(eine, capsys):
    def vor(att, name, daten, folderid):
        raise AbbruchWieKill()

    eine.att.vor_upload = vor
    with pytest.raises(AbbruchWieKill):
        eine.lauf("--schreiben")
    eine.att.vor_upload = None
    assert eine.att.dateien == {}
    capsys.readouterr()
    assert eine.lauf("--schreiben") == 0
    z = kennzahlen(capsys.readouterr().out)
    assert z["unklar_begonnen"] == 1 and eine.att.dateien == {}
    assert eine.att.aufrufe["uploadfile"] == 1            # nur der abgebrochene Versuch
    # mit --offene-neu genau ein neuer Upload mit neuer Kennung
    assert eine.lauf("--schreiben", "--offene-neu") == 0
    assert eine.att.aufrufe["uploadfile"] == 2 and len(eine.att.dateien) == 1
    zeilen = manifest_zeilen(eine.manifest)
    kennungen = {x["kennung"] for x in zeilen if x["zustand"] == "upload_begonnen"}
    assert len(kennungen) == 2                            # alte Zeile bleibt als Protokoll
    assert any(x["zustand"] == "unklar_begonnen" for x in zeilen)
    assert sum(1 for x in zeilen if x["zustand"] == "hochgeladen") == 1
    # und danach ist die Datei erledigt
    eine.lauf("--schreiben")
    assert eine.att.aufrufe["uploadfile"] == 2


def test_offene_neu_ohne_schreiben_ist_aufrufFehler(eine, capsys):
    assert eine.lauf("--offene-neu") == 2
    assert eine.att.gesamt == 0 and not eine.ablage.exists()


def test_abbruch_nach_upload_dann_verschoben_ist_unklar_begonnen(eine, capsys):
    def nach(att, fileid):
        raise AbbruchWieKill()

    eine.att.nach_upload = nach
    with pytest.raises(AbbruchWieKill):
        eine.lauf("--schreiben")
    eine.att.nach_upload = None
    fid = next(iter(eine.att.dateien))
    eine.att.verschieben(fid, "/Agent/anderswo")
    capsys.readouterr()
    assert eine.lauf("--schreiben") == 0
    z = kennzahlen(capsys.readouterr().out)
    assert z["unklar_begonnen"] == 1
    assert eine.att.aufrufe["uploadfile"] == 1 and len(eine.att.dateien) == 1
    assert not any(x["zustand"] == "hochgeladen" for x in manifest_zeilen(eine.manifest))


def test_fremde_inhaltsgleiche_datei_wird_nie_als_eigene_gebucht(eine, capsys):
    original = (eine.wurzel / "IMG-20200101-WA0001.jpg").read_bytes()

    def vor(att, name, daten, folderid):
        raise AbbruchWieKill()

    eine.att.vor_upload = vor
    with pytest.raises(AbbruchWieKill):
        eine.lauf("--schreiben")
    eine.att.vor_upload = None
    fremd = eine.att.datei_ablegen(f"{ZIEL}/empfangen/2020", "IMG-20200101-WA0001.jpg", original)
    capsys.readouterr()
    assert eine.lauf("--schreiben") == 0
    z = kennzahlen(capsys.readouterr().out)
    assert z["unklar_begonnen"] == 1 and z["erledigt"] == 0
    zeilen = manifest_zeilen(eine.manifest)
    assert not any(x.get("fileid") == fremd for x in zeilen)
    assert not any(x["zustand"] == "hochgeladen" for x in zeilen)
    assert fremd not in eine.wa.entfernbare_fileids(zeilen)
    assert eine.att.aufrufe["uploadfile"] == 1


def test_kennungs_kollision_zieht_neue_kennung_hoechstens_dreimal(eine, capsys, monkeypatch):
    belegt = "aaaaaaaaaaaa"
    eine.att.datei_ablegen(f"{ZIEL}/empfangen/2020", f"IMG-20200101-WA0001_wa{belegt}.jpg", b"x")
    folge = iter([belegt, belegt, "bbbbbbbbbbbb", "cccccccccccc"])
    monkeypatch.setattr(eine.wa.secrets, "token_hex", lambda n=None: next(folge))
    assert eine.lauf("--schreiben") == 0
    zeilen = manifest_zeilen(eine.manifest)
    hoch = [x for x in zeilen if x["zustand"] == "hochgeladen"]
    assert len(hoch) == 1 and hoch[0]["kennung"] == "bbbbbbbbbbbb"


def test_kennungs_kollision_dreimal_ist_unklar_ohne_upload(eine, capsys, monkeypatch):
    belegt = "aaaaaaaaaaaa"
    eine.att.datei_ablegen(f"{ZIEL}/empfangen/2020", f"IMG-20200101-WA0001_wa{belegt}.jpg", b"x")
    monkeypatch.setattr(eine.wa.secrets, "token_hex", lambda n=None: belegt)
    assert eine.lauf("--schreiben") == 0
    z = kennzahlen(capsys.readouterr().out)
    assert z["unklar"] == 1 and eine.att.aufrufe["uploadfile"] == 0
    assert not any(x["zustand"] == "upload_begonnen" for x in manifest_zeilen(eine.manifest))


def test_fehler_bei_der_beleg_abfrage_bucht_nichts_und_laedt_nicht_neu(eine, capsys):
    eine.lauf("--schreiben")
    capsys.readouterr()
    anzahl = eine.att.aufrufe["uploadfile"]
    zeilen_vorher = manifest_zeilen(eine.manifest)
    eine.att.stat_fehler = httpx.ConnectError(f"kaputt {TOKEN}")
    assert eine.lauf("--schreiben") == 1
    z = kennzahlen(capsys.readouterr().out)
    assert z["fehler"] == 1 and eine.att.aufrufe["uploadfile"] == anzahl
    assert manifest_zeilen(eine.manifest) == zeilen_vorher


# ═══════════════════════════════════════════════════════════════════════════
# 6. Sperre, Ziel, Host, Manifest-Ort
# ═══════════════════════════════════════════════════════════════════════════

def test_zweiter_gleichzeitiger_lauf_ist_exit_3(eine, capsys):
    ergebnisse = []

    def hook(att, name, daten, folderid):
        ergebnisse.append(eine.lauf("--schreiben"))     # zweiter Lauf mitten im ersten

    eine.att.vor_upload = hook
    assert eine.lauf("--schreiben") == 0
    assert ergebnisse == [3]
    assert not eine.sperre.exists()                       # der erste gab sie frei
    assert len(eine.att.dateien) == 1


def test_vorhandene_sperre_gibt_exit_3_ohne_netz(eine, capsys):
    eine.ablage.mkdir()
    eine.sperre.mkdir()
    assert eine.lauf("--schreiben") == 3
    err = capsys.readouterr().err
    assert err.strip().count("\n") == 0 and ".whatsapp_hochladen.sperre" in err
    assert eine.att.gesamt == 0
    assert eine.sperre.exists()                           # fremde Sperre bleibt unberuehrt


def test_trockenlauf_braucht_und_beachtet_keine_sperre(eine, capsys):
    eine.ablage.mkdir()
    eine.sperre.mkdir()
    assert eine.lauf() == 0                               # nur --schreiben nimmt die Sperre


@pytest.mark.parametrize("ziel", ["/Andere/Ort", "/Agent/../Privat", "Agent", "/", "/Agent/"])
def test_ziel_ausserhalb_agent_ist_exit_2_ohne_netz(eine, capsys, ziel):
    assert eine.lauf("--ziel", ziel, "--schreiben") == 2
    assert eine.att.gesamt == 0 and not eine.ablage.exists()
    err = capsys.readouterr().err
    assert len(err.strip().splitlines()) == 1
    assert "Andere" not in err and "Privat" not in err


@pytest.mark.parametrize("quelle", ["umgebung", "env_datei"])
def test_abweichender_host_ist_exit_3_ohne_netzanfrage(welt, capsys, monkeypatch, quelle):
    if quelle == "umgebung":
        monkeypatch.setenv("PCLOUD_HOST", "boesewicht.example")
    else:
        env = welt.tmp / "x.env"
        env.write_text("PCLOUD_HOST=boesewicht.example\n", encoding="utf-8")
        monkeypatch.setattr(welt.ug, "ENV_DATEI", env)
    for zusatz in ((), ("--schreiben",)):
        assert welt.lauf(*zusatz) == 3
        aus = capsys.readouterr()
        assert "boesewicht" not in aus.out + aus.err
        assert aus.err.strip() and aus.err.strip().count("\n") == 0
    assert welt.att.gesamt == 0 and not welt.ablage.exists()


def test_us_host_ist_ebenfalls_gesperrt(welt, monkeypatch):
    monkeypatch.setenv("PCLOUD_HOST", "api.pcloud.com")
    assert welt.lauf() == 3 and welt.att.gesamt == 0


def test_token_fehlt_ist_exit_3(welt, monkeypatch, capsys):
    monkeypatch.delenv("PCLOUD_TOKEN")
    assert welt.lauf("--schreiben") == 3
    assert welt.att.gesamt == 0
    assert TOKEN not in capsys.readouterr().err


def test_token_nur_in_env_datei_wird_gefunden(welt, monkeypatch):
    monkeypatch.delenv("PCLOUD_TOKEN")
    env = welt.tmp / "x.env"
    env.write_text(f"PCLOUD_TOKEN={TOKEN}\n", encoding="utf-8")
    monkeypatch.setattr(welt.ug, "ENV_DATEI", env)
    assert welt.lauf("--schreiben") == 0
    assert welt.att.aufrufe["uploadfile"] == 5
    token_gesehen = {p.get("auth") for _, p in welt.att.parameter}
    assert token_gesehen == {TOKEN}


def test_manifest_im_repo_ist_exit_2(eine, capsys):
    im_repo = PROJEKT / "wa_test_manifest_nicht_anlegen.jsonl"
    argv = ["--ordner", str(eine.wurzel), "--manifest", str(im_repo),
            "--sperre", str(eine.sperre), "--schreiben"]
    assert eine.wa.main(argv) == 2
    assert not im_repo.exists() and eine.att.gesamt == 0
    assert str(PROJEKT) not in capsys.readouterr().err


def test_medienordner_ohne_zugriff_ist_exit_3(eine, monkeypatch, capsys):
    monkeypatch.setattr(os, "access", lambda *a, **k: False)
    assert eine.lauf("--schreiben") == 3
    assert eine.att.gesamt == 0 and not eine.sperre.exists()
    assert "kein Zugriff auf den WhatsApp-Medienordner" in capsys.readouterr().err


def test_ungueltiger_aufruf_ist_exit_2_ohne_pfadecho(eine, capsys):
    assert eine.wa.main(["--gibts-nicht", "/pfad/Zaunstein"]) == 2
    aus = capsys.readouterr()
    assert "Zaunstein" not in aus.out + aus.err


# ═══════════════════════════════════════════════════════════════════════════
# 7. Ausgabe nur Zahlen
# ═══════════════════════════════════════════════════════════════════════════

def test_keine_sensiblen_namen_und_kein_token_in_der_ausgabe(welt, capsys, monkeypatch):
    gesehen = []

    def sammeln():
        aus = capsys.readouterr()
        gesehen.append(aus.out + "\n" + aus.err)

    welt.lauf()                                           # Trockenlauf
    sammeln()
    welt.lauf("--schreiben")                              # Schreiblauf
    sammeln()
    welt.lauf("--schreiben")                              # Folgelauf
    sammeln()
    welt.att.entfernen(next(iter(welt.att.dateien)))      # fehlt_in_cloud
    welt.lauf("--schreiben")
    sammeln()
    welt.att.stat_fehler = httpx.ConnectError(f"{TOKEN} Anna-Zaunstein-Krankenhaus")
    welt.lauf("--schreiben")                              # Fehlerfall
    sammeln()
    welt.att.stat_fehler = None
    welt.att.upload_fehler = httpx.ReadTimeout(f"{TOKEN} Familie_Zaunstein")
    (welt.wurzel / "IMG-20230101-WA0009.jpg").write_bytes(b"\xff\xd8neu")
    welt.lauf("--schreiben")
    sammeln()
    welt.att.upload_fehler = None
    monkeypatch.setenv("PCLOUD_HOST", "boesewicht.example")
    welt.lauf("--schreiben")
    sammeln()
    monkeypatch.delenv("PCLOUD_HOST")
    welt.lauf("--ziel", "/Zaunstein/geheim")
    sammeln()
    insgesamt = "\n".join(gesehen)
    assert "Fehlerarten" in insgesamt                     # die Fehlerzeile gab es wirklich
    for wort in SENSIBEL + (TOKEN,):
        assert wort not in insgesamt, f"{wort!r} taucht in der Ausgabe auf"
    # Dateinamen der Medien tauchen nicht auf, auch nicht die erfundenen "normalen"
    assert "IMG-2020" not in insgesamt and "WA0001" not in insgesamt


def test_ausnahmetexte_der_erweiterungen_enthalten_keinen_token(module, monkeypatch):
    ug = module.ug
    monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(
        httpx.ConnectError(f"https://x/stat?auth={TOKEN}")))
    monkeypatch.setattr(httpx, "post", lambda *a, **k: (_ for _ in ()).throw(
        httpx.ConnectError(f"https://x/uploadfile?auth={TOKEN}")))
    for aufruf in (lambda: ug.stat_datei(5, token=TOKEN, host="eapi.pcloud.com"),
                   lambda: ug.pruefsumme_cloud(5, token=TOKEN, host="eapi.pcloud.com"),
                   lambda: ug.ordner_auflisten(folderid=5, token=TOKEN, host="eapi.pcloud.com"),
                   lambda: ug.hochladen_ohne_ueberschreiben(
                       "a.jpg", b"x", 5, token=TOKEN, host="eapi.pcloud.com")):
        with pytest.raises(ug.UebergabeFehler) as fehler:
            aufruf()
        assert TOKEN not in str(fehler.value)


# ═══════════════════════════════════════════════════════════════════════════
# 8. Erweiterungen in uebergabe_hochladen.py, Bestehendes unveraendert
# ═══════════════════════════════════════════════════════════════════════════

def test_hochladen_bleibt_unveraendert(module):
    ug = module.ug
    gesendet = []

    def senden(url, params=None, files=None, timeout=None):
        gesendet.append(dict(params))
        return _Antwort({"result": 0, "fileids": [77]})

    assert ug.hochladen("a.json", b"x", 5, token="t", host="h", senden=senden) == 77
    assert gesendet == [{"auth": "t", "folderid": 5, "nopartial": 1}]   # kein renameifexists
    assert ug.ERLAUBTE_METHODEN == ("createfolderifnotexists", "uploadfile")


def test_hochladen_ohne_ueberschreiben_sendet_beide_schutzparameter(module):
    ug = module.ug
    gesendet = []

    def senden(url, params=None, files=None, timeout=None):
        gesendet.append((url, dict(params), files))
        return _Antwort({"result": 0, "fileids": [91], "metadata": [
            {"fileid": 91, "name": "a (1).jpg"}]})

    ergebnis = ug.hochladen_ohne_ueberschreiben(
        "a.jpg", b"daten", 5, token="t", host="eapi.pcloud.com", senden=senden)
    assert ergebnis == (91, "a (1).jpg")
    url, params, files = gesendet[0]
    assert url == "https://eapi.pcloud.com/uploadfile"
    assert params == {"auth": "t", "folderid": 5, "nopartial": 1, "renameifexists": 1}
    assert files["file"][0] == "a.jpg" and files["file"][1] == b"daten"


def test_hochladen_ohne_ueberschreiben_ohne_fileid_und_fehler(module):
    ug = module.ug
    kein_id = lambda *a, **k: _Antwort({"result": 0})
    assert ug.hochladen_ohne_ueberschreiben(
        "a.jpg", b"x", 5, token="t", host="h", senden=kein_id) == (None, "a.jpg")
    abgelehnt = lambda *a, **k: _Antwort({"result": 2000, "error": "nein t"})
    with pytest.raises(ug.UebergabeFehler) as fehler:
        ug.hochladen_ohne_ueberschreiben("a.jpg", b"x", 5, token="t", host="h", senden=abgelehnt)
    assert "nein" not in str(fehler.value) and fehler.value.art == "abgelehnt 2000"
    for name in ("", "a/b.jpg", "..", "a\\b.jpg"):
        with pytest.raises(ug.UebergabeFehler):
            ug.hochladen_ohne_ueberschreiben(name, b"x", 5, token="t", host="h", senden=kein_id)
    with pytest.raises(ug.UebergabeFehler):
        ug.hochladen_ohne_ueberschreiben("a.jpg", b"", 5, token="t", host="h", senden=kein_id)


def test_lesefunktionen_nutzen_nur_die_lese_positivliste(module, monkeypatch):
    ug = module.ug
    att = PCloudAttrappe().installieren(monkeypatch)
    assert set(ug.ERLAUBTE_LESE_METHODEN) == {"stat", "checksumfile", "listfolder", "userinfo"}
    with pytest.raises(ug.UebergabeFehler):
        ug._api_lesen("renamefile", {}, token="t", host="eapi.pcloud.com")
    assert att.gesamt == 0                                 # abgewiesen, bevor etwas gesendet wird
    fid = att.datei_ablegen("/Agent/x", "a.jpg", b"abc")
    meta = ug.stat_datei(fid, token="t", host="eapi.pcloud.com")
    assert meta["name"] == "a.jpg" and meta["parentfolderid"] == att.ordner_id["/Agent/x"]
    assert ug.pruefsumme_cloud(fid, token="t", host="eapi.pcloud.com") == _sha(b"abc")
    assert [e["name"] for e in ug.ordner_auflisten(
        pfad="/Agent/x", token="t", host="eapi.pcloud.com")] == ["a.jpg"]
    assert ug.ordner_auflisten(pfad="/Agent/fehlt", token="t", host="eapi.pcloud.com") is None
    assert ug.ordner_auflisten(folderid=99999, token="t", host="eapi.pcloud.com") is None
    with pytest.raises(ug.PCloudNichtGefunden):
        ug.stat_datei(424242, token="t", host="eapi.pcloud.com")
    with pytest.raises(ug.UebergabeFehler):
        ug.ordner_auflisten(pfad="/Andere/Ort", token="t", host="eapi.pcloud.com")
    att.ohne_sha256 = True
    with pytest.raises(ug.UebergabeFehler):
        ug.pruefsumme_cloud(fid, token="t", host="eapi.pcloud.com")
    assert att.schreibend == 0 and att.unerlaubt == []


def test_datumsmuster_erkennt_cloud_name_mit_kennung():
    eob = _lade_modul("eob_wa_test", PFAD_EOB)
    zeitpunkt, mit_uhrzeit = eob.datum_aus_name("IMG-20200101-WA0001_wa3f9a2c1d0b7e.jpg")
    assert (zeitpunkt.year, zeitpunkt.month, zeitpunkt.day) == (2020, 1, 1)
    assert mit_uhrzeit is False
    themen = _lade_modul("foto_themen_wa_test", PFAD_THEMEN)
    assert themen.zeit_aus_name("IMG-20200101-WA0001_wa3f9a2c1d0b7e.jpg") is None


# ═══════════════════════════════════════════════════════════════════════════
# 9. Nachbesserung R1: strenges Manifest, fsync, feste Fehlerarten
# ═══════════════════════════════════════════════════════════════════════════

def test_beschaedigte_mittlere_zeile_ist_exit_3_ohne_upload(eine, capsys):
    assert eine.lauf("--schreiben") == 0
    zeilen = eine.manifest.read_text(encoding="utf-8").splitlines()
    zeilen.insert(1, '{"pfad": "empfangen/IMG-Zaunstein-Anna')
    eine.manifest.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    _bild(eine.wurzel / "IMG-20240101-WA0007.jpg", "neues-bild")
    capsys.readouterr()
    uploads, gesamt = eine.att.aufrufe["uploadfile"], eine.att.gesamt
    for zusatz in (("--schreiben",), ()):
        assert eine.lauf(*zusatz) == 3
        aus = capsys.readouterr()
        assert len(aus.err.strip().splitlines()) == 1 and "Zeile 2" in aus.err
        assert "Zaunstein" not in aus.out + aus.err and "IMG-" not in aus.out + aus.err
    assert eine.att.aufrufe["uploadfile"] == uploads and eine.att.gesamt == gesamt
    assert not eine.sperre.exists()                       # Sperre wieder frei


def test_nicht_utf8_zeile_mitten_im_manifest_ist_exit_3(eine, capsys):
    assert eine.lauf("--schreiben") == 0
    roh = eine.manifest.read_bytes().split(b"\n")
    roh.insert(1, b"\xff\xfe kaputt")
    eine.manifest.write_bytes(b"\n".join(roh))
    anzahl = eine.att.aufrufe["uploadfile"]
    assert eine.lauf("--schreiben") == 3
    assert eine.att.aufrufe["uploadfile"] == anzahl


def test_halbe_letzte_zeile_wird_mit_option_verworfen_und_manifest_danach_lesbar(eine, capsys):
    assert eine.lauf("--schreiben") == 0
    vorher = eine.manifest.read_bytes()
    halb = b'{"zeit": "2026-10-22T10:00:00+02:00", "pfad": "empfangen/IMG-2024'
    eine.manifest.write_bytes(vorher + halb)              # kein Zeilenumbruch am Ende
    _bild(eine.wurzel / "IMG-20240101-WA0007.jpg", "neues-bild")
    capsys.readouterr()
    uploads = eine.att.aufrufe["uploadfile"]
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 0
    z = kennzahlen(capsys.readouterr().out)
    assert z["erledigt"] == 1 and z["hochgeladen"] == 1   # alte Datei keine Dublette
    assert eine.att.aufrufe["uploadfile"] == uploads + 1 and len(eine.att.dateien) == 2
    assert eine.manifest.read_bytes().startswith(vorher + halb)      # nichts geloescht
    gelesen = eine.wa.manifest_streng_lesen(str(eine.manifest))      # wirft nicht
    assert any(x.get("zustand") == "vorab_abgebrochen" for x in gelesen.zeilen)
    assert Counter(x["zustand"] for x in gelesen.zeilen
                   if x["zustand"] in ("hochgeladen", "upload_begonnen")) == {
        "upload_begonnen": 2, "hochgeladen": 2}
    # und weitere Laeufe bleiben gueltig
    assert eine.lauf("--schreiben") == 0
    z = kennzahlen(capsys.readouterr().out)
    assert z["erledigt"] == 2 and eine.att.aufrufe["uploadfile"] == uploads + 1
    assert eine.lauf() == 0


def test_letzte_zeile_gueltig_aber_ohne_umbruch_wird_gelesen(eine):
    eine.ablage.mkdir()
    eine.manifest.write_bytes(
        b'{"zustand": "unklar", "pfad": "p", "sha256": "s", "kennung": "k"}\n'
        b'{"zustand": "fehlt_in_cloud", "pfad": "p", "sha256": "s", "kennung": "k"}')
    gelesen = eine.wa.manifest_streng_lesen(str(eine.manifest))
    assert [x["zustand"] for x in gelesen.zeilen] == ["unklar", "fehlt_in_cloud"]
    assert gelesen.ohne_umbruch is True and gelesen.abgebrochene_zeile is None


def test_fehlendes_manifest_ist_leer(eine):
    gelesen = eine.wa.manifest_streng_lesen(str(eine.manifest))
    assert gelesen.zeilen == [] and gelesen.ohne_umbruch is False


@pytest.mark.parametrize("scheitert_bei", [1, 2])
def test_fsync_fehler_stoppt_alle_weiteren_uploads(welt, capsys, monkeypatch, scheitert_bei):
    echte = os.fsync
    aufrufe = []

    def fsync(fd):
        aufrufe.append(1)
        if len(aufrufe) >= scheitert_bei:
            raise OSError(5, "kaputt Anna-Zaunstein-Krankenhaus")
        return echte(fd)

    monkeypatch.setattr(os, "fsync", fsync)
    assert welt.lauf("--schreiben") == 1
    aus = capsys.readouterr()
    # bei 1: schon die Vorab-Zeile scheitert -> 0 Uploads; bei 2: der Upload lief, dann Stopp
    assert welt.att.aufrufe["uploadfile"] == scheitert_bei - 1
    assert "Fehlerarten" in aus.err + aus.out and "Zaunstein" not in aus.out + aus.err
    assert kennzahlen(aus.out)["fehler"] >= 1
    assert not welt.sperre.exists()


def test_schreibfehler_der_vorab_zeile_laedt_nicht_hoch(eine, capsys, monkeypatch):
    echt = builtins.open

    def kaputt(datei, mode="r", *a, **k):
        if str(datei) == str(eine.manifest) and "a" in mode:
            raise OSError(28, "Platte voll Zaunstein")
        return echt(datei, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", kaputt)
    assert eine.lauf("--schreiben") == 1
    assert eine.att.aufrufe["uploadfile"] == 0
    aus = capsys.readouterr()
    assert "Zaunstein" not in aus.out + aus.err


HOSTILE_ANTWORTEN = [
    {"result": "Anna-Zaunstein-Krankenhaus", "error": "x Anna-Zaunstein-Krankenhaus.jpg " + TOKEN},
    {"result": 2000, "error": "Datei Anna-Zaunstein-Krankenhaus.jpg " + TOKEN},
    {"result": True, "error": "Familie_Zaunstein " + TOKEN},
    {"result": 3.5, "error": "Familie_Zaunstein " + TOKEN},
    {"result": 2009, "error": "File Anna-Zaunstein-Krankenhaus.jpg not found " + TOKEN},
    {"result": 10 ** 30, "error": TOKEN},
]


def _alles_pruefen(gemeinsam, fehler):
    import re
    for text in (str(fehler), repr(fehler), repr(fehler.args), fehler.art,
                 gemeinsam.fehlerart(fehler)):
        for wort in SENSIBEL + (TOKEN,):
            assert wort not in text, f"{wort!r} in {text!r}"
    assert re.fullmatch(r"(netz|http|json|abgelehnt|nicht_gefunden|antwort|konfig|aufruf)"
                        r"( \d{1,5})?", gemeinsam.fehlerart(fehler))


@pytest.mark.parametrize("antwort", HOSTILE_ANTWORTEN)
def test_pcloud_fehlertext_wird_nie_in_ausnahmen_gespeichert(module, monkeypatch, antwort):
    ug, gemeinsam = module.ug, module.gemeinsam
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Antwort(antwort))
    senden = lambda *a, **k: _Antwort(antwort)
    aufrufe = (
        lambda: ug.stat_datei(5, token=TOKEN, host="eapi.pcloud.com"),
        lambda: ug.pruefsumme_cloud(5, token=TOKEN, host="eapi.pcloud.com"),
        lambda: ug.ordner_auflisten(folderid=5, token=TOKEN, host="eapi.pcloud.com"),
        lambda: ug.userinfo_pruefen(token=TOKEN, host="eapi.pcloud.com"),
        lambda: ug.hochladen_ohne_ueberschreiben(
            "a.jpg", b"x", 5, token=TOKEN, host="eapi.pcloud.com", senden=senden),
    )
    for aufruf in aufrufe:
        try:
            aufruf()
        except ug.UebergabeFehler as fehler:
            _alles_pruefen(gemeinsam, fehler)
        else:
            # ordner_auflisten mit "nicht gefunden" liefert None statt Fehler
            assert antwort["result"] == 2009


def test_art_enthaelt_nur_geprueften_ganzzahligen_code(module, monkeypatch):
    ug = module.ug
    for result, erwartet in ((2000, "abgelehnt 2000"), (2009, "nicht_gefunden 2009"),
                             ("text", "abgelehnt"), (True, "abgelehnt"), (3.5, "abgelehnt"),
                             (10 ** 30, "abgelehnt")):
        monkeypatch.setattr(httpx, "get", lambda *a, r=result, **k: _Antwort(
            {"result": r, "error": "egal"}))
        with pytest.raises(ug.PCloudFehler) as fehler:
            ug.userinfo_pruefen(token="t", host="eapi.pcloud.com")
        assert fehler.value.art == erwartet
        assert isinstance(fehler.value, ug.PCloudNichtGefunden) == (result == 2009)


def test_http_netz_json_arten(module, monkeypatch):
    ug = module.ug
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Antwort({}, 503))
    with pytest.raises(ug.PCloudFehler) as f1:
        ug.userinfo_pruefen(token="t", host="eapi.pcloud.com")
    assert f1.value.art == "http 503"
    monkeypatch.setattr(httpx, "get", lambda *a, **k: (_ for _ in ()).throw(
        httpx.ConnectError("Zaunstein " + TOKEN)))
    with pytest.raises(ug.PCloudFehler) as f2:
        ug.userinfo_pruefen(token="t", host="eapi.pcloud.com")
    assert f2.value.art == "netz" and "Zaunstein" not in str(f2.value) + repr(f2.value)

    class KeinJson:
        status_code = 200

        def json(self):
            raise ValueError("Zaunstein")

    monkeypatch.setattr(httpx, "get", lambda *a, **k: KeinJson())
    with pytest.raises(ug.PCloudFehler) as f3:
        ug.userinfo_pruefen(token="t", host="eapi.pcloud.com")
    assert f3.value.art == "json"


def test_fehlerart_gibt_nie_fremde_werte_aus(module):
    gemeinsam = module.gemeinsam

    class Boese(Exception):
        art = "Anna-Zaunstein-Krankenhaus " + TOKEN

    assert gemeinsam.fehlerart(Boese("Zaunstein")) == "Boese"
    assert gemeinsam.fehlerart(ValueError("Zaunstein")) == "ValueError"

    class Gut(Exception):
        art = "abgelehnt 2000"

    assert gemeinsam.fehlerart(Gut()) == "abgelehnt 2000"
    assert set(gemeinsam.ERLAUBTE_ARTEN) == set(module.ug.ARTEN)


def test_ungueltiger_zielpfad_in_ordner_auflisten_nennt_den_pfad_nicht(module):
    ug = module.ug
    with pytest.raises(ug.PCloudFehler) as fehler:
        ug.ordner_auflisten(pfad="/Zaunstein/geheim", token="t", host="eapi.pcloud.com")
    assert "Zaunstein" not in str(fehler.value) + repr(fehler.value) + fehler.value.art


@pytest.mark.parametrize("methode", ["stat", "checksumfile"])
def test_lauf_mit_hostiler_pcloud_antwort_gibt_nichts_preis(welt, capsys, methode):
    welt.lauf("--schreiben")
    capsys.readouterr()
    welt.att.antwort_override[methode] = _Antwort(
        {"result": 2000, "error": "Anna-Zaunstein-Krankenhaus.jpg " + TOKEN})
    anzahl = welt.att.aufrufe["uploadfile"]
    assert welt.lauf("--schreiben") == 1
    aus = capsys.readouterr()
    text = aus.out + aus.err
    for wort in SENSIBEL + (TOKEN,):
        assert wort not in text
    assert "Fehlerarten: abgelehnt 2000 x5" in text
    assert welt.att.aufrufe["uploadfile"] == anzahl


# ═══════════════════════════════════════════════════════════════════════════
# 10. Nachbesserung R2: Inhalt der Manifestzeilen, Schreibfehler, Ordnerweg
# ═══════════════════════════════════════════════════════════════════════════

def _manifest_aendern(welt, aenderung, *, letzte=False):
    """Ein echtes Manifest laden, eine Zeile veraendern und zurueckschreiben."""
    zeilen = welt.manifest.read_text(encoding="utf-8").splitlines()
    index = len(zeilen) - 1 if letzte else 0
    obj = json.loads(zeilen[index])
    aenderung(obj)
    zeilen[index] = json.dumps(obj, ensure_ascii=False)
    welt.manifest.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return index + 1


def _ohne(feld):
    return lambda obj: obj.pop(feld)


def _setze(feld, wert):
    return lambda obj: obj.__setitem__(feld, wert)


UNGUELTIGE_ZEILEN = [
    ("vorab_ohne_kennung", False, _ohne("kennung")),
    ("vorab_ohne_pfad", False, _ohne("pfad")),
    ("vorab_ohne_sha256", False, _ohne("sha256")),
    ("vorab_ohne_ordner_id", False, _ohne("ordner_id")),
    ("vorab_ordner_id_text", False, _setze("ordner_id", "7")),
    ("vorab_cloud_name_zahl", False, _setze("cloud_name", 5)),
    ("vorab_kennung_leer", False, _setze("kennung", "")),
    ("vorab_kennung_zahl", False, _setze("kennung", 12)),
    ("unbekannter_zustand", False, _setze("zustand", "geisterhaft")),
    ("zustand_fehlt", False, _ohne("zustand")),
    ("zustand_zahl", False, _setze("zustand", 3)),
    ("pfad_liste", False, _setze("pfad", ["a"])),
    ("groesse_text", False, _setze("groesse", "12")),
    ("groesse_bool", False, _setze("groesse", True)),
    ("ergebnis_ohne_fileid", True, _ohne("fileid")),
    ("ergebnis_fileid_text", True, _setze("fileid", "12")),
    ("ergebnis_fileid_bool", True, _setze("fileid", True)),
    ("ergebnis_ohne_kennung", True, _ohne("kennung")),
    ("ergebnis_ordner_id_text", True, _setze("ordner_id", "7")),
]


@pytest.mark.parametrize("name,letzte,aenderung", UNGUELTIGE_ZEILEN,
                         ids=[x[0] for x in UNGUELTIGE_ZEILEN])
def test_gueltiges_json_aber_unvollstaendige_zeile_ist_exit_3_ohne_upload(
        eine, capsys, name, letzte, aenderung):
    assert eine.lauf("--schreiben") == 0
    nr = _manifest_aendern(eine, aenderung, letzte=letzte)
    _bild(eine.wurzel / "IMG-20240101-WA0007.jpg", "neues-bild")
    capsys.readouterr()
    uploads, gesamt = eine.att.aufrufe["uploadfile"], eine.att.gesamt
    for zusatz in (("--schreiben",), ()):
        assert eine.lauf(*zusatz) == 3
        aus = capsys.readouterr()
        meldung = aus.err.strip().splitlines()
        assert len(meldung) == 1 and f"Zeile {nr}" in meldung[0]
        for wort in SENSIBEL + (TOKEN,):
            assert wort not in aus.out + aus.err
        assert "IMG-" not in aus.out + aus.err and "empfangen" not in aus.out + aus.err
    assert eine.att.aufrufe["uploadfile"] == uploads and eine.att.gesamt == gesamt
    assert not eine.sperre.exists()


def test_marker_mit_falschem_feldtyp_ist_exit_3(eine, capsys):
    assert eine.lauf("--schreiben") == 0
    with open(eine.manifest, "a", encoding="utf-8", newline="\n") as datei:
        datei.write('{"zeit": "z", "zustand": "vorab_abgebrochen", "zeile": "drei"}\n')
    uploads = eine.att.aufrufe["uploadfile"]
    assert eine.lauf("--schreiben") == 3
    assert eine.att.aufrufe["uploadfile"] == uploads


def test_unvollstaendige_letzte_zeile_ohne_umbruch_aber_gueltiges_json_ist_exit_3(eine):
    assert eine.lauf("--schreiben") == 0
    with open(eine.manifest, "ab") as datei:
        datei.write(b'{"zustand": "upload_begonnen", "pfad": "p", "sha256": "s"}')
    with pytest.raises(eine.gemeinsam.Voraussetzung) as fehler:
        eine.wa.manifest_streng_lesen(str(eine.manifest))
    assert "Zeile" in fehler.value.meldung and "upload_begonnen" not in fehler.value.meldung


def test_alle_fuenf_zustaende_mit_vollstaendigen_feldern_werden_gelesen(eine):
    eine.ablage.mkdir()
    basis = '"pfad": "p", "sha256": "s", "kennung": "k"'
    voll = basis + ', "ordner_id": 7, "cloud_name": "n_wak.jpg"'
    zeilen = [
        '{"zustand": "upload_begonnen", ' + voll + ', "groesse": 3, "mtime": 5}',
        '{"zustand": "hochgeladen", ' + voll + ', "fileid": 12}',
        '{"zustand": "unklar_begonnen", ' + voll + '}',
        '{"zustand": "fehlt_in_cloud", ' + basis + '}',
        '{"zustand": "unklar", ' + basis + '}',
        '{"zustand": "vorab_abgebrochen", "zeile": 9}',
    ]
    eine.manifest.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    gelesen = eine.wa.manifest_streng_lesen(str(eine.manifest))
    assert len(gelesen.zeilen) == 6


# ── Schreibfehler jeder Art stoppen den Lauf ───────────────────────────────

class _KaputteDatei:
    """Stellt eine echte Manifestdatei dar, deren write() einen Fehler wirft."""

    def __init__(self, echt, fehler):
        self._echt, self._fehler = echt, fehler

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self._echt.close()
        return False

    def write(self, text):
        raise self._fehler

    def __getattr__(self, name):
        return getattr(self._echt, name)


SCHREIBFEHLER = [
    UnicodeEncodeError("utf-8", "\udc80", 0, 1, "surrogates not allowed"),
    ValueError("Zaunstein kaputt"),
    TypeError("Zaunstein kaputt"),
    RuntimeError("Zaunstein kaputt"),
]


@pytest.mark.parametrize("fehler", SCHREIBFEHLER, ids=lambda f: type(f).__name__)
@pytest.mark.parametrize("beim_wievielten", [1, 2])
def test_jeder_schreibfehler_stoppt_den_lauf_exit_1(welt, capsys, monkeypatch, fehler,
                                                    beim_wievielten):
    echt = builtins.open
    zaehler = []

    def oeffnen(datei, mode="r", *a, **k):
        f = echt(datei, mode, *a, **k)
        if str(datei) == str(welt.manifest) and "a" in mode:
            zaehler.append(1)
            if len(zaehler) >= beim_wievielten:
                return _KaputteDatei(f, fehler)
        return f

    monkeypatch.setattr(builtins, "open", oeffnen)
    assert welt.lauf("--schreiben") == 1
    aus = capsys.readouterr()
    assert welt.att.aufrufe["uploadfile"] == beim_wievielten - 1      # danach keiner mehr
    assert "Lauf gestoppt" in aus.out
    assert "Zaunstein" not in aus.out + aus.err
    assert not welt.sperre.exists()


def test_manifestschreiber_wandelt_alle_fehler_in_manifestfehler(module, tmp_path):
    wa = module.wa
    schreiber = wa.ManifestSchreiber(str(tmp_path / "m.jsonl"), lambda: "z")
    for eintrag in ({"pfad": "a\udc80b.jpg"},          # nicht kodierbar
                    {"pfad": {1, 2}},                  # nicht serialisierbar
                    {"pfad": float("nan"), "x": object()}):
        with pytest.raises(wa.ManifestFehler) as fehler:
            schreiber.anhaengen(eintrag)
        assert str(fehler.value) == "" and fehler.value.__cause__ is None
    assert not (tmp_path / "m.jsonl").exists() or (tmp_path / "m.jsonl").read_bytes() == b""


def test_nicht_kodierbarer_dateiname_im_manifest_stoppt_lauf(eine, capsys, monkeypatch):
    wa = eine.wa
    echt = wa.Lauf._buche

    def buche(self, rel, sha, v, zustand, **zusatz):
        return echt(self, "bild\udc80.jpg", sha, v, zustand, **zusatz)

    monkeypatch.setattr(wa.Lauf, "_buche", buche)
    assert eine.lauf("--schreiben") == 1
    assert eine.att.aufrufe["uploadfile"] == 0
    assert "Lauf gestoppt" in capsys.readouterr().out


# ── Ordnerweg mit fester Fehlerart ─────────────────────────────────────────

HOSTILE_ORDNER_ANTWORTEN = [
    ({"result": 2000, "error": "Ordner Anna-Zaunstein-Krankenhaus " + TOKEN}, 200),
    ({"result": "Anna-Zaunstein-Krankenhaus", "error": TOKEN}, 200),
    ({"result": 0, "metadata": {"name": "Anna-Zaunstein-Krankenhaus"}}, 200),   # keine folderid
    ({"result": 0, "metadata": {"folderid": "Familie_Zaunstein"}}, 200),
    ({}, 503),
]


@pytest.mark.parametrize("antwort,status", HOSTILE_ORDNER_ANTWORTEN)
def test_ordnerweg_gibt_nur_feste_fehlerarten_aus(welt, capsys, antwort, status):
    welt.att.antwort_override["createfolderifnotexists"] = _Antwort(antwort, status)
    assert welt.lauf("--schreiben") == 1
    aus = capsys.readouterr()
    text = aus.out + aus.err
    for wort in SENSIBEL + (TOKEN,):
        assert wort not in text
    assert "Fehlerarten: " in text
    assert welt.att.aufrufe["uploadfile"] == 0


def test_ordnerweg_zaehlt_die_fehlerart_mit_code(welt, capsys):
    welt.att.antwort_override["createfolderifnotexists"] = _Antwort(
        {"result": 2000, "error": "Datei Anna-Zaunstein-Krankenhaus.jpg " + TOKEN})
    assert welt.lauf("--schreiben") == 1
    assert "Fehlerarten: abgelehnt 2000 x5" in capsys.readouterr().out


@pytest.mark.parametrize("antwort,status", HOSTILE_ORDNER_ANTWORTEN)
def test_ordner_huelle_wirft_nur_pcloudfehler_ohne_text_und_ohne_kontext(
        module, monkeypatch, antwort, status):
    wa, ug = module.wa, module.ug
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Antwort(antwort, status))
    with pytest.raises(ug.PCloudFehler) as fehler:
        wa.ordner_holen_sicher(ug, "/Agent/Zaunstein/2019", token=TOKEN, host="eapi.pcloud.com")
    _alles_pruefen(module.gemeinsam, fehler.value)
    assert fehler.value.__cause__ is None and fehler.value.__context__ is None


def test_ordner_huelle_verbirgt_auch_zielpfad_und_netzfehlertext(module, monkeypatch):
    wa, ug = module.wa, module.ug
    with pytest.raises(ug.PCloudFehler) as f1:
        wa.ordner_holen_sicher(ug, "/Zaunstein/geheim", token=TOKEN, host="eapi.pcloud.com")
    assert "Zaunstein" not in str(f1.value) + repr(f1.value) + f1.value.art
    assert f1.value.art == "aufruf"

    def netz(*a, **k):
        raise httpx.ConnectError("Zaunstein " + TOKEN)

    monkeypatch.setattr(httpx, "get", netz)
    with pytest.raises(ug.PCloudFehler) as f2:
        wa.ordner_holen_sicher(ug, "/Agent/x", token=TOKEN, host="eapi.pcloud.com")
    _alles_pruefen(module.gemeinsam, f2.value)
    assert f2.value.art == "netz" and f2.value.__context__ is None


def test_ordner_huelle_gibt_den_ordner_zurueck(module, monkeypatch):
    wa, ug = module.wa, module.ug
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Antwort(
        {"result": 0, "metadata": {"folderid": 42}}))
    assert wa.ordner_holen_sicher(ug, "/Agent/x", token="t", host="eapi.pcloud.com") == 42


# ═══════════════════════════════════════════════════════════════════════════
# 11. Nachbesserung R3: weder __cause__ noch __context__ tragen Fremdtext
# ═══════════════════════════════════════════════════════════════════════════

def _kette_leer(fehler):
    """Die Ausnahme haengt an keiner Ursache und an keinem Kontext."""
    assert fehler.__cause__ is None, repr(fehler.__cause__)
    assert fehler.__context__ is None, repr(fehler.__context__)


def _sauber(fehler):
    _kette_leer(fehler)
    text = str(fehler) + repr(fehler) + repr(getattr(fehler, "args", ()))
    for wort in SENSIBEL + (TOKEN,):
        assert wort not in text


def test_manifest_schreibfehler_traegt_weder_ursache_noch_kontext(module, tmp_path, monkeypatch):
    wa = module.wa
    echt = builtins.open

    def kaputt(datei, mode="r", *a, **k):
        if "a" in mode:
            raise OSError(28, "Platte voll bei Anna-Zaunstein-Krankenhaus.jpg " + TOKEN)
        return echt(datei, mode, *a, **k)

    schreiber = wa.ManifestSchreiber(str(tmp_path / "m.jsonl"), lambda: "z")
    monkeypatch.setattr(builtins, "open", kaputt)
    with pytest.raises(wa.ManifestFehler) as f1:
        schreiber.anhaengen({"pfad": "x"})
    _sauber(f1.value)
    monkeypatch.setattr(builtins, "open", echt)
    with pytest.raises(wa.ManifestFehler) as f2:
        schreiber.anhaengen({"pfad": "Anna-Zaunstein-Krankenhaus\udc80.jpg"})   # nicht kodierbar
    _sauber(f2.value)


def test_api_lesen_netzfehler_traegt_weder_ursache_noch_kontext(module, monkeypatch):
    ug = module.ug

    def netz(*a, **k):
        raise httpx.ConnectError("Verbindung zu /Agent/Zaunstein/x?auth=" + TOKEN + " verloren")

    monkeypatch.setattr(httpx, "get", netz)
    with pytest.raises(ug.PCloudFehler) as fehler:
        ug.userinfo_pruefen(token=TOKEN, host="eapi.pcloud.com")
    assert fehler.value.art == "netz"
    _sauber(fehler.value)


def test_api_lesen_json_fehler_traegt_weder_ursache_noch_kontext(module, monkeypatch):
    ug = module.ug

    class KeinJson:
        status_code = 200

        def json(self):
            raise ValueError("kaputt Anna-Zaunstein-Krankenhaus " + TOKEN)

    monkeypatch.setattr(httpx, "get", lambda *a, **k: KeinJson())
    with pytest.raises(ug.PCloudFehler) as fehler:
        ug.stat_datei(5, token=TOKEN, host="eapi.pcloud.com")
    assert fehler.value.art == "json"
    _sauber(fehler.value)


def test_upload_netz_und_jsonfehler_tragen_weder_ursache_noch_kontext(module):
    ug = module.ug

    def netz(*a, **k):
        raise httpx.ConnectError("Upload /Agent/Zaunstein/a.jpg " + TOKEN)

    with pytest.raises(ug.PCloudFehler) as f1:
        ug.hochladen_ohne_ueberschreiben("a.jpg", b"x", 5, token=TOKEN, host="eapi.pcloud.com",
                                         senden=netz)
    assert f1.value.art == "netz"
    _sauber(f1.value)

    class KeinJson:
        status_code = 200

        def json(self):
            raise ValueError("Familie_Zaunstein " + TOKEN)

    with pytest.raises(ug.PCloudFehler) as f2:
        ug.hochladen_ohne_ueberschreiben("a.jpg", b"x", 5, token=TOKEN, host="eapi.pcloud.com",
                                         senden=lambda *a, **k: KeinJson())
    assert f2.value.art == "json"
    _sauber(f2.value)


def test_ordner_auflisten_ungueltiger_pfad_traegt_keinen_kontext(module):
    ug = module.ug
    with pytest.raises(ug.PCloudFehler) as fehler:
        ug.ordner_auflisten(pfad="/Zaunstein/geheim", token="t", host="eapi.pcloud.com")
    _sauber(fehler.value)


def test_ordnerweg_traegt_keinen_kontext_auch_bei_netzfehler(module, monkeypatch):
    wa, ug = module.wa, module.ug

    def netz(*a, **k):
        raise httpx.ConnectError("Zaunstein " + TOKEN)

    monkeypatch.setattr(httpx, "get", netz)
    with pytest.raises(ug.PCloudFehler) as fehler:
        wa.ordner_holen_sicher(ug, "/Agent/x", token=TOKEN, host="eapi.pcloud.com")
    _sauber(fehler.value)


def test_voraussetzungen_tragen_keinen_kontext(module, monkeypatch, tmp_path):
    gemeinsam, wa = module.gemeinsam, module.wa

    # httpx nicht importierbar
    echt_import = gemeinsam.importlib.import_module

    def ohne_httpx(name, *a, **k):
        if name == "httpx":
            raise ImportError("kein httpx bei Zaunstein " + TOKEN)
        return echt_import(name, *a, **k)

    monkeypatch.setattr(gemeinsam.importlib, "import_module", ohne_httpx)
    with pytest.raises(gemeinsam.Voraussetzung) as f1:
        gemeinsam.httpx_pruefen()
    _sauber(f1.value)
    monkeypatch.setattr(gemeinsam.importlib, "import_module", echt_import)

    # Medienordner nicht lesbar
    def liste(pfad):
        raise OSError(13, "verboten Zaunstein")

    monkeypatch.setattr(os, "listdir", liste)
    with pytest.raises(gemeinsam.Voraussetzung) as f2:
        gemeinsam._ordner_listen(str(tmp_path))
    _sauber(f2.value)
    monkeypatch.undo()

    # Manifest nicht lesbar
    datei = tmp_path / "m.jsonl"
    datei.write_text("{}\n", encoding="utf-8")
    echt_open = builtins.open

    def kaputt(pfad, mode="r", *a, **k):
        if str(pfad) == str(datei):
            raise OSError(13, "verboten Zaunstein")
        return echt_open(pfad, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", kaputt)
    with pytest.raises(gemeinsam.Voraussetzung) as f3:
        wa.manifest_streng_lesen(str(datei))
    _sauber(f3.value)
    monkeypatch.setattr(builtins, "open", echt_open)

    # Sperre: vorhanden und nicht anlegbar
    sperre = tmp_path / "sperre"
    sperre.mkdir()
    with pytest.raises(gemeinsam.Voraussetzung) as f4:
        wa._sperre_nehmen(str(sperre))
    _sauber(f4.value)

    def kein_mkdir(pfad, *a, **k):
        raise OSError(13, "verboten Zaunstein")

    monkeypatch.setattr(os, "mkdir", kein_mkdir)
    with pytest.raises(gemeinsam.Voraussetzung) as f5:
        wa._sperre_nehmen(str(tmp_path / "neu"))
    _sauber(f5.value)


def test_userinfo_pruefung_von_w0_traegt_keinen_kontext(tmp_path, monkeypatch, module):
    monkeypatch.syspath_prepend(str(HANDY))
    import whatsapp_bilder_zaehlen as wz
    for name in ("PCLOUD_TOKEN", "PCLOUD_HOST", "PCLOUD_UEBERGABE_MANIFEST"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(module.ug, "ENV_DATEI", tmp_path / "keine.env")
    monkeypatch.setenv("PCLOUD_TOKEN", TOKEN)

    def netz(*a, **k):
        raise httpx.ConnectError("Zaunstein " + TOKEN)

    monkeypatch.setattr(httpx, "get", netz)
    with pytest.raises(module.gemeinsam.Voraussetzung) as fehler:
        wz.voraussetzungen_pruefen()
    _sauber(fehler.value)


# ── Wächter: kein "raise <Ausnahme>" innerhalb eines except-Handlers ───────

def _neuer_teil_von_uebergabe(baum):
    """Zeilenbereich des NEUEN Teils: ab ``ERLAUBTE_LESE_METHODEN`` bis Ende von
    ``hochladen_ohne_ueberschreiben`` (der Altcode davor und danach bleibt unberuehrt)."""
    anfang = ende = None
    for knoten in baum.body:
        if isinstance(knoten, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "ERLAUBTE_LESE_METHODEN"
                for t in knoten.targets):
            anfang = knoten.lineno
        if isinstance(knoten, ast.FunctionDef) and knoten.name == "hochladen_ohne_ueberschreiben":
            ende = knoten.end_lineno
    assert anfang and ende and anfang < ende
    return anfang, ende


def _raise_in_handlern(pfad, von=0, bis=10 ** 9):
    baum = ast.parse(pfad.read_text(encoding="utf-8"))
    funde = []
    for handler in ast.walk(baum):
        if not isinstance(handler, ast.ExceptHandler):
            continue
        if not (von <= handler.lineno <= bis):
            continue
        for stmt in handler.body:
            for knoten in ast.walk(stmt):
                if isinstance(knoten, ast.Raise) and knoten.exc is not None:
                    funde.append(knoten.lineno)
    return sorted(set(funde))


def test_waechter_kein_raise_mit_ausnahme_in_except_der_werkzeuge():
    """Im ``except`` wird nur ein Merkmal gesetzt; die neue Ausnahme kommt DANACH.

    Erlaubt bleibt das blanke ``raise`` (reicht dieselbe, schon sichere Ausnahme
    weiter, erzeugt keinen neuen Kontext) — genutzt nur in ``ordner_holen_sicher``.
    """
    for name in ("whatsapp_bilder_gemeinsam.py", "whatsapp_bilder_zaehlen.py",
                 "whatsapp_bilder_hochladen.py"):
        assert _raise_in_handlern(HANDY / name) == [], name
    baum = ast.parse(PFAD_UEBERGABE.read_text(encoding="utf-8"))
    von, bis = _neuer_teil_von_uebergabe(baum)
    assert _raise_in_handlern(PFAD_UEBERGABE, von, bis) == []


def test_waechter_findet_ein_raise_im_handler(tmp_path):
    """Gegenprobe: der Waechter schlaegt bei dem verbotenen Muster wirklich an."""
    datei = tmp_path / "x.py"
    datei.write_text("def f():\n    try:\n        pass\n    except Exception:\n"
                     "        raise ValueError('x') from None\n"
                     "def g():\n    try:\n        pass\n    except Exception:\n        raise\n",
                     encoding="utf-8")
    assert _raise_in_handlern(datei) == [5]


def test_waechter_bereich_in_uebergabe_umfasst_die_neuen_funktionen():
    baum = ast.parse(PFAD_UEBERGABE.read_text(encoding="utf-8"))
    von, bis = _neuer_teil_von_uebergabe(baum)
    namen = {k.name: k.lineno for k in baum.body if isinstance(k, ast.FunctionDef)}
    for neu in ("_api_lesen", "userinfo_pruefen", "stat_datei", "pruefsumme_cloud",
                "ordner_auflisten", "hochladen_ohne_ueberschreiben"):
        assert von <= namen[neu] <= bis
    for alt in ("hochladen", "_api_get", "ordner_holen_oder_anlegen"):
        assert not (von <= namen[alt] <= bis)


# ═══════════════════════════════════════════════════════════════════════════
# 12. Nachbesserung R4: Altcode-Leser (.env) reicht keine fremde Ausnahme durch
# ═══════════════════════════════════════════════════════════════════════════

def _kaputte_env(welt, monkeypatch):
    """Eine .env mit ungueltigem UTF-8 UND erfundenem Token; kein Token in der Umgebung."""
    env = welt.tmp / "kaputt.env"
    env.write_bytes(b"PCLOUD_TOKEN=" + TOKEN.encode("utf-8") + b"\n\xff\xfe\x80 Zaunstein\n")
    monkeypatch.delenv("PCLOUD_TOKEN", raising=False)
    monkeypatch.delenv("PCLOUD_HOST", raising=False)
    monkeypatch.setattr(welt.ug, "ENV_DATEI", env)
    return env


def test_kaputte_env_w1_ist_exit_3_ohne_token_und_ohne_netz(eine, capsys, monkeypatch):
    _kaputte_env(eine, monkeypatch)
    for zusatz in ((), ("--schreiben",)):
        assert eine.lauf(*zusatz) == 3
        aus = capsys.readouterr()
        text = aus.out + aus.err
        for wort in SENSIBEL + (TOKEN,):
            assert wort not in text
        assert "UnicodeDecodeError" not in text and "Fehler: unerwarteter" not in text
        assert len(aus.err.strip().splitlines()) == 1
    assert eine.att.gesamt == 0 and not eine.manifest.exists() and not eine.sperre.exists()


def test_kaputte_env_w0_voraussetzungen_ist_exit_3(eine, capsys, monkeypatch):
    monkeypatch.syspath_prepend(str(HANDY))
    import whatsapp_bilder_zaehlen as wz
    _kaputte_env(eine, monkeypatch)
    assert wz.main(["--ordner", str(eine.wurzel), "--voraussetzungen"]) == 3
    aus = capsys.readouterr()
    text = aus.out + aus.err
    for wort in SENSIBEL + (TOKEN,):
        assert wort not in text
    assert "UnicodeDecodeError" not in text and "Fehler: unerwarteter" not in text
    assert len(aus.err.strip().splitlines()) == 1
    assert eine.att.gesamt == 0


def test_zugang_aufloesen_aus_kaputter_env_ohne_ursache_und_kontext(eine, monkeypatch):
    _kaputte_env(eine, monkeypatch)
    with pytest.raises(eine.gemeinsam.Voraussetzung) as fehler:
        eine.gemeinsam.zugang_aufloesen()
    _sauber(fehler.value)


@pytest.mark.parametrize("stelle", ["_token_aus_quellen", "_host_aus_quellen"])
@pytest.mark.parametrize("ausnahme", [
    RuntimeError("Altcode-Leser Anna-Zaunstein-Krankenhaus " + TOKEN),
    UnicodeDecodeError("utf-8", b"\xff", 0, 1, "Zaunstein " + TOKEN),
    KeyError(TOKEN),
], ids=lambda a: type(a).__name__)
def test_attrappe_altcode_leser_wirft_beliebig_feste_meldung(eine, monkeypatch, stelle, ausnahme):
    def kaputt(*a, **k):
        raise ausnahme

    monkeypatch.setattr(eine.ug, stelle, kaputt)
    with pytest.raises(eine.gemeinsam.Voraussetzung) as fehler:
        eine.gemeinsam.zugang_aufloesen()
    _sauber(fehler.value)


def test_attrappe_altcode_leser_im_lauf_gibt_exit_3_und_nichts_preis(eine, capsys, monkeypatch):
    def kaputt(*a, **k):
        raise RuntimeError("Altcode Anna-Zaunstein-Krankenhaus " + TOKEN)

    monkeypatch.setattr(eine.ug, "_token_aus_quellen", kaputt)
    assert eine.lauf("--schreiben") == 3
    aus = capsys.readouterr()
    for wort in SENSIBEL + (TOKEN,):
        assert wort not in aus.out + aus.err
    assert eine.att.gesamt == 0


def test_laden_des_altcode_moduls_scheitert_mit_fester_meldung(module, monkeypatch):
    gemeinsam = module.gemeinsam

    class Lader:
        def exec_module(self, modul):
            raise RuntimeError("Syntax bei Anna-Zaunstein-Krankenhaus " + TOKEN)

    spez = SimpleNamespace(loader=Lader())
    monkeypatch.setattr(gemeinsam, "_UEBERGABE", None)
    monkeypatch.setattr(gemeinsam.importlib.util, "spec_from_file_location",
                        lambda *a, **k: spez)
    monkeypatch.setattr(gemeinsam.importlib.util, "module_from_spec",
                        lambda s: SimpleNamespace())
    with pytest.raises(gemeinsam.Voraussetzung) as fehler:
        gemeinsam.uebergabe_laden()
    _sauber(fehler.value)


def test_neuer_teil_von_uebergabe_liest_zugang_mit_fester_art(module, monkeypatch, tmp_path):
    ug = module.ug
    env = tmp_path / "kaputt.env"
    env.write_bytes(b"PCLOUD_TOKEN=" + TOKEN.encode("utf-8") + b"\n\xff\xfe\n")
    monkeypatch.delenv("PCLOUD_TOKEN", raising=False)
    monkeypatch.delenv("PCLOUD_HOST", raising=False)
    monkeypatch.setattr(ug, "ENV_DATEI", env)
    aufrufe = (
        lambda: ug.userinfo_pruefen(),
        lambda: ug.stat_datei(5),
        lambda: ug.ordner_auflisten(folderid=5),
        lambda: ug.hochladen_ohne_ueberschreiben("a.jpg", b"x", 5),
    )
    for aufruf in aufrufe:
        with pytest.raises(ug.PCloudFehler) as fehler:
            aufruf()
        assert fehler.value.art == "konfig"
        _sauber(fehler.value)


# ═══════════════════════════════════════════════════════════════════════════
# 13. Nachbesserung R5: Huellen um _im_repo und ziel_pfad_pruefen, Bestandsliste
# ═══════════════════════════════════════════════════════════════════════════

def _lauf_mit(eine, *zusatz):
    return eine.lauf(*zusatz)


@pytest.mark.parametrize("ausnahme", [
    OSError(13, "Zugriff verweigert: /home/Anna-Zaunstein-Krankenhaus/m.jsonl " + TOKEN),
    RuntimeError("kaputt Familie_Zaunstein " + TOKEN),
    ValueError(TOKEN),
], ids=lambda a: type(a).__name__)
def test_im_repo_fehler_ist_exit_2_ohne_pfad_und_text(eine, capsys, monkeypatch, ausnahme):
    def kaputt(pfad):
        raise ausnahme

    monkeypatch.setattr(eine.ug, "_im_repo", kaputt)
    for zusatz in ((), ("--schreiben",)):
        assert eine.lauf(*zusatz) == 2
        aus = capsys.readouterr()
        text = aus.out + aus.err
        for wort in SENSIBEL + (TOKEN, str(eine.tmp)):
            assert wort not in text
        assert "unerwarteter Abbruch" not in text
        assert len(aus.err.strip().splitlines()) == 1 and "Manifestpfad" in aus.err
    assert eine.att.gesamt == 0 and not eine.sperre.exists() and not eine.manifest.exists()


@pytest.mark.parametrize("ausnahme", [
    RuntimeError("kaputt Anna-Zaunstein-Krankenhaus " + TOKEN),
    TypeError(TOKEN),
], ids=lambda a: type(a).__name__)
def test_ziel_pruefung_mit_fremder_ausnahme_ist_exit_2(eine, capsys, monkeypatch, ausnahme):
    def kaputt(pfad):
        raise ausnahme

    monkeypatch.setattr(eine.ug, "ziel_pfad_pruefen", kaputt)
    assert eine.lauf() == 2
    aus = capsys.readouterr()
    for wort in SENSIBEL + (TOKEN,):
        assert wort not in aus.out + aus.err
    assert "unerwarteter Abbruch" not in aus.out + aus.err and "--ziel" in aus.err
    assert eine.att.gesamt == 0


def test_im_repo_huelle_direkt_wirft_nur_feste_ausnahme(module):
    wa, ug = module.wa, module.ug

    class Boese(Exception):
        pass

    def kaputt(pfad):
        raise Boese("Pfad /Zaunstein/geheim " + TOKEN)

    echt = ug._im_repo
    ug._im_repo = kaputt
    try:
        with pytest.raises(wa.AufrufFehler) as fehler:
            wa.manifest_im_repo(ug, "/Zaunstein/geheim/m.jsonl")
    finally:
        ug._im_repo = echt
    _sauber(fehler.value)
    assert "Zaunstein" not in str(fehler.value) and fehler.value.args == (wa.MELDUNG_MANIFEST_PRUEFEN,)


def test_im_repo_huelle_liefert_wahrheitswert(module, tmp_path):
    wa, ug = module.wa, module.ug
    assert wa.manifest_im_repo(ug, str(tmp_path / "m.jsonl")) is False
    assert wa.manifest_im_repo(ug, str(PROJEKT / "m.jsonl")) is True


def test_ziel_huelle_direkt_wirft_nur_feste_ausnahme(module):
    wa, ug = module.wa, module.ug
    with pytest.raises(wa.AufrufFehler) as f1:
        wa.ziel_pruefen(ug, "/Zaunstein/geheim")            # UebergabeFehler mit Pfad im Text
    _sauber(f1.value)
    assert f1.value.args == (wa.MELDUNG_ZIEL,)

    echt = ug.ziel_pfad_pruefen

    def kaputt(pfad):
        raise RuntimeError("Familie_Zaunstein " + TOKEN)

    ug.ziel_pfad_pruefen = kaputt
    try:
        with pytest.raises(wa.AufrufFehler) as f2:
            wa.ziel_pruefen(ug, "/Agent/x")
    finally:
        ug.ziel_pfad_pruefen = echt
    _sauber(f2.value)
    assert wa.ziel_pruefen(ug, "/Agent/x/") == "/Agent/x"


# ── Bestandsliste: jedem Altcode-Namen ist ein Test zugeordnet ─────────────

ALTCODE_ZUORDNUNG = {
    "whatsapp_bilder_gemeinsam.py": {
        "_host_aus_quellen": "test_attrappe_altcode_leser_wirft_beliebig_feste_meldung",
        "_token_aus_quellen": "test_attrappe_altcode_leser_wirft_beliebig_feste_meldung",
    },
    "whatsapp_bilder_zaehlen.py": {
        "userinfo_pruefen": "test_userinfo_pruefung_von_w0_traegt_keinen_kontext",
        "UebergabeFehler": "test_userinfo_pruefung_von_w0_traegt_keinen_kontext",
    },
    "whatsapp_bilder_hochladen.py": {
        "ordner_holen_oder_anlegen":
            "test_ordner_huelle_wirft_nur_pcloudfehler_ohne_text_und_ohne_kontext",
        "PCloudFehler": "test_art_enthaelt_nur_geprueften_ganzzahligen_code",
        "PCloudNichtGefunden": "test_art_enthaelt_nur_geprueften_ganzzahligen_code",
        "_jetzt_iso": "test_schreiblauf_laedt_hoch_und_bucht",
        "stat_datei": "test_lauf_mit_hostiler_pcloud_antwort_gibt_nichts_preis",
        "pruefsumme_cloud": "test_lauf_mit_hostiler_pcloud_antwort_gibt_nichts_preis",
        "ordner_auflisten": "test_ordner_auflisten_ungueltiger_pfad_traegt_keinen_kontext",
        "ziel_pfad_pruefen": "test_ziel_huelle_direkt_wirft_nur_feste_ausnahme",
        "_im_repo": "test_im_repo_huelle_direkt_wirft_nur_feste_ausnahme",
        "hochladen_ohne_ueberschreiben":
            "test_upload_netz_und_jsonfehler_tragen_weder_ursache_noch_kontext",
    },
}


def _ug_zugriffe(name):
    baum = ast.parse((HANDY / name).read_text(encoding="utf-8"))
    gefunden = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Attribute) and (
                (isinstance(knoten.value, ast.Name) and knoten.value.id == "ug")
                or (isinstance(knoten.value, ast.Attribute) and knoten.value.attr == "ug")):
            gefunden.add(knoten.attr)
    return gefunden


def test_alle_altcode_aufrufe_der_werkzeuge_sind_erfasst():
    """Jeder Zugriff der drei Werkzeugdateien auf den Altcode ``ug`` steht in der
    Zuordnung (und nur dort) — neue Aufrufe muessen bewusst eingetragen werden."""
    for name, zuordnung in ALTCODE_ZUORDNUNG.items():
        assert _ug_zugriffe(name) == set(zuordnung), (name, _ug_zugriffe(name) ^ set(zuordnung))


def test_jedem_altcode_namen_ist_ein_vorhandener_test_zugeordnet():
    vorhanden = {k.name for k in ast.walk(ast.parse(Path(__file__).read_text(encoding="utf-8")))
                 if isinstance(k, ast.FunctionDef) and k.name.startswith("test_")}
    for name, zuordnung in ALTCODE_ZUORDNUNG.items():
        for altname, testname in zuordnung.items():
            assert testname in vorhanden, (name, altname, testname)


# ═══════════════════════════════════════════════════════════════════════════
# 14. Nachbesserung R6: Leerzeilen im Manifest sind ein Fehler, CRLF ist gueltig
# ═══════════════════════════════════════════════════════════════════════════
# Entscheidung CRLF: Der Schreiber schreibt nur "\n". Eine Zeile "{...}\r\n" ist aber
# inhaltlich vollstaendig (z. B. von einem Windows-Editor angefasst); sie wird gueltig
# gelesen (ein einzelnes abschliessendes "\r" wird abgezogen). Eine Zeile, die nach dem
# Abziehen leer ist, bleibt ein Fehler wie jede andere Leerzeile.

def _manifest_mit_leerzeile(welt, leer, *, ende=False):
    """Echtes Manifest laden und an Stelle 1 (oder am Ende) eine Leerzeile einfuegen."""
    zeilen = welt.manifest.read_bytes().split(b"\n")[:-1]
    if ende:
        zeilen.append(leer)
        nr = len(zeilen)
    else:
        zeilen.insert(1, leer)
        nr = 2
    welt.manifest.write_bytes(b"\n".join(zeilen) + b"\n")
    return nr


@pytest.mark.parametrize("leer", [b"", b"   ", b"\t", b"\r", b" \r"],
                         ids=["leer", "leerzeichen", "tab", "nur_cr", "leerzeichen_cr"])
@pytest.mark.parametrize("ende", [False, True], ids=["mitte", "ende"])
def test_leerzeile_im_manifest_ist_exit_3_ohne_upload(eine, capsys, leer, ende):
    assert eine.lauf("--schreiben") == 0
    nr = _manifest_mit_leerzeile(eine, leer, ende=ende)
    _bild(eine.wurzel / "IMG-20240101-WA0007.jpg", "neues-bild")
    capsys.readouterr()
    uploads, gesamt = eine.att.aufrufe["uploadfile"], eine.att.gesamt
    for zusatz in (("--schreiben",), ()):
        assert eine.lauf(*zusatz) == 3
        aus = capsys.readouterr()
        meldung = aus.err.strip().splitlines()
        assert len(meldung) == 1 and f"Zeile {nr}" in meldung[0]
        for wort in SENSIBEL + (TOKEN,):
            assert wort not in aus.out + aus.err
    assert eine.att.aufrufe["uploadfile"] == uploads and eine.att.gesamt == gesamt
    assert not eine.sperre.exists()


def test_leerzeile_ohne_abschliessenden_umbruch_ist_ein_fehler(eine):
    assert eine.lauf("--schreiben") == 0
    with open(eine.manifest, "ab") as datei:
        datei.write(b"   ")                            # nur Leerzeichen, kein Umbruch
    with pytest.raises(eine.gemeinsam.Voraussetzung) as fehler:
        eine.wa.manifest_streng_lesen(str(eine.manifest))
    assert "Zeile 3" in fehler.value.meldung


def test_doppelter_umbruch_am_ende_ist_ein_fehler(eine):
    assert eine.lauf("--schreiben") == 0
    with open(eine.manifest, "ab") as datei:
        datei.write(b"\n")                             # "...}\n\n"
    with pytest.raises(eine.gemeinsam.Voraussetzung) as fehler:
        eine.wa.manifest_streng_lesen(str(eine.manifest))
    assert "Zeile 3" in fehler.value.meldung


def test_datei_endet_mit_umbruch_wird_normal_gelesen(eine):
    assert eine.lauf("--schreiben") == 0
    roh = eine.manifest.read_bytes()
    assert roh.endswith(b"\n") and not roh.endswith(b"\n\n")
    gelesen = eine.wa.manifest_streng_lesen(str(eine.manifest))
    assert gelesen.ohne_umbruch is False and len(gelesen.zeilen) == 2
    assert eine.manifest.read_bytes() == roh              # Lesen aendert nichts


def test_leeres_manifest_und_nur_umbruch(eine):
    eine.ablage.mkdir()
    eine.manifest.write_bytes(b"")
    assert eine.wa.manifest_streng_lesen(str(eine.manifest)).zeilen == []
    eine.manifest.write_bytes(b"\n")                       # eine Leerzeile, keine Zeilen
    with pytest.raises(eine.gemeinsam.Voraussetzung) as fehler:
        eine.wa.manifest_streng_lesen(str(eine.manifest))
    assert "Zeile 1" in fehler.value.meldung


def test_reparatur_der_halben_zeile_erzeugt_keine_leerzeile(eine, capsys):
    assert eine.lauf("--schreiben") == 0
    eine.manifest.write_bytes(eine.manifest.read_bytes()
                              + b'{"zeit": "2026-10-22T10:00:00+02:00", "pfad": "empfangen/IMG-2024')
    _bild(eine.wurzel / "IMG-20240101-WA0007.jpg", "neues-bild")
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 0
    for _ in range(2):                                      # und weitere Laeufe bleiben lesbar
        roh = eine.manifest.read_bytes()
        assert roh.endswith(b"\n") and b"\n\n" not in roh
        assert all(z.strip() for z in roh.split(b"\n")[:-1])
        eine.wa.manifest_streng_lesen(str(eine.manifest))   # wirft nicht
        assert eine.lauf("--schreiben") == 0


def test_crlf_zeilenenden_werden_gueltig_gelesen(eine, capsys):
    assert eine.lauf("--schreiben") == 0
    eine.manifest.write_bytes(eine.manifest.read_bytes().replace(b"\n", b"\r\n"))
    uploads = eine.att.aufrufe["uploadfile"]
    gelesen = eine.wa.manifest_streng_lesen(str(eine.manifest))
    assert len(gelesen.zeilen) == 2 and gelesen.ohne_umbruch is False
    capsys.readouterr()
    assert eine.lauf("--schreiben") == 0                    # erledigt, kein neuer Upload
    assert kennzahlen(capsys.readouterr().out)["erledigt"] == 1
    assert eine.att.aufrufe["uploadfile"] == uploads


def test_crlf_leerzeile_ist_trotzdem_ein_fehler(eine):
    assert eine.lauf("--schreiben") == 0
    eine.manifest.write_bytes(eine.manifest.read_bytes().replace(b"\n", b"\r\n\r\n", 1))
    with pytest.raises(eine.gemeinsam.Voraussetzung) as fehler:
        eine.wa.manifest_streng_lesen(str(eine.manifest))
    assert "Zeile 2" in fehler.value.meldung


def test_crlf_mit_halber_letzter_zeile_wird_repariert(eine, capsys):
    assert eine.lauf("--schreiben") == 0
    eine.manifest.write_bytes(eine.manifest.read_bytes().replace(b"\n", b"\r\n")
                              + b'{"zeit": "z", "pfad": "empfangen/IMG-20')
    _bild(eine.wurzel / "IMG-20240101-WA0007.jpg", "neues-bild")
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 0
    eine.wa.manifest_streng_lesen(str(eine.manifest))


# ═══════════════════════════════════════════════════════════════════════════
# 15. Nachbesserung R7: unlesbare letzte Zeile nur mit --letzte-zeile-verwerfen
# ═══════════════════════════════════════════════════════════════════════════
# Ein Schreibabbruch und eine Beschaedigung (NUL, BOM, fremder Zeilentrenner) sind am
# Inhalt nicht sicher zu unterscheiden. Ohne Zustimmung: Exit 3 vor jedem Upload.

VORAB_B = (b'{"zeit": "2026-10-22T10:00:00+02:00", "pfad": "empfangen/2024/IMG-20240101-WA0007.jpg", '
           b'"groesse": 11, "sha256": "ab12", "mtime": 1700000000, "kennung": "aabbccddeeff", '
           b'"zustand": "upload_begonnen", "fileid": null, "cloud_name": "IMG-20240101-WA0007_waaabbccddeeff.jpg", '
           b'"ordner_id": 5}')

U2028 = chr(0x2028).encode("utf-8")

BESCHAEDIGUNGEN = {
    "nul": VORAB_B[:40] + b"\x00" + VORAB_B[40:],
    "nul_am_ende": VORAB_B + b"\x00",
    "bom_vorn": b"\xef\xbb\xbf" + VORAB_B,
    "u2028_am_ende": VORAB_B + U2028,
    "u2028_mitten": VORAB_B[:1] + U2028 + VORAB_B[1:],
    "abgeschnitten": VORAB_B[:77],
    "kein_utf8": VORAB_B[:50] + b"\xff\xfe" + VORAB_B[50:],
}


def _manifest_mit_beschaedigter_letzter_zeile(welt, kaputt):
    """Eine heile Datei A im Manifest, danach eine beschaedigte letzte Zeile (ohne Umbruch)."""
    assert welt.lauf("--schreiben") == 0
    welt.manifest.write_bytes(welt.manifest.read_bytes() + kaputt)
    _bild(welt.wurzel / "IMG-20240101-WA0007.jpg", "neues-bild-b")


def _markierungen(welt):
    treffer = []
    for zeile in welt.manifest.read_bytes().split(b"\n"):
        try:
            eintrag = json.loads(zeile.decode("utf-8"))
        except ValueError:
            continue
        if isinstance(eintrag, dict) and eintrag.get("zustand") == "vorab_abgebrochen":
            treffer.append(eintrag)
    return treffer


@pytest.mark.parametrize("name", sorted(BESCHAEDIGUNGEN))
def test_beschaedigte_letzte_zeile_ohne_option_ist_exit_3_vor_jedem_upload(eine, capsys, name):
    _manifest_mit_beschaedigter_letzter_zeile(eine, BESCHAEDIGUNGEN[name])
    roh = eine.manifest.read_bytes()
    capsys.readouterr()
    uploads, gesamt = eine.att.aufrufe["uploadfile"], eine.att.gesamt
    for zusatz in (("--schreiben",), ()):
        assert eine.lauf(*zusatz) == 3
        aus = capsys.readouterr()
        meldung = aus.err.strip().splitlines()
        assert len(meldung) == 1 and "Zeile 3" in meldung[0]
        assert "--letzte-zeile-verwerfen" in meldung[0]
        for wort in SENSIBEL + (TOKEN,):
            assert wort not in aus.out + aus.err
        assert "IMG-" not in aus.out + aus.err
    assert eine.att.aufrufe["uploadfile"] == uploads and eine.att.gesamt == gesamt
    assert eine.manifest.read_bytes() == roh                   # nichts veraendert
    assert not eine.sperre.exists()


@pytest.mark.parametrize("name", sorted(BESCHAEDIGUNGEN))
def test_beschaedigte_letzte_zeile_mit_option_genau_eine_markierung_keine_dublette(
        eine, capsys, name):
    _manifest_mit_beschaedigter_letzter_zeile(eine, BESCHAEDIGUNGEN[name])
    roh = eine.manifest.read_bytes()
    capsys.readouterr()
    uploads = eine.att.aufrufe["uploadfile"]
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 0
    z = kennzahlen(capsys.readouterr().out)
    assert z["erledigt"] == 1 and z["hochgeladen"] == 1         # A nicht doppelt, B neu
    assert eine.att.aufrufe["uploadfile"] == uploads + 1 and len(eine.att.dateien) == 2
    neu = eine.manifest.read_bytes()
    assert neu.startswith(roh)                                  # nichts geloescht/ueberschrieben
    assert len(_markierungen(eine)) == 1
    gelesen = eine.wa.manifest_streng_lesen(str(eine.manifest))  # danach streng lesbar
    assert sum(1 for x in gelesen.zeilen if x["zustand"] == "vorab_abgebrochen") == 1
    assert b"\n\n" not in neu and neu.endswith(b"\n")
    for _ in range(2):                                          # weitere Laeufe ohne Option
        assert eine.lauf("--schreiben") == 0
    assert len(_markierungen(eine)) == 1 and eine.att.aufrufe["uploadfile"] == uploads + 1


def test_markierung_wird_sofort_geschrieben_auch_ohne_neuen_upload(eine, capsys):
    assert eine.lauf("--schreiben") == 0
    eine.manifest.write_bytes(eine.manifest.read_bytes() + BESCHAEDIGUNGEN["nul"])
    uploads = eine.att.aufrufe["uploadfile"]
    capsys.readouterr()
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 0
    assert eine.att.aufrufe["uploadfile"] == uploads
    assert len(_markierungen(eine)) == 1
    eine.wa.manifest_streng_lesen(str(eine.manifest))
    assert eine.lauf("--schreiben") == 0                        # ohne Option wieder normal
    assert eine.lauf() == 0


def test_option_ohne_schreiben_ist_exit_2_ohne_netz(eine, capsys):
    capsys.readouterr()
    assert eine.lauf("--letzte-zeile-verwerfen") == 2
    aus = capsys.readouterr()
    assert "--letzte-zeile-verwerfen" in aus.err and "--schreiben" in aus.err
    assert eine.att.gesamt == 0 and not eine.manifest.exists() and not eine.sperre.exists()


def test_option_ohne_schreiben_ist_auch_bei_beschaedigter_datei_exit_2(eine, capsys):
    _manifest_mit_beschaedigter_letzter_zeile(eine, BESCHAEDIGUNGEN["nul"])
    roh = eine.manifest.read_bytes()
    assert eine.lauf("--letzte-zeile-verwerfen") == 2
    assert eine.manifest.read_bytes() == roh


def test_option_bei_gesunder_datei_hat_keine_wirkung_und_sagt_das(eine, capsys):
    assert eine.lauf("--schreiben") == 0
    roh = eine.manifest.read_bytes()
    capsys.readouterr()
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 0
    aus = capsys.readouterr().out
    hinweise = [z for z in aus.splitlines() if "letzte-zeile-verwerfen" in z]
    assert len(hinweise) == 1 and "ohne Wirkung" in hinweise[0]
    assert eine.manifest.read_bytes() == roh and _markierungen(eine) == []


def test_option_bei_fehlendem_manifest_hat_keine_wirkung(eine, capsys):
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 0
    aus = capsys.readouterr().out
    assert sum("ohne Wirkung" in z for z in aus.splitlines()) == 1
    assert _markierungen(eine) == []


def test_option_gilt_nicht_fuer_beschaedigte_zeile_mit_umbruch(eine, capsys):
    """Nur 'letzte Zeile ohne Umbruch' — eine beschaedigte Zeile MIT Umbruch bleibt Fehler."""
    _manifest_mit_beschaedigter_letzter_zeile(eine, BESCHAEDIGUNGEN["nul"] + b"\n")
    uploads = eine.att.aufrufe["uploadfile"]
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 3
    assert eine.att.aufrufe["uploadfile"] == uploads and _markierungen(eine) == []


def test_option_gilt_nicht_fuer_semantisch_ungueltige_letzte_zeile(eine):
    assert eine.lauf("--schreiben") == 0
    eine.manifest.write_bytes(eine.manifest.read_bytes()
                              + b'{"zustand": "upload_begonnen", "pfad": "p"}')
    uploads = eine.att.aufrufe["uploadfile"]
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 3
    assert eine.att.aufrufe["uploadfile"] == uploads


def test_streng_lesen_ohne_zustimmung_wirft_mit_zeilennummer_und_hinweis(eine):
    assert eine.lauf("--schreiben") == 0
    eine.manifest.write_bytes(eine.manifest.read_bytes() + BESCHAEDIGUNGEN["abgeschnitten"])
    with pytest.raises(eine.gemeinsam.Voraussetzung) as fehler:
        eine.wa.manifest_streng_lesen(str(eine.manifest))
    assert "Zeile 3" in fehler.value.meldung and "--letzte-zeile-verwerfen" in fehler.value.meldung
    stand = eine.wa.manifest_streng_lesen(str(eine.manifest), letzte_zeile_verwerfen=True)
    assert stand.abgebrochene_zeile == 3 and stand.ohne_umbruch is True


def test_hilfetext_der_option_nennt_schreiben_und_bekannten_abbruch(eine, capsys):
    with pytest.raises(SystemExit):
        eine.wa._argumente(["--help"])
    hilfe = " ".join(capsys.readouterr().out.split())
    assert "--letzte-zeile-verwerfen" in hilfe and "--schreiben" in hilfe


# ═══════════════════════════════════════════════════════════════════════════
# 16. Nachbesserung R8: stat/checksumfile-Widerspruch ist unklar; atomare Reparatur
# ═══════════════════════════════════════════════════════════════════════════

def _nach_erstlauf(welt):
    assert welt.lauf("--schreiben") == 0
    return welt.att.aufrufe["uploadfile"], welt.manifest.read_bytes()


def _zustaende(welt):
    return [x["zustand"] for x in manifest_zeilen(welt.manifest)]


@pytest.mark.parametrize("antwort", [
    _Antwort({"result": 2009, "error": "File not found Anna-Zaunstein-Krankenhaus " + TOKEN}),
    _Antwort({"result": 2002, "error": "nicht da"}),
    _Antwort({"result": 0, "sha256": "kurz"}),                 # keine gueltige Pruefsumme
    _Antwort({"result": 0}),
    _Antwort({"result": 0, "sha256": "z" * 64}),
], ids=["2009", "2002", "ungueltig_kurz", "ohne_summe", "kein_hex"])
def test_stat_findet_datei_checksumfile_nicht_ist_unklar_ohne_upload(eine, capsys, antwort):
    uploads, _roh = _nach_erstlauf(eine)
    eine.att.antwort_override["checksumfile"] = antwort
    capsys.readouterr()
    for _ in range(2):                                          # auch im Folgelauf
        assert eine.lauf("--schreiben") == 0
        z = kennzahlen(capsys.readouterr().out)
        assert z["unklar"] == 1 and z["fehlt_in_cloud"] == 0 and z["erledigt"] == 0
        assert eine.att.aufrufe["uploadfile"] == uploads and len(eine.att.dateien) == 1
    assert _zustaende(eine).count("unklar") == 1               # nur einmal gebucht
    assert "fehlt_in_cloud" not in _zustaende(eine)
    fileid = [x for x in manifest_zeilen(eine.manifest) if x["zustand"] == "hochgeladen"][0]["fileid"]
    assert fileid not in eine.wa.entfernbare_fileids(manifest_zeilen(eine.manifest))
    del eine.att.antwort_override["checksumfile"]                # Widerspruch weg -> wieder normal
    assert eine.lauf("--schreiben") == 0
    assert kennzahlen(capsys.readouterr().out)["erledigt"] == 1
    assert eine.att.aufrufe["uploadfile"] == uploads


@pytest.mark.parametrize("antwort,status", [
    ({"result": 2000, "error": "Log in required " + TOKEN}, 200),
    ({}, 503),
], ids=["abgelehnt_2000", "http_503"])
def test_anderer_checksumfile_fehler_zaehlt_fehlerart_ohne_upload(eine, capsys, antwort, status):
    uploads, _roh = _nach_erstlauf(eine)
    eine.att.antwort_override["checksumfile"] = _Antwort(antwort, status)
    capsys.readouterr()
    assert eine.lauf("--schreiben") == 1
    aus = capsys.readouterr()
    assert kennzahlen(aus.out)["fehler"] == 1 and "Fehlerarten: " in aus.out
    for wort in SENSIBEL + (TOKEN,):
        assert wort not in aus.out + aus.err
    assert eine.att.aufrufe["uploadfile"] == uploads
    assert "unklar" not in _zustaende(eine) and "fehlt_in_cloud" not in _zustaende(eine)


def test_stat_nicht_gefunden_bleibt_fehlt_in_cloud_mit_neuem_upload(eine, capsys):
    uploads, _roh = _nach_erstlauf(eine)
    echte_get = eine.att.get
    fileid = [x for x in manifest_zeilen(eine.manifest) if x["zustand"] == "hochgeladen"][0]["fileid"]
    # nur DIESE Datei ist fuer stat "nicht gefunden"; neue Dateien werden normal belegt
    eine.att.dateien.pop(fileid)
    capsys.readouterr()
    assert eine.lauf("--schreiben") == 0
    z = kennzahlen(capsys.readouterr().out)
    assert z["fehlt_in_cloud"] == 1 and z["hochgeladen"] == 1
    assert eine.att.aufrufe["uploadfile"] == uploads + 1
    assert "fehlt_in_cloud" in _zustaende(eine)


# ── Atomare Reparatur mit --letzte-zeile-verwerfen ─────────────────────────

def _kopien(welt):
    return sorted(p.name for p in welt.ablage.iterdir() if ".vor_verwerfen_" in p.name)


def _temps(welt):
    """Alle Temp-Dateien der Reparatur: ``<manifest>.verwerfen_<stempel>.tmp``."""
    vorn = welt.manifest.name + ".verwerfen_"
    return sorted(p.name for p in welt.ablage.iterdir()
                  if p.name.startswith(vorn) and p.name.endswith(".tmp"))


def _ist_temp_pfad(welt, pfad):
    name = os.path.basename(str(pfad))
    return name.startswith(welt.manifest.name + ".verwerfen_") and name.endswith(".tmp")


def _beschaedigt(welt):
    _manifest_mit_beschaedigter_letzter_zeile(welt, BESCHAEDIGUNGEN["nul"])
    return welt.manifest.read_bytes()


def test_reparatur_legt_kopie_an_und_ersetzt_atomar(eine, capsys):
    roh = _beschaedigt(eine)
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 0
    kopien = _kopien(eine)
    assert len(kopien) == 1
    assert (eine.ablage / kopien[0]).read_bytes() == roh           # Kopie = alter Stand
    neu = eine.manifest.read_bytes()
    assert neu.startswith(roh + b"\n") and neu.endswith(b"\n") and b"\n\n" not in neu
    assert len(_markierungen(eine)) == 1 and _temps(eine) == []
    eine.wa.manifest_streng_lesen(str(eine.manifest))


def test_abbruch_vor_os_replace_laesst_manifest_unveraendert_und_zweiter_lauf_gelingt(
        eine, capsys, monkeypatch):
    roh = _beschaedigt(eine)
    echt = os.replace

    def abbruch(quelle, ziel, *a, **k):
        raise AbbruchWieKill()

    monkeypatch.setattr(os, "replace", abbruch)
    with pytest.raises(AbbruchWieKill):
        eine.lauf("--schreiben", "--letzte-zeile-verwerfen")
    assert eine.manifest.read_bytes() == roh                        # byteweise unveraendert
    assert len(_temps(eine)) == 1 and len(_kopien(eine)) == 1
    assert _markierungen(eine) == [] and not eine.sperre.exists()
    # Ausweg funktioniert erneut; die verwaiste Temp-Datei bleibt unveraendert liegen
    monkeypatch.setattr(os, "replace", echt)
    verwaist = _temps(eine)
    verwaist_inhalt = (eine.ablage / verwaist[0]).read_bytes()
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 0
    assert _temps(eine) == verwaist                                  # nichts umbenannt, nichts neu
    assert (eine.ablage / verwaist[0]).read_bytes() == verwaist_inhalt
    assert len(_kopien(eine)) == 2                                   # je Versuch eine Kopie
    assert len(_markierungen(eine)) == 1
    eine.wa.manifest_streng_lesen(str(eine.manifest))


def test_abbruch_nach_os_replace_ist_fertig_und_ohne_option_streng_lesbar(
        eine, capsys, monkeypatch):
    roh = _beschaedigt(eine)
    echt = os.replace

    def danach_abbruch(quelle, ziel, *a, **k):
        echt(quelle, ziel, *a, **k)
        raise AbbruchWieKill()

    monkeypatch.setattr(os, "replace", danach_abbruch)
    with pytest.raises(AbbruchWieKill):
        eine.lauf("--schreiben", "--letzte-zeile-verwerfen")
    monkeypatch.setattr(os, "replace", echt)
    assert len(_kopien(eine)) == 1 and _temps(eine) == []
    assert (eine.ablage / _kopien(eine)[0]).read_bytes() == roh
    eine.wa.manifest_streng_lesen(str(eine.manifest))                # ohne Option lesbar
    assert len(_markierungen(eine)) == 1
    uploads = eine.att.aufrufe["uploadfile"]
    capsys.readouterr()
    assert eine.lauf("--schreiben") == 0                             # ohne Option normal
    assert eine.att.aufrufe["uploadfile"] == uploads + 1             # Datei B neu, A nicht doppelt
    assert len(_markierungen(eine)) == 1


def test_teilweise_geschriebene_temp_datei_laesst_manifest_unveraendert(eine, monkeypatch):
    roh = _beschaedigt(eine)
    echt = builtins.open

    class HalbSchreiber:
        def __init__(self, datei):
            self._datei = datei

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self._datei.close()
            return False

        def write(self, daten):
            self._datei.write(daten[: len(daten) // 2])             # nur die Haelfte
            self._datei.flush()
            raise AbbruchWieKill()

        def __getattr__(self, name):
            return getattr(self._datei, name)

    def oeffnen(datei, mode="r", *a, **k):
        f = echt(datei, mode, *a, **k)
        return HalbSchreiber(f) if _ist_temp_pfad(eine, datei) else f

    monkeypatch.setattr(builtins, "open", oeffnen)
    with pytest.raises(AbbruchWieKill):
        eine.lauf("--schreiben", "--letzte-zeile-verwerfen")
    monkeypatch.setattr(builtins, "open", echt)
    assert eine.manifest.read_bytes() == roh                         # kein Zwischenstand
    verwaist = _temps(eine)
    assert len(verwaist) == 1
    halb = (eine.ablage / verwaist[0]).read_bytes()
    assert 0 < len(halb) < len(roh) + 200
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 0  # Ausweg bleibt offen
    assert _temps(eine) == verwaist and (eine.ablage / verwaist[0]).read_bytes() == halb
    assert len(_markierungen(eine)) == 1
    eine.wa.manifest_streng_lesen(str(eine.manifest))


def test_fehler_beim_kopieren_oder_ersetzen_stoppt_mit_exit_1_und_aendert_nichts(
        eine, capsys, monkeypatch):
    roh = _beschaedigt(eine)

    def kaputt(quelle, ziel, *a, **k):
        raise OSError(28, "Platte voll bei Anna-Zaunstein-Krankenhaus " + TOKEN)

    monkeypatch.setattr(os, "replace", kaputt)
    uploads = eine.att.aufrufe["uploadfile"]
    capsys.readouterr()
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 1
    aus = capsys.readouterr()
    for wort in SENSIBEL + (TOKEN,):
        assert wort not in aus.out + aus.err
    assert "Lauf gestoppt" in aus.out
    assert eine.manifest.read_bytes() == roh and eine.att.aufrufe["uploadfile"] == uploads


def test_reparatur_loescht_nichts(eine, monkeypatch):
    """Bestehende Kopien und Temp-Dateien bleiben byteweise gleich (nicht nur die Namen)."""
    roh = _beschaedigt(eine)
    echt = os.replace
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(AbbruchWieKill()))
    with pytest.raises(AbbruchWieKill):                              # liefert Kopie + verwaiste Temp
        eine.lauf("--schreiben", "--letzte-zeile-verwerfen")
    monkeypatch.setattr(os, "replace", echt)
    vorher = {p.name: p.read_bytes() for p in eine.ablage.iterdir() if p.name != eine.manifest.name}
    assert len(vorher) == 2 and len(_kopien(eine)) == 1 and len(_temps(eine)) == 1
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 0
    nachher = {p.name: p.read_bytes() for p in eine.ablage.iterdir()}
    assert eine.manifest.name in nachher and len(_kopien(eine)) == 2
    for name, inhalt in vorher.items():
        assert nachher[name] == inhalt                               # byteweise unveraendert
    assert nachher[eine.manifest.name].startswith(roh)


def test_temp_name_der_erst_nach_der_namenswahl_entsteht_wird_nie_ueberschrieben(
        eine, monkeypatch):
    """Kollision zwischen Namenswahl und Anlegen: der fremde Inhalt bleibt, ein neuer Name gilt."""
    roh = _beschaedigt(eine)
    echt = builtins.open
    fremd = b"fremde Datei, die waehrend der Namenswahl entstand"
    belegt = []

    def oeffnen(datei, mode="r", *a, **k):
        if "x" in mode and _ist_temp_pfad(eine, datei) and not belegt:
            belegt.append(str(datei))
            with echt(datei, "wb") as f:                    # jemand war schneller
                f.write(fremd)
        return echt(datei, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", oeffnen)
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 0
    monkeypatch.setattr(builtins, "open", echt)
    assert len(belegt) == 1
    assert Path(belegt[0]).read_bytes() == fremd                 # nicht ueberschrieben
    assert _temps(eine) == [os.path.basename(belegt[0])]         # nur die fremde Datei bleibt
    assert eine.manifest.read_bytes().startswith(roh + b"\n")
    assert len(_markierungen(eine)) == 1
    eine.wa.manifest_streng_lesen(str(eine.manifest))


def test_kopie_name_der_erst_nach_der_namenswahl_entsteht_wird_nie_ueberschrieben(
        eine, monkeypatch):
    roh = _beschaedigt(eine)
    echt = builtins.open
    fremd = b"fremde Kopie"
    belegt = []

    def oeffnen(datei, mode="r", *a, **k):
        if "x" in mode and ".vor_verwerfen_" in os.path.basename(str(datei)) and not belegt:
            belegt.append(str(datei))
            with echt(datei, "wb") as f:
                f.write(fremd)
        return echt(datei, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", oeffnen)
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 0
    monkeypatch.setattr(builtins, "open", echt)
    assert Path(belegt[0]).read_bytes() == fremd
    kopien = _kopien(eine)
    assert len(kopien) == 2
    echte = [k for k in kopien if str(eine.ablage / k) != belegt[0]]
    assert (eine.ablage / echte[0]).read_bytes() == roh


def test_zwei_versuche_in_derselben_sekunde_bekommen_verschiedene_temp_namen(eine, monkeypatch):
    """Auch bei gleichem Zeitstempel kollidieren zwei abgebrochene Versuche nicht."""
    _beschaedigt(eine)
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(AbbruchWieKill()))
    monkeypatch.setattr("time.strftime", lambda *a, **k: "20261022T120000")
    monkeypatch.setattr("secrets.token_hex", lambda *a, **k: "abc123")
    for _ in range(2):
        with pytest.raises(AbbruchWieKill):
            eine.lauf("--schreiben", "--letzte-zeile-verwerfen")
    assert len(_temps(eine)) == 2 and len(_kopien(eine)) == 2


def _umbenennungen_in(pfad):
    """Zeilen mit ``rename``/``renames``/``shutil.move``/``import shutil`` im Quelltext (AST)."""
    funde = []
    for knoten in ast.walk(ast.parse(Path(pfad).read_text(encoding="utf-8"))):
        if isinstance(knoten, ast.Attribute) and knoten.attr in ("rename", "renames", "move"):
            funde.append(knoten.lineno)
        elif isinstance(knoten, ast.Name) and knoten.id in ("rename", "renames", "move"):
            funde.append(knoten.lineno)
        elif isinstance(knoten, ast.Import) and any(a.name == "shutil" for a in knoten.names):
            funde.append(knoten.lineno)
        elif isinstance(knoten, ast.ImportFrom) and knoten.module in ("shutil", "os") \
                and any(a.name in ("rename", "renames", "move") for a in knoten.names):
            funde.append(knoten.lineno)
    return sorted(set(funde))


def test_waechter_kein_os_rename_und_kein_shutil_move_in_den_werkzeugen():
    for name in ("whatsapp_bilder_gemeinsam.py", "whatsapp_bilder_zaehlen.py",
                 "whatsapp_bilder_hochladen.py"):
        assert _umbenennungen_in(HANDY / name) == [], name


def test_waechter_umbenennungen_findet_das_verbotene_muster(tmp_path):
    datei = tmp_path / "x.py"
    datei.write_text("import os\nimport shutil\nos.rename('a', 'b')\nshutil.move('a', 'b')\n"
                     "from os import rename\n", encoding="utf-8")
    assert _umbenennungen_in(datei) == [2, 3, 4, 5]


# ═══════════════════════════════════════════════════════════════════════════
# 17. Nachbesserung R10: symbolische Links bei Manifest und Sperre
# ═══════════════════════════════════════════════════════════════════════════

def _link(ziel, name, ordner=False):
    """Symbolischer Link ``name`` -> ``ziel``; ohne Rechte (Windows) wird der Test uebersprungen."""
    try:
        os.symlink(str(ziel), str(name), target_is_directory=ordner)
    except (OSError, NotImplementedError, AttributeError) as grund:
        pytest.skip(f"symbolische Links nicht anlegbar ({type(grund).__name__})")


def _repo_attrappe(tmp):
    """Ein 'Repo' (Ordner mit .git) mit einer Datei darin; alles in tmp, ausserhalb des echten Repos."""
    repo = tmp / "fremdes_repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "unterordner").mkdir()
    datei = repo / "unterordner" / "m.jsonl"
    datei.write_bytes(b"unveraendert\n")
    return repo, datei


def _aufruf(welt, manifest, sperre, *zusatz):
    return welt.wa.main(["--ordner", str(welt.wurzel), "--manifest", str(manifest),
                         "--sperre", str(sperre), *zusatz])


def _schnappschuss(*ordner):
    ergebnis = {}
    for wurzel in ordner:
        for pfad in sorted(Path(wurzel).rglob("*")):
            if not pfad.is_symlink() and pfad.is_file():
                ergebnis[str(pfad)] = pfad.read_bytes()
            else:
                ergebnis[str(pfad)] = None
    return ergebnis


def _ohne_ausgabe_des_pfads(aus, welt):
    text = aus.out + aus.err
    for wort in SENSIBEL + (TOKEN, str(welt.tmp), "fremdes_repo", "m.jsonl"):
        assert wort not in text
    assert len(aus.err.strip().splitlines()) == 1


@pytest.mark.parametrize("zusatz", [(), ("--schreiben",)], ids=["trocken", "schreiben"])
def test_manifest_link_ausserhalb_auf_datei_im_repo_ist_exit_2(eine, capsys, zusatz):
    repo, datei = _repo_attrappe(eine.tmp)
    aussen = eine.tmp / "aussen"
    aussen.mkdir()
    _link(datei, aussen / "manifest.jsonl")
    vorher = _schnappschuss(repo)
    capsys.readouterr()
    assert _aufruf(eine, aussen / "manifest.jsonl", eine.sperre, *zusatz) == 2
    _ohne_ausgabe_des_pfads(capsys.readouterr(), eine)
    assert datei.read_bytes() == b"unveraendert\n" and _schnappschuss(repo) == vorher
    assert eine.att.gesamt == 0 and not eine.sperre.exists() and not eine.ablage.exists()


@pytest.mark.parametrize("zusatz", [(), ("--schreiben",)], ids=["trocken", "schreiben"])
def test_manifest_link_nach_aussen_ist_exit_2(eine, capsys, zusatz):
    ziel = eine.tmp / "ziel_aussen.jsonl"
    ziel.write_bytes(b"unveraendert\n")
    aussen = eine.tmp / "aussen"
    aussen.mkdir()
    _link(ziel, aussen / "manifest.jsonl")
    capsys.readouterr()
    assert _aufruf(eine, aussen / "manifest.jsonl", eine.sperre, *zusatz) == 2
    _ohne_ausgabe_des_pfads(capsys.readouterr(), eine)
    assert ziel.read_bytes() == b"unveraendert\n"
    assert eine.att.gesamt == 0 and not eine.sperre.exists()


@pytest.mark.parametrize("zusatz", [(), ("--schreiben",)], ids=["trocken", "schreiben"])
def test_toter_manifest_link_ist_exit_2_und_wird_nicht_angelegt(eine, capsys, zusatz):
    aussen = eine.tmp / "aussen"
    aussen.mkdir()
    ziel = eine.tmp / "gibt_es_nicht.jsonl"
    _link(ziel, aussen / "manifest.jsonl")
    capsys.readouterr()
    assert _aufruf(eine, aussen / "manifest.jsonl", eine.sperre, *zusatz) == 2
    _ohne_ausgabe_des_pfads(capsys.readouterr(), eine)
    assert not ziel.exists() and eine.att.gesamt == 0 and not eine.sperre.exists()


@pytest.mark.parametrize("zusatz", [(), ("--schreiben",)], ids=["trocken", "schreiben"])
def test_ordner_link_ausserhalb_der_ins_repo_zeigt_ist_exit_2(eine, capsys, zusatz):
    repo, datei = _repo_attrappe(eine.tmp)
    aussen = eine.tmp / "aussen"
    aussen.mkdir()
    _link(repo / "unterordner", aussen / "ordnerlink", ordner=True)
    vorher = _schnappschuss(repo)
    capsys.readouterr()
    assert _aufruf(eine, aussen / "ordnerlink" / "neu.jsonl", eine.sperre, *zusatz) == 2
    _ohne_ausgabe_des_pfads(capsys.readouterr(), eine)
    assert _schnappschuss(repo) == vorher and not (repo / "unterordner" / "neu.jsonl").exists()
    assert eine.att.gesamt == 0 and not eine.sperre.exists()


def test_ordner_link_ausserhalb_der_nach_aussen_zeigt_bleibt_erlaubt(eine, capsys):
    echt = eine.tmp / "echter_ordner"
    echt.mkdir()
    aussen = eine.tmp / "aussen"
    aussen.mkdir()
    _link(echt, aussen / "ordnerlink", ordner=True)
    capsys.readouterr()
    assert _aufruf(eine, aussen / "ordnerlink" / "m.jsonl", eine.sperre) == 0      # Trockenlauf
    assert not (echt / "m.jsonl").exists()
    assert _aufruf(eine, aussen / "ordnerlink" / "m.jsonl", eine.sperre, "--schreiben") == 0
    assert (echt / "m.jsonl").exists()                                             # echter Ort
    assert not eine.sperre.exists()


def test_reparatur_ueber_ordner_link_legt_kopie_und_temp_im_aufgeloesten_ordner_an(eine, capsys):
    """Kopie, Temp und os.replace gelten im aufgeloesten Ordner; der Link selbst bleibt."""
    echt = eine.tmp / "echter_ordner"
    echt.mkdir()
    aussen = eine.tmp / "aussen"
    aussen.mkdir()
    _link(echt, aussen / "ordnerlink", ordner=True)
    manifest = aussen / "ordnerlink" / "m.jsonl"
    assert _aufruf(eine, manifest, eine.sperre, "--schreiben") == 0
    roh = (echt / "m.jsonl").read_bytes() + BESCHAEDIGUNGEN["nul"]
    (echt / "m.jsonl").write_bytes(roh)
    _bild(eine.wurzel / "IMG-20240101-WA0007.jpg", "neues-bild-b")
    assert _aufruf(eine, manifest, eine.sperre, "--schreiben", "--letzte-zeile-verwerfen") == 0
    kopien = [p for p in echt.iterdir() if ".vor_verwerfen_" in p.name]
    assert len(kopien) == 1 and kopien[0].read_bytes() == roh
    assert not [p for p in echt.iterdir() if p.name.endswith(".tmp")]
    assert (aussen / "ordnerlink").is_symlink() and not (aussen / "m.jsonl").exists()
    eine.wa.manifest_streng_lesen(str(echt / "m.jsonl"))


@pytest.mark.parametrize("zusatz", [(), ("--schreiben",)], ids=["trocken", "schreiben"])
def test_sperre_link_ausserhalb_auf_ordner_im_repo_ist_exit_2(eine, capsys, zusatz):
    repo, datei = _repo_attrappe(eine.tmp)
    aussen = eine.tmp / "aussen"
    aussen.mkdir()
    _link(repo / "unterordner", aussen / "sperre", ordner=True)
    vorher = _schnappschuss(repo)
    capsys.readouterr()
    assert _aufruf(eine, eine.manifest, aussen / "sperre", *zusatz) == 2
    _ohne_ausgabe_des_pfads(capsys.readouterr(), eine)
    assert _schnappschuss(repo) == vorher and eine.att.gesamt == 0 and not eine.manifest.exists()


@pytest.mark.parametrize("zusatz", [(), ("--schreiben",)], ids=["trocken", "schreiben"])
def test_sperre_ordner_link_ausserhalb_der_ins_repo_zeigt_ist_exit_2(eine, capsys, zusatz):
    repo, datei = _repo_attrappe(eine.tmp)
    aussen = eine.tmp / "aussen"
    aussen.mkdir()
    _link(repo / "unterordner", aussen / "ordnerlink", ordner=True)
    vorher = _schnappschuss(repo)
    capsys.readouterr()
    assert _aufruf(eine, eine.manifest, aussen / "ordnerlink" / "sperre", *zusatz) == 2
    _ohne_ausgabe_des_pfads(capsys.readouterr(), eine)
    assert _schnappschuss(repo) == vorher and not (repo / "unterordner" / "sperre").exists()
    assert eine.att.gesamt == 0 and not eine.manifest.exists()


@pytest.mark.parametrize("zusatz", [(), ("--schreiben",)], ids=["trocken", "schreiben"])
def test_sperre_link_nach_aussen_und_toter_sperre_link_sind_exit_2(eine, capsys, zusatz):
    aussen = eine.tmp / "aussen"
    aussen.mkdir()
    echt = eine.tmp / "echte_sperre"
    echt.mkdir()
    _link(echt, aussen / "sperre_lebend", ordner=True)
    _link(eine.tmp / "gibt_es_nicht", aussen / "sperre_tot", ordner=True)
    for name in ("sperre_lebend", "sperre_tot"):
        capsys.readouterr()
        assert _aufruf(eine, eine.manifest, aussen / name, *zusatz) == 2
        _ohne_ausgabe_des_pfads(capsys.readouterr(), eine)
    assert echt.exists() and not (eine.tmp / "gibt_es_nicht").exists()
    assert eine.att.gesamt == 0 and not eine.manifest.exists()


def test_sperre_ordner_link_ausserhalb_der_nach_aussen_zeigt_bleibt_erlaubt(eine, capsys):
    echt = eine.tmp / "echter_ordner"
    echt.mkdir()
    aussen = eine.tmp / "aussen"
    aussen.mkdir()
    _link(echt, aussen / "ordnerlink", ordner=True)
    assert _aufruf(eine, eine.manifest, aussen / "ordnerlink" / "sperre") == 0
    assert _aufruf(eine, eine.manifest, aussen / "ordnerlink" / "sperre", "--schreiben") == 0
    assert not (echt / "sperre").exists()                                          # wieder frei


def test_link_pruefung_huelle_direkt_und_feste_meldungen(module, tmp_path):
    wa, ug = module.wa, module.ug
    repo, datei = _repo_attrappe(tmp_path)
    assert wa.manifest_im_repo(ug, str(tmp_path / "m.jsonl")) is False
    ziel = tmp_path / "ziel.jsonl"
    ziel.write_bytes(b"x")
    aussen = tmp_path / "aussen"
    aussen.mkdir()
    _link(datei, aussen / "m.jsonl")
    assert wa.manifest_im_repo(ug, str(aussen / "m.jsonl")) is True          # ueber realpath
    _link(ziel, aussen / "l.jsonl")
    with pytest.raises(wa.AufrufFehler) as fehler:
        wa.datei_kein_link(str(aussen / "l.jsonl"), wa.MELDUNG_MANIFEST_PRUEFEN)
    assert fehler.value.args == (wa.MELDUNG_MANIFEST_PRUEFEN,)
    assert fehler.value.__cause__ is None and fehler.value.__context__ is None
    wa.datei_kein_link(str(tmp_path / "gibt_es_nicht.jsonl"), wa.MELDUNG_MANIFEST_PRUEFEN)


# ═══════════════════════════════════════════════════════════════════════════
# 18. Nachbesserung R11: harte Links beim Manifest; "Sent" nie still leer
# ═══════════════════════════════════════════════════════════════════════════

def _hartlink(ziel, name):
    """Harter Link ``name`` -> ``ziel``; ohne Moeglichkeit wird der Test uebersprungen."""
    try:
        os.link(str(ziel), str(name))
    except (OSError, NotImplementedError, AttributeError) as grund:
        pytest.skip(f"harte Links nicht anlegbar ({type(grund).__name__})")


@pytest.mark.parametrize("zusatz", [(), ("--schreiben",)], ids=["trocken", "schreiben"])
def test_manifest_harter_link_ausserhalb_auf_repo_datei_ist_exit_2(eine, capsys, zusatz):
    repo, datei = _repo_attrappe(eine.tmp)
    aussen = eine.tmp / "aussen"
    aussen.mkdir()
    _hartlink(datei, aussen / "manifest.jsonl")
    vorher = _schnappschuss(repo)
    capsys.readouterr()
    assert _aufruf(eine, aussen / "manifest.jsonl", eine.sperre, *zusatz) == 2
    aus = capsys.readouterr()
    _ohne_ausgabe_des_pfads(aus, eine)
    assert "Manifestpfad" in aus.err
    assert datei.read_bytes() == b"unveraendert\n" and _schnappschuss(repo) == vorher
    assert eine.att.gesamt == 0 and not eine.sperre.exists() and not eine.ablage.exists()


def test_manifest_mit_einem_einzigen_namen_ist_weiter_erlaubt(eine, capsys):
    assert eine.lauf("--schreiben") == 0
    assert os.stat(eine.manifest).st_nlink == 1
    assert eine.lauf("--schreiben") == 0 and eine.lauf() == 0


class _StatMitLinkzahl:
    """os.stat-Ergebnis, dessen st_nlink ueberschrieben ist (alles andere echt)."""

    def __init__(self, echt, nlink):
        self._echt = echt
        self.st_nlink = nlink

    def __getattr__(self, name):
        return getattr(self._echt, name)


@pytest.mark.parametrize("ab", ["erster_aufruf", "nach_dem_upload"])
def test_nlink_springt_erst_vor_dem_anhaengen_auf_2_ist_exit_1_ohne_weiteren_upload(
        welt, capsys, monkeypatch, ab):
    welt.ablage.mkdir()
    welt.manifest.write_bytes(b"")                           # existiert, nlink 1
    echt_stat = os.stat
    ziel = os.path.normcase(os.path.realpath(str(welt.manifest)))

    def springt():
        return (welt.att.gesamt >= 1 if ab == "erster_aufruf"
                else welt.att.aufrufe["uploadfile"] >= 1)

    def stat(pfad, *a, **k):
        st = echt_stat(pfad, *a, **k)
        if os.path.normcase(os.path.realpath(str(pfad))) == ziel and springt():
            return _StatMitLinkzahl(st, 2)
        return st

    monkeypatch.setattr(os, "stat", stat)
    capsys.readouterr()
    assert welt.lauf("--schreiben") == 1
    aus = capsys.readouterr()
    assert "Lauf gestoppt" in aus.out and "Zaunstein" not in aus.out + aus.err
    for wort in SENSIBEL + (TOKEN,):
        assert wort not in aus.out + aus.err
    assert welt.att.aufrufe["uploadfile"] == (0 if ab == "erster_aufruf" else 1)
    text = welt.manifest.read_bytes()
    assert b"hochgeladen" not in text and b"upload_begonnen" not in (
        text if ab == "erster_aufruf" else b"")
    assert not welt.sperre.exists()


@pytest.mark.parametrize("ab_pruefung", [2, 3], ids=["vor_der_kopie", "vor_os_replace"])
def test_nlink_springt_bei_der_reparatur_auf_2_ist_exit_1_manifest_unveraendert(
        eine, capsys, monkeypatch, ab_pruefung):
    """Pruefung 1 = _lauf, 2 = vor der Kopie, 3 = vor os.replace; ab ``ab_pruefung`` gilt nlink 2."""
    roh = _beschaedigt(eine)
    echt_stat = os.stat
    ziel = os.path.normcase(os.path.realpath(str(eine.manifest)))
    zaehler = []
    ersetzt = []

    def stat(pfad, *a, **k):
        st = echt_stat(pfad, *a, **k)
        if os.path.normcase(os.path.realpath(str(pfad))) == ziel:
            zaehler.append(1)
            if len(zaehler) >= ab_pruefung:
                return _StatMitLinkzahl(st, 2)
        return st

    echt_replace = os.replace

    def ersetzen(quelle, ziel_pfad, *a, **k):
        ersetzt.append(1)
        return echt_replace(quelle, ziel_pfad, *a, **k)

    monkeypatch.setattr(os, "stat", stat)
    monkeypatch.setattr(os, "replace", ersetzen)
    uploads = eine.att.aufrufe["uploadfile"]
    capsys.readouterr()
    assert eine.lauf("--schreiben", "--letzte-zeile-verwerfen") == 1
    aus = capsys.readouterr()
    assert "Lauf gestoppt" in aus.out
    for wort in SENSIBEL + (TOKEN,):
        assert wort not in aus.out + aus.err
    assert eine.manifest.read_bytes() == roh and eine.att.aufrufe["uploadfile"] == uploads
    assert ersetzt == [] and len(zaehler) >= ab_pruefung


# ── "Sent" ist nie still leer (R11/2) ──────────────────────────────────────

def _sent_pfad(welt):
    return os.path.join(str(welt.wurzel), "Sent")


MELDUNG_MEDIEN = ("kein Zugriff auf den WhatsApp-Medienordner "
                  "(Termux-Speicherrecht: termux-setup-storage)")


def test_w1_sent_isdir_false_ist_exit_3_ohne_upload(welt, capsys, monkeypatch):
    echt = os.path.isdir
    sent = _sent_pfad(welt)
    monkeypatch.setattr(os.path, "isdir", lambda p: False if str(p) == sent else echt(p))
    for zusatz in (("--schreiben",), ()):
        capsys.readouterr()
        assert welt.lauf(*zusatz) == 3
        assert capsys.readouterr().err.strip() == MELDUNG_MEDIEN
    assert welt.att.gesamt == 0 and not welt.sperre.exists() and not welt.manifest.exists()


def test_w1_sent_als_datei_ist_exit_3_ohne_upload(eine, capsys):
    (eine.wurzel / "Sent").write_bytes(b"ich bin kein Ordner")
    for zusatz in (("--schreiben",), ()):
        capsys.readouterr()
        assert eine.lauf(*zusatz) == 3
        assert capsys.readouterr().err.strip() == MELDUNG_MEDIEN
    assert eine.att.gesamt == 0 and not eine.sperre.exists() and not eine.manifest.exists()


def test_w1_sent_stat_wirft_ist_exit_3_ohne_upload(welt, capsys, monkeypatch):
    echt = os.stat
    sent = _sent_pfad(welt)

    def stat(pfad, *a, **k):
        if str(pfad) == sent:
            raise PermissionError(13, f"Zugriff verweigert: {pfad}")
        return echt(pfad, *a, **k)

    monkeypatch.setattr(os, "stat", stat)
    for zusatz in (("--schreiben",), ()):
        capsys.readouterr()
        assert welt.lauf(*zusatz) == 3
        assert capsys.readouterr().err.strip() == MELDUNG_MEDIEN
    assert welt.att.gesamt == 0 and not welt.sperre.exists() and not welt.manifest.exists()


def test_w1_sent_fehlt_ganz_bleibt_exit_0(eine, capsys):
    assert not (eine.wurzel / "Sent").exists()
    assert eine.lauf("--schreiben") == 0
    assert "(empfangen 1, gesendet 0)" in capsys.readouterr().out
    assert eine.att.aufrufe["uploadfile"] == 1
