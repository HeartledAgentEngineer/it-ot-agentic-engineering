"""Waechter: EIN gemeinsamer Startweg fuer App-Knopf und Widget (10.10.2026).

Entscheidung Sebastian (10.10.2026): Der App-Knopf (de.sebastian.heyagent) ist
DER Weg zum Starten; das Widget bleibt funktionsfaehig, ist aber nicht mehr der
empfohlene Weg. Damit kein Schritt nur auf einer Seite laeuft (Befund: die
Wissensdatei-Uebernahme hing allein im Widget), rufen beide dieselbe Ablaufdatei
auf: ``termux/start-vorbereiten.sh`` (git pull -> Einrichtung -> Schluessel ->
Datendateien -> Wissensdatei -> Weckruf -> Sicherung auf Auftrag -> Daemon).

Zusaetzlich zu den Text-Waechtern laeuft der Ablauf hier ECHT in Git Bash in
einem Sandkasten (Attrappen-Schritte schreiben ihre Reihenfolge auf stdout) —
inklusive der Einrichtung (Bruecke ~/agent-ensure.sh, allow-external-apps).
Offline, nur erfundene Pfade; kein Netz, kein Geraet.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TERMUX = REPO / "termux"
SHARED = TERMUX / "start-vorbereiten.sh"
WIDGET = TERMUX / "agent-start"
APP = TERMUX / "agent-ensure.sh"
EINRICHTEN = TERMUX / "hey-agent-einrichten.sh"


def _lies(pfad: Path) -> str:
    return pfad.read_text(encoding="utf-8")


def _bash() -> str:
    bash = shutil.which("bash")
    if not bash or "system32" in bash.lower():
        pytest.skip("Git Bash nicht vorhanden")
    return bash


def _posix(pfad: Path) -> str:
    return str(pfad).replace("\\", "/")


def _kanonisch(pfad: Path) -> str:
    """Wie Git Bash den Pfad nach cd/pwd sieht (Windows: /c/... statt C:/...)."""
    return subprocess.run([_bash(), "-c", f'cd "{_posix(pfad)}" && pwd'],
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()


def _ohne_msys_konvertierung(umgebung: dict) -> dict:
    """Wie in test_wiederherstellung.py: die Hermes-Shell unterdrueckt die
    Uebersetzung von Unix- in Windows-Pfade; fuer den Lauf freigeben."""
    for _v in ("MSYS2_ARG_CONV_EXCL", "MSYS_NO_PATHCONV"):
        umgebung.pop(_v, None)
    return umgebung


# ── Beide Wege rufen dieselbe Ablaufdatei ────────────────────────────────────


def test_beide_wege_rufen_genau_eine_gemeinsame_ablaufdatei():
    for name, pfad in (("agent-start", WIDGET), ("agent-ensure.sh", APP)):
        text = _lies(pfad)
        aufrufe = [z for z in text.splitlines()
                   if "start-vorbereiten.sh" in z
                   and z.lstrip().startswith(("bash ", "sh "))]
        assert len(aufrufe) == 1, f"{name}: genau ein Aufruf der gemeinsamen Vorbereitung"
        assert aufrufe[0].rstrip().endswith("|| true"), (
            f"{name}: die Vorbereitung darf den Start nie verhindern")


def test_die_uebernahme_schritte_stehen_nur_noch_in_der_gemeinsamen_datei():
    """Kein Schritt doppelt: die App-/Widget-Dateien rufen nur die Ablaufdatei;
    die einzelnen Uebernahme-Skripte erscheinen dort nicht mehr als Aufruf."""
    schritte = (
        "pcloud-schluessel-uebernehmen.sh",
        "schluessel-uebernehmen.sh",
        "uebergabe_uebernehmen.py",
        "wissensdatei-uebernehmen.sh",
        "sicherung-auftrag.sh",
        "hey-agent-einrichten.sh",
    )
    for name, pfad in (("agent-start", WIDGET), ("agent-ensure.sh", APP)):
        for zeile in _lies(pfad).splitlines():
            if zeile.lstrip().startswith("#"):
                continue
            for schritt in schritte:
                assert schritt not in zeile, (
                    f"{name}: '{schritt}' gehoert in termux/start-vorbereiten.sh")


def test_reihenfolge_der_schritte_in_der_gemeinsamen_datei():
    text = _lies(SHARED)
    anker = [
        "if git pull --ff-only --quiet; then",
        'sh "$HIER/hey-agent-einrichten.sh"',
        'bash "$HIER/pcloud-schluessel-uebernehmen.sh"',
        'bash "$HIER/schluessel-uebernehmen.sh"',
        'python "$PROJEKT/tools/handy/uebergabe_uebernehmen.py"',
        'bash "$HIER/wissensdatei-uebernehmen.sh"',
        "command -v termux-wake-lock",
        'bash "$HIER/sicherung-auftrag.sh" || true',
        '_daemon_skript="hermes_inbox_daemon.py"',
    ]
    positionen = [text.index(a) for a in anker]
    assert positionen == sorted(positionen), (
        "Reihenfolge: Pull -> Einrichtung -> Schluessel -> Datendateien -> "
        "Wissensdatei -> Weckruf -> Sicherung -> Daemon")


def test_sicherung_laeuft_nur_ohne_laufend():
    """--laufend (App-Druck auf laufenden Server) schaltet NUR die Sicherung ab:
    aus dem laufenden Betrieb wird nicht gesichert, der Rest laeuft weiter."""
    text = _lies(SHARED)
    wache = text.index('if [ "$LAUFEND" != "1" ]; then')
    aufruf = text.index('bash "$HIER/sicherung-auftrag.sh" || true')
    ende = text.index("fi", aufruf)
    assert wache < aufruf < ende


def test_beide_wege_bereiten_vor_bevor_sie_den_server_starten():
    widget = _lies(WIDGET)
    app = _lies(APP)
    assert widget.index('bash "$HIER/start-vorbereiten.sh"') < \
        widget.index("python -m uvicorn app.main:app --host")
    assert app.index('bash "$PROJEKT/termux/start-vorbereiten.sh"') < \
        app.index("nohup python -m uvicorn app.main:app")
    # Der App-Weg schaltet bei laufendem Backend auf --laufend und beendet sich
    # dann OHNE Serverstart und OHNE Ruecksprung zur App; gekillt wird nie.
    assert 'if health_ok; then LAEUFT=1; else LAEUFT=0; fi' in app
    assert '_VORBEREITUNG_MODUS="--laufend"' in app
    assert app.index("Serverstart uebersprungen") < app.index("nohup python -m uvicorn app.main:app")
    assert app.rindex("heyagent://start") > app.index("nohup python -m uvicorn app.main:app")
    for verboten in ("pkill", "kill -9"):
        assert verboten not in app, f"der App-Weg beendet nichts: {verboten}"


# ── Der Ablauf laeuft ECHT (Git Bash, Sandkasten mit Attrappen) ─────────────


def _sandkasten(tmp_path: Path):
    """Projekt-Sandkasten: echte Ablaufdatei + Einrichtung, alle Schritte als
    Attrappen, die 'SCHRITT:<name>' auf stdout schreiben; python als Attrappe."""
    sb = tmp_path / "projekt"
    (sb / "termux").mkdir(parents=True)
    (sb / "backend").mkdir()
    (sb / "tools" / "handy").mkdir(parents=True)
    shutil.copy(SHARED, sb / "termux" / "start-vorbereiten.sh")
    shutil.copy(EINRICHTEN, sb / "termux" / "hey-agent-einrichten.sh")
    for name, marke in (
        ("pcloud-schluessel-uebernehmen.sh", "pcloud"),
        ("schluessel-uebernehmen.sh", "schluessel"),
        ("wissensdatei-uebernehmen.sh", "wissensdatei"),
        ("pcloud-uebernehmen.sh", "pclouduebergabe"),
        ("sicherung-auftrag.sh", "sicherung"),
    ):
        (sb / "termux" / name).write_bytes(
            f'#!/bin/sh\necho "SCHRITT:{marke}"\nexit 0\n'.encode())
    for stub in ("agent-start", "agent-ensure.sh"):
        (sb / "termux" / stub).write_bytes(b"#!/bin/sh\nexit 0\n")
    bin_ordner = tmp_path / "bin"
    bin_ordner.mkdir()
    (bin_ordner / "python").write_bytes(b'#!/bin/sh\necho "SCHRITT:daten"\nexit 0\n')
    return sb, bin_ordner


def _vorbereitung_umgebung(bin_ordner: Path, heim: Path, prefix: Path) -> dict:
    umgebung = dict(os.environ,
                    HOME=_posix(heim),
                    PREFIX=_posix(prefix),
                    PATH=_posix(bin_ordner) + os.pathsep + os.environ.get("PATH", ""))
    umgebung.pop("PROJEKT", None)
    return _ohne_msys_konvertierung(umgebung)


def _vorbereitung_lauf(sb: Path, umgebung: dict, *extra):
    return subprocess.run([_bash(), _posix(sb / "termux" / "start-vorbereiten.sh"), *extra],
                          env=umgebung, capture_output=True, text=True,
                          encoding="utf-8", timeout=120)


def _stellen(ausgabe: str, *marken: str):
    index = {m: ausgabe.index(m) for m in marken}
    assert [index[m] for m in marken] == sorted(index.values()), (
        "Reihenfolge im echten Lauf: " + ", ".join(marken))


def test_ablauf_laeuft_echt_und_haelt_die_reihenfolge(tmp_path):
    sb, bin_ordner = _sandkasten(tmp_path)
    heim, prefix = tmp_path / "heim", tmp_path / "prefix"
    heim.mkdir()
    (prefix / "etc").mkdir(parents=True)
    (prefix / "etc" / "profile").write_bytes(b"# liest profile.d/*.sh\n")
    umgebung = _vorbereitung_umgebung(bin_ordner, heim, prefix)
    lauf = _vorbereitung_lauf(sb, umgebung)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    # Kein Git-Repo im Sandkasten -> der Pull scheitert, der Ablauf laeuft TROTZDEM
    # weiter (das ist die Eigenschaft 'darf den Start nie verhindern').
    assert "git fetch fehlgeschlagen" in lauf.stdout
    _stellen(lauf.stdout, "git fetch fehlgeschlagen", "SCHRITT:pcloud", "SCHRITT:schluessel",
             "SCHRITT:daten", "SCHRITT:wissensdatei", "SCHRITT:pclouduebergabe", "SCHRITT:sicherung")
    # Einrichtung (echte Datei) hat Hook + Bruecke im Sandkasten-Heim angelegt.
    assert (heim / "agent-ensure.sh").is_file()
    assert (prefix / "etc" / "profile.d" / "hey-agent.sh").is_file()


def test_ablauf_mit_laufend_laesst_nur_die_sicherung_aus(tmp_path):
    sb, bin_ordner = _sandkasten(tmp_path)
    heim, prefix = tmp_path / "heim", tmp_path / "prefix"
    heim.mkdir()
    (prefix / "etc").mkdir(parents=True)
    (prefix / "etc" / "profile").write_bytes(b"# liest profile.d/*.sh\n")
    umgebung = _vorbereitung_umgebung(bin_ordner, heim, prefix)
    lauf = _vorbereitung_lauf(sb, umgebung, "--laufend")
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "SCHRITT:sicherung" not in lauf.stdout
    _stellen(lauf.stdout, "SCHRITT:pcloud", "SCHRITT:schluessel", "SCHRITT:daten",
             "SCHRITT:wissensdatei", "SCHRITT:pclouduebergabe")


# ── Einrichtung: Bruecke ~/agent-ensure.sh (keine veraltende Kopie) ─────────


def _einrichten_umgebung(heim: Path, prefix: Path, sb: Path) -> dict:
    umgebung = dict(os.environ, HOME=_posix(heim), PREFIX=_posix(prefix))
    umgebung.pop("PROJEKT", None)
    return _ohne_msys_konvertierung(umgebung)


def _einrichten_lauf(sb: Path, umgebung: dict):
    return subprocess.run([_bash(), _posix(sb / "termux" / "hey-agent-einrichten.sh")],
                          env=umgebung, capture_output=True, text=True,
                          encoding="utf-8", timeout=60)


def _projekt_sandkasten(tmp_path: Path) -> Path:
    sb, _ = _sandkasten(tmp_path)
    return sb


def test_einrichtung_sichert_die_alte_kopie_und_legt_die_bruecke_an(tmp_path):
    sb = _projekt_sandkasten(tmp_path)
    heim, prefix = tmp_path / "heim", tmp_path / "prefix"
    (prefix / "etc").mkdir(parents=True)
    (prefix / "etc" / "profile").write_bytes(b"# liest profile.d/*.sh\n")
    heim.mkdir()
    (heim / "agent-ensure.sh").write_bytes(b"# alte Kopie ohne Marke\nexit 0\n")
    umgebung = _einrichten_umgebung(heim, prefix, sb)
    lauf = _einrichten_lauf(sb, umgebung)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    sicherungen = sorted(heim.glob("agent-ensure.sh.vor_*"))
    assert len(sicherungen) == 1, "die alte Fassung wird gesichert, nie geloescht"
    assert "alte Kopie ohne Marke" in sicherungen[0].read_text(encoding="utf-8")
    bruecke = (heim / "agent-ensure.sh").read_text(encoding="utf-8")
    assert "duenne Weiterleitung auf den Projektordner" in bruecke
    assert "exec sh" in bruecke
    assert _kanonisch(sb) in bruecke, "der Projektpfad wird fest eingetragen"
    # Zweiter Lauf: Bruecke erkennt sich selbst -> keine zweite Sicherung.
    lauf2 = _einrichten_lauf(sb, umgebung)
    assert lauf2.returncode == 0
    assert len(sorted(heim.glob("agent-ensure.sh.vor_*"))) == 1


def test_bruecke_startet_das_projekt_skript_und_reicht_argumente_durch(tmp_path):
    sb = _projekt_sandkasten(tmp_path)
    (sb / "termux" / "agent-ensure.sh").write_bytes(
        b'#!/bin/sh\necho "STUB:agent-ensure $*"\nexit 0\n')
    heim, prefix = tmp_path / "heim", tmp_path / "prefix"
    heim.mkdir()
    (prefix / "etc").mkdir(parents=True)
    (prefix / "etc" / "profile").write_bytes(b"# liest profile.d/*.sh\n")
    umgebung = _einrichten_umgebung(heim, prefix, sb)
    assert _einrichten_lauf(sb, umgebung).returncode == 0
    lauf = subprocess.run([_bash(), _posix(heim / "agent-ensure.sh"), "--app-zurueck"],
                          env=umgebung, capture_output=True, text=True,
                          encoding="utf-8", timeout=60)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "STUB:agent-ensure --app-zurueck" in lauf.stdout


def test_bruecke_nimmt_projekt_aus_der_umgebung_und_meldet_wenn_nichts_da(tmp_path):
    sb = _projekt_sandkasten(tmp_path)
    heim, prefix = tmp_path / "heim", tmp_path / "prefix"
    heim.mkdir()
    (prefix / "etc").mkdir(parents=True)
    (prefix / "etc" / "profile").write_bytes(b"# liest profile.d/*.sh\n")
    umgebung = _einrichten_umgebung(heim, prefix, sb)
    assert _einrichten_lauf(sb, umgebung).returncode == 0

    # (a) PROJEKT aus der Umgebung hat Vorrang (funktioniert auch, wenn das
    # Projekt noch nie gepullt wurde - die Datei muss nur da sein).
    sb2 = _projekt_sandkasten(tmp_path / "zweite")
    (sb2 / "termux" / "agent-ensure.sh").write_bytes(
        b'#!/bin/sh\necho "STUB2:agent-ensure $*"\nexit 0\n')
    umgebung2 = dict(umgebung, PROJEKT=_posix(sb2))
    lauf = subprocess.run([_bash(), _posix(heim / "agent-ensure.sh")],
                          env=umgebung2, capture_output=True, text=True,
                          encoding="utf-8", timeout=60)
    assert "STUB2:agent-ensure" in lauf.stdout

    # (b) Weder Umgebung noch Projektordner da -> klare Meldung, Exit 1,
    # Zeile im Log (nie ein stiller Fehlschlag).
    bruecke_pfad = heim / "agent-ensure.sh"
    bruecke_pfad.write_bytes(bruecke_pfad.read_bytes().replace(
        _kanonisch(sb).encode(), b"/gibt/es/nicht"))
    lauf = subprocess.run([_bash(), _posix(bruecke_pfad)],
                          env=umgebung, capture_output=True, text=True,
                          encoding="utf-8", timeout=60)
    assert lauf.returncode == 1
    assert "fehlt" in lauf.stdout
    assert "BRUECKE" in (heim / "agent-ensure.log").read_text(encoding="utf-8")


def test_einrichtung_setzt_allow_external_apps_genau_einmal(tmp_path):
    sb = _projekt_sandkasten(tmp_path)
    heim, prefix = tmp_path / "heim", tmp_path / "prefix"
    (prefix / "etc").mkdir(parents=True)
    (prefix / "etc" / "profile").write_bytes(b"# liest profile.d/*.sh\n")
    heim.mkdir()
    props = heim / ".termux" / "termux.properties"
    props.parent.mkdir()
    props.write_bytes(b"# eigene Einstellung bleibt stehen\nextra-keys=ctrl-alt\n")
    umgebung = _einrichten_umgebung(heim, prefix, sb)
    lauf = _einrichten_lauf(sb, umgebung)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    inhalt = props.read_text(encoding="utf-8")
    assert inhalt.count("allow-external-apps=true") == 1
    assert "extra-keys=ctrl-alt" in inhalt, "nichts entfernt"
    assert "allow-external-apps=true gesetzt" in lauf.stdout
    # Zweiter Lauf dupliziert die Zeile nicht.
    assert _einrichten_lauf(sb, umgebung).returncode == 0
    assert props.read_text(encoding="utf-8").count("allow-external-apps=true") == 1


# ── Datei-Hygiene: Syntax + reine LF (CRLF bricht auf dem Handy) ────────────


def test_startdateien_sind_syntaxgeprueft_und_reine_lf():
    for pfad in (SHARED, WIDGET, APP, EINRICHTEN):
        roh = pfad.read_bytes()
        assert b"\r" not in roh, f"{pfad.name}: reine LF verlangt (kein CR)"
        assert roh.startswith(b"#!"), f"{pfad.name}: Shebang fehlt"
    bash = shutil.which("bash")
    if not bash or "system32" in bash.lower():
        pytest.skip("Git Bash nicht vorhanden")
    for pfad in (SHARED, WIDGET, APP, EINRICHTEN):
        ergebnis = subprocess.run([bash, "-n", _posix(pfad)], capture_output=True, text=True)
        assert ergebnis.returncode == 0, f"bash -n {pfad.name}: {ergebnis.stderr}"


def test_dokumentation_nennt_die_bruecke_statt_der_kopie():
    app_text = _lies(APP)
    assert "Weiterleitung" in app_text
    readme = _lies(REPO / "android" / "README.md")
    assert "Weiterleitung" in readme
    assert "hey-agent-einrichten.sh" in readme
    assert "cp <Repo>" not in readme, "die alte Kopieranweisung ist ersetzt"
    assert "allow-external-apps=true" in readme
