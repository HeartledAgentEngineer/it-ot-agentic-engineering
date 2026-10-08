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
    rootfs = basis / "usr" / "var" / "lib" / "proot-distro" / "installed-rootfs" / "debian"
    (rootfs / "root" / "facy_venv").mkdir(parents=True)
    (rootfs / "etc").mkdir()
    (rootfs / "etc" / "os-release").write_text("ID=debian\n", encoding="utf-8")
    return basis


def _age_platzhalter(tmp_path: Path) -> Path:
    """'age -r KEY -o DATEI' -> Strom unveraendert in DATEI schreiben."""
    ordner = tmp_path / "werkzeuge"
    ordner.mkdir()
    datei = ordner / "age"
    datei.write_text('#!/bin/bash\nwhile [ $# -gt 0 ]; do case "$1" in -o) aus="$2"; shift 2;; '
                     '*) shift;; esac; done\ncat > "$aus"\n', encoding="utf-8", newline="\n")
    # 'proot-distro backup <name>' -> tar des Rootfs auf stdout (wie das echte Werkzeug)
    (ordner / "proot-distro").write_text(
        '#!/bin/bash\n[ "$1" = backup ] || exit 2\n'
        '[ -n "${PD_KAPUTT:-}" ] && { echo "kaputt" >&2; exit 1; }\n'
        'tar -C "$TERMUX_BASIS/usr/var/lib/proot-distro/installed-rootfs" -cf - "$2"\n',
        encoding="utf-8", newline="\n")
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
    # nur die eigenen Zwischendateien (Eintragsliste, Fehlermeldungen)
    assert {z.strip() for z in loeschen} == {'rm -f "$liste" "$fehler"', 'rm -f "$fehler"'}
    assert "usr.tar.age" not in text and "teil_sichern usr" not in text


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
    assert set(manifest) == {"home.tar.age", "distro_debian.tar.age"}
    assert manifest["distro_debian.tar.age"]["eintraege"] == -1

    with tarfile.open(ordner / "home.tar.age") as archiv:
        namen = archiv.getnames()
    assert "home/projekt/notiz.txt" in namen
    assert not any(n.startswith(("home/.cache", "home/storage")) for n in namen)
    with tarfile.open(ordner / "distro_debian.tar.age") as archiv:
        assert "debian/root/facy_venv" in archiv.getnames()

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


# ── Sicherung auf Auftrag beim Widget-Start ───────────────────────────────

AUFTRAG_SKRIPT = PROJEKT / "termux" / "sicherung-auftrag.sh"
WIDGET = PROJEKT / "termux" / "agent-start"

spez_a = importlib.util.spec_from_file_location(
    "sicherung_auftrag", PROJEKT / "tools" / "handy" / "sicherung_auftrag.py")
assert spez_a is not None and spez_a.loader is not None
sa = importlib.util.module_from_spec(spez_a)
spez_a.loader.exec_module(sa)


def _auftrag_lauf(tmp_path: Path, mit_auftrag: bool):
    bash = _bash()
    basis = _termux_attrappe(tmp_path)
    download = tmp_path / "download"
    download.mkdir()
    (basis / "home" / ".sicherung_empfaenger.txt").write_text(SCHLUESSEL + "\n", encoding="utf-8")
    if mit_auftrag:
        (download / "AUFTRAG").write_text("20261008223000\n", encoding="utf-8")
    werkzeuge = _age_platzhalter(tmp_path)
    umgebung = dict(os.environ, TERMUX_BASIS=_posix(basis), SICHERUNG_ZIEL=_posix(download),
                    SICHERUNG_STAND="2026-10-08_2230", HOME=_posix(basis / "home"),
                    TMPDIR=_posix(tmp_path), PORT="1")
    befehl = f'export PATH="{_posix(werkzeuge)}:$PATH"; bash "{_posix(AUFTRAG_SKRIPT)}"'
    ergebnis = subprocess.run([bash, "-c", befehl], env=umgebung, capture_output=True,
                              text=True, encoding="utf-8", timeout=120)
    return ergebnis, download


def test_auftrag_ohne_datei_tut_nichts(tmp_path):
    ergebnis, download = _auftrag_lauf(tmp_path, mit_auftrag=False)
    assert ergebnis.returncode == 0
    assert list(download.iterdir()) == []


def test_auftrag_sichert_einmal_und_benennt_um(tmp_path):
    ergebnis, download = _auftrag_lauf(tmp_path, mit_auftrag=True)
    assert ergebnis.returncode == 0, ergebnis.stdout + ergebnis.stderr
    assert not (download / "AUFTRAG").exists()
    assert (download / "AUFTRAG.erledigt_20261008223000").is_file()
    assert (download / "2026-10-08_2230" / "FERTIG").is_file()
    log = (download / "lauf_20261008223000.log").read_text(encoding="utf-8").splitlines()
    assert log[-1] == "EXIT=0"
    assert any(z.startswith("Sicherung nach ") for z in log)


def test_widget_ruft_auftrag_nach_pull_und_vor_serverstart():
    text = WIDGET.read_text(encoding="utf-8")
    aufruf = text.index('bash "$HIER/sicherung-auftrag.sh" || true')
    assert text.index("git pull --ff-only") < aufruf < text.index("cd backend ||")
    assert text.index("_pkill_server\n") < aufruf


def test_auftrag_skript_syntax_und_shebang():
    bash = _bash()
    assert AUFTRAG_SKRIPT.read_text(encoding="utf-8").startswith(SHEBANG)
    for datei in (AUFTRAG_SKRIPT, WIDGET):
        ergebnis = subprocess.run([bash, "-n", _posix(datei)], capture_output=True, text=True)
        assert ergebnis.returncode == 0, ergebnis.stderr


class AdbAttrappe:
    """Spielt das Handy: Geraet, Schluessel, Log waechst bis EXIT, pull legt Ordner an."""
    def __init__(self, tmp_path, geraet=True, schluessel=True, exit_code=0, laeuft=False):
        self.tmp, self.geraet, self.schluessel = tmp_path, geraet, schluessel
        self.exit_code, self.laeuft = exit_code, laeuft
        self.aufrufe, self.cat_runde = [], 0

    def __call__(self, argumente):
        self.aufrufe.append(argumente)
        if argumente[0] == "devices":
            return 0, "List of devices attached\n" + ("ABC123\tdevice\n" if self.geraet else "")
        if argumente[0] == "shell" and argumente[1].startswith("ls "):
            pfad = argumente[1][3:]
            da = (pfad.endswith("sicherung_empfaenger.txt") and self.schluessel) or \
                 (pfad.endswith("AUFTRAG.laeuft") and self.laeuft)
            return (0, pfad) if da else (1, f"ls: {pfad}: No such file or directory")
        if argumente[0] == "shell" and argumente[1].startswith("cat "):
            self.cat_runde += 1
            zeilen = ["Start", "Sicherung nach /sdcard/Download/termux-sicherung/2026-10-08_2230"]
            if self.cat_runde >= 2:
                zeilen += ["  home: fertig: 12 Eintraege, 1 MB", f"EXIT={self.exit_code}"]
            return 0, "\n".join(zeilen) + "\n"
        if argumente[0] == "pull":
            os.makedirs(os.path.join(argumente[2], "2026-10-08_2230"))
            return 0, "1 file pulled"
        return 0, ""


def test_fernauftrag_ganzer_weg(tmp_path, capsys):
    adb = AdbAttrappe(tmp_path)
    geprueft = []
    code = sa.main(["--lokal", str(tmp_path / "lokal"), "--kennung", "k1"], adb=adb,
                   schlafen=lambda s: None, pruefen=lambda a: geprueft.append(a) or 0)
    ausgabe = capsys.readouterr().out
    assert code == 0
    assert "Agent-Widget antippen" in ausgabe and "EXIT=0" in ausgabe
    push = [a for a in adb.aufrufe if a[0] == "push"]
    assert len(push) == 1 and push[0][2] == "/sdcard/Download/termux-sicherung/AUFTRAG"
    assert geprueft == [[str(tmp_path / "lokal" / "2026-10-08_2230")]]


def test_fernauftrag_holt_vorhandenes_nicht_doppelt(tmp_path):
    (tmp_path / "lokal" / "2026-10-08_2230").mkdir(parents=True)
    adb = AdbAttrappe(tmp_path)
    code = sa.main(["--lokal", str(tmp_path / "lokal"), "--kennung", "k1"], adb=adb,
                   schlafen=lambda s: None, pruefen=lambda a: 0)
    assert code == 0 and not [a for a in adb.aufrufe if a[0] == "pull"]


def test_fernauftrag_fehlerfaelle(tmp_path):
    ohne = dict(schlafen=lambda s: None, pruefen=lambda a: 0)
    lokal = ["--lokal", str(tmp_path / "l")]
    assert sa.main(lokal, adb=AdbAttrappe(tmp_path, geraet=False), **ohne) == 1
    assert sa.main(lokal, adb=AdbAttrappe(tmp_path, schluessel=False), **ohne) == 2
    assert sa.main(lokal, adb=AdbAttrappe(tmp_path, laeuft=True), **ohne) == 6
    assert sa.main(lokal, adb=AdbAttrappe(tmp_path, exit_code=6), **ohne) == 3
    assert sa.main(lokal, adb=AdbAttrappe(tmp_path), schlafen=lambda s: None,
                   pruefen=lambda a: 3) == 5


def test_fernauftrag_zeitablauf(tmp_path):
    class Stumm(AdbAttrappe):
        def __call__(self, argumente):
            if argumente[0] == "shell" and argumente[1].startswith("cat "):
                return 1, ""
            return super().__call__(argumente)
    code = sa.main(["--lokal", str(tmp_path / "l"), "--max-minuten", "1"], adb=Stumm(tmp_path),
                   schlafen=lambda s: None, pruefen=lambda a: 0)
    assert code == 4


# ── Linux-Umgebung (proot-distro) statt usr/ (nach Lauf 08.10. 22:35) ─────

def test_distro_fehler_zeigt_meldung_und_bricht_ab(tmp_path, monkeypatch):
    monkeypatch.setenv("PD_KAPUTT", "1")
    ergebnis, ordner = _lauf(tmp_path)
    assert ergebnis.returncode == 6
    assert "Linux-Umgebung debian: wird gesichert" in ergebnis.stdout
    assert "kaputt" in ergebnis.stdout                 # Meldung wird nicht mehr verschluckt
    assert not (ordner / "FERTIG").exists()


def test_ohne_linux_umgebung_nur_home(tmp_path):
    bash = _bash()
    basis = _termux_attrappe(tmp_path)
    shutil.rmtree(basis / "usr" / "var")
    (basis / "home" / ".sicherung_empfaenger.txt").write_text(SCHLUESSEL, encoding="utf-8")
    werkzeuge = _age_platzhalter(tmp_path)
    umgebung = dict(os.environ, TERMUX_BASIS=_posix(basis), SICHERUNG_ZIEL=_posix(tmp_path / "d"),
                    SICHERUNG_STAND="s", HOME=_posix(basis / "home"), TMPDIR=_posix(tmp_path),
                    PORT="1")
    befehl = f'export PATH="{_posix(werkzeuge)}:$PATH"; bash "{_posix(SKRIPT)}"'
    ergebnis = subprocess.run([bash, "-c", befehl], env=umgebung, capture_output=True, text=True)
    assert ergebnis.returncode == 0, ergebnis.stdout
    assert "Keine Linux-Umgebung" in ergebnis.stdout
    assert set(sp.manifest_lesen(str(tmp_path / "d" / "s" / "MANIFEST.txt"))) == {"home.tar.age"}


def test_pruefer_ohne_eintragszahl_und_komprimiert(tmp_path):
    import gzip
    ordner = tmp_path / "s"
    ordner.mkdir()
    puffer = io.BytesIO()
    with tarfile.open(fileobj=puffer, mode="w") as archiv:
        info = tarfile.TarInfo("debian/etc/os-release")
        info.size = 3
        archiv.addfile(info, io.BytesIO(b"x=1"))
    teil = ordner / "distro_debian.tar.age"
    teil.write_bytes(gzip.compress(puffer.getvalue()))
    (ordner / "MANIFEST.txt").write_text(
        f"distro_debian.tar.age groesse={teil.stat().st_size} eintraege=-1 "
        f"sha256={sp.sha256_datei(str(teil))}\n", encoding="utf-8")
    (ordner / "FERTIG").write_text("x", encoding="utf-8")
    zeilen, gruen = sp.pruefen(str(ordner), _datei_oeffnen)
    assert gruen and "Eintraege" not in zeilen[0] and "bis zum Ende lesbar" in zeilen[0]
