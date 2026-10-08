"""Pruefungen fuer ``termux/sicherung.sh`` und ``tools/handy/sicherung_pruefen.py`` (08.10.2026).

Das Shell-Skript laeuft wirklich - in Git Bash statt Termux, auf einem
kuenstlichen Termux-Ordner (``home/``, ``usr/``) und mit einem Platzhalter-``age``,
das den Strom unveraendert durchreicht. Danach prueft ``sicherung_pruefen.py``
genau diese Sicherung (Entschluesseler = Datei oeffnen). So passen beide Seiten
nachweislich zusammen. Kein Handy, keine echten Daten, keine echte Verschluesselung.
"""
from __future__ import annotations

import importlib.util
import io
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

PROJEKT = Path(__file__).resolve().parents[2]
SKRIPT = PROJEKT / "termux" / "sicherung.sh"
PRUEFER = PROJEKT / "tools" / "handy" / "sicherung_pruefen.py"
SHEBANG = "#!/data/data/com.termux/files/usr/bin/bash"
SCHLUESSEL = "age1qyqszqgpqyqszqgpqyqszqgpqyqszqgpqyqszqgpqyqszqgpqyqs0test"

spez = importlib.util.spec_from_file_location("sicherung_pruefen", PRUEFER)
assert spez is not None and spez.loader is not None
sp = importlib.util.module_from_spec(spez)
spez.loader.exec_module(sp)


def _bash():
    bash = shutil.which("bash")
    if not bash or "system32" in bash.lower() or not shutil.which("tar") \
            or not shutil.which("sha256sum"):
        pytest.skip("Git Bash mit tar/sha256sum nicht vorhanden")
    return bash


def _posix(pfad: Path) -> str:
    """C:\\x\\y -> /c/x/y (GNU tar liest 'C:' sonst als Rechnername)."""
    text = str(pfad).replace("\\", "/")
    treffer = re.match(r"^([A-Za-z]):/(.*)$", text)
    return f"/{treffer.group(1).lower()}/{treffer.group(2)}" if treffer else text


def _termux_attrappe(tmp_path: Path) -> Path:
    basis = tmp_path / "files"
    (basis / "home" / "projekt").mkdir(parents=True)
    (basis / "home" / "projekt" / "notiz.txt").write_text("erfunden", encoding="utf-8")
    (basis / "home" / ".cache").mkdir()
    (basis / "home" / ".cache" / "weg.bin").write_bytes(b"x" * 10)
    (basis / "home" / "storage").mkdir()
    (basis / "home" / "storage" / "nicht_sichern.txt").write_text("x", encoding="utf-8")
    (basis / "usr" / "bin").mkdir(parents=True)
    (basis / "usr" / "bin" / "programm").write_text("#!/bin/sh\n", encoding="utf-8")
    (basis / "usr" / "tmp").mkdir()
    (basis / "usr" / "tmp" / "fluechtig").write_text("x", encoding="utf-8")
    return basis


def _age_platzhalter(tmp_path: Path) -> Path:
    """'age -r KEY -o DATEI' -> Strom unveraendert in DATEI schreiben."""
    ordner = tmp_path / "werkzeuge"
    ordner.mkdir()
    datei = ordner / "age"
    datei.write_text('#!/bin/bash\nwhile [ $# -gt 0 ]; do case "$1" in -o) aus="$2"; shift 2;; '
                     '*) shift;; esac; done\ncat > "$aus"\n', encoding="utf-8", newline="\n")
    return ordner


def _lauf(tmp_path: Path, schluessel: str | None = SCHLUESSEL, stand="2026-10-08_2200"):
    bash = _bash()
    basis = _termux_attrappe(tmp_path)
    ziel = tmp_path / "download"
    home = basis / "home"
    if schluessel is not None:
        (home / ".sicherung_empfaenger.txt").write_text(
            f"# public key: {schluessel}\n{schluessel}\n", encoding="utf-8")
    werkzeuge = _age_platzhalter(tmp_path)
    umgebung = dict(os.environ)
    umgebung.update({
        "TERMUX_BASIS": _posix(basis), "SICHERUNG_ZIEL": _posix(ziel),
        "SICHERUNG_STAND": stand, "HOME": _posix(home), "TMPDIR": _posix(tmp_path),
        "PORT": "1",
    })
    befehl = f'export PATH="{_posix(werkzeuge)}:$PATH"; bash "{_posix(SKRIPT)}"'
    ergebnis = subprocess.run([bash, "-c", befehl], env=umgebung, capture_output=True,
                              text=True, encoding="utf-8", timeout=120)
    return ergebnis, ziel / stand


def _datei_oeffnen(pfad):
    return open(pfad, "rb")


# ── Skript: Aufbau ────────────────────────────────────────────────────────

def test_skript_hat_termux_shebang_und_loescht_nichts_fremdes():
    text = SKRIPT.read_text(encoding="utf-8")
    assert text.startswith(SHEBANG)
    assert "set -u -o pipefail" in text
    loeschen = [z for z in text.splitlines() if re.search(r"\brm\b", z) and not z.lstrip().startswith("#")]
    assert loeschen == ['    rm -f "$liste"']        # nur die eigene Zaehl-Zwischendatei


def test_skript_syntax():
    bash = _bash()
    ergebnis = subprocess.run([bash, "-n", _posix(SKRIPT)], capture_output=True, text=True)
    assert ergebnis.returncode == 0, ergebnis.stderr


# ── Skript: echter Lauf mit Attrappen ─────────────────────────────────────

def test_sicherung_und_pruefung_passen_zusammen(tmp_path, capsys):
    ergebnis, ordner = _lauf(tmp_path)
    assert ergebnis.returncode == 0, ergebnis.stdout + ergebnis.stderr
    assert (ordner / "FERTIG").is_file()
    manifest = sp.manifest_lesen(str(ordner / "MANIFEST.txt"))
    assert set(manifest) == {"home.tar.age", "usr.tar.age"}

    with tarfile.open(ordner / "home.tar.age") as archiv:
        namen = archiv.getnames()
    assert "home/projekt/notiz.txt" in namen
    assert not any(n.startswith(("home/.cache", "home/storage")) for n in namen)
    with tarfile.open(ordner / "usr.tar.age") as archiv:
        assert not any(n.startswith("usr/tmp") for n in archiv.getnames())

    code = sp.main([str(ordner)], oeffnen=_datei_oeffnen)
    ausgabe = capsys.readouterr().out
    assert code == 0 and "GRUEN" in ausgabe
    assert "notiz" not in ausgabe                     # keine Dateinamen in der Ausgabe
    assert not list(tmp_path.glob(".sicherung_liste_*"))   # Zwischendatei weg


def test_zweiter_lauf_ueberschreibt_nie(tmp_path):
    ergebnis, ordner = _lauf(tmp_path)
    assert ergebnis.returncode == 0
    vorher = (ordner / "MANIFEST.txt").read_bytes()
    bash = _bash()
    umgebung = dict(os.environ, TERMUX_BASIS=_posix(tmp_path / "files"),
                    SICHERUNG_ZIEL=_posix(tmp_path / "download"), SICHERUNG_STAND="2026-10-08_2200",
                    HOME=_posix(tmp_path / "files" / "home"), PORT="1")
    befehl = f'export PATH="{_posix(tmp_path / "werkzeuge")}:$PATH"; bash "{_posix(SKRIPT)}"'
    zweiter = subprocess.run([bash, "-c", befehl], env=umgebung, capture_output=True, text=True)
    assert zweiter.returncode == 4
    assert (ordner / "MANIFEST.txt").read_bytes() == vorher


def test_ohne_schluessel_exit_2_und_kein_ordner(tmp_path):
    ergebnis, ordner = _lauf(tmp_path, schluessel=None)
    assert ergebnis.returncode == 2
    assert not ordner.exists()


def test_ungueltiger_schluessel_exit_2(tmp_path):
    ergebnis, ordner = _lauf(tmp_path, schluessel="kein-schluessel")
    assert ergebnis.returncode == 2
    assert not ordner.exists()


# ── Pruefer allein ────────────────────────────────────────────────────────

def _sicherung_bauen(ordner: Path, eintraege_soll=None, fertig=True) -> Path:
    ordner.mkdir(parents=True)
    puffer = io.BytesIO()
    with tarfile.open(fileobj=puffer, mode="w") as archiv:
        for name in ("home", "home/a.txt", "home/b.txt"):
            info = tarfile.TarInfo(name)
            if name == "home":
                info.type = tarfile.DIRTYPE
                archiv.addfile(info)
            else:
                daten = b"erfunden"
                info.size = len(daten)
                archiv.addfile(info, io.BytesIO(daten))
    teil = ordner / "home.tar.age"
    teil.write_bytes(puffer.getvalue())
    (ordner / "MANIFEST.txt").write_text(
        "stand=x\nbasis=y\n"
        f"home.tar.age groesse={teil.stat().st_size} eintraege={eintraege_soll or 3} "
        f"sha256={sp.sha256_datei(str(teil))}\n", encoding="utf-8")
    if fertig:
        (ordner / "FERTIG").write_text("2026-10-08", encoding="utf-8")
    return ordner


def test_pruefer_gruen(tmp_path):
    zeilen, gruen = sp.pruefen(str(_sicherung_bauen(tmp_path / "s")), _datei_oeffnen)
    assert gruen and zeilen[0].startswith("✔ home.tar.age: 3 Eintraege")


def test_pruefer_ohne_fertig_rot(tmp_path):
    assert sp.main([str(_sicherung_bauen(tmp_path / "s", fertig=False))],
                   oeffnen=_datei_oeffnen) == 3


def test_pruefer_beschaedigte_kopie_rot(tmp_path):
    ordner = _sicherung_bauen(tmp_path / "s")
    teil = ordner / "home.tar.age"
    daten = bytearray(teil.read_bytes())
    daten[600] ^= 0xFF                                 # ein Byte kippen, Groesse gleich
    teil.write_bytes(bytes(daten))
    zeilen, gruen = sp.pruefen(str(ordner), _datei_oeffnen)
    assert not gruen and "sha256 weicht ab" in zeilen[0]


def test_pruefer_falsche_eintragszahl_rot(tmp_path):
    zeilen, gruen = sp.pruefen(str(_sicherung_bauen(tmp_path / "s", eintraege_soll=5)),
                               _datei_oeffnen)
    assert not gruen and "3 Eintraege statt 5" in zeilen[0]


def test_pruefer_entschluesselung_scheitert_rot(tmp_path):
    def kaputt(_pfad):                                 # entschluesselt "falsch": kein tar
        return io.BytesIO(b"kein tar")
    zeilen, gruen = sp.pruefen(str(_sicherung_bauen(tmp_path / "s")), kaputt)
    assert not gruen and "nicht lesbar" in zeilen[0]


def test_pruefer_ohne_schluessel_exit_1(tmp_path):
    ordner = _sicherung_bauen(tmp_path / "s")
    assert sp.main([str(ordner), "--schluessel", str(tmp_path / "fehlt.key")]) == 1
