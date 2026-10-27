"""Tests für `masterwechsel kurz` (Kurzübersicht für den Chat)."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from master_schalter import besitz, cli, kurz, modi, paare, status
from master_schalter.signale import Fenster, Kontingent

UTC = timezone.utc
JETZT = datetime(2026, 10, 27, 20, 0, tzinfo=UTC)
THREAD = "00000000-0000-4000-8000-0000000000b2"


def _k(name: str, fuenf: float | None, woche: float | None, *, reset_fuenf: datetime | None = None,
       zurueck: bool = False, fehler: str | None = None) -> Kontingent:
    if fehler:
        return Kontingent(name, fehler=fehler)
    return Kontingent(name, (Fenster("5h", fuenf, reset_fuenf or JETZT + timedelta(hours=2), zurueck),
                             Fenster("Woche", woche, JETZT + timedelta(days=3))), JETZT - timedelta(minutes=5))


def _zeilen(kontingente=None, themen=(), sitzungen=(), automatik=True, schwelle=95):
    return kurz.zeilen(kontingente or [_k("Claude", 10, 20), _k("Codex", 10, 20)], list(themen), list(sitzungen),
                       schwelle=schwelle, automatik_global=automatik, jetzt=JETZT, zone=UTC)


def _thema(name: str = "t1", master: str = "kontingent", worker: str = "workflow", modell: str | None = None,
           besitzer: str | None = "claude", aktiv: bool | None = True) -> kurz.Thema:
    return kurz.Thema(name, modi.Profil(master, worker, modell), besitzer, aktiv)


def test_rest_statt_verbrauch():
    assert kurz.rest(76) == 24
    assert kurz.rest(130) == 0 and kurz.rest(-5) == 100
    text = "\n".join(_zeilen([_k("Claude", 76, 51), _k("Codex", 10, 20)]))
    assert "Claude: 5h 24 % (Reset 22:00) · Woche 49 %" in text


def test_fenster_nach_reset_und_messfehler_sind_unbekannt():
    text = "\n".join(_zeilen([_k("Claude", 0.0, 20, zurueck=True), _k("Codex", None, None, fehler="Messung alt")]))
    assert "Claude: 5h neu, nicht gemessen" in text
    assert "Codex: unbekannt (Messung alt)" in text
    assert "Als Nächstes: jetzt Claude neu messen" in text


def test_lage_unbekannt_zeigt_keine_besetzung():
    zeilen = _zeilen([_k("Claude", 0.0, 20, zurueck=True), _k("Codex", 10, 20)])
    assert zeilen[0].endswith("Lage ? · Automatik an")
    matrix = next(z for z in zeilen if z.startswith("Matrix:"))
    assert matrix.startswith("Matrix: Lage unbekannt – Claude 5h nach Reset")
    assert "Planer" not in matrix


def test_lage_bekannt_zeigt_matrix_ohne_klammern():
    zeilen = _zeilen([_k("Claude", 10, 20), _k("Codex", 99, 20)])
    assert zeilen[0].startswith("Master-Schalter · 20:00 · Lage 2B")
    assert ("Matrix: Planer Claude Opus 5.5 · Prüfer DeepSeek V4.1 Flash · "
            "Ausführer Claude Sonnet 5.5 / DeepSeek V4.1 Flash") in zeilen


def test_automatik_wirksam_nur_mit_kontingent_master_aktivem_paar_und_global_an():
    themen = [_thema("a"), _thema("b", master="hermes"), _thema("c", aktiv=False), _thema("d", aktiv=None)]
    text = "\n".join(_zeilen(themen=themen))
    assert "a: Master nach Kontingent (Besitz claude) · Ausführer Workflow · Auto an" in text
    assert "b: Master Hermes (Besitz claude) · Ausführer Workflow · Auto aus (fester Master)" in text
    assert "c: Master nach Kontingent (Besitz claude) · Ausführer Workflow · Auto aus" in text
    assert "d: Master nach Kontingent (Besitz claude) · Ausführer Workflow · kein Paar" in text
    aus = "\n".join(_zeilen(themen=[_thema("a")], automatik=False))
    assert "a: Master nach Kontingent (Besitz claude) · Ausführer Workflow · Auto aus" in aus


def test_unbekannter_besitz_und_modell():
    text = "\n".join(_zeilen(themen=[_thema(worker="codex", modell="gpt-6-luna", besitzer=None)]))
    assert "t1: Master nach Kontingent (Besitz unbekannt) · Ausführer Codex gpt-6-luna · Auto an" in text


def test_als_naechstes_waehlt_fruehesten_reset_im_limit():
    kontingente = [_k("Claude", 99, 20, reset_fuenf=JETZT + timedelta(hours=3)),
                   _k("Codex", 100, 20, reset_fuenf=JETZT + timedelta(hours=1))]
    assert "Als Nächstes: 21:00 Codex 5h wieder frei (Reset, danach neu messen)" in _zeilen(kontingente)
    assert "Als Nächstes: kein Limitwechsel absehbar" in _zeilen()


def test_sitzungen_hoechstens_drei_gekuerzt_und_veraltetes_arbeitet_markiert():
    sitzungen = [kurz.Sitzung("claude", f"{i}abcdefghijklmnop", status.ARBEITET, JETZT - timedelta(minutes=10 * i))
                 for i in range(5)]
    sitzungen.append(kurz.Sitzung("claude", "altaltaltalt", status.ARBEITET, JETZT - timedelta(hours=11)))
    zeilen = [z for z in _zeilen(sitzungen=sitzungen) if z.startswith("Sitzung ")]
    ohne = "Thema nicht zugeordnet"
    assert zeilen == [f"Sitzung Claude 0abcdefg · {ohne} · arbeitet · 20:00",
                      f"Sitzung Claude 1abcdefg · {ohne} · arbeitet · 19:50",
                      f"Sitzung Claude 2abcdefg · {ohne} · arbeitet · 19:40"]
    alt = _zeilen(sitzungen=[sitzungen[-1]])
    assert f"Sitzung Claude altaltal · {ohne} · arbeitet? (veraltet) · 09:00" in alt
    mit = _zeilen(sitzungen=[kurz.Sitzung("claude", "abcdefghij", status.RUHT, JETZT, "portfolio")])
    assert "Sitzung Claude abcdefgh · portfolio · ruht · 20:00" in mit


def test_zeilenzahl_und_ehrliche_wartezeile():
    themen = [_thema(f"t{i}") for i in range(6)]
    sitzungen = [kurz.Sitzung("claude", f"s{i}", status.RUHT, JETZT) for i in range(3)]
    zeilen = _zeilen(themen=themen, sitzungen=sitzungen)
    # Kopf, „Rest:“, 2 Limits, Matrix, „Themen:“, 6 Themen, 3 Sitzungen, Als Nächstes, Wartet = 17
    assert len(zeilen) == 17
    assert zeilen[-1] == kurz.WARTET == "Wartet worauf: noch keine Statusquelle"
    assert "Sitzungen: keine gemeldet" in _zeilen()


def _umgebung(tmp_path: Path, monkeypatch) -> Path:
    daten = tmp_path / "daten"
    daten.mkdir()
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    paare.setzen("thema-a", THREAD, paare.laufend_bilden("thema-a"), aktiv=True)
    besitz.schreiben(besitz.pfad(repo, paare.laufend_bilden("thema-a")), "hermes 2026-10-27T20:00:00+00:00 modus x")
    status.schreiben("claude", "eins-sitzung", status.RUHT, "Stop")
    status.schreiben("claude", "zwei-sitzung", status.RUHT, "Stop")
    (daten / "zuordnung.json").write_text('{"claude:eins-sitzung": "thema-a"}', encoding="utf-8")
    return repo


def test_sammeln_liest_echte_quellen_ohne_uuid(tmp_path, monkeypatch):
    _umgebung(tmp_path, monkeypatch)
    text = "\n".join(kurz.sammeln())
    assert "thema-a: Master nach Kontingent (Besitz hermes)" in text
    assert "Sitzung Claude eins-sit · thema-a · ruht" in text
    assert "Sitzung Claude zwei-sit · Thema nicht zugeordnet · ruht" in text
    assert THREAD not in text and str(tmp_path) not in text


def test_sammeln_liest_nur(tmp_path, monkeypatch):
    repo = _umgebung(tmp_path, monkeypatch)
    vorher = sorted((p, p.stat().st_mtime_ns) for p in tmp_path.rglob("*") if p.is_file())
    kurz.sammeln()
    nachher = sorted((p, p.stat().st_mtime_ns) for p in tmp_path.rglob("*") if p.is_file())
    assert vorher == nachher and (repo / ".git").is_dir()


def test_cli_kurz_schreibt_utf8_ueber_pipe(tmp_path, monkeypatch):
    _umgebung(tmp_path, monkeypatch)
    quelle = Path(cli.__file__).resolve().parents[1]
    lauf = subprocess.run([sys.executable, "-c",
                           "import sys; from master_schalter import cli; sys.exit(cli.main(['kurz']))"],
                          capture_output=True, timeout=60, cwd=str(quelle),
                          env={**os.environ, "PYTHONIOENCODING": "", "PYTHONUTF8": "0"})
    assert lauf.returncode == 0, lauf.stderr
    text = lauf.stdout.decode("utf-8")      # kein UnicodeDecodeError
    assert "Als Nächstes:" in text and "Ausführer" in text
