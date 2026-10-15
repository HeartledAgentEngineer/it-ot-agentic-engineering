"""Tests für das Übergabepaket – Git per Attrappe, Repo ist ein Ordner unter tmp_path."""
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from master_schalter import uebergabe

JETZT = datetime(2026, 10, 14, 21, 50, 7, tzinfo=timezone.utc)
GEHEIM = "GEHEIMER-DATEIINHALT-NICHT-UEBERNEHMEN"


def _attrappe(log="abc1234 feat: eins\ndef5678 fix: zwei\n", status=" M src/a.py\n?? neu.txt\n"):
    def git(repo, args):
        if args[0] == "log":
            return log
        if args[0] == "status":
            return status
        raise AssertionError(args)
    return git


def _plan(repo: Path, name: str, zeilen: list[str], mtime: float) -> Path:
    datei = repo / ".hermes" / "plans" / name
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    os.utime(datei, (mtime, mtime))
    return datei


@pytest.fixture
def repo(tmp_path):
    ordner = tmp_path / "repo"
    (ordner / ".git").mkdir(parents=True)
    return ordner


def _paket(repo, **kw):
    kw.setdefault("git", _attrappe())
    return uebergabe.paket_bauen("claude", "codex", kw.pop("hinweis", None), repo=repo, jetzt=JETZT, **kw)


def test_dateiname_und_ort(repo):
    pfad = _paket(repo)
    assert pfad == repo / ".hermes" / "uebergabe" / "2026-10-14_215007_masterwechsel-claude-codex.md"
    assert pfad.is_file()


def test_paket_hat_alle_vier_abschnitte(repo):
    text = _paket(repo, hinweis="Nicht anfassen: serve.py").read_text(encoding="utf-8")
    for abschnitt in ("## Stand", "## Offen", "## Plan", "## Hinweise"):
        assert abschnitt in text
    assert "abc1234 feat: eins" in text and "def5678 fix: zwei" in text
    assert "M src/a.py" in text and "?? neu.txt" in text
    assert "Nicht anfassen: serve.py" in text


def test_hinweis_leer_zeigt_strich(repo):
    text = _paket(repo, hinweis=None).read_text(encoding="utf-8")
    assert text.split("## Hinweise", 1)[1].strip().splitlines()[0] == "—"


def test_name_kollidiert_nie_zweimal_gleiche_sekunde(repo):
    erst, zweit, dritt = _paket(repo), _paket(repo), _paket(repo)
    assert erst.name.endswith("masterwechsel-claude-codex.md")
    assert zweit.name.endswith("masterwechsel-claude-codex-2.md")
    assert dritt.name.endswith("masterwechsel-claude-codex-3.md")
    assert len({erst, zweit, dritt}) == 3


def test_vorhandenes_paket_wird_nie_ueberschrieben(repo):
    ziel = repo / ".hermes" / "uebergabe"
    ziel.mkdir(parents=True)
    (ziel / "2026-10-14_215007_masterwechsel-claude-codex.md").write_text("ALT", encoding="utf-8")
    neu = _paket(repo)
    assert neu.name.endswith("-2.md")
    assert (ziel / "2026-10-14_215007_masterwechsel-claude-codex.md").read_text(encoding="utf-8") == "ALT"


def test_ohne_git_wird_trotzdem_geschrieben(repo):
    def kaputt(repo, args):
        raise OSError("git fehlt")

    text = _paket(repo, git=kaputt).read_text(encoding="utf-8")
    assert "git nicht lesbar" in text
    assert "## Stand" in text and "## Hinweise" in text


def test_git_rueckgabe_ungleich_null_ist_nicht_lesbar(repo):
    def fehler(repo, args):
        raise uebergabe.GitFehler("rc 128")

    assert "git nicht lesbar" in _paket(repo, git=fehler).read_text(encoding="utf-8")


def test_plan_positivliste_nur_markierte_erscheinen(repo):
    _plan(repo, "technisch.md", ["# Plan A", "", "Einordnung: technisch (reiner Code)", GEHEIM], 1_000_000)
    _plan(repo, "ohne.md", ["# Plan B", GEHEIM], 1_000_100)
    _plan(repo, "sensibel.md", ["# Plan C", "Einordnung sensibel: Lebenslauf", GEHEIM], 1_000_200)
    _plan(repo, "fett.md", ["# Plan D", "**Einordnung:** technisch", GEHEIM], 1_000_300)
    _plan(repo, "sensibel2.md", ["# Plan E", "Einordnung: sensibel", GEHEIM], 1_000_400)
    spaet = ["zeile"] * 20 + ["Einordnung: technisch"]   # erst Zeile 21
    _plan(repo, "spaet.md", spaet, 1_000_500)

    text = _paket(repo).read_text(encoding="utf-8")

    assert ".hermes/plans/technisch.md" in text
    for nicht in ("ohne.md", "sensibel.md", "fett.md", "sensibel2.md", "spaet.md"):
        assert nicht not in text
    assert "5 weitere Pläne nicht aufgeführt – nicht als technisch eingeordnet" in text


def test_marker_in_zeile_20_zaehlt_zeile_21_nicht(repo):
    _plan(repo, "z20.md", ["zeile"] * 19 + ["Einordnung: technisch"], 1_000_000)
    _plan(repo, "z21.md", ["zeile"] * 20 + ["Einordnung: technisch"], 1_000_100)
    text = _paket(repo).read_text(encoding="utf-8")
    assert "z20.md" in text and "z21.md" not in text


def test_kein_dateiinhalt_im_paket(repo):
    _plan(repo, "technisch.md", ["# Plan A", "Einordnung: technisch", GEHEIM], 1_000_000)
    _plan(repo, "ohne.md", ["# Plan B", GEHEIM], 1_000_100)
    (repo / "geheim.txt").write_text(GEHEIM, encoding="utf-8")
    text = _paket(repo).read_text(encoding="utf-8")
    assert GEHEIM not in text
    assert "# Plan A" not in text


def test_hoechstens_drei_plaene_neueste_zuerst_und_plan_abschnitt(repo):
    for i in range(5):
        _plan(repo, f"p{i}.md", ["Einordnung: technisch"], 1_000_000 + i * 100)
    text = _paket(repo).read_text(encoding="utf-8")
    offen = text.split("## Offen", 1)[1].split("## Plan", 1)[0]
    assert offen.index("p4.md") < offen.index("p3.md") < offen.index("p2.md")
    assert "p1.md" not in offen and "p0.md" not in offen
    assert "2 ältere technische Pläne nicht aufgeführt" in offen
    plan = text.split("## Plan", 1)[1].split("## Hinweise", 1)[0]
    assert ".hermes/plans/p4.md" in plan


def test_ohne_plaene(repo):
    text = _paket(repo).read_text(encoding="utf-8")
    assert "## Plan" in text
    assert "kein technisch eingeordneter Plan" in text


def test_archivpfade_werden_nie_aufgefuehrt(repo):
    status = " M normal.py\n?? Chats von GPT, GEMINI, Claude/Takeout/alles.json\n"
    text = _paket(repo, git=_attrappe(status=status)).read_text(encoding="utf-8")
    assert "Chats von GPT" not in text
    assert "normal.py" in text
    assert "1 Pfad aus gesperrtem Archivordner nicht aufgeführt" in text


def test_lange_statusliste_wird_gekuerzt(repo):
    status = "".join(f" M datei{i}.py\n" for i in range(80))
    text = _paket(repo, git=_attrappe(status=status)).read_text(encoding="utf-8")
    assert "datei0.py" in text and "datei79.py" not in text
    assert "30 weitere" in text


def test_repo_wurzel_aus_umgebung(monkeypatch, tmp_path):
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(tmp_path))
    assert uebergabe.repo_wurzel() == tmp_path


def test_repo_wurzel_umgebung_kein_ordner_ist_fehler(monkeypatch, tmp_path):
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(tmp_path / "gibt-es-nicht"))
    with pytest.raises(uebergabe.UebergabeFehler):
        uebergabe.repo_wurzel()


def test_repo_wurzel_sucht_ab_quelldatei_nach_oben(monkeypatch, tmp_path):
    monkeypatch.delenv("MASTER_SCHALTER_REPO", raising=False)
    (tmp_path / "w" / ".git").mkdir(parents=True)
    quelle = tmp_path / "w" / "a" / "b" / "uebergabe.py"
    assert uebergabe.repo_wurzel(quelle) == tmp_path / "w"


def test_repo_wurzel_git_als_datei_zaehlt(monkeypatch, tmp_path):
    monkeypatch.delenv("MASTER_SCHALTER_REPO", raising=False)
    (tmp_path / "w").mkdir()
    (tmp_path / "w" / ".git").write_text("gitdir: x", encoding="utf-8")
    assert uebergabe.repo_wurzel(tmp_path / "w" / "q" / "x.py") == tmp_path / "w"


def test_ohne_wurzel_fehler_repo_nicht_gefunden(monkeypatch, tmp_path):
    monkeypatch.delenv("MASTER_SCHALTER_REPO", raising=False)
    # Ein Ordner ohne .git in allen Eltern lässt sich nicht garantieren – daher die Suche gezielt leer laufen lassen.
    monkeypatch.setattr(uebergabe, "_hat_git", lambda ordner: False)
    with pytest.raises(uebergabe.UebergabeFehler, match="Repo nicht gefunden"):
        uebergabe.repo_wurzel(tmp_path / "x" / "y.py")


def test_schreibfehler_wird_zu_uebergabefehler(repo, monkeypatch):
    (repo / ".hermes").write_text("ich bin eine Datei, kein Ordner", encoding="utf-8")
    with pytest.raises(uebergabe.UebergabeFehler):
        _paket(repo)
