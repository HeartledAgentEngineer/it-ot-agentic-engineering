"""HTTPS-Plan H3b (14.10.2026): ein Start, ein Stopp, Umstellung HTTP -> HTTPS.

Geprueft werden die Skripte ``termux/backend-starten.sh``, ``termux/backend-beenden.sh``
und ``termux/tls-umstellung.sh`` sowie die vier Startwege, die nur noch diese rufen.

Die Skripte laufen ECHT in Git Bash in einem Sandkasten unter ``tmp_path``. Ein
Server wird nie gestartet und kein Prozess beendet: ``python``, ``ss``, ``curl``,
``pgrep``, ``pkill``, ``setsid`` und ``nohup`` sind Attrappen auf dem ``PATH``.
Sie schreiben ihre Aufrufe in ``aufrufe.log`` und fuehren ueber zwei Zustandsdateien
Buch, was "laeuft" (``prozesse.txt``: eine erfundene Kommandozeile je Zeile) und
was "lauscht" (``ss.txt``: Zeilen im Format von ``ss -tln``). Alle Zertifikatsdateien
sind Textattrappen; die Attrappe-``curl`` prueft die CA, indem sie den Inhalt der
uebergebenen ``--cacert``-Datei mit ``ca_erwartet`` vergleicht.

Offline, nur erfundene Pfade; kein Netz, kein Geraet, keine .env des Projekts.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TERMUX = REPO / "termux"
STARTEN = TERMUX / "backend-starten.sh"
BEENDEN = TERMUX / "backend-beenden.sh"
UMSTELLUNG = TERMUX / "tls-umstellung.sh"
ENSURE = TERMUX / "agent-ensure.sh"
NEUSTART = TERMUX / "neu-start-nach-lauf.sh"
WIDGET = TERMUX / "agent-start"
START_TERMUX = REPO / "start-termux.sh"
GEAENDERT = (STARTEN, BEENDEN, UMSTELLUNG, ENSURE, NEUSTART, WIDGET, START_TERMUX)
TLS_DATEIEN = ("server.crt", "server.key", "ca.crt")

SS_KOPF = "State Recv-Q Send-Q Local Address:Port Peer Address:Port"


def _bash() -> str:
    bash = shutil.which("bash")
    if not bash or "system32" in bash.lower():
        pytest.skip("Git Bash nicht vorhanden")
    return bash


def _posix(pfad: Path) -> str:
    return str(pfad).replace("\\", "/")


def _lies(pfad: Path) -> str:
    return pfad.read_text(encoding="utf-8")


def _warten(bedingung, sekunden: float = 8.0) -> bool:
    """Hintergrundprozesse (setsid ... &) schreiben ihre Spuren etwas spaeter."""
    ende = time.time() + sekunden
    while time.time() < ende:
        if bedingung():
            return True
        time.sleep(0.1)
    return bool(bedingung())


# ── Attrappen ───────────────────────────────────────────────────────────────

ATTRAPPE_PYTHON = """#!/bin/sh
echo "python $* [cwd=$(basename "$PWD") PORT=${PORT:-} HOST_BIND=${HOST_BIND:-} TLS=${AGENT_TLS_ORDNER:-}]" >> "$ATT/aufrufe.log"
echo "SERVERAUSGABE"
case "$*" in
  *serve.py*)
    echo "python serve.py" >> "$ATT/prozesse.txt"
    printf 'LISTEN 0 128 127.0.0.1:%s 0.0.0.0:*\\nLISTEN 0 128 0.0.0.0:8443 0.0.0.0:*\\n' "${PORT:-8080}" > "$ATT/ss.txt"
    ;;
  *uvicorn*)
    host=0.0.0.0; port=8080
    while [ $# -gt 0 ]; do
      [ "$1" = "--host" ] && host="$2"
      [ "$1" = "--port" ] && port="$2"
      shift
    done
    echo "python -m uvicorn app.main:app --host $host --port $port" >> "$ATT/prozesse.txt"
    printf 'LISTEN 0 128 %s:%s 0.0.0.0:*\\n' "$host" "$port" > "$ATT/ss.txt"
    ;;
esac
exit 0
"""

ATTRAPPE_SS = """#!/bin/sh
echo "ss $*" >> "$ATT/aufrufe.log"
echo "State Recv-Q Send-Q Local Address:Port Peer Address:Port"
cat "$ATT/ss.txt" 2>/dev/null
exit 0
"""

ATTRAPPE_CURL = """#!/bin/sh
echo "curl $*" >> "$ATT/aufrufe.log"
cacert=""; url=""; mit_w=0
while [ $# -gt 0 ]; do
  case "$1" in
    --cacert) cacert="$2"; shift ;;
    -w) mit_w=1; shift ;;
    http*) url="$1" ;;
  esac
  shift
done
case "$url" in
  https://*)
    if grep -q ':8443' "$ATT/ss.txt" 2>/dev/null && [ -n "$cacert" ] \\
       && [ "$(cat "$cacert" 2>/dev/null)" = "$(cat "$ATT/ca_erwartet" 2>/dev/null)" ]; then
      echo '{"ok":true}'; exit 0
    fi
    exit 60 ;;
  *)
    port=$(echo "$url" | sed -n 's|^http://127\\.0\\.0\\.1:\\([0-9]*\\)/.*|\\1|p')
    if [ -n "$port" ] && grep -q ":$port " "$ATT/ss.txt" 2>/dev/null; then
      [ "$mit_w" = 1 ] && printf '200'
      exit 0
    fi
    [ "$mit_w" = 1 ] && printf '000'
    exit 7 ;;
esac
"""

ATTRAPPE_PGREP = """#!/bin/sh
echo "pgrep $*" >> "$ATT/aufrufe.log"
for letztes; do :; done
grep -E -- "$letztes" "$ATT/prozesse.txt" >/dev/null 2>&1
"""

ATTRAPPE_PKILL = """#!/bin/sh
echo "pkill $*" >> "$ATT/aufrufe.log"
signal=""
for letztes; do :; done
for a in "$@"; do
  case "$a" in -TERM|-KILL|-9|-15) signal="$a" ;; esac
done
[ -f "$ATT/unsterblich" ] && exit 0
if [ -f "$ATT/hartnaeckig" ]; then
  case "$signal" in -TERM|-15) exit 0 ;; esac
fi
[ -f "$ATT/prozesse.txt" ] || exit 1
vorher=$(wc -l < "$ATT/prozesse.txt")
grep -Ev -- "$letztes" "$ATT/prozesse.txt" > "$ATT/prozesse.neu"
mv "$ATT/prozesse.neu" "$ATT/prozesse.txt"
nachher=$(wc -l < "$ATT/prozesse.txt")
if [ "$vorher" -gt "$nachher" ] && ! grep -Eq 'uvicorn|serve[.]py' "$ATT/prozesse.txt"; then : > "$ATT/ss.txt"; fi
exit 0
"""

ATTRAPPE_LOESER = """#!/bin/sh
echo "$(basename "$0") $*" >> "$ATT/aufrufe.log"
exec "$@"
"""


class Sandkasten:
    """Projekt-Sandkasten: echte Skripte, erfundene Umgebung."""

    def __init__(self, tmp_path: Path):
        self.wurzel = tmp_path
        self.projekt = tmp_path / "projekt"
        (self.projekt / "termux").mkdir(parents=True)
        (self.projekt / "backend").mkdir()
        for skript in (STARTEN, BEENDEN, UMSTELLUNG, ENSURE, NEUSTART):
            (self.projekt / "termux" / skript.name).write_bytes(skript.read_bytes())
        # Die Vorbereitung ist hier nicht Gegenstand: eine Attrappe, die nichts tut.
        (self.projekt / "termux" / "start-vorbereiten.sh").write_bytes(
            b'#!/bin/sh\necho "VORBEREITUNG $*"\nexit 0\n')
        self.att = tmp_path / "att"
        self.att.mkdir()
        self.heim = tmp_path / "heim"
        self.heim.mkdir()
        self.tls = tmp_path / "tls"
        self.tls.mkdir()
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        for name, text in (("python", ATTRAPPE_PYTHON), ("ss", ATTRAPPE_SS),
                           ("curl", ATTRAPPE_CURL), ("pgrep", ATTRAPPE_PGREP),
                           ("pkill", ATTRAPPE_PKILL), ("setsid", ATTRAPPE_LOESER),
                           ("nohup", ATTRAPPE_LOESER)):
            (self.bin / name).write_bytes(text.encode("utf-8"))
        (self.att / "ca_erwartet").write_bytes(b"CA-A")
        # Das Skript liest einen echten Termux-Pfad nicht; Termux-Programme fehlen hier.
        self.umgebung = dict(
            os.environ,
            HOME=_posix(self.heim),
            ATT=_posix(self.att),
            AGENT_TLS_ORDNER=_posix(self.tls),
            PATH=_posix(self.bin) + os.pathsep + os.environ.get("PATH", ""),
            BEENDEN_WARTEN_S="1",
            BEENDEN_KILL_WARTEN_S="1",
            UMSTELLUNG_WARTEN_S="1",
        )
        for weg in ("PORT", "HOST_BIND", "PROJEKT", "MSYS2_ARG_CONV_EXCL", "MSYS_NO_PATHCONV"):
            self.umgebung.pop(weg, None)

    # -- Zustand setzen / lesen -------------------------------------------
    def zertifikate(self, ca: str = "CA-A", crt: str = "CRT-1", fehlt: str | None = None,
                    leer: str | None = None):
        for name in TLS_DATEIEN:
            if name == fehlt:
                (self.tls / name).unlink(missing_ok=True)
                continue
            inhalt = ca if name == "ca.crt" else (crt if name == "server.crt" else "SCHLUESSEL")
            (self.tls / name).write_bytes(b"" if name == leer else inhalt.encode())

    def laufend(self, *zeilen: str, ss: tuple[str, ...] = ()):
        (self.att / "prozesse.txt").write_text("".join(z + "\n" for z in zeilen), encoding="utf-8")
        (self.att / "ss.txt").write_text("".join(z + "\n" for z in ss), encoding="utf-8")

    def http_offen(self):
        """Ein alter HTTP-Server im WLAN: uvicorn auf 0.0.0.0:8080."""
        self.laufend("python -m uvicorn app.main:app --host 0.0.0.0 --port 8080",
                     ss=("LISTEN 0 128 0.0.0.0:8080 0.0.0.0:*",))

    def tls_aktiv(self, ca_ok: bool = True):
        self.laufend("python serve.py",
                     ss=("LISTEN 0 128 127.0.0.1:8080 0.0.0.0:*",
                         "LISTEN 0 128 0.0.0.0:8443 0.0.0.0:*"))
        (self.att / "ca_erwartet").write_bytes(b"CA-A" if ca_ok else b"CA-ANDERE")

    def env_datei(self, text: str):
        (self.projekt / "backend" / ".env").write_text(text, encoding="utf-8")

    def aufrufe(self) -> list[str]:
        pfad = self.att / "aufrufe.log"
        return pfad.read_text(encoding="utf-8").splitlines() if pfad.exists() else []

    def aufrufe_mit(self, *teile: str) -> list[str]:
        return [z for z in self.aufrufe() if all(t in z for t in teile)]

    def starts(self) -> list[str]:
        """Nur echte python-Aufrufe (nicht pgrep/pkill, die den Text als Muster tragen)."""
        return [z for z in self.aufrufe() if z.startswith("python ")]

    def prozesse(self) -> list[str]:
        pfad = self.att / "prozesse.txt"
        return [z for z in pfad.read_text(encoding="utf-8").splitlines() if z] if pfad.exists() else []

    def warnung(self) -> Path:
        return self.projekt / "backend" / "hermes_diag" / "tls_umstellung_gescheitert.txt"

    # -- Skripte laufen lassen ----------------------------------------------
    def lauf(self, skript: str, *args: str, umgebung: dict | None = None):
        env = dict(self.umgebung, **(umgebung or {}))
        return subprocess.run(
            [_bash(), _posix(self.projekt / "termux" / skript), *args],
            env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)


@pytest.fixture
def sb(tmp_path):
    return Sandkasten(tmp_path)


# ── backend-starten.sh: Moduswahl ───────────────────────────────────────────


def test_mit_drei_tls_dateien_startet_serve_py(sb):
    sb.zertifikate()
    lauf = sb.lauf("backend-starten.sh")
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    start = sb.starts()
    assert len(start) == 1 and start[0].startswith("python serve.py"), start
    assert "cwd=backend" in start[0], "serve.py liegt in backend/: dort wird gestartet"
    assert not sb.aufrufe_mit("uvicorn")
    assert f"TLS={_posix(sb.tls)}" in start[0], "serve.py bekommt denselben Zertifikatsordner"


@pytest.mark.parametrize("fehlt", TLS_DATEIEN)
def test_fehlt_eine_datei_startet_uvicorn(sb, fehlt):
    sb.zertifikate(fehlt=fehlt)
    lauf = sb.lauf("backend-starten.sh")
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    (start,) = sb.starts()
    assert start.startswith("python -m uvicorn app.main:app --host 0.0.0.0 --port 8080"), start
    assert "serve.py" not in start
    assert "cwd=backend" in start


@pytest.mark.parametrize("leer", TLS_DATEIEN)
def test_leere_datei_zaehlt_als_fehlend(sb, leer):
    sb.zertifikate(leer=leer)
    assert sb.lauf("backend-starten.sh").returncode == 0
    (start,) = sb.starts()
    assert "-m uvicorn" in start and "serve.py" not in start


def test_ohne_tls_ordner_startet_uvicorn(sb):
    shutil.rmtree(sb.tls)
    assert sb.lauf("backend-starten.sh").returncode == 0
    (start,) = sb.starts()
    assert "-m uvicorn" in start


def test_reload_wirkt_nur_ohne_tls(sb):
    lauf = sb.lauf("backend-starten.sh", "--reload")          # ohne Zertifikat
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    (start,) = sb.starts()
    assert " --reload" in start
    assert "ignoriert" not in lauf.stdout


def test_reload_mit_tls_wird_ignoriert_mit_logzeile(sb):
    sb.zertifikate()
    lauf = sb.lauf("backend-starten.sh", "--reload")
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    (start,) = sb.starts()
    assert start.startswith("python serve.py") and "--reload" not in start
    assert "--reload" in lauf.stdout and "ignoriert" in lauf.stdout


def test_port_und_host_bind_kommen_aus_der_env_und_werden_exportiert(sb):
    sb.env_datei('PORT=9090 # eigener Port\nHOST_BIND="127.0.0.1"\n')
    sb.lauf("backend-starten.sh")
    (start,) = sb.starts()
    assert "--host 127.0.0.1 --port 9090" in start
    sb.zertifikate()
    (sb.att / "aufrufe.log").unlink()
    sb.lauf("backend-starten.sh")
    (start,) = sb.starts()
    assert "PORT=9090" in start and "HOST_BIND=127.0.0.1" in start, (
        "serve.py liest PORT und HOST_BIND aus der Umgebung")


def test_standard_ist_8080_und_0_0_0_0(sb):
    sb.lauf("backend-starten.sh")
    (start,) = sb.starts()
    assert "--host 0.0.0.0 --port 8080" in start


def test_unbrauchbarer_port_faellt_auf_8080(sb):
    sb.env_datei("PORT=abc\n")
    lauf = sb.lauf("backend-starten.sh")
    assert lauf.returncode == 0
    (start,) = sb.starts()
    assert "--port 8080" in start


def test_abloesen_nutzt_setsid_und_gibt_die_pid_aus(sb):
    log = sb.wurzel / "server.log"
    lauf = sb.lauf("backend-starten.sh", "--abloesen", "--log", _posix(log))
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "Backend gestartet (PID" in lauf.stdout
    assert _warten(lambda: sb.aufrufe_mit("setsid python -m uvicorn"))
    # die Ausgabe des Servers landet in der Logdatei, nicht auf dem Schirm
    assert _warten(lambda: log.exists() and "SERVERAUSGABE" in log.read_text(encoding="utf-8"))
    assert "SERVERAUSGABE" not in lauf.stdout


def test_abloesen_faellt_ohne_setsid_auf_nohup_zurueck(sb):
    (sb.bin / "setsid").unlink()
    if shutil.which("setsid", path=os.environ.get("PATH")):
        pytest.skip("ein echtes setsid liegt im PATH")
    sb.zertifikate()
    assert sb.lauf("backend-starten.sh", "--abloesen").returncode == 0
    assert _warten(lambda: sb.aufrufe_mit("nohup python serve.py"))


def test_ohne_abloesen_wird_das_skript_zum_server(sb):
    """Ohne --abloesen bleibt der Server das Kind des Aufrufers (exec): kein setsid/nohup."""
    assert sb.lauf("backend-starten.sh").returncode == 0
    assert not sb.aufrufe_mit("setsid") and not sb.aufrufe_mit("nohup")
    text = _lies(STARTEN)
    assert re.search(r'^exec "\$\{BEFEHL\[@\]\}"', text, re.M)
    assert '< /dev/null' in text, "abgeloest heisst: stdin von /dev/null"


def test_unbekannter_schalter_ist_exit_2(sb):
    lauf = sb.lauf("backend-starten.sh", "--quatsch")
    assert lauf.returncode == 2
    assert not sb.starts()


# ── backend-starten.sh: --modus-pruefen ─────────────────────────────────────


def test_modus_tls_passt_wenn_curl_ok_und_http_nur_lokal(sb):
    sb.zertifikate()
    sb.tls_aktiv()
    lauf = sb.lauf("backend-starten.sh", "--modus-pruefen")
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert not sb.starts(), "die Pruefung startet nichts"
    assert not sb.aufrufe_mit("pkill")


def test_modus_curl_scheitert_ist_3(sb):
    sb.zertifikate()
    sb.tls_aktiv(ca_ok=False)                  # fremde CA: die Kette passt nicht
    assert sb.lauf("backend-starten.sh", "--modus-pruefen").returncode == 3


def test_modus_http_server_laeuft_mit_zertifikat_ist_3(sb):
    sb.zertifikate()
    sb.http_offen()
    assert sb.lauf("backend-starten.sh", "--modus-pruefen").returncode == 3


@pytest.mark.parametrize("adresse", ["0.0.0.0:8080", "*:8080", "[::]:8080", "192.168.178.20:8080"])
def test_modus_http_port_nicht_nur_lokal_ist_3(sb, adresse):
    sb.zertifikate()
    sb.laufend("python serve.py",
               ss=("LISTEN 0 128 127.0.0.1:8080 0.0.0.0:*",
                   f"LISTEN 0 128 {adresse} 0.0.0.0:*",
                   "LISTEN 0 128 0.0.0.0:8443 0.0.0.0:*"))
    assert sb.lauf("backend-starten.sh", "--modus-pruefen").returncode == 3


@pytest.mark.parametrize("fehlt", TLS_DATEIEN)
def test_modus_ohne_vollstaendiges_zertifikat_ist_immer_0(sb, fehlt):
    sb.zertifikate(fehlt=fehlt)
    sb.http_offen()                            # offener HTTP-Server, aber kein TLS gewuenscht
    lauf = sb.lauf("backend-starten.sh", "--modus-pruefen")
    assert lauf.returncode == 0, lauf.stdout
    assert not sb.aufrufe_mit("curl"), "ohne gewuenschtes TLS wird nicht einmal gefragt"


def test_modus_leere_datei_ist_kein_tls_und_0(sb):
    sb.zertifikate(leer="ca.crt")
    sb.http_offen()
    assert sb.lauf("backend-starten.sh", "--modus-pruefen").returncode == 0


def test_modus_curl_nutzt_cacert_und_nie_k(sb):
    sb.zertifikate()
    sb.tls_aktiv()
    sb.lauf("backend-starten.sh", "--modus-pruefen")
    (aufruf,) = sb.aufrufe_mit("curl", "https://")
    assert f"--cacert {_posix(sb.tls)}/ca.crt" in aufruf
    assert "https://127.0.0.1:8443/api/health" in aufruf
    for wort in aufruf.split():
        assert wort != "--insecure"
        assert not (wort.startswith("-") and not wort.startswith("--") and "k" in wort), (
            f"nie -k (auch nicht gebuendelt): {wort}")
    text = _lies(STARTEN)
    assert "--insecure" not in text
    assert not re.search(r"curl[^\n]*\s-k(\s|$)", text), "die Pruefung nutzt nie -k"


def test_modus_mit_port_aus_der_env(sb):
    sb.env_datei("PORT=9090\n")
    sb.zertifikate()
    sb.laufend("python serve.py",
               ss=("LISTEN 0 128 127.0.0.1:9090 0.0.0.0:*", "LISTEN 0 128 0.0.0.0:8443 0.0.0.0:*"))
    assert sb.lauf("backend-starten.sh", "--modus-pruefen").returncode == 0
    sb.laufend("python serve.py",
               ss=("LISTEN 0 128 0.0.0.0:9090 0.0.0.0:*", "LISTEN 0 128 0.0.0.0:8443 0.0.0.0:*"))
    assert sb.lauf("backend-starten.sh", "--modus-pruefen").returncode == 3


# ── backend-beenden.sh ───────────────────────────────────────────────────────

DREI_ARTEN = ("python -m uvicorn app.main:app --host 0.0.0.0 --port 8080",
              "uvicorn app.main:app --reload",
              "python serve.py")


def test_beenden_erwischt_alle_drei_prozessarten(sb):
    sb.laufend(*DREI_ARTEN, ss=("LISTEN 0 128 0.0.0.0:8080 0.0.0.0:*",))
    lauf = sb.lauf("backend-beenden.sh")
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert sb.prozesse() == []
    muster = " ".join(sb.aufrufe_mit("pkill", "-TERM"))
    assert "uvicorn app.main:app" in muster and "python -m uvicorn" in muster
    assert "serve" in muster, "auch serve.py bekommt sein TERM"


def test_beenden_einzeln_je_art(sb):
    for art in DREI_ARTEN:
        sb.laufend(art, ss=("LISTEN 0 128 0.0.0.0:8080 0.0.0.0:*",))
        assert sb.lauf("backend-beenden.sh").returncode == 0, art
        assert sb.prozesse() == [], art


def test_beenden_erst_term_dann_kill_bei_haertnaeckigem_prozess(sb):
    sb.laufend("python serve.py", ss=("LISTEN 0 128 0.0.0.0:8443 0.0.0.0:*",))
    (sb.att / "hartnaeckig").write_text("1")
    lauf = sb.lauf("backend-beenden.sh")
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    zeilen = [z for z in sb.aufrufe() if z.startswith("pkill")]
    erste_kill = next(i for i, z in enumerate(zeilen) if "-KILL" in z)
    letzte_term = max(i for i, z in enumerate(zeilen) if "-TERM" in z)
    assert letzte_term < erste_kill, "KILL erst nach der Wartezeit auf TERM"


def test_beenden_ohne_laufenden_prozess_ist_0_und_sendet_nichts(sb):
    lauf = sb.lauf("backend-beenden.sh")
    assert lauf.returncode == 0
    assert not sb.aufrufe_mit("pkill")


def test_beenden_prozess_nicht_wegzubekommen_ist_nicht_0(sb):
    sb.laufend("python serve.py", ss=())
    (sb.att / "unsterblich").write_text("1")
    lauf = sb.lauf("backend-beenden.sh")
    assert lauf.returncode == 1, lauf.stdout
    assert "FEHLER" in lauf.stdout


@pytest.mark.parametrize("belegt", ["0.0.0.0:8080", "127.0.0.1:8080", "0.0.0.0:8443"])
def test_beenden_ports_belegt_ist_nicht_0(sb, belegt):
    sb.laufend(ss=(f"LISTEN 0 128 {belegt} 0.0.0.0:*",))     # kein Prozess, aber der Port steht
    lauf = sb.lauf("backend-beenden.sh")
    assert lauf.returncode == 2, lauf.stdout
    assert "belegt" in lauf.stdout


def test_beenden_prueft_den_port_aus_der_env(sb):
    sb.env_datei("PORT=9090\n")
    sb.laufend(ss=("LISTEN 0 128 127.0.0.1:9090 0.0.0.0:*",))
    assert sb.lauf("backend-beenden.sh").returncode == 2
    sb.laufend(ss=("LISTEN 0 128 127.0.0.1:8080 0.0.0.0:*",))   # 8080 ist hier nicht der Port
    assert sb.lauf("backend-beenden.sh").returncode == 0


def test_beenden_laesst_den_inbox_daemon_in_ruhe(sb):
    sb.laufend("python serve.py", "python hermes_inbox_daemon.py",
               ss=("LISTEN 0 128 0.0.0.0:8443 0.0.0.0:*",))
    assert sb.lauf("backend-beenden.sh").returncode == 0
    assert sb.prozesse() == ["python hermes_inbox_daemon.py"]
    assert not sb.aufrufe_mit("pkill", "hermes_inbox")


def test_laeuft_noch_meldet_nur_ohne_etwas_zu_beenden(sb):
    sb.laufend("python serve.py")
    assert sb.lauf("backend-beenden.sh", "--laeuft-noch").returncode == 0
    assert not sb.aufrufe_mit("pkill")
    sb.laufend("python hermes_inbox_daemon.py")
    assert sb.lauf("backend-beenden.sh", "--laeuft-noch").returncode == 1


# ── Übergangstest über agent-ensure.sh (Plan H3, Punkte 1-6) ────────────────


def _ensure(sb: Sandkasten):
    lauf = sb.lauf("agent-ensure.sh")
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    return lauf


def _ensure_log(sb: Sandkasten) -> str:
    pfad = sb.heim / "agent-ensure.log"
    return pfad.read_text(encoding="utf-8") if pfad.exists() else ""


def _starts(sb: Sandkasten) -> list[str]:
    return sb.starts()


def _beenden_runden(sb: Sandkasten) -> int:
    """Wie oft wurde beendet? Je Beenden genau ein pkill -TERM auf das erste Muster."""
    return len(sb.aufrufe_mit("pkill", "-TERM", "uvicorn app.main:app"))


def test_uebergang_http_zu_https_einmal_dann_ruhe(sb):
    sb.http_offen()                                           # 1. alter HTTP-Server im WLAN

    # 5. ohne Zertifikat laeuft er unveraendert weiter, ohne Neustart
    log = _ensure(sb)
    assert _beenden_runden(sb) == 0 and _starts(sb) == []
    assert sb.prozesse() == ["python -m uvicorn app.main:app --host 0.0.0.0 --port 8080"]
    assert "Serverstart uebersprungen" in _ensure_log(sb)

    # 2./3. das Zertifikat kommt hinzu -> genau ein Beenden, genau ein serve.py
    sb.zertifikate()
    _ensure(sb)
    assert _beenden_runden(sb) == 1
    (start,) = _starts(sb)
    assert start.startswith("python serve.py")
    assert sb.aufrufe_mit("setsid python serve.py"), "abgeloest gestartet (--abloesen)"
    assert sb.prozesse() == ["python serve.py"]
    assert "Umstellung HTTP -> HTTPS" in _ensure_log(sb)
    assert not sb.warnung().exists()

    # 4. zweiter Lauf: nichts mehr zu tun
    _ensure(sb)
    assert _beenden_runden(sb) == 1 and len(_starts(sb)) == 1

    # Zertifikat verschwindet wieder: HTTP gewuenscht, kein Zwang, kein Neustart
    sb.zertifikate(fehlt="ca.crt")
    _ensure(sb)
    assert _beenden_runden(sb) == 1 and len(_starts(sb)) == 1


def test_uebergang_ohne_laufenden_server_startet_regulaer_ohne_umstellung(sb):
    sb.zertifikate()
    sb.laufend()                                              # nichts laeuft
    _ensure(sb)
    assert _beenden_runden(sb) == 0
    assert _warten(lambda: len(_starts(sb)) == 1)
    assert _starts(sb)[0].startswith("python serve.py")
    assert "Umstellung HTTP -> HTTPS" not in _ensure_log(sb)


def test_uebergang_ohne_laufenden_server_und_ohne_zertifikat_startet_uvicorn_mit_reload(sb):
    sb.laufend()
    _ensure(sb)
    assert _warten(lambda: len(_starts(sb)) == 1)
    start = _starts(sb)[0]
    assert "-m uvicorn app.main:app" in start and " --reload" in start


def test_uebergang_gescheitert_schreibt_warnung_und_versucht_nicht_erneut(sb):
    sb.http_offen()
    sb.zertifikate(ca="CA-A", crt="CRT-1")
    (sb.att / "ca_erwartet").write_bytes(b"CA-X")             # die Kette passt nie (fremde CA)

    # erster Lauf: ein Versuch, danach die Warnung mit den Pruefsummen
    _ensure(sb)
    assert _beenden_runden(sb) == 1 and len(_starts(sb)) == 1
    warnung = sb.warnung()
    assert warnung.is_file()
    text = warnung.read_text(encoding="utf-8")
    sha_crt = hashlib.sha256(b"CRT-1").hexdigest()
    sha_ca = hashlib.sha256(b"CA-A").hexdigest()
    assert f"server.crt sha256={sha_crt}" in text.splitlines()
    assert f"ca.crt sha256={sha_ca}" in text.splitlines()

    # weiterer Lauf mit denselben Dateien: kein weiterer Versuch, nur eine Logzeile
    lauf = _ensure(sb)
    _ensure(sb)
    assert _beenden_runden(sb) == 1 and len(_starts(sb)) == 1
    assert "schon einmal gescheitert" in _ensure_log(sb)

    # neue ca.crt -> wieder genau ein Versuch, neue Pruefsumme in der Warnung
    sb.zertifikate(ca="CA-B", crt="CRT-1")
    _ensure(sb)
    assert _beenden_runden(sb) == 2 and len(_starts(sb)) == 2
    text = warnung.read_text(encoding="utf-8")
    assert f"ca.crt sha256={hashlib.sha256(b'CA-B').hexdigest()}" in text.splitlines()
    assert sha_ca not in text

    # und wieder Ruhe, solange die Dateien gleich bleiben
    _ensure(sb)
    assert _beenden_runden(sb) == 2 and len(_starts(sb)) == 2


def test_neues_serverzertifikat_gibt_ebenfalls_einen_versuch_frei(sb):
    """Der Schleifenschutz hängt an server.crt UND ca.crt: ändert sich eine, gilt er nicht mehr."""
    sb.http_offen()
    sb.zertifikate(ca="CA-A", crt="CRT-1")
    (sb.att / "ca_erwartet").write_bytes(b"CA-X")             # die Kette passt nie
    assert sb.lauf("tls-umstellung.sh", "--abloesen").returncode == 4
    assert _beenden_runden(sb) == 1
    lauf = sb.lauf("tls-umstellung.sh", "--abloesen")          # gleiche Dateien: kein Versuch
    assert lauf.returncode == 0 and "schon einmal gescheitert" in lauf.stdout
    assert _beenden_runden(sb) == 1
    sb.zertifikate(ca="CA-A", crt="CRT-2")                    # nur das Serverzertifikat ist neu
    assert sb.lauf("tls-umstellung.sh", "--abloesen").returncode == 4
    assert _beenden_runden(sb) == 2


def test_uebergang_beenden_misslingt_dann_warnung_und_kein_start(sb):
    sb.http_offen()
    sb.zertifikate()
    (sb.att / "unsterblich").write_text("1")
    _ensure(sb)
    assert _starts(sb) == [], "ein Server, der nicht beendet werden konnte, wird nicht doppelt gestartet"
    assert sb.warnung().is_file()


def test_tls_umstellung_nur_beenden_startet_nicht(sb):
    sb.http_offen()
    sb.zertifikate()
    lauf = sb.lauf("tls-umstellung.sh", "--nur-beenden")
    assert lauf.returncode == 10, lauf.stdout + lauf.stderr
    assert _beenden_runden(sb) == 1 and _starts(sb) == []
    assert "Umstellung HTTP -> HTTPS" in lauf.stdout


def test_tls_umstellung_ohne_zertifikat_tut_nichts(sb):
    sb.http_offen()
    lauf = sb.lauf("tls-umstellung.sh", "--nur-beenden")
    assert lauf.returncode == 0
    assert _beenden_runden(sb) == 0


# ── neu-start-nach-lauf.sh laeuft echt ──────────────────────────────────────


def test_neustart_nach_lauf_nutzt_beenden_und_starten(sb):
    sb.http_offen()
    sb.zertifikate()
    lauf = sb.lauf("neu-start-nach-lauf.sh")
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert _beenden_runden(sb) >= 1
    gestartet = _starts(sb)
    assert len(gestartet) == 1 and gestartet[0].startswith("python serve.py")
    assert sb.aufrufe_mit("setsid python serve.py"), "--abloesen"
    assert "--reload" not in gestartet[0]
    assert sb.aufrufe_mit("pkill", "hermes_inbox_daemon.py"), "der Daemon wird weiter dort beendet"


def test_neustart_nach_lauf_ohne_zertifikat_startet_uvicorn_ohne_reload(sb):
    sb.http_offen()
    lauf = sb.lauf("neu-start-nach-lauf.sh")
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    (start,) = _starts(sb)
    assert "-m uvicorn app.main:app --host 0.0.0.0 --port 8080" in start
    assert "--reload" not in start


# ── Waechter: nur zwei Dateien starten/beenden den Server ──────────────────

ERLAUBT = {"backend-starten.sh", "backend-beenden.sh"}
STARTBEFEHL = re.compile(r"uvicorn|serve\.py")


def _code(text: str) -> str:
    """Skripttext ohne Kommentarzeilen (Reihenfolgen gelten fuer Befehle, nicht fuer Erklaertes)."""
    return "\n".join(z for z in text.splitlines() if not z.lstrip().startswith("#"))


def _skripte():
    for pfad in sorted(TERMUX.iterdir()):
        if pfad.is_file() and pfad.suffix in (".sh", ""):
            try:
                yield pfad, pfad.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
    yield START_TERMUX, _lies(START_TERMUX)


def test_waechter_nur_zwei_dateien_starten_oder_beenden_den_server():
    gelesen = 0
    for pfad, text in _skripte():
        gelesen += 1
        if pfad.name in ERLAUBT:
            continue
        for nr, zeile in enumerate(text.splitlines(), 1):
            if zeile.lstrip().startswith("#"):
                continue                                         # Kommentare ausgenommen
            assert not STARTBEFEHL.search(zeile), (
                f"{pfad.name}:{nr} startet/beendet den Server selbst: {zeile.strip()}")
    assert gelesen >= 10, "der Waechter hat die Skripte wirklich gefunden"


def test_waechter_beide_zentralen_skripte_sind_vorhanden_und_nutzen_die_muster():
    assert "python serve.py" in _lies(STARTEN) or "(python serve.py)" in _lies(STARTEN)
    assert "-m uvicorn app.main:app" in _lies(STARTEN)
    text = _lies(BEENDEN)
    for muster in ("uvicorn app.main:app", "python -m uvicorn", "serve"):
        assert muster in text


def test_waechter_keine_kommandozeile_mit_pkill_auf_server_ausserhalb():
    """Ausserhalb der zwei Dateien beendet kein pkill etwas anderes als den Inbox-Daemon,
    und kein ``kill -9/-TERM`` ist uebrig (``kill -0`` fuer 'lebt noch?' bleibt erlaubt)."""
    for pfad, text in _skripte():
        if pfad.name in ERLAUBT:
            continue
        for nr, zeile in enumerate(text.splitlines(), 1):
            if zeile.lstrip().startswith("#"):
                continue
            if re.search(r"pkill", zeile):
                assert "hermes_inbox_daemon.py" in zeile, f"{pfad.name}:{nr}: {zeile.strip()}"
            assert not re.search(r"(?<!p)kill\s+-(9|TERM|KILL|15)", zeile), (
                f"{pfad.name}:{nr}: {zeile.strip()}")


def test_waechter_alle_vier_startwege_rufen_die_zwei_skripte():
    ensure, widget = _lies(ENSURE), _lies(WIDGET)
    neustart, startt = _lies(NEUSTART), _lies(START_TERMUX)
    for name, text in (("agent-ensure.sh", ensure), ("agent-start", widget),
                       ("neu-start-nach-lauf.sh", neustart), ("start-termux.sh", startt)):
        assert "backend-starten.sh" in text, f"{name}: Start ueber backend-starten.sh"
        assert "tls-umstellung.sh" in text, f"{name}: ruft die Umstellung"
    for name, text in (("agent-start", widget), ("neu-start-nach-lauf.sh", neustart),
                       ("start-termux.sh", startt)):
        assert "backend-beenden.sh" in text, f"{name}: Stopp ueber backend-beenden.sh"
    # die Schalter der Aufrufer
    assert 'backend-starten.sh" --abloesen --reload' in ensure
    assert 'backend-starten.sh" --abloesen --log' in neustart and "--reload" not in re.search(
        r'backend-starten\.sh"[^\n]*', neustart).group(0)
    assert 'backend-starten.sh" --reload &' in startt
    assert re.search(r'backend-starten\.sh" &\n', widget)


def test_waechter_umstellung_steht_nach_der_vorbereitung_und_vor_dem_start():
    ensure = _code(_lies(ENSURE))
    vorb = ensure.index('bash "$PROJEKT/termux/start-vorbereiten.sh"')
    umst = ensure.index('bash "$PROJEKT/termux/tls-umstellung.sh"')
    ausstieg = ensure.index("Serverstart uebersprungen")
    start = ensure.index('bash "$PROJEKT/termux/backend-starten.sh"')
    assert vorb < umst < ausstieg < start, (
        "agent-ensure.sh: die Modusprufung steht VOR dem Ausstieg bei laufendem Server")
    widget = _code(_lies(WIDGET))
    assert widget.index('bash "$HIER/start-vorbereiten.sh"') < widget.index(
        'bash "$HIER/tls-umstellung.sh"') < widget.index('bash "$HIER/backend-starten.sh"')
    startt = _code(_lies(START_TERMUX))
    assert startt.index("backend-beenden.sh") < startt.index("tls-umstellung.sh") < startt.index(
        "backend-starten.sh")
    neustart = _code(_lies(NEUSTART))
    assert neustart.index("backend-beenden.sh") < neustart.index("tls-umstellung.sh") < neustart.index(
        "backend-starten.sh")


# ── Datei-Hygiene ───────────────────────────────────────────────────────────


def test_geaenderte_skripte_sind_syntaxgeprueft_und_reine_lf():
    bash = _bash()
    for pfad in GEAENDERT:
        roh = pfad.read_bytes()
        assert b"\r" not in roh, f"{pfad.name}: reine LF verlangt (kein CR)"
        assert roh.startswith(b"#!"), f"{pfad.name}: Shebang fehlt"
        ergebnis = subprocess.run([bash, "-n", _posix(pfad)], capture_output=True, text=True)
        assert ergebnis.returncode == 0, f"bash -n {pfad.name}: {ergebnis.stderr}"
