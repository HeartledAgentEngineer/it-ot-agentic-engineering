"""Waechter-Tests fuer den Belegstand beim Rundenstart (N24c).

Alles OHNE Netz, ohne Kabel, ohne echtes Handy: geprueft wird das neue
PC-Werkzeug ``tools/handy/belegstand.py`` (als Text **und** im Lauf gegen eine
**Attrappen-adb** — ein kleines Bash-Skript unter ``tmp_path``, Muster aus
``test_belegweg_handy.py``). Es wird nichts an ein echtes Geraet geschickt und
nichts aus dem Netz geladen.

Die Regelgruppen des Auftrags ``docs/auftrag-n24c-belegstand.md``:

 1. ``spiegel_lesen`` ohne Ordner -> ``vorhanden False``, kein Werfen; mit zwei
    erfundenen Dateien stimmen Namen und Groessen.
 2. ``letzter_tipp``: gueltige Kopfzeile -> ISO-Text; fehlende/falsche -> ``""``.
 3. ``belegstand`` ohne Geraet -> ``kein_geraet``, ``job_1901_belegt=unbekannt``,
    ``fehler is None``, kein Werfen; mit Geraet + Spiegel -> ``ja``/``nein``/
    ``unbekannt``; die Felder sind immer dieselben. **Nachtrag:** Geraet am
    Kabel, aber ``hermes_diag/`` fehlt -> ``geraet_ordner_fehlt`` (an der rohen
    adb-Ausgabe unterschieden), unbrauchbare Meldung -> ``unbekannt``.
 4. ``journal_zeile`` ist **eine** Zeile, enthaelt alle drei Felder, und bei
    fehlender Angabe steht ``kein_geraet`` / ``nicht_vorhanden`` / ``unbekannt``.
 5. ``merken``: erster Aufruf schreibt, zweiter gleicher Aufruf schreibt nicht
    (Datei-Inhalt byte-gleich), andere Zeile schreibt; IM Repo -> ``ValueError``.
 6. CLI: ``--spiegel`` IM Repo -> Exit 2, nichts geschrieben; ``--ohne-kabel``
    ruft ``adb`` **nie** auf (Attrappe legt bei Aufruf eine Markierungsdatei an
    — die bleibt aus); letzte Ausgabezeile ist die Journal-Zeile.
 7. Datenschutz: keine Loeschfunktion, kein ``rm``, kein ``--force``, kein HTTP,
    kein pCloud; Schreiben **nur** nach ``--merken`` und **nie** ins Repo.
 8. Keine echten Namen/Nummern in den neuen Dateien; kein Schluesselmuster.

**Nur erfundene/kunstliche Kennungen** — echte Namen, Orte, Nummern und
Schluesselwerte kommen hier nicht vor (ausser in der Waechter-Liste, die genau
das prueft).

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_belegstand_handy.py -q
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "handy" / "belegstand.py"

# Der Geraete-Ordner, den die Attrappen-adb kennt (wie im Auftrag).
ORDNER_GERAET = "/sdcard/Download/hermes_diag"

# Der Dateiname der Markierung: entsteht NUR, wenn die Attrappen-adb wirklich
# aufgerufen wurde. So ist „adb nie aufgerufen" beweisbar.
MERKER_NAME = "adb-wurde-gerufen"

# Namen, die in einer ECHTEN Umgebung vorkommen und in NEUEN Dateien nichts zu
# suchen haben. Wortgleich aus ``test_belegweg_handy.py:65`` uebernommen — die
# Liste *ist* der Waechter.
VERBOTENE_NAMEN = ("Sebastian", "sebas", "Motorola", "Termux-Nutzer")


# ── Laden und kleine Helfer ───────────────────────────────────────────────

def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


bs = _laden(WERKZEUG, "belegstand")


def _text(pfad: Path) -> str:
    assert pfad.is_file(), f"Datei fehlt: {pfad}"
    return pfad.read_text(encoding="utf-8")


def _lauf(argv: list):
    """``main`` aufrufen und Exit-Code + Ausgabe einsammeln (ohne echten adb)."""
    import io
    import contextlib
    puffer = io.StringIO()
    fehler = io.StringIO()
    with contextlib.redirect_stdout(puffer), contextlib.redirect_stderr(fehler):
        code = bs.main(argv)
    return code, puffer.getvalue(), fehler.getvalue()


def _als_programm(skript: Path):
    """Ein Bash-Skript startbar machen — auf POSIX direkt, sonst per ``.cmd``.

    Auf Windows kann ein Bash-Skript nicht direkt ausgefuehrt werden (kein
    Win32-Programm); dort entsteht daneben ein kleiner ``.cmd``-Umweg, der
    denselben Bash-Aufruf macht.
    """
    bash = shutil.which("bash")
    assert bash, "bash wird fuer die Attrappen-adb gebraucht"
    if os.name != "nt":
        skript.chmod(0o755)
        return str(skript)
    umweg = skript.parent / (skript.name + ".cmd")
    umweg.write_text(
        "@echo off\r\n"
        f'"{bash}" "%~dp0{skript.name}" %*\r\n',
        encoding="ascii")
    return str(umweg)


def _attrappen_adb(tmp_path: Path):
    """Attrappen-``adb`` mit Geraet: feste Liste, kein echtes Geraet, kein Netz.

    Legt bei **jedem** Aufruf die Markierungsdatei ``adb-wurde-gerufen`` an —
    so kann ein Test beweisen, dass ``--ohne-kabel`` ``adb`` gar nicht aufruft.
    """
    skript = tmp_path / "attrappe-adb"
    skript.write_text(
        "#!/usr/bin/env bash\n"
        "# Attrappen-adb fuer die Tests: feste Antworten, kein echtes Geraet,\n"
        "# kein Netz. Nur erfundene Inhalte.\n"
        "set -u\n"
        f"MERKER=\"$(dirname \"$0\")/{MERKER_NAME}\"\n"
        ": > \"$MERKER\"\n"
        "case \"${1:-}\" in\n"
        "  shell)\n"
        "    printf 'total 4\\n'\n"
        "    printf -- '-rw-rw---- 1 u0_a1 u0_a1 42 2026-09-29 03:00 "
        "job_liste.txt\\n'\n"
        "    exit 0\n"
        "    ;;\n"
        "esac\n"
        "exit 2\n",
        encoding="utf-8")
    return _als_programm(skript)


def _attrappen_adb_ohne_geraet(tmp_path: Path):
    """Attrappen-``adb`` ohne Geraet: meldet ehrlich 'no devices', Exit 1."""
    skript = tmp_path / "attrappe-adb-ohne"
    skript.write_text(
        "#!/usr/bin/env bash\n"
        "# Attrappen-adb ohne Kabel: nur die ehrliche Meldung, kein Geraet.\n"
        "set -u\n"
        "echo 'adb: no devices/emulators found' >&2\n"
        "exit 1\n",
        encoding="utf-8")
    return _als_programm(skript)


def _attrappen_adb_ordner_fehlt(tmp_path: Path):
    """Attrappen-``adb`` mit Geraet, aber fehlendem Ordner ``hermes_diag/``.

    Genau der Zustand direkt nach dem Bau von N24b: das Geraet haengt am Kabel,
    aber den Geraete-Ordner gibt es noch nicht. ``ls`` meldet ehrlich
    ``No such file or directory`` und endet mit Fehlercode — daraus muss
    ``geraet_ordner_fehlt`` werden, **nicht** ``kein_geraet``.
    """
    skript = tmp_path / "attrappe-adb-ordner-fehlt"
    skript.write_text(
        f"""#!/usr/bin/env bash
# Attrappen-adb: Geraet da, aber der Ordner fehlt (nur erfundene Texte).
set -u
echo 'ls: {ORDNER_GERAET}: No such file or directory' >&2
exit 1
""",
        encoding="utf-8")
    return _als_programm(skript)


def _attrappen_adb_andere_meldung(tmp_path: Path):
    """Attrappen-``adb`` mit unbekannter Meldung: weder Geraet noch Ordner-Aussage.

    Eine solche Ausgabe darf **nicht** gedeutet werden — es bleibt ehrlich
    ``unbekannt``.
    """
    skript = tmp_path / "attrappe-adb-andere"
    skript.write_text(
        """#!/usr/bin/env bash
# Attrappen-adb mit unbrauchbarer Meldung (nur erfundene Texte).
set -u
echo 'adb: irgendein unerwarteter Fehler' >&2
exit 1
""",
        encoding="utf-8")
    return _als_programm(skript)


def _spiegel_bauen(tmp_path: Path, gefunden=None):
    """Einen lokalen Spiegel mit ``job_liste.txt`` bauen (nur erfundene Inhalte).

    ``gefunden`` ist ``None`` (Zeile fehlt), ``"ja"``, ``"nein"`` oder
    ``"unbekannt"``. Die Kopfzeile hat die Form ``beleg job-liste <ISO>``.
    """
    ordner = tmp_path / "spiegel"
    ordner.mkdir(exist_ok=True)
    zeilen = ["beleg job-liste 2026-09-29T03:00:00+02:00",
              "JOB_ID_ERWARTET=1901"]
    if gefunden is not None:
        zeilen.append(f"JOB_ID_GEFUNDEN={gefunden}")
    (ordner / "job_liste.txt").write_text("\n".join(zeilen) + "\n",
                                          encoding="utf-8")
    return ordner


# ── 1. spiegel_lesen ───────────────────────────────────────────────────────

def test_spiegel_lesen_ohne_ordner_ist_kein_fehler(tmp_path):
    fehlt = tmp_path / "gibt_es_nicht"
    for eingabe in (str(fehlt), "", None):
        stand = bs.spiegel_lesen(eingabe)            # darf nicht werfen
        assert stand["vorhanden"] is False
        assert stand["dateien"] == []
        assert stand["job_liste_vorhanden"] is False


def test_spiegel_lesen_zwei_dateien_mit_groessen(tmp_path):
    ordner = tmp_path / "spiegel"
    ordner.mkdir()
    inhalt_job = "beleg job-liste 2026-09-29T03:00:00+02:00\n"
    inhalt_rest = "nur eine erfundene Zeile\n"
    (ordner / "job_liste.txt").write_bytes(inhalt_job.encode("utf-8"))
    (ordner / "nachpflege_letzte.txt").write_bytes(inhalt_rest.encode("utf-8"))

    stand = bs.spiegel_lesen(str(ordner))
    assert stand["vorhanden"] is True
    assert stand["job_liste_vorhanden"] is True
    namen = {d["name"]: d["groesse"] for d in stand["dateien"]}
    assert namen == {
        "job_liste.txt": len(inhalt_job.encode("utf-8")),
        "nachpflege_letzte.txt": len(inhalt_rest.encode("utf-8")),
    }


# ── 2. letzter_tipp ───────────────────────────────────────────────────────

def test_letzter_tipp_gueltige_kopfzeile():
    inhalt = ("beleg job-liste 2026-09-29T03:00:00+02:00\n"
              "JOB_ID_ERWARTET=1901\n"
              "JOB_ID_GEFUNDEN=ja\n")
    assert bs.letzter_tipp(inhalt) == "2026-09-29T03:00:00+02:00"


def test_letzter_tipp_falsche_oder_fehlende_kopfzeile():
    assert bs.letzter_tipp("Kopf fehlt hier\nJOB_ID_GEFUNDEN=ja\n") == ""
    assert bs.letzter_tipp("beleg andere-art 2026-09-29T03:00:00\n") == ""
    assert bs.letzter_tipp("") == ""
    assert bs.letzter_tipp(None) == ""


# ── 3. belegstand ─────────────────────────────────────────────────────────

def test_belegstand_ohne_geraet_ist_ehrlich(tmp_path):
    attrappe = _attrappen_adb_ohne_geraet(tmp_path)
    stand = bs.belegstand(adb=attrappe, ordner=ORDNER_GERAET,
                          spiegel=str(tmp_path / "leer"))     # darf nicht werfen
    assert stand["geraet"] == "kein_geraet"
    assert stand["job_1901_belegt"] == "unbekannt"
    assert stand["spiegel"] == "nicht_vorhanden"
    assert stand["fehler"] is None


def test_belegstand_job_beleg_ja_nein_unbekannt(tmp_path):
    attrappe = _attrappen_adb(tmp_path)
    faelle = {"ja": "ja", "nein": "nein", None: "unbekannt"}
    zaehler = 0
    for gefunden, erwartet in faelle.items():
        zaehler += 1
        ordner = tmp_path / f"spiegel_{zaehler}"
        ordner.mkdir()
        zeilen = ["beleg job-liste 2026-09-29T03:00:00+02:00"]
        if gefunden is not None:
            zeilen.append(f"JOB_ID_GEFUNDEN={gefunden}")
        (ordner / "job_liste.txt").write_text("\n".join(zeilen) + "\n",
                                              encoding="utf-8")
        stand = bs.belegstand(adb=attrappe, ordner=ORDNER_GERAET,
                              spiegel=str(ordner))
        assert stand["geraet"] == "verbunden", stand
        assert stand["job_liste"] == "vorhanden"
        assert stand["job_1901_belegt"] == erwartet, (gefunden, stand)


def test_belegstand_felder_sind_immer_gleich(tmp_path):
    attrappe = _attrappen_adb(tmp_path)
    erwartet = {"geraet", "device_ordner", "device_dateien", "spiegel",
                "job_liste", "job_1901_belegt", "letzter_tipp", "fehler"}
    ohne = bs.belegstand(adb=attrappe, ordner=ORDNER_GERAET,
                         spiegel=str(tmp_path / "leer"))
    mit = bs.belegstand(adb=attrappe, ordner=ORDNER_GERAET,
                        spiegel=str(_spiegel_bauen(tmp_path, "ja")))
    assert set(ohne) == erwartet
    assert set(mit) == erwartet


def test_geraete_lage_regel_aus_roher_ausgabe():
    # Reine Regel (Nachtrag): nur die rohe adb-Ausgabe entscheidet.
    assert bs.geraete_lage("adb: no devices/emulators found") == "kein_geraet"
    assert bs.geraete_lage("error: device not found") == "kein_geraet"
    assert bs.geraete_lage(
        "ls: /sdcard/Download/hermes_diag: No such file or directory"
    ) == "geraet_ordner_fehlt"
    assert bs.geraete_lage("No such file") == "geraet_ordner_fehlt"
    assert bs.geraete_lage("dieser Ordner does not exist") == "geraet_ordner_fehlt"
    assert bs.geraete_lage("irgendein anderer Text") == "unbekannt"
    assert bs.geraete_lage("") == "unbekannt"
    assert bs.geraete_lage(None) == "unbekannt"


def test_belegstand_geraet_ohne_ordner_ist_geraet_ordner_fehlt(tmp_path):
    # Geraet am Kabel, aber hermes_diag/ fehlt -> geraet_ordner_fehlt, NICHT kein_geraet.
    attrappe = _attrappen_adb_ordner_fehlt(tmp_path)
    stand = bs.belegstand(adb=attrappe, ordner=ORDNER_GERAET,
                          spiegel=str(tmp_path / "leer"))     # darf nicht werfen
    assert stand["geraet"] == "geraet_ordner_fehlt", stand
    assert stand["geraet"] != "kein_geraet"
    assert stand["job_1901_belegt"] == "unbekannt"
    assert stand["fehler"] is None


def test_belegstand_unbekannte_adb_meldung_bleibt_unbekannt(tmp_path):
    # Eine unbrauchbare Meldung wird nicht gedeutet: es bleibt ehrlich unbekannt.
    attrappe = _attrappen_adb_andere_meldung(tmp_path)
    stand = bs.belegstand(adb=attrappe, ordner=ORDNER_GERAET,
                          spiegel=str(tmp_path / "leer"))
    assert stand["geraet"] == "unbekannt", stand
    assert stand["fehler"] is None


# ── 4. journal_zeile ──────────────────────────────────────────────────────

def test_journal_zeile_ist_eine_zeile_mit_drei_feldern():
    zeile = bs.journal_zeile({"geraet": "verbunden", "spiegel": "vorhanden",
                              "job_1901_belegt": "ja"})
    assert len(zeile.splitlines()) == 1
    assert "\n" not in zeile
    assert zeile.startswith("Belegstand ")
    assert "Geraet=verbunden" in zeile
    assert "Spiegel=vorhanden" in zeile
    assert "job_1901_belegt=ja" in zeile


def test_journal_zeile_bei_fehlender_angabe():
    zeile = bs.journal_zeile({})
    assert len(zeile.splitlines()) == 1
    assert "Geraet=unbekannt" in zeile
    assert "Spiegel=nicht_vorhanden" in zeile
    assert "job_1901_belegt=unbekannt" in zeile
    leer = bs.journal_zeile({"geraet": "kein_geraet", "spiegel": "nicht_vorhanden",
                             "job_1901_belegt": "unbekannt"})
    assert "Geraet=kein_geraet" in leer
    assert "job_1901_belegt=unbekannt" in leer


# ── 5. merken (die einzige Schreibstelle, idempotent) ─────────────────────

def test_merken_schreibt_und_ist_idempotent(tmp_path):
    ziel = tmp_path / "belegstand.jsonl"
    zeile = ("Belegstand 29.09.2026: Geraet=verbunden | Spiegel=vorhanden | "
             "job_1901_belegt=ja")
    assert bs.merken(str(ziel), zeile) is True
    inhalt1 = ziel.read_bytes()
    # Zweiter gleicher Aufruf: nichts tun, Datei byte-gleich.
    assert bs.merken(str(ziel), zeile) is False
    assert ziel.read_bytes() == inhalt1
    # Eine andere Zeile wird angehaengt.
    zeile2 = ("Belegstand 29.09.2026: Geraet=kein_geraet | "
              "Spiegel=nicht_vorhanden | job_1901_belegt=unbekannt")
    assert bs.merken(str(ziel), zeile2) is True
    assert ziel.read_text(encoding="utf-8").splitlines()[-1] == zeile2


def test_merken_im_repo_wirft_und_schreibt_nichts(tmp_path):
    verboten = REPO / "belegstand_probe_verboten.jsonl"
    with pytest.raises(ValueError):
        bs.merken(str(verboten), "Belegstand 29.09.2026: Geraet=unbekannt | "
                                 "Spiegel=nicht_vorhanden | job_1901_belegt=unbekannt")
    assert not verboten.exists(), "IM Repo darf nichts entstehen"


# ── 6. Kommandozeile ──────────────────────────────────────────────────────

def test_cli_ohne_kabel_ruft_adb_nie_auf(tmp_path):
    attrappe = _attrappen_adb(tmp_path)
    spiegel = _spiegel_bauen(tmp_path, "ja")
    markierung = tmp_path / MERKER_NAME
    code, aus, _ = _lauf(["--ohne-kabel", "--adb", attrappe,
                          "--spiegel", str(spiegel)])
    assert code == 0, aus
    assert not markierung.exists(), "--ohne-kabel darf adb nie aufrufen"
    zeilen = [z for z in aus.splitlines() if z.strip()]
    assert zeilen[-1].startswith("Belegstand ")
    assert "Geraet=" in zeilen[-1] and "Spiegel=" in zeilen[-1]
    assert "job_1901_belegt=" in zeilen[-1]


def test_cli_spiegel_im_repo_gibt_exit_2(tmp_path):
    verboten = REPO / "handy_diag_probe_verboten"
    code, _, fehler = _lauf(["--ohne-kabel", "--spiegel", str(verboten)])
    assert code == 2, f"Repo-Spiegel muss Exit 2 geben (war {code})"
    assert "IM Repo" in fehler
    assert not verboten.exists()


# ── 7. Datenschutz / Waechter im Werkzeug ────────────────────────────────

def test_keine_loesch_und_schreibstellen_im_werkzeug():
    text = _text(WERKZEUG)
    for muster in ("os.remove", "os.rmdir", "shutil.rmtree", "unlink",
                   "--force", "urllib", "requests", "socket", "pcloud"):
        assert muster not in text, f"{muster!r} hat im Werkzeug nichts zu suchen"
    # Kein ``rm``-Aufruf — Wortgrenze, damit das deutsche Wort „Form“ nicht faelschlich zaehlt.
    assert re.search(r"(?<![A-Za-z0-9_])rm\s+\S", text) is None, \
        "ein rm-Aufruf ist im Werkzeug verboten"
    # Genau eine Schreibstelle: ``merken`` haengt an ("a"); sonst nur "r".
    assert text.count('open(pfad, "a"') == 1
    assert '"w"' not in text
    assert "_im_repo" in text, "Schutzpruefung fehlt"


# ── 8. Keine echten Namen / kein Schluesselwert ───────────────────────────

def test_keine_echten_namen_in_den_neuen_dateien():
    # Nur das Werkzeug wird geprueft: diese Testdatei enthaelt die Waechter-
    # Liste selbst (sie *ist* der Waechter).
    text = _text(WERKZEUG)
    for name in VERBOTENE_NAMEN:
        assert name not in text, f"{name!r} darf in belegstand.py nicht vorkommen"


def test_keine_geheimnismuster():
    verboten = "Bea" + "rer "                 # getrennt, sonst prueft sich der Test selbst
    for pfad in (WERKZEUG, Path(__file__)):
        text = _text(pfad)
        assert verboten not in text, f"Bearer-Muster in {pfad.name}"
        assert re.search(r"sk-[A-Za-z0-9-]{20,}", text) is None, \
            f"Schluessel-Muster in {pfad.name}"
        assert re.search(r"\d{30,}", text) is None, \
            f"lange Ziffernfolge in {pfad.name}"
