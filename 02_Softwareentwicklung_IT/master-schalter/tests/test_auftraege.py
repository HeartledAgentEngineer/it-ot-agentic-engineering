"""Tests für Aufträge an eine Claude-Code-Sitzung (v0.5.1): Ablage, Prüfung, Zustellung per Hook, CLI."""
from __future__ import annotations

import json
import subprocess

import pytest

from master_schalter import auftraege, claude_hook, cli, postfach, status

KENNUNG = "sitzung-4711"
THEMA = "engineering"
DATEI = ".hermes/plans/auftrag-test.md"


@pytest.fixture
def auftrag_datei(umgebung) -> str:
    pfad = umgebung.repo / DATEI
    pfad.parent.mkdir(parents=True)
    pfad.write_text("# Prüfauftrag\n", encoding="utf-8")
    return DATEI


def _ereignis(name: str, **extra: object) -> bytes:
    return json.dumps({"hook_event_name": name, "session_id": KENNUNG, **extra}).encode("utf-8")


def _hook(capsys, eingabe: bytes) -> str:
    assert claude_hook.main(eingabe) == 0
    ausgabe = capsys.readouterr()
    assert ausgabe.err == ""
    return ausgabe.out


def _offen() -> list[str]:
    ordner = auftraege.ordner(KENNUNG)
    return sorted(p.name for p in ordner.glob("*.json")) if ordner.is_dir() else []


# --- Ablage ------------------------------------------------------------------------------------

def test_einlegen_legt_genau_die_felder_ab_und_ist_idempotent(umgebung, auftrag_datei):
    auftrag_id, pfad = auftraege.einlegen(KENNUNG, THEMA, auftrag_datei, umgebung.repo, auftrag_id="a-1")

    assert auftrag_id == "a-1" and pfad.name == "a-1.json"
    inhalt = json.loads(pfad.read_text(encoding="utf-8"))
    assert set(inhalt) == auftraege.FELDER
    assert inhalt["datei"] == DATEI and inhalt["von"] == "codex"
    assert auftraege.einlegen(KENNUNG, THEMA, auftrag_datei, umgebung.repo, auftrag_id="a-1")[1] == pfad
    assert _offen() == ["a-1.json"]


def test_backslashes_werden_normalisiert(umgebung, auftrag_datei):
    assert auftraege.datei_pruefen(auftrag_datei.replace("/", "\\"), umgebung.repo) == DATEI


@pytest.mark.parametrize("datei, grund", [
    ("docs/auftrag.md", "unter `.hermes/`"),
    (".hermes/plans/auftrag.txt", "auf `.md`"),
    (".hermes/../README.md", "ohne `..`"),
    ("C:/Users/x/.hermes/a.md", "repo-relativer"),
    ("/.hermes/a.md", "repo-relativer"),
    (".hermes/plans/fehlt.md", "nicht gefunden"),
    ("", "fehlt"),
])
def test_unzulaessige_auftragsdatei_wird_abgewiesen(umgebung, auftrag_datei, datei, grund):
    with pytest.raises(auftraege.AuftragFehler, match=grund.replace(".", r"\.").replace("`", "`")):
        auftraege.einlegen(KENNUNG, THEMA, datei, umgebung.repo)
    assert _offen() == []


@pytest.mark.parametrize("kennung", ["../x", "a" * 81, "x\n", ""])
def test_unzulaessige_sitzungskennung(umgebung, auftrag_datei, kennung):
    with pytest.raises(auftraege.AuftragFehler):
        auftraege.einlegen(kennung, THEMA, auftrag_datei, umgebung.repo)


def test_unzulaessiger_absender_und_thema(umgebung, auftrag_datei):
    with pytest.raises(auftraege.AuftragFehler, match="Absender"):
        auftraege.einlegen(KENNUNG, THEMA, auftrag_datei, umgebung.repo, von="claude")
    with pytest.raises(auftraege.AuftragFehler):
        auftraege.einlegen(KENNUNG, "Thema!", auftrag_datei, umgebung.repo)


def test_basis_folgt_master_schalter_repo(umgebung):
    assert auftraege.basis() == umgebung.repo


def test_basis_findet_hauptarbeitsbaum_aus_einem_worktree(tmp_path, monkeypatch):
    haupt = tmp_path / "haupt"
    haupt.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=haupt, check=True)
    (haupt / ".hermes").mkdir()
    (haupt / "x.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "add", "x.txt"], cwd=haupt, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"], cwd=haupt, check=True)
    neben = tmp_path / "neben"
    subprocess.run(["git", "worktree", "add", "-q", str(neben)], cwd=haupt, check=True)
    modulordner = neben / "src" / "master_schalter"
    modulordner.mkdir(parents=True)
    monkeypatch.delenv("MASTER_SCHALTER_REPO", raising=False)
    monkeypatch.setattr(auftraege, "__file__", str(modulordner / "auftraege.py"))

    assert auftraege.basis().resolve() == haupt.resolve()


# --- Vormerken und Bestätigen --------------------------------------------------------------------

def test_vormerken_verschiebt_nichts_bestaetigen_nach_erledigt(umgebung, auftrag_datei):
    auftraege.einlegen(KENNUNG, THEMA, auftrag_datei, umgebung.repo, auftrag_id="a-1")

    vorgemerkt = auftraege.vormerken(KENNUNG, umgebung.repo)

    assert [v.auftrag for v in vorgemerkt] == ["a-1"] and _offen() == ["a-1.json"]
    assert "`.hermes/plans/auftrag-test-ergebnis-a-1.md`" in vorgemerkt[0].text
    assert auftraege.LAEUFT in vorgemerkt[0].text
    assert auftraege.bestaetigen(vorgemerkt) == ["a-1"]
    assert _offen() == [] and (auftraege.ordner(KENNUNG) / "erledigt" / "a-1.json").exists()


def test_vorhandenes_ergebnis_verhindert_erneute_zustellung(umgebung, auftrag_datei):
    auftraege.einlegen(KENNUNG, THEMA, auftrag_datei, umgebung.repo, auftrag_id="a-1")
    (umgebung.repo / auftraege.ergebnis_pfad(DATEI, "a-1")).write_text("ERGEBNIS: LÄUFT (Auftrag a-1)\n", encoding="utf-8")

    assert auftraege.vormerken(KENNUNG, umgebung.repo) == []
    erledigt = json.loads((auftraege.ordner(KENNUNG) / "erledigt" / "a-1.json").read_text(encoding="utf-8"))
    assert erledigt["grund"].startswith("Ergebnis vorhanden")


def test_neuer_auftrag_zur_selben_datei_wird_trotz_altem_ergebnis_zugestellt(umgebung, auftrag_datei):
    auftraege.einlegen(KENNUNG, THEMA, auftrag_datei, umgebung.repo, auftrag_id="a-1")
    (umgebung.repo / auftraege.ergebnis_pfad(DATEI, "a-1")).write_text("ERGEBNIS: FERTIG\n", encoding="utf-8")
    auftraege.einlegen(KENNUNG, THEMA, auftrag_datei, umgebung.repo, auftrag_id="a-2")

    assert [v.auftrag for v in auftraege.vormerken(KENNUNG, umgebung.repo)] == ["a-2"]


def test_verknuepfter_hermes_ordner_ausserhalb_des_repos_wird_abgewiesen(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    aussen = tmp_path / "aussen"
    (aussen / "plans").mkdir(parents=True)
    (aussen / "plans" / "a.md").write_text("x", encoding="utf-8")
    try:
        (repo / ".hermes").symlink_to(aussen, target_is_directory=True)
    except OSError:
        pytest.skip("Verzeichnisverknüpfung auf diesem System nicht erlaubt")

    with pytest.raises(auftraege.AuftragFehler, match="Repo heraus"):
        auftraege.datei_pruefen(".hermes/plans/a.md", repo)


def test_verknuepfte_datei_ausserhalb_von_hermes_wird_abgewiesen(umgebung, auftrag_datei):
    ziel = umgebung.repo / "README.md"
    ziel.write_text("x", encoding="utf-8")
    try:
        (umgebung.repo / ".hermes" / "plans" / "link.md").symlink_to(ziel)
    except OSError:
        pytest.skip("Dateiverknüpfung auf diesem System nicht erlaubt")

    with pytest.raises(auftraege.AuftragFehler, match="heraus"):
        auftraege.datei_pruefen(".hermes/plans/link.md", umgebung.repo)


def test_geaenderte_datei_wird_nicht_bestaetigt(umgebung, auftrag_datei):
    _, pfad = auftraege.einlegen(KENNUNG, THEMA, auftrag_datei, umgebung.repo, auftrag_id="a-1")
    vorgemerkt = auftraege.vormerken(KENNUNG, umgebung.repo)
    roh = json.loads(pfad.read_text(encoding="utf-8"))
    pfad.write_text(json.dumps({**roh, "zeit": "anders"}), encoding="utf-8")

    assert auftraege.bestaetigen(vorgemerkt) == [] and _offen() == ["a-1.json"]


def test_kaputte_und_fremde_dateien_wandern_nach_verworfen(umgebung, auftrag_datei):
    ordner = auftraege.ordner(KENNUNG)
    ordner.mkdir(parents=True)
    (ordner / "kaputt.json").write_text("{", encoding="utf-8")
    (ordner / "falsch.json").write_text(json.dumps({"auftrag": "anders", "thema": THEMA, "von": "codex",
                                                     "datei": DATEI, "zeit": "x"}), encoding="utf-8")

    assert auftraege.vormerken(KENNUNG, umgebung.repo) == []
    assert sorted(p.name for p in (ordner / "verworfen").glob("*.json")) == ["falsch.json", "kaputt.json"]


def test_verschwundene_auftragsdatei_wird_verworfen(umgebung, auftrag_datei):
    auftraege.einlegen(KENNUNG, THEMA, auftrag_datei, umgebung.repo, auftrag_id="a-1")
    (umgebung.repo / DATEI).rename(umgebung.repo / ".hermes/plans/woanders.md")

    assert auftraege.vormerken(KENNUNG, umgebung.repo) == []
    assert (auftraege.ordner(KENNUNG) / "verworfen" / "a-1.json").exists()


# --- Hook --------------------------------------------------------------------------------------

@pytest.mark.parametrize("ereignis", ["UserPromptSubmit", "PostToolUse"])
def test_hook_stellt_auftrag_als_zusatzkontext_zu(umgebung, auftrag_datei, capsys, ereignis):
    auftraege.einlegen(KENNUNG, THEMA, auftrag_datei, umgebung.repo, auftrag_id="a-1")

    daten = json.loads(_hook(capsys, _ereignis(ereignis)))

    kontext = daten["hookSpecificOutput"]["additionalContext"]
    assert kontext.split("\n")[0] == claude_hook.EINLEITUNG and "Auftrag a-1" in kontext
    assert KENNUNG not in kontext
    assert _offen() == []


def test_hook_stop_blockiert_einmal_und_haelt_status_arbeitet(umgebung, auftrag_datei, capsys):
    auftraege.einlegen(KENNUNG, THEMA, auftrag_datei, umgebung.repo, auftrag_id="a-1")

    daten = json.loads(_hook(capsys, _ereignis("Stop")))

    assert set(daten) == {"decision", "reason"} and daten["decision"] == "block"
    assert "Auftrag a-1" in daten["reason"]
    assert _offen() == []
    assert status.lesen("claude", KENNUNG)[0] == status.ARBEITET
    assert _hook(capsys, _ereignis("Stop")) == ""                             # nichts mehr offen: kein Block
    assert status.lesen("claude", KENNUNG)[0] == status.RUHT


def test_hook_stop_blockiert_nicht_bei_aktivem_stop_hook(umgebung, auftrag_datei, capsys):
    auftraege.einlegen(KENNUNG, THEMA, auftrag_datei, umgebung.repo, auftrag_id="a-1")

    assert _hook(capsys, _ereignis("Stop", stop_hook_active=True)) == ""

    assert _offen() == ["a-1.json"]                                           # bleibt für das nächste Ereignis
    assert status.lesen("claude", KENNUNG)[0] == status.RUHT


def test_hook_stop_ohne_auftrag_bleibt_still(umgebung, capsys):
    assert _hook(capsys, _ereignis("Stop")) == ""


def test_hook_fehler_in_auftraegen_verhindert_postfach_nicht(umgebung, auftrag_datei, capsys, monkeypatch):
    def kaputt(*_a, **_k):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(auftraege, "vormerken", kaputt)
    auftraege.einlegen(KENNUNG, THEMA, auftrag_datei, umgebung.repo, auftrag_id="a-1")

    assert _hook(capsys, _ereignis("PostToolUse")) == ""
    assert _hook(capsys, _ereignis("Stop")) == ""
    assert _offen() == ["a-1.json"]


def test_postfach_ordner_wird_von_auftraegen_nicht_beruehrt(umgebung, auftrag_datei, capsys):
    auftraege.einlegen(KENNUNG, THEMA, auftrag_datei, umgebung.repo, auftrag_id="a-1")
    _hook(capsys, _ereignis("PostToolUse"))

    assert not postfach.ordner("claude", KENNUNG).exists()


# --- CLI ---------------------------------------------------------------------------------------

def test_cli_claude_auftrag_legt_ab_und_nennt_ergebnis(umgebung, auftrag_datei, capsys):
    assert cli.main(["claude-auftrag", "--sitzung", KENNUNG, "--thema", THEMA, "--datei", DATEI]) == 0

    ausgabe = capsys.readouterr().out
    assert "abgelegt" in ausgabe and "auftrag-test-ergebnis-a-" in ausgabe
    assert len(_offen()) == 1


def test_cli_claude_auftrag_unzulaessig_exit_2(umgebung, capsys):
    assert cli.main(["claude-auftrag", "--sitzung", KENNUNG, "--thema", THEMA, "--datei", "docs/x.md"]) == 2
    assert "Auftrag nicht abgelegt" in capsys.readouterr().err


def test_cli_claude_sitzungen_listet_status(umgebung, capsys):
    assert cli.main(["claude-sitzungen"]) == 0
    assert "Keine Claude-Sitzung" in capsys.readouterr().out

    status.schreiben("claude", KENNUNG, status.RUHT, "Stop")
    assert cli.main(["claude-sitzungen"]) == 0
    assert f"{KENNUNG} · ruht" in capsys.readouterr().out
