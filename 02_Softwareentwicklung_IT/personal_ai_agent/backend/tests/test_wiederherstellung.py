"""Tests: Termux-Wiederherstellung nach dem Umzug (10.10.2026).

``tools/handy/wiederherstellung_senden.py`` (PC) und ``termux/wiederherstellen.sh``
(Handy). Offline mit erfundenen Daten: ein winziger Heimordner wird an einen
Test-Hauptschluessel verschluesselt, ueber den Einmal-Schluessel umgeschluesselt
und im Test-"Termux" (Git Bash) wieder ausgepackt.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_wiederherstellung.py -q
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

PROJEKT = Path(__file__).resolve().parents[2]
SKRIPT = PROJEKT / "termux" / "wiederherstellen.sh"
SHEBANG = "#!/data/data/com.termux/files/usr/bin/bash"

spez = importlib.util.spec_from_file_location(
    "wiederherstellung_senden", PROJEKT / "tools" / "handy" / "wiederherstellung_senden.py")
assert spez is not None and spez.loader is not None
ws = importlib.util.module_from_spec(spez)
spez.loader.exec_module(ws)

# Streaming-Filter als Attrappe fuer age: XOR je Byte (umkehrbar, aendert die Daten).
XOR = [sys.executable, "-c",
       "import sys\nwhile True:\n b=sys.stdin.buffer.read(65536)\n if not b: break\n"
       " sys.stdout.buffer.write(bytes(x ^ int(sys.argv[1]) for x in b))", ]


def _schreiber(pfad):
    return [sys.executable, "-c",
            "import shutil,sys; shutil.copyfileobj(sys.stdin.buffer, open(sys.argv[1], 'wb'))", str(pfad)]


def _sha(pfad) -> str:
    return hashlib.sha256(Path(pfad).read_bytes()).hexdigest()


# ── Strom: entschluesseln -> verschluesseln -> Ziel ─────────────────────────

def test_teil_senden_strom_und_pruefsummen(tmp_path):
    quelle = tmp_path / "teil.bin"
    quelle.write_bytes(os.urandom(3 * 1024 * 1024 + 17))
    ziel = tmp_path / "ziel.bin"
    alt, neu, groesse = ws.teil_senden(str(quelle), XOR + ["85"], XOR + ["17"], _schreiber(ziel))
    assert alt == _sha(quelle) and neu == _sha(ziel) and groesse == ziel.stat().st_size
    erwartet = bytes(b ^ 85 ^ 17 for b in quelle.read_bytes())
    assert ziel.read_bytes() == erwartet


def test_teil_senden_bricht_bei_fehlerhafter_stufe_ab(tmp_path):
    quelle = tmp_path / "teil.bin"
    quelle.write_bytes(b"x" * 100000)
    kaputt = [sys.executable, "-c", "import sys; sys.stdin.buffer.read(10); sys.exit(1)"]
    with pytest.raises(ws.TransferFehler):
        ws.teil_senden(str(quelle), kaputt, XOR + ["1"], _schreiber(tmp_path / "z.bin"))


# ── Ganzer Weg mit echtem age (Probelauf in einen Ordner) ───────────────────

def _age():
    if not (shutil.which("age") and shutil.which("age-keygen")):
        pytest.skip("age nicht installiert")
    return shutil.which("age")


def _schluessel(ordner: Path, name: str):
    pfad = ordner / name
    subprocess.run(["age-keygen", "-o", str(pfad)], check=True, capture_output=True)
    oeffentlich = subprocess.run(["age-keygen", "-y", str(pfad)], check=True,
                                 capture_output=True, text=True).stdout.strip()
    return pfad, oeffentlich


def _home_tar() -> bytes:
    roh = io.BytesIO()
    with tarfile.open(fileobj=roh, mode="w") as archiv:
        for name, inhalt in (("home/foto_sortierung/personen_bestaetigt.json", b'{"bestaetigt": {"P_1": "Leon"}}'),
                             ("home/notiz.txt", b"aus der Sicherung")):
            info = tarfile.TarInfo(name)
            info.size = len(inhalt)
            archiv.addfile(info, io.BytesIO(inhalt))
    return roh.getvalue()


def _sicherung(tmp_path: Path, haupt_oeffentlich: str, mit_distro=False) -> Path:
    ordner = tmp_path / "pc" / "2026-10-10_0247"
    ordner.mkdir(parents=True)
    teile = {"home.tar.age": _home_tar()}
    if mit_distro:
        teile["distro_debian.tar.age"] = b"debian-attrappe" * 100
    zeilen = ["stand=2026-10-10_0247"]
    for name, klar in teile.items():
        ziel = ordner / name
        subprocess.run(["age", "-r", haupt_oeffentlich, "-o", str(ziel)], input=klar, check=True)
        zeilen.append(f"{name} groesse={ziel.stat().st_size} eintraege=2 sha256={_sha(ziel)}")
    (ordner / "MANIFEST.txt").write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    (ordner / "pakete_manuell.txt").write_text("age\npython\n", encoding="utf-8")
    (ordner / "FERTIG").write_text("2026-10-10_0247\n", encoding="utf-8")
    return ordner


def test_probelauf_schluesselt_um_und_ist_idempotent(tmp_path, capsys):
    _age()
    haupt, haupt_oeff = _schluessel(tmp_path, "haupt.key")
    einmal, einmal_oeff = _schluessel(tmp_path, "einmal.key")
    sicherung = _sicherung(tmp_path, haupt_oeff)
    ziel = tmp_path / "handy"
    argv = ["--sicherung", str(sicherung), "--schluessel", str(haupt),
            "--lokal-ziel", str(ziel), "--empfaenger", einmal_oeff]
    assert ws.main(argv) == 0
    sendung = ziel / "wiederherstellung_2026-10-10_0247"
    assert (sendung / "FERTIG").exists() and (sendung / "pakete_manuell.txt").exists()
    assert (sendung / "EMPFAENGER.txt").read_text().strip() == einmal_oeff
    manifest = (sendung / "MANIFEST.txt").read_text()
    assert f"sha256={_sha(sendung / 'home.tar.age')}" in manifest
    klar = subprocess.run(["age", "-d", "-i", str(einmal), str(sendung / "home.tar.age")],
                          check=True, capture_output=True).stdout
    assert klar == _home_tar()                                  # Inhalt unveraendert
    with pytest.raises(subprocess.CalledProcessError):          # Hauptschluessel passt NICHT mehr
        subprocess.run(["age", "-d", "-i", str(haupt), str(sendung / "home.tar.age")],
                       check=True, capture_output=True)
    capsys.readouterr()
    assert ws.main(argv) == 0                                   # zweiter Lauf: nichts Neues
    assert "nichts zu tun" in capsys.readouterr().out
    assert sorted(p.name for p in ziel.iterdir()) == ["wiederherstellung_2026-10-10_0247"]


def test_probelauf_anderer_schluessel_neuer_ordner_nie_ueberschreiben(tmp_path):
    _age()
    haupt, haupt_oeff = _schluessel(tmp_path, "haupt.key")
    _, erst = _schluessel(tmp_path, "e1.key")
    _, zweit = _schluessel(tmp_path, "e2.key")
    sicherung = _sicherung(tmp_path, haupt_oeff)
    ziel = tmp_path / "handy"
    basis = ["--sicherung", str(sicherung), "--schluessel", str(haupt), "--lokal-ziel", str(ziel)]
    assert ws.main(basis + ["--empfaenger", erst]) == 0
    vorher = _sha(ziel / "wiederherstellung_2026-10-10_0247" / "home.tar.age")
    assert ws.main(basis + ["--empfaenger", zweit]) == 0
    assert (ziel / "wiederherstellung_2026-10-10_0247_2" / "FERTIG").exists()
    assert _sha(ziel / "wiederherstellung_2026-10-10_0247" / "home.tar.age") == vorher


def test_beschaedigte_sicherung_wird_erkannt_kein_fertig(tmp_path):
    _age()
    haupt, haupt_oeff = _schluessel(tmp_path, "haupt.key")
    _, einmal_oeff = _schluessel(tmp_path, "einmal.key")
    sicherung = _sicherung(tmp_path, haupt_oeff)
    manifest = sicherung / "MANIFEST.txt"
    manifest.write_text(re.sub(r"sha256=[0-9a-f]{64}", "sha256=" + "0" * 64, manifest.read_text()),
                        encoding="utf-8")
    ziel = tmp_path / "handy"
    assert ws.main(["--sicherung", str(sicherung), "--schluessel", str(haupt),
                    "--lokal-ziel", str(ziel), "--empfaenger", einmal_oeff]) == 5
    assert not (ziel / "wiederherstellung_2026-10-10_0247" / "FERTIG").exists()


def test_ohne_einmal_schluessel_exit_3(tmp_path):
    assert ws.main(["--lokal-ziel", str(tmp_path), "--empfaenger", ""]) == 3


def test_ohne_handy_exit_1():
    assert ws.main([], adb=lambda a, eingabe=None: (0, "List of devices attached\n")) == 1


def test_handy_weg_legt_skript_ab_und_fragt_nach_schluessel():
    aufrufe = []

    def adb(argumente, eingabe=None):
        aufrufe.append((argumente, eingabe))
        if argumente[0] == "devices":
            return 0, "List of devices attached\nABC\tdevice\n"
        return (1, "") if argumente[0] == "shell" and argumente[1].startswith("cat ") else (0, "")
    assert ws.main([], adb=adb) == 3
    skript = [e for a, e in aufrufe if a[0] == "exec-in" and a[1].endswith("/wiederherstellen.sh")]
    assert skript and skript[0].startswith(SHEBANG.encode()) and b"\r\n" not in skript[0]


# ── Handy-Skript ────────────────────────────────────────────────────────────

def _bash():
    bash = shutil.which("bash")
    if not bash or "system32" in bash.lower() or not shutil.which("tar") \
            or not shutil.which("sha256sum"):
        pytest.skip("Git Bash mit tar/sha256sum nicht vorhanden")
    return bash


def _posix(pfad: Path) -> str:
    text = str(pfad).replace("\\", "/")
    treffer = re.match(r"^([A-Za-z]):/(.*)$", text)
    return f"/{treffer.group(1).lower()}/{treffer.group(2)}" if treffer else text


def test_skript_syntax_shebang_und_kein_loeschen():
    text = SKRIPT.read_text(encoding="utf-8")
    assert text.startswith(SHEBANG + "\n") and "\r\n" not in text
    assert "--skip-old-files" in text
    assert not re.search(r"\brm\s", text) and "proot-distro remove" not in text
    ergebnis = subprocess.run([_bash(), "-n", _posix(SKRIPT)], capture_output=True, text=True)
    assert ergebnis.returncode == 0, ergebnis.stderr


def _termux(tmp_path: Path):
    basis = tmp_path / "termux"
    (basis / "home").mkdir(parents=True)
    ablage = tmp_path / "download"
    umgebung = dict(os.environ, TERMUX_BASIS=_posix(basis), HOME=_posix(basis / "home"),
                    WIEDERHERSTELLUNG_ABLAGE=_posix(ablage), WIEDERHERSTELLUNG_OHNE_PAKETE="1")
    return basis, ablage, umgebung


def _skript(umgebung, *argumente):
    return subprocess.run([_bash(), _posix(SKRIPT), *argumente], capture_output=True,
                          text=True, env=umgebung)


def test_ganzer_umzug_vorbereiten_senden_einspielen(tmp_path):
    _age()
    basis, ablage, umgebung = _termux(tmp_path)
    (basis / "home" / "notiz.txt").write_text("schon im neuen Termux", encoding="utf-8")
    lager = basis / "usr" / "var" / "lib" / "proot-distro" / "containers" / "debian"
    lager.mkdir(parents=True)
    (lager / "bleibt.txt").write_text("x", encoding="utf-8")

    vor = _skript(umgebung, "vorbereiten")
    assert vor.returncode == 0, vor.stdout + vor.stderr
    einmal_oeff = (ablage / "einmal_empfaenger.txt").read_text().strip()
    assert einmal_oeff.startswith("age1") and (basis / "home" / ".wiederherstellung_einmal.key").exists()
    assert _skript(umgebung, "vorbereiten").returncode == 0                     # Schluessel bleibt derselbe
    assert (ablage / "einmal_empfaenger.txt").read_text().strip() == einmal_oeff

    haupt, haupt_oeff = _schluessel(tmp_path, "haupt.key")
    sicherung = _sicherung(tmp_path, haupt_oeff, mit_distro=True)
    assert ws.main(["--sicherung", str(sicherung), "--schluessel", str(haupt),
                    "--lokal-ziel", str(ablage), "--empfaenger", einmal_oeff]) == 0

    ein = _skript(umgebung, "einspielen")
    assert ein.returncode == 0, ein.stdout + ein.stderr
    assert "Pruefsumme ok" in ein.stdout and "bleibt unberuehrt" in ein.stdout
    namen = basis / "home" / "foto_sortierung" / "personen_bestaetigt.json"
    assert "Leon" in namen.read_text(encoding="utf-8")
    assert (basis / "home" / "notiz.txt").read_text(encoding="utf-8") == "schon im neuen Termux"   # nicht ueberschrieben
    assert (lager / "bleibt.txt").exists()


def test_einspielen_ohne_sendung_und_mit_falscher_pruefsumme(tmp_path):
    _age()
    basis, ablage, umgebung = _termux(tmp_path)
    assert _skript(umgebung, "einspielen").returncode == 4                     # nichts da
    assert _skript(umgebung, "vorbereiten").returncode == 0
    einmal_oeff = (ablage / "einmal_empfaenger.txt").read_text().strip()
    haupt, haupt_oeff = _schluessel(tmp_path, "haupt.key")
    sicherung = _sicherung(tmp_path, haupt_oeff)
    assert ws.main(["--sicherung", str(sicherung), "--schluessel", str(haupt),
                    "--lokal-ziel", str(ablage), "--empfaenger", einmal_oeff]) == 0
    teil = ablage / "wiederherstellung_2026-10-10_0247" / "home.tar.age"
    teil.write_bytes(teil.read_bytes() + b"kaputt")
    ergebnis = _skript(umgebung, "einspielen")
    assert ergebnis.returncode == 5 and not (basis / "home" / "foto_sortierung").exists()


def test_unbekannter_aufruf_exit_1(tmp_path):
    _, _, umgebung = _termux(tmp_path)
    assert _skript(umgebung).returncode == 1
