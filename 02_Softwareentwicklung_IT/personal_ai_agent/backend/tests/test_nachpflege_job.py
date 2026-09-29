"""Waechter-Tests fuer den Termux-Nachtjob der Archiv-Index-Nachpflege (N23).

Alles OHNE Netz, ohne Kabel, ohne echtes Handy: geprueft werden die beiden
neuen Termux-Skripte und der neue Block in ``start-termux.sh`` als Text (bzw.
per ``bash -n`` als Syntaxpruefung). Es wird nichts ausgefuehrt, was das Handy
beschreiben koennte.

Die 12 Punkte des Auftrags ``docs/auftrag-n23-handy-scheduler.md``:

 1. Beide Skripte existieren, sind nicht leer, haben den Termux-Bash-Shebang.
 2. Verbotene Muster fehlen (kein ``rm -rf``, kein ``deletefile``/``deletefolder``,
    kein ``shutil.rmtree``/``os.remove``, kein Daten-``curl``/``wget``).
 3. Der Job ruft genau ``backend/scripts/archiv_nachpflege.py`` mit
    ``--schreiben``; der Rueckfall ohne ``--mit-vektoren`` (Exit 3) ist da.
 4. Sperre + Wake-Lock + Log-Kuerzung sind vorhanden (``mkdir``,
    ``termux-wake-lock``, ``tail -n 500``).
 5. Der Job schreibt die Berichtsdatei in den Diagnose-Ordner; der Name enthaelt
    ``nachpflege_letzte.txt``.
 6. ``start-termux.sh`` ruft das Einricht-Skript mit ``|| true`` auf — nach dem
    ``git fetch`` und nach dem Index-Block.
 7. ``start-termux.sh`` erwaehnt kein ``--force`` und kein ``rm -rf``.
 8. Waechter gegen Auseinanderlaufen: derselbe Indexname (``archiv_index.db``)
    in Job und Startskript; die Einrichtung nennt ``nachpflege-job.sh`` und die
    Datei existiert.
 9. Die Einrichtung hat eine feste ``JOB_ID`` (Zahl), prueft vorher ``--list``
    und nutzt ``--period-ms 86400000``.
10. Kein Geheimnis-Muster in den Skripten (``sk-``, ``Bearer ``, Ziffernfolgen
    ab 30 Stellen); ``PCLOUD_TOKEN=`` zusaetzlich in den beiden NEUEN Skripten.
    (In ``start-termux.sh`` kommt ``PCLOUD_TOKEN=`` bewusst vor: das ist der
    Variablenname der bestehenden ``.env``-Uebernahme, kein Schluesselwert.)
11. Kein echter Personen-, Orts- oder Ereignisname in den neuen Dateien.
12. ``bash -n`` auf alle drei Skripte (nur wenn ``bash`` vorhanden, sonst skip).

**Nur erfundene/kunstliche Kennungen** — echte Namen, Orte, Nummern und
Schluesselwerte kommen hier nicht vor.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_nachpflege_job.py -q
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
JOB = REPO / "termux" / "nachpflege-job.sh"
EINRICHTEN = REPO / "termux" / "nachpflege-einrichten.sh"
STARTTERMUX = REPO / "start-termux.sh"

SHEBANG = "#!/data/data/com.termux/files/usr/bin/bash"

# Namen, die im Repo nichts zu suchen haben (Personen/Ort/Produkt einer echten
# Umgebung). Nur zur Absicherung — die neuen Dateien nennen bewusst niemanden.
VERBOTENE_NAMEN = ("Sebastian", "sebas", "Motorola", "Termux-Nutzer")


def _text(pfad: Path) -> str:
    assert pfad.is_file(), f"Datei fehlt: {pfad}"
    return pfad.read_text(encoding="utf-8")


def _zeilen(pfad: Path) -> int:
    return len(_text(pfad).splitlines())


def _befehle(text: str) -> list:
    """Befehlszeilen zusammenfassen: Fortsetzungen mit ``\\`` aneinanderhaengen.

    Kommentarzeilen werden uebersprungen. So laesst sich ein mehrzeiliger
    Aufruf als EIN Befehl pruefen, ohne vom Zeilenumbruch abzuhaengen.
    """
    befehle: list = []
    puffer: list = []
    for zeile in text.splitlines():
        if zeile.lstrip().startswith("#"):
            continue
        puffer.append(zeile.rstrip())
        if not zeile.rstrip().endswith("\\"):
            if puffer:
                befehle.append(" ".join(puffer))
                puffer = []
    if puffer:
        befehle.append(" ".join(puffer))
    return befehle


def _ohne_kommentare(text: str) -> str:
    """Nur die Code-Zeilen (ohne ``#``-Kommentare) — fuer Reihenfolge-Pruefungen.

    Sonst wuerde z. B. ein Schalter, der in der Kopfzeile erklaert wird, eine
    spaetere Code-Stelle vortaeuschen.
    """
    return "\n".join(z for z in text.splitlines()
                     if not z.lstrip().startswith("#"))


def _werkzeug_aufrufe(text: str) -> list:
    """Nur die Befehle, die das Nachpflege-Werkzeug per python aufrufen."""
    return [b for b in _befehle(text)
            if "archiv_nachpflege.py" in b and "python" in b]


# ── 1. Existenz, Inhalt, Shebang ──────────────────────────────────────────────

def test_punkt1_beide_skripte_existieren_und_sind_nicht_leer():
    for pfad in (JOB, EINRICHTEN):
        assert pfad.is_file(), f"fehlt: {pfad}"
        assert _zeilen(pfad) > 20, f"zu kurz: {pfad}"


def test_punkt1_beide_skripte_haben_den_termux_bash_shebang():
    for pfad in (JOB, EINRICHTEN):
        erste = _text(pfad).splitlines()[0]
        assert erste == SHEBANG, f"falscher Shebang in {pfad}: {erste!r}"


# ── 2. Verbotene Muster fehlen ────────────────────────────────────────────────

def test_punkt2_keine_verbotenen_muster_in_beiden_skripten():
    verboten = ("rm -rf", "deletefile", "deletefolder", "shutil.rmtree",
                "os.remove", "curl -X POST", "curl -X PUT", "curl -X DELETE",
                "wget")
    for pfad in (JOB, EINRICHTEN):
        text = _text(pfad)
        for muster in verboten:
            assert muster not in text, f"{muster!r} in {pfad.name} verboten"


def test_punkt2_kein_curl_oder_upload_ueberhaupt():
    for pfad in (JOB, EINRICHTEN):
        text = _text(pfad).lower()
        for muster in ("curl ", "wget ", "scp ", "rsync ", "pcloud", "upload"):
            assert muster not in text, f"{muster!r} in {pfad.name} verboten"


# ── 3. Werkzeugaufruf mit Rueckfall ohne Vektoren ─────────────────────────────

def test_punkt3_job_ruft_genau_das_nachpflege_werkzeug():
    aufrufe = _werkzeug_aufrufe(_text(JOB))
    assert len(aufrufe) == 2, f"erwartet 2 Aufrufe, gefunden {len(aufrufe)}"
    for befehl in aufrufe:
        assert "backend/scripts/archiv_nachpflege.py" in befehl


def test_punkt3_beide_aufrufe_schreiben():
    for befehl in _werkzeug_aufrufe(_text(JOB)):
        assert "--schreiben" in befehl, f"ohne --schreiben: {befehl}"


def test_punkt3_genau_ein_aufruf_mit_vektoren_und_der_rueckfall_ohne():
    aufrufe = _werkzeug_aufrufe(_text(JOB))
    mit = [b for b in aufrufe if "--mit-vektoren" in b]
    ohne = [b for b in aufrufe if "--mit-vektoren" not in b]
    assert len(mit) == 1, "genau ein Aufruf mit --mit-vektoren"
    assert len(ohne) == 1, "genau ein Rueckfall ohne --mit-vektoren"
    # Reihenfolge: zuerst mit Vektoren, der Rueckfall danach.
    assert aufrufe.index(mit[0]) < aufrufe.index(ohne[0])


def test_punkt3_rueckfall_haengt_an_exit_3():
    text = _text(JOB)
    assert '"$rc" = "3"' in text, "Rueckfall muss an Exit 3 geknuepft sein"
    assert "Exit 3" in text
    assert "--quelle-db" in text and "--index" in text


# ── 4. Sperre, Wake-Lock, Log-Kuerzung ────────────────────────────────────────

def test_punkt4_sperre_wakelock_logkuerzung_vorhanden():
    text = _text(JOB)
    assert "mkdir" in text, "Sperre per mkdir fehlt"
    assert ".nachpflege.lock" in text, "Sperrdatei fehlt"
    assert "termux-wake-lock" in text, "Wake-Lock fehlt"
    assert "tail -n 500" in text, "Log-Kuerzung (letzte 500 Zeilen) fehlt"


def test_punkt4_doppellauf_ergibt_exit_0_ohne_arbeit():
    text = _text(JOB)
    # Belegter Lock -> eine Zeile ins Log und exit 0 (kein Fehler).
    assert "laeuft schon" in text
    assert "rm -f \"$LOCK/zeit\"" in text, "veraltete Sperre ohne rm -rf loesen"


# ── 5. Berichtsdatei im Diagnose-Ordner ───────────────────────────────────────

def test_punkt5_bericht_im_diagnose_ordner():
    text = _text(JOB)
    assert "hermes_diag" in text
    assert "nachpflege_letzte.txt" in text
    assert "/sdcard/Download" in text, "Rueckfall auf den freigegebenen Ordner fehlt"


def test_punkt5_bericht_hat_kopfzeile_und_letzte_50_zeilen():
    text = _text(JOB)
    assert "nachpflege_bericht" in text
    assert "index_mb=" in text and "exit=" in text and "quelle=" in text
    assert "tail -n 50" in text, "die letzten 50 Log-Zeilen gehoeren in den Bericht"


# ── 6. Startskript: Einricht-Aufruf mit || true an der richtigen Stelle ───────

def test_punkt6_startskript_ruft_einricht_mit_oder_true():
    text = _text(STARTTERMUX)
    assert 'bash "$PROJEKT/termux/nachpflege-einrichten.sh" || true' in text


def test_punkt6_aufruf_steht_nach_git_fetch_und_index_block():
    text = _text(STARTTERMUX)
    stelle = text.index("nachpflege-einrichten.sh")
    assert text.index("git fetch") < stelle, "Aufruf muss nach dem Git-Abgleich stehen"
    assert text.index("Archiv-Index übernehmen") < stelle, \
        "Aufruf muss nach dem Index-Block stehen"


def test_punkt6_block_verhindert_den_serverstart_nicht():
    """Der Einricht-Aufruf steht im Skript VOR dem Serverstart und mit || true."""
    text = _text(STARTTERMUX)
    assert text.index("nachpflege-einrichten.sh") < text.index("── Server startet")


# ── 7. Startskript: kein --force, kein rm -rf ─────────────────────────────────

def test_punkt7_startskript_ohne_force_und_ohne_rm_rf():
    text = _text(STARTTERMUX)
    assert "--force" not in text
    assert "rm -rf" not in text


# ── 8. Waechter gegen Auseinanderlaufen ───────────────────────────────────────

def test_punkt8_gleicher_indexname_in_job_und_startskript():
    assert "archiv_index.db" in _text(JOB)
    assert "archiv_index.db" in _text(STARTTERMUX)


def test_punkt8_einrichtung_nennt_den_existierenden_jobnamen():
    text = _text(EINRICHTEN)
    assert "nachpflege-job.sh" in text
    assert JOB.is_file(), "der genannte Jobname muss existieren"


def test_punkt8_der_job_nennt_denselben_lock_und_berichtsnamen():
    text = _text(JOB)
    assert ".nachpflege.lock" in text
    assert "nachpflege_letzte.txt" in text


# ── 9. Feste JOB_ID, Idempotenz-Pruefung, Periodendauer ───────────────────────

def test_punkt9_feste_job_id_ist_eine_zahl():
    text = _text(EINRICHTEN)
    treffer = re.search(r"^JOB_ID=(\d+)\s*$", text, re.MULTILINE)
    assert treffer is not None, "feste JOB_ID (Zahl) fehlt"
    assert len(treffer.group(1)) >= 3


def test_punkt9_prueft_vorher_die_liste_zur_idempotenz():
    text = _text(EINRICHTEN)
    assert "--list" in text
    assert "schon eingerichtet" in text
    code = _ohne_kommentare(text)
    assert code.index("--period-ms 86400000") > code.index("--list"), \
        "erst fragen (--list), dann einrichten"


def test_punkt9_taegliche_periode_und_persisted_geprueft():
    text = _text(EINRICHTEN)
    assert "--period-ms 86400000" in text
    assert "--persisted" in text
    # Nicht unterstuetzte Schalter werden zur Laufzeit geprueft, nicht geraten.
    assert "--help" in text


def test_punkt9_crond_rueckfall_und_ehrlicher_exit_4():
    text = _text(EINRICHTEN)
    assert "crond" in text
    assert "crontabs" in text, "termux-services-Layout des Crontab fehlt"
    assert "exit 4" in text


# ── 10. Kein Geheimnis-Muster ─────────────────────────────────────────────────

def _ziffernfolge(text: str) -> bool:
    return re.search(r"\d{30,}", text) is not None


def test_punkt10_keine_schluessel_muster_in_allen_drei_skripten():
    for pfad in (JOB, EINRICHTEN, STARTTERMUX):
        text = _text(pfad)
        assert "Bearer " not in text, f"'Bearer ' in {pfad.name} verboten"
        # Ein echter Schluessel ist 'sk-' plus eine lange Zeichenkette; die
        # kurze Buchstabenfolge 'sk-' allein kommt z. B. in 'Task-Menü' vor und
        # ist kein Geheimnis.
        assert re.search(r"sk-[A-Za-z0-9-]{20,}", text) is None, \
            f"Schluessel-Muster in {pfad.name} verboten"
        assert not _ziffernfolge(text), f"lange Ziffernfolge in {pfad.name} verboten"


def test_punkt10_kein_token_muster_in_den_neuen_skripten():
    for pfad in (JOB, EINRICHTEN):
        assert "PCLOUD_TOKEN=" not in _text(pfad)
        assert "API_KEY" not in _text(pfad)


# ── 11. Keine echten Namen/Orte/Ereignisse ────────────────────────────────────

def test_punkt11_keine_echten_namen_in_den_neuen_dateien():
    # Nur die neuen Skripte werden geprueft; diese Testdatei selbst traegt die
    # Namensliste in ihrer Prueflogik und kann sich nicht selbst ausschliessen.
    for pfad in (JOB, EINRICHTEN):
        text = _text(pfad)
        for name in VERBOTENE_NAMEN:
            assert name not in text, f"{name!r} darf nicht vorkommen ({pfad.name})"


def test_punkt11_keine_mailadresse_oder_rufnummer():
    for pfad in (JOB, EINRICHTEN):
        text = _text(pfad)
        assert "@" not in text, "keine Mailadresse/Herkunft in den Skripten"
        # Rufnummernartige Muster: Laendervorwahl oder Zifferngruppen mit
        # Trennzeichen (reine Zeit-/Groessenangaben wie 1048576 bleiben erlaubt).
        assert "+49" not in text and "+1 " not in text
        assert re.search(r"\d{2,4}[ /-]\d{2,4}[ /-]\d{2,}", text) is None



# ── 12. Syntaxpruefung mit bash -n ────────────────────────────────────────────

def test_punkt12_bash_syntaxpruefung():
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash nicht vorhanden")
    for pfad in (JOB, EINRICHTEN, STARTTERMUX):
        ziel = str(pfad).replace("\\", "/")
        ergebnis = subprocess.run([bash, "-n", ziel],
                                  capture_output=True, text=True)
        assert ergebnis.returncode == 0, \
            f"bash -n scheiterte in {pfad.name}:\n{ergebnis.stderr}"
