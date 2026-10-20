"""Pruefungen fuer die Schnellpruefung mit Pruefstempel (20.10.2026).

Anlass: ``termux/wissensdatei-uebernehmen.sh`` und ``termux/pcloud-uebernehmen.sh``
rechneten bei JEDEM Oeffnen der Handy-App volle sha256 ueber Quelle und Ziel
(memory.db hat 230 MB), auch ohne Aenderung. Jetzt merkt sich eine Stempeldatei
``<ziel>.pruefstempel`` Groesse und Zeit; passt beides noch und ist der Stempel
juenger als ``PRUEFSTEMPEL_MAX_ALTER_S``, entfaellt die Pruefsumme.

Alles ECHTE Laeufe in Git Bash (``tmp_path``, erfundene kleine Dateien). Ein
``sha256sum``-Wrapper im PATH zaehlt die Aufrufe und beweist, ob gerechnet
wurde.

Aufruf:
    cd backend && .venv/Scripts/python.exe -m pytest tests/test_pruefstempel.py -q
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pytest

PROJEKT = Path(__file__).resolve().parents[2]
TERMUX = PROJEKT / "termux"
WISSEN = TERMUX / "wissensdatei-uebernehmen.sh"
PCLOUD = TERMUX / "pcloud-uebernehmen.sh"
STEMPEL_SH = TERMUX / "pruefstempel.sh"

KEIN_PRUEFSUMME = "keine Pruefsumme"


# ── Hilfen ──────────────────────────────────────────────────────────────────

def _bash() -> str:
    bash = shutil.which("bash")
    if not bash or "system32" in bash.lower():
        pytest.skip("Git Bash nicht vorhanden")
    assert bash is not None
    return bash


def _posix(pfad: Path) -> str:
    return str(pfad).replace("\\", "/")


def _zaehler_wrapper(ordner: Path) -> Path:
    """PATH-Wrapper fuer sha256sum: zaehlt jeden Aufruf, ruft das echte Programm."""
    echt = shutil.which("sha256sum")
    if not echt:
        pytest.skip("sha256sum nicht vorhanden")
    ordner.mkdir(parents=True, exist_ok=True)
    zaehler = ordner / "sha_zaehler.txt"
    zaehler.write_text("", encoding="utf-8")
    skript = (
        "#!/bin/sh\n"
        f'echo x >> "{_posix(zaehler)}"\n'
        f'exec "{_posix(Path(echt))}" "$@"\n'
    )
    (ordner / "sha256sum").write_bytes(skript.encode())
    os.chmod(ordner / "sha256sum", 0o755)
    return zaehler


def _aufrufe(zaehler: Path) -> int:
    return len(zaehler.read_text(encoding="utf-8").split())


def _alt_machen(pfad: Path, sekunden: int = 2 * 86400) -> None:
    t = time.time() - sekunden
    os.utime(pfad, (t, t))


def _setze_mtime(pfad: Path, t: float) -> None:
    os.utime(pfad, (t, t))


# ── wissensdatei-uebernehmen.sh ─────────────────────────────────────────────

class WissenLauf:
    def __init__(self, tmp_path: Path):
        self.heim = tmp_path / "heim"
        self.heim.mkdir()
        self.download = tmp_path / "download"
        self.download.mkdir()
        self.quelle = self.download / "memory.db"
        self.ziel = self.heim / "memory.db"
        self.stempel = self.heim / "memory.db.pruefstempel"
        self.protokoll = self.download / "hermes_diag" / "wissensdatei_uebernahme.log"
        self.bin = tmp_path / "bin"
        self.zaehler = _zaehler_wrapper(self.bin)

    def quelle_setzen(self, inhalt: bytes, mtime: float | None = None) -> None:
        self.quelle.write_bytes(inhalt)
        _setze_mtime(self.quelle, mtime if mtime is not None else time.time() - 5000)

    def lauf(self, **extra: str) -> subprocess.CompletedProcess:
        umgebung = dict(
            os.environ, HOME=_posix(self.heim),
            WISSENSDATEI_QUELLE=_posix(self.quelle),
            WISSENSDATEI_ZIEL=_posix(self.ziel),
            WISSENSDATEI_PROTOKOLL=_posix(self.protokoll),
            PATH=_posix(self.bin) + os.pathsep + os.environ.get("PATH", ""),
        )
        for v in ("MSYS2_ARG_CONV_EXCL", "MSYS_NO_PATHCONV", "PRUEFSTEMPEL_AUS",
                  "PRUEFSTEMPEL_MAX_ALTER_S"):
            umgebung.pop(v, None)
        umgebung.update(extra)
        ergebnis = subprocess.run([_bash(), _posix(WISSEN)], capture_output=True,
                                  text=True, env=umgebung, timeout=60)
        assert ergebnis.returncode == 0, ergebnis.stdout + ergebnis.stderr
        return ergebnis

    def log(self) -> str:
        return self.protokoll.read_text(encoding="utf-8")

    def letzte_zeile(self) -> str:
        return self.log().strip().splitlines()[-1]

    def aufrufe(self) -> int:
        return _aufrufe(self.zaehler)


@pytest.fixture
def wissen(tmp_path):
    w = WissenLauf(tmp_path)
    w.quelle_setzen(b"erfundene Wissensdatei Fassung eins" * 50)
    return w


@pytest.fixture
def wissen_geprueft(wissen):
    """Erster Lauf ist durch: kopiert, Stempel liegt da."""
    wissen.lauf()
    assert wissen.stempel.is_file()
    return wissen


def test_a_erster_lauf_volle_pruefung_und_stempel_entsteht(wissen):
    wissen.lauf()
    assert wissen.aufrufe() > 0                         # Pruefsumme wurde gerechnet
    assert "uebernommen (kopiert)" in wissen.letzte_zeile()
    assert wissen.ziel.read_bytes() == wissen.quelle.read_bytes()
    zeilen = wissen.stempel.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 3
    assert zeilen[0].startswith(_posix(wissen.quelle) + "|")
    assert len(zeilen[1]) == 64                          # sha256
    assert not (wissen.heim / "memory.db.pruefstempel.teil").exists()


def test_a2_gleiche_dateien_ohne_stempel_schreiben_den_stempel(wissen):
    wissen.ziel.write_bytes(wissen.quelle.read_bytes())
    wissen.lauf()
    assert "Pruefsumme gleich" in wissen.letzte_zeile()
    assert wissen.stempel.is_file()


def test_b_zweiter_lauf_ohne_aenderung_keine_pruefsumme(wissen_geprueft):
    w = wissen_geprueft
    vorher = w.aufrufe()
    stempel_vorher = w.stempel.read_bytes()
    ziel_mtime = w.ziel.stat().st_mtime_ns
    ergebnis = w.lauf()
    assert w.aufrufe() == vorher, "sha256sum darf nicht aufgerufen werden"
    assert KEIN_PRUEFSUMME in w.letzte_zeile()
    assert "Groesse und Zeit unveraendert seit letzter Pruefung" in w.letzte_zeile()
    assert ergebnis.stdout.strip() == ""
    assert w.stempel.read_bytes() == stempel_vorher
    assert w.ziel.stat().st_mtime_ns == ziel_mtime
    assert list(w.heim.glob("memory.db.vor_*")) == []


def test_c_quelle_geaendert_volle_pruefung_sicherung_neuer_stempel(wissen_geprueft):
    w = wissen_geprueft
    alt = w.ziel.read_bytes()
    stempel_alt = w.stempel.read_text(encoding="utf-8").splitlines()[1]
    vorher = w.aufrufe()
    w.quelle_setzen(b"neue Fassung mit mehr Inhalt, anders und laenger" * 60)
    w.lauf()
    assert w.aufrufe() > vorher
    assert w.ziel.read_bytes() == w.quelle.read_bytes()
    sicherungen = list(w.heim.glob("memory.db.vor_*"))
    assert len(sicherungen) == 1 and sicherungen[0].read_bytes() == alt
    neu = w.stempel.read_text(encoding="utf-8").splitlines()
    assert neu[1] != stempel_alt and len(neu[1]) == 64
    # und der neue Stempel traegt: der naechste Lauf rechnet nichts
    nach = w.aufrufe()
    w.lauf()
    assert w.aufrufe() == nach and KEIN_PRUEFSUMME in w.letzte_zeile()


def test_d_gleiche_groesse_andere_mtime_volle_pruefung(wissen_geprueft):
    w = wissen_geprueft
    vorher = w.aufrufe()
    _setze_mtime(w.quelle, time.time() - 9999)          # gleicher Inhalt, andere Zeit
    w.lauf()
    assert w.aufrufe() > vorher
    assert "Pruefsumme gleich" in w.letzte_zeile()
    assert list(w.heim.glob("memory.db.vor_*")) == []   # nichts kopiert
    # Stempel wurde mit der neuen Zeit erneuert -> danach wieder schnell
    nach = w.aufrufe()
    w.lauf()
    assert w.aufrufe() == nach and KEIN_PRUEFSUMME in w.letzte_zeile()


def test_e_stempel_zu_alt_volle_pruefung(wissen_geprueft):
    w = wissen_geprueft
    # (1) ueber die Umgebungsgrenze
    vorher = w.aufrufe()
    w.lauf(PRUEFSTEMPEL_MAX_ALTER_S="0")
    assert w.aufrufe() > vorher and KEIN_PRUEFSUMME not in w.letzte_zeile()
    # (2) ueber die mtime der Stempeldatei (Standardgrenze 1 Tag)
    _alt_machen(w.stempel, 2 * 86400)
    vorher = w.aufrufe()
    w.lauf()
    assert w.aufrufe() > vorher and "Pruefsumme gleich" in w.letzte_zeile()
    # Stempel danach wieder frisch
    nach = w.aufrufe()
    w.lauf()
    assert w.aufrufe() == nach


def test_e2_stempel_aus_der_zukunft_wird_nicht_geglaubt(wissen_geprueft):
    w = wissen_geprueft
    t = time.time() + 7 * 86400
    os.utime(w.stempel, (t, t))
    vorher = w.aufrufe()
    w.lauf()
    assert w.aufrufe() > vorher


@pytest.mark.parametrize("inhalt", [
    b"",                                                 # leer
    b"Muell ohne Struktur",                              # kaputt
    b"nur eine Zeile ohne Zeilenumbruch",                # unvollstaendig
    b"stimmt|nicht\nxyz\nabc\n",                         # zweite Zeile keine sha256
])
def test_f_kaputter_stempel_volle_pruefung_kein_abbruch(wissen_geprueft, inhalt):
    w = wissen_geprueft
    w.stempel.write_bytes(inhalt)
    vorher = w.aufrufe()
    w.lauf()                                             # Exit 0 wird in lauf() geprueft
    assert w.aufrufe() > vorher
    assert KEIN_PRUEFSUMME not in w.letzte_zeile()
    assert "Pruefsumme gleich" in w.letzte_zeile()
    assert len(w.stempel.read_text(encoding="utf-8").splitlines()) == 3   # repariert


def test_f2_stempel_als_verzeichnis_bricht_den_start_nicht_ab(wissen_geprueft):
    w = wissen_geprueft
    w.stempel.unlink()
    w.stempel.mkdir()                                    # Schreiben/Lesen unmoeglich
    w.lauf()
    assert "Pruefsumme gleich" in w.letzte_zeile()


def test_g_pruefstempel_aus_erzwingt_volle_pruefung(wissen_geprueft):
    w = wissen_geprueft
    for _ in range(2):
        vorher = w.aufrufe()
        w.lauf(PRUEFSTEMPEL_AUS="1")
        assert w.aufrufe() > vorher
        assert KEIN_PRUEFSUMME not in w.letzte_zeile()


def test_h_ziel_von_aussen_veraendert_volle_pruefung(wissen_geprueft):
    w = wissen_geprueft
    original = w.quelle.read_bytes()
    w.ziel.write_bytes(original + b"zusaetzlich von aussen")   # andere Groesse
    vorher = w.aufrufe()
    w.lauf()
    assert w.aufrufe() > vorher
    assert w.ziel.read_bytes() == original                      # wieder uebernommen
    sicherungen = list(w.heim.glob("memory.db.vor_*"))
    assert len(sicherungen) == 1
    assert sicherungen[0].read_bytes() == original + b"zusaetzlich von aussen"


def test_h2_ziel_geloescht_wird_neu_uebernommen(wissen_geprueft):
    w = wissen_geprueft
    original = w.quelle.read_bytes()
    w.ziel.unlink()
    w.lauf()
    assert w.ziel.read_bytes() == original
    assert "uebernommen (kopiert)" in w.letzte_zeile()


def test_wissen_quelle_fehlt_bleibt_exit0_ohne_stempel(wissen):
    wissen.quelle.unlink()
    wissen.lauf()
    assert "Quelle fehlt" in wissen.letzte_zeile()
    assert not wissen.stempel.exists()


# ── Hilfsdatei direkt ───────────────────────────────────────────────────────

def _sh(skript: str, **extra: str) -> subprocess.CompletedProcess:
    umgebung = dict(os.environ)
    for v in ("MSYS2_ARG_CONV_EXCL", "MSYS_NO_PATHCONV", "PRUEFSTEMPEL_AUS",
              "PRUEFSTEMPEL_MAX_ALTER_S"):
        umgebung.pop(v, None)
    umgebung.update(extra)
    return subprocess.run([_bash(), "-c", f'. "{_posix(STEMPEL_SH)}"\n{skript}'],
                          capture_output=True, text=True, env=umgebung, timeout=30)


def test_hilfsdatei_zeile_und_fehlerfaelle(tmp_path):
    q, z = tmp_path / "q", tmp_path / "z"
    q.write_bytes(b"abc")
    z.write_bytes(b"abcd")
    ok = _sh(f'stempel_zeile "{_posix(q)}" "{_posix(z)}"')
    assert ok.returncode == 0
    teile = ok.stdout.split("|")
    assert teile[0] == _posix(q) and teile[1].split()[0] == "3" and teile[2].split()[0] == "4"
    fehlt = _sh(f'stempel_zeile "{_posix(q)}" "{_posix(tmp_path / "nein")}"')
    assert fehlt.returncode != 0 and fehlt.stdout == ""
    # Schreiben mit ungueltiger sha256 legt nichts an, Exit 0
    s = tmp_path / "s.pruefstempel"
    kaputt = _sh(f'stempel_schreiben "{_posix(s)}" "{_posix(q)}" "{_posix(z)}" "keinesha"')
    assert kaputt.returncode == 0 and not s.exists()
    # Schreiben in nicht vorhandenen Ordner: harmlos
    nirgends = _sh(f'stempel_schreiben "{_posix(tmp_path / "x" / "s")}" "{_posix(q)}" '
                   f'"{_posix(z)}" "{"a" * 64}"')
    assert nirgends.returncode == 0


def test_hilfsdatei_nicht_numerische_grenze_faellt_auf_standard(wissen_geprueft):
    w = wissen_geprueft
    vorher = w.aufrufe()
    w.lauf(PRUEFSTEMPEL_MAX_ALTER_S="abc")               # Muell -> Standard 86400
    assert w.aufrufe() == vorher and KEIN_PRUEFSUMME in w.letzte_zeile()


# ── pcloud-uebernehmen.sh ───────────────────────────────────────────────────

class PcloudLauf:
    """Sandkasten wie in test_pcloud_uebergabe.py, aber mit pruefstempel.sh und
    einem Attrappen-python, das die Dateien MIT erhaltener mtime ins Staging legt
    (``cp -p``) - so passt der volle Stempel; ``neu_holen=True`` legt sie dagegen
    wie der echte Holer mit frischer mtime neu an."""

    def __init__(self, tmp_path: Path):
        self.sb = tmp_path / "projekt"
        (self.sb / "termux").mkdir(parents=True)
        shutil.copy(PCLOUD, self.sb / "termux" / "pcloud-uebernehmen.sh")
        shutil.copy(STEMPEL_SH, self.sb / "termux" / "pruefstempel.sh")
        (self.sb / "tools" / "handy").mkdir(parents=True)
        (self.sb / "tools" / "handy" / "pcloud_dateien_holen.py").write_text("# Attrappe\n", encoding="utf-8")
        self.heim = tmp_path / "heim"
        self.heim.mkdir()
        self.vorlage = tmp_path / "vorlage"
        self.vorlage.mkdir()
        self.bin = tmp_path / "bin"
        self.zaehler = _zaehler_wrapper(self.bin)
        stub = (
            "#!/bin/sh\n"
            'Z=""; L=""\n'
            'while [ $# -gt 0 ]; do case "$1" in --ziel) Z="$2"; shift 2;; '
            '--liste) L="$2"; shift 2;; --env) shift 2;; *) shift;; esac; done\n'
            '[ -n "$Z" ] && mkdir -p "$Z"\n'
            'for f in "$BH_VORLAGE"/*; do [ -f "$f" ] || continue; '
            'if [ "$BH_NEU_HOLEN" = "1" ]; then cp -f "$f" "$Z/"; '
            'else cp -pf "$f" "$Z/"; fi; done\n'
            '[ -n "$L" ] && { for f in "$BH_VORLAGE"/*; do [ -f "$f" ] && basename "$f"; done > "$L"; }\n'
            "exit 0\n"
        )
        (self.bin / "python").write_bytes(stub.encode())
        os.chmod(self.bin / "python", 0o755)
        self.ziel_ordner = self.heim / "foto_sortierung"
        self.protokoll = self.heim / "proto.log"

    def vorlage_setzen(self, name: str, inhalt: bytes, mtime: float | None = None) -> None:
        p = self.vorlage / name
        p.write_bytes(inhalt)
        _setze_mtime(p, mtime if mtime is not None else time.time() - 5000)

    def lauf(self, **extra: str) -> subprocess.CompletedProcess:
        umgebung = dict(
            os.environ, HOME=_posix(self.heim),
            PCLOUD_UEBERGABE_ZIEL=_posix(self.ziel_ordner),
            PCLOUD_UEBERGABE_STAGING=_posix(self.heim / "staging"),
            PCLOUD_UEBERGABE_PROTOKOLL=_posix(self.protokoll),
            BH_VORLAGE=_posix(self.vorlage),
            PATH=_posix(self.bin) + os.pathsep + os.environ.get("PATH", ""),
        )
        for v in ("MSYS2_ARG_CONV_EXCL", "MSYS_NO_PATHCONV", "PROJEKT", "PRUEFSTEMPEL_AUS",
                  "PRUEFSTEMPEL_MAX_ALTER_S", "BH_NEU_HOLEN"):
            umgebung.pop(v, None)
        umgebung.update(extra)
        ergebnis = subprocess.run(
            [_bash(), _posix(self.sb / "termux" / "pcloud-uebernehmen.sh"), _posix(self.sb)],
            capture_output=True, text=True, encoding="utf-8", env=umgebung, timeout=120)
        assert ergebnis.returncode == 0, ergebnis.stdout + ergebnis.stderr
        return ergebnis

    def log(self) -> str:
        return self.protokoll.read_text(encoding="utf-8")

    def aufrufe(self) -> int:
        return _aufrufe(self.zaehler)


@pytest.fixture
def pcloud(tmp_path):
    p = PcloudLauf(tmp_path)
    p.vorlage_setzen("a.json", b'{"fassung": 1}' * 20)
    p.vorlage_setzen("b.jsonl", b"zeile\n" * 30)
    return p


def test_i_pcloud_erster_lauf_kopiert_und_stempelt_jede_datei(pcloud):
    pcloud.lauf()
    assert pcloud.aufrufe() > 0
    for name in ("a.json", "b.jsonl"):
        assert (pcloud.ziel_ordner / name).read_bytes() == (pcloud.vorlage / name).read_bytes()
        assert (pcloud.ziel_ordner / f"{name}.pruefstempel").is_file()
    assert pcloud.log().count("uebernommen (kopiert)") == 2


def test_i_pcloud_zweiter_lauf_ohne_aenderung_keine_pruefsumme(pcloud):
    pcloud.lauf()
    vorher = pcloud.aufrufe()
    pcloud.lauf()
    assert pcloud.aufrufe() == vorher, "sha256sum darf nicht aufgerufen werden"
    zeilen = [z for z in pcloud.log().splitlines() if KEIN_PRUEFSUMME in z]
    assert len(zeilen) == 2
    assert any("PCLOUD-Uebergabe a.json uebersprungen (Groesse und Zeit unveraendert "
               "seit letzter Pruefung" in z for z in zeilen)
    assert "uebernommen=0 uebersprungen=2 fehler=0" in pcloud.log().splitlines()[-1]
    assert list(pcloud.ziel_ordner.glob("*.vor_*")) == []


def test_i_pcloud_quelle_geaendert_sicherung_und_neuer_stempel(pcloud):
    pcloud.lauf()
    alt = (pcloud.ziel_ordner / "a.json").read_bytes()
    vorher = pcloud.aufrufe()
    pcloud.vorlage_setzen("a.json", b'{"fassung": 2, "mehr": "inhalt"}' * 25)
    pcloud.lauf()
    assert pcloud.aufrufe() > vorher
    assert (pcloud.ziel_ordner / "a.json").read_bytes() == (pcloud.vorlage / "a.json").read_bytes()
    sicherungen = list(pcloud.ziel_ordner.glob("a.json.vor_*"))
    assert len(sicherungen) == 1 and sicherungen[0].read_bytes() == alt
    assert list(pcloud.ziel_ordner.glob("b.jsonl.vor_*")) == []   # b unberuehrt
    nach = pcloud.aufrufe()
    pcloud.lauf()
    assert pcloud.aufrufe() == nach


def test_i_pcloud_frisch_geholte_quelle_spart_wenigstens_die_ziel_pruefsumme(pcloud):
    """Der echte Holer legt Staging-Dateien bei jedem Lauf neu an (neue mtime):
    der volle Stempel passt dann nicht, aber die Pruefsumme des unveraenderten
    Ziels kommt aus dem Stempel - je Datei nur EINE statt zwei Pruefsummen."""
    pcloud.lauf(BH_NEU_HOLEN="1")
    vorher = pcloud.aufrufe()
    time.sleep(1.1)                                       # sicher neue mtime-Sekunde
    pcloud.lauf(BH_NEU_HOLEN="1")
    assert pcloud.aufrufe() - vorher == 2                 # 2 Dateien x nur Quelle
    assert "Pruefsumme gleich" in pcloud.log()
    # Stempel wird dabei NICHT erneuert: nach Ablauf greift wieder die volle Pruefung
    for name in ("a.json", "b.jsonl"):
        _alt_machen(pcloud.ziel_ordner / f"{name}.pruefstempel")
    vorher = pcloud.aufrufe()
    time.sleep(1.1)
    pcloud.lauf(BH_NEU_HOLEN="1")
    assert pcloud.aufrufe() - vorher == 4                 # Quelle + Ziel je Datei


def test_i_pcloud_aus_und_abgelaufen_rechnen_voll(pcloud):
    pcloud.lauf()
    vorher = pcloud.aufrufe()
    pcloud.lauf(PRUEFSTEMPEL_AUS="1")
    assert pcloud.aufrufe() - vorher == 4                 # 2 Dateien x (Quelle + Ziel)
    vorher = pcloud.aufrufe()
    pcloud.lauf(PRUEFSTEMPEL_MAX_ALTER_S="0")
    assert pcloud.aufrufe() - vorher == 4


def test_i_pcloud_ohne_hilfsdatei_laeuft_wie_frueher(pcloud):
    (pcloud.sb / "termux" / "pruefstempel.sh").unlink()   # Sandkasten-Kopie
    pcloud.lauf()
    vorher = pcloud.aufrufe()
    pcloud.lauf()
    assert pcloud.aufrufe() - vorher == 4                 # volle Pruefung, kein Abbruch
    assert not list(pcloud.ziel_ordner.glob("*.pruefstempel"))


# ── Einbindung, Syntax, Zeilenenden ─────────────────────────────────────────

@pytest.mark.parametrize("pfad", [STEMPEL_SH, WISSEN, PCLOUD], ids=lambda p: p.name)
def test_skripte_syntax_und_reine_lf(pfad):
    roh = pfad.read_bytes()
    assert b"\r" not in roh, f"{pfad.name}: reine LF verlangt"
    assert roh.startswith(b"#!/data/data/com.termux/files/usr/bin/bash\n")
    ergebnis = subprocess.run([_bash(), "-n", _posix(pfad)], capture_output=True, text=True)
    assert ergebnis.returncode == 0, ergebnis.stderr


def test_beide_skripte_binden_die_hilfsdatei_ein_und_loeschen_nichts():
    for pfad in (WISSEN, PCLOUD):
        text = pfad.read_text(encoding="utf-8")
        assert '. "$HIER/pruefstempel.sh"' in text
        assert "stempel_passt" in text and "stempel_schreiben" in text
    hilfe = STEMPEL_SH.read_text(encoding="utf-8")
    import re
    assert not re.search(r"\brm\s", hilfe), "es wird nie etwas geloescht"
    assert "PRUEFSTEMPEL_AUS" in hilfe and "PRUEFSTEMPEL_MAX_ALTER_S" in hilfe


def test_datum_des_kopfkommentars_stimmt():
    for pfad in (WISSEN, PCLOUD):
        assert "20.10.2026" in pfad.read_text(encoding="utf-8")
    assert datetime.now().year >= 2026
