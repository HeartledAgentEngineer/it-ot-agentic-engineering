"""Tests für den Wechsel (Sperre → Paket → Zustand) und die CLI-Befehle `master` / `wechsel`."""
import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from master_schalter import cli, uebergabe, wechsel, zustand

JETZT = datetime(2026, 10, 14, 21, 50, 7, tzinfo=timezone.utc)


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    monkeypatch.setenv("MASTER_SCHALTER_CODEX_SESSIONS", str(tmp_path / "codex"))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    monkeypatch.setattr(uebergabe, "_git", lambda r, args: "abc1234 feat: x\n" if args[0] == "log" else " M a.py\n")
    return repo


def _pakete(repo):
    ordner = repo / ".hermes" / "uebergabe"
    return sorted(ordner.glob("*.md")) if ordner.is_dir() else []


def test_wechsel_schreibt_paket_und_zustand(umgebung):
    erg = wechsel.wechseln("codex", "Hinweis X", jetzt=JETZT)
    assert erg.art == "gewechselt" and erg.master == "codex"
    assert erg.paket in _pakete(umgebung)
    z = zustand.lesen()
    assert z.master == "codex"
    assert z.uebergabe == str(erg.paket)
    assert z.seit == JETZT.isoformat()
    assert "Hinweis X" in erg.paket.read_text(encoding="utf-8")


def test_dateiname_nennt_von_und_nach(umgebung):
    wechsel.wechseln("claude", jetzt=JETZT)
    erg = wechsel.wechseln("codex", jetzt=JETZT)
    assert erg.paket.name == "2026-10-14_215007_masterwechsel-claude-codex.md"


def test_wechsel_nach_hermes_schreibt_paket_und_zustand(umgebung):
    wechsel.wechseln("claude", jetzt=JETZT)
    erg = wechsel.wechseln("hermes", jetzt=JETZT)
    assert erg.art == "gewechselt" and erg.master == "hermes"
    assert erg.paket.name == "2026-10-14_215007_masterwechsel-claude-hermes.md"
    assert zustand.lesen().master == "hermes"


def test_erster_wechsel_ohne_vorherigen_master(umgebung):
    erg = wechsel.wechseln("claude", jetzt=JETZT)
    assert erg.paket.name == "2026-10-14_215007_masterwechsel-unbekannt-claude.md"
    assert zustand.lesen().master == "claude"


def test_gleicher_master_kein_paket_kein_schreiben(umgebung):
    wechsel.wechseln("codex", jetzt=JETZT)
    anzahl = len(_pakete(umgebung))
    zustand_vorher = zustand.lesen()
    erg = wechsel.wechseln("codex", jetzt=JETZT)
    assert erg.art == "gleich" and erg.paket is None
    assert len(_pakete(umgebung)) == anzahl
    assert zustand.lesen() == zustand_vorher


def test_sperr_zeitueberschreitung_kein_paket_zustand_unveraendert(umgebung):
    zustand.aendern(lambda z: replace(z, master="claude"))
    with zustand.sperre(frist=1.0):
        erg = wechsel.wechseln("codex", jetzt=JETZT, frist=0.2)
    assert erg.art == "fehler"
    assert "Sperre" in erg.meldung
    assert _pakete(umgebung) == []
    assert zustand.lesen().master == "claude"


def test_paketfehler_laesst_zustand_unveraendert(umgebung, monkeypatch):
    zustand.aendern(lambda z: replace(z, master="claude", uebergabe="alt.md"))

    def kaputt(*a, **k):
        raise uebergabe.UebergabeFehler("Platte voll")

    monkeypatch.setattr(uebergabe, "paket_bauen", kaputt)
    erg = wechsel.wechseln("codex", jetzt=JETZT)
    assert erg.art == "fehler" and "Platte voll" in erg.meldung
    z = zustand.lesen()
    assert (z.master, z.uebergabe) == ("claude", "alt.md")


def test_ohne_repo_wurzel_kein_wechsel(umgebung, monkeypatch):
    zustand.aendern(lambda z: replace(z, master="claude"))
    monkeypatch.delenv("MASTER_SCHALTER_REPO")
    monkeypatch.setattr(uebergabe, "_hat_git", lambda ordner: False)
    erg = wechsel.wechseln("codex", jetzt=JETZT)
    assert erg.art == "fehler" and "Repo nicht gefunden" in erg.meldung
    assert zustand.lesen().master == "claude"


def test_unbekannter_master_wird_abgelehnt(umgebung):
    with pytest.raises(ValueError):
        wechsel.wechseln("gemini")


# --- Themensperre und Entwertung (v0.3.0) -------------------------------------

THREAD = "01a12557-3bb3-7171-a021-53e6ac879534"


def _paar_setzen(thema="engineering", aktiv=True):
    from master_schalter import paare
    paare.setzen(thema, THREAD, paare.laufend_bilden(thema), aktiv=aktiv)


def test_rueckwechsel_wartet_hoechstens_und_meldet_die_sperre(umgebung):
    from master_schalter import paare
    _paar_setzen()
    zustand.aendern(lambda z: replace(z, master="codex"))

    with zustand.thema_sperre("engineering") as frei:
        assert frei is True
        erg = wechsel.wechseln("claude", jetzt=JETZT, themen_frist=0.2)

    assert erg.art == "fehler" and erg.meldung == wechsel.MELDUNG_SPERRE
    assert zustand.lesen().master == "codex"
    assert _pakete(umgebung) == []
    assert paare.lesen()   # unverändert


def test_rueckwechsel_ohne_paare_laesst_sich_nicht_aufhalten(umgebung):
    zustand.aendern(lambda z: replace(z, master="codex"))
    erg = wechsel.wechseln("claude", jetzt=JETZT, themen_frist=0.2)
    assert erg.art == "gewechselt"


def test_rueckwechsel_entwertet_offene_vorgaenge(umgebung):
    from master_schalter import besitz, paare, vorgaenge
    _paar_setzen()
    zustand.aendern(lambda z: replace(z, master="codex"))
    kennung = "engineering@4102444800"
    laufend = paare.laufend_bilden("engineering")
    besitz.schreiben(besitz.pfad(umgebung, laufend), f"codex {kennung} {JETZT.isoformat()}")
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(kennung, "engineering", "lauf-1",
                                                           "gesendet", JETZT.isoformat())])

    erg = wechsel.wechseln("claude", jetzt=JETZT)

    assert erg.art == "gewechselt"
    assert vorgaenge.finden(kennung).phase == "entwertet"
    text = besitz.lesen(besitz.pfad(umgebung, laufend))
    assert text.startswith("claude ") and f"entwertet {kennung}" in text


def test_wechsel_zu_codex_entwertet_nichts(umgebung):
    from master_schalter import paare, vorgaenge
    _paar_setzen()
    kennung = "engineering@4102444800"
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(kennung, "engineering", "lauf-1",
                                                           "gesendet", JETZT.isoformat())])
    wechsel.wechseln("codex", jetzt=JETZT)
    assert vorgaenge.finden(kennung).phase == "gesendet"
    assert paare.lesen()


def test_rueckwechsel_gibt_auch_einen_bestaetigten_besitz_zurueck(umgebung):
    """Sonst bliebe das Thema für die Automatik dauerhaft „von Codex übernommen"."""
    from master_schalter import besitz, paare, vorgaenge
    _paar_setzen()
    zustand.aendern(lambda z: replace(z, master="codex"))
    kennung = "engineering@4102444800"
    laufend = paare.laufend_bilden("engineering")
    besitz.schreiben(besitz.pfad(umgebung, laufend), f"codex {kennung} {JETZT.isoformat()}")
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(kennung, "engineering", "lauf-1",
                                                           "bestaetigt", JETZT.isoformat())])

    assert wechsel.wechseln("claude", jetzt=JETZT).art == "gewechselt"

    assert vorgaenge.finden(kennung).phase == "bestaetigt"   # die Zustellung war echt
    text = besitz.lesen(besitz.pfad(umgebung, laufend))
    assert text.startswith("claude ") and "entwertet" not in text
    assert zustand.lesen().master == "claude"


def test_wechsel_haelt_die_themensperre(umgebung):
    """Während des Wechsels ist die Themensperre belegt – eine zweite Automatik überspringt das Thema."""
    _paar_setzen()
    zwischenstand = {}
    echt = wechsel.uebergabe.paket_bauen

    def nachsehen(*a, **k):
        with zustand.thema_sperre("engineering") as frei:
            zwischenstand["frei"] = frei
        return echt(*a, **k)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(wechsel.uebergabe, "paket_bauen", nachsehen)
        wechsel.wechseln("codex", jetzt=JETZT)

    assert zwischenstand["frei"] is False


# --- CLI ---------------------------------------------------------------------

def test_cli_master_ohne_zustand(umgebung, capsys):
    assert cli.main(["master"]) == 0
    aus = capsys.readouterr().out
    assert "Master: nicht gesetzt" in aus
    assert "Lage ?" in aus


def test_cli_wechsel_und_master(umgebung, capsys):
    assert cli.main(["wechsel", "codex", "--hinweis", "Technik: bitte serve.py lesen"]) == 0
    aus = capsys.readouterr().out
    paket = _pakete(umgebung)[0]
    assert str(paket) in aus
    assert cli.main(["master"]) == 0
    aus = capsys.readouterr().out
    assert "Master: Codex (seit " in aus


def test_cli_wechsel_auf_gleichen_master_rc0_hinweis(umgebung, capsys):
    cli.main(["wechsel", "claude"])
    capsys.readouterr()
    assert cli.main(["wechsel", "claude"]) == 0
    assert "schon" in capsys.readouterr().out
    assert len(_pakete(umgebung)) == 1


def test_cli_wechsel_fehler_rc_ungleich_null(umgebung, capsys, monkeypatch):
    monkeypatch.delenv("MASTER_SCHALTER_REPO")
    monkeypatch.setattr(uebergabe, "_hat_git", lambda ordner: False)
    assert cli.main(["wechsel", "codex"]) == 1
    assert "Repo nicht gefunden" in capsys.readouterr().err
    assert zustand.lesen().master is None


def test_cli_wechsel_unbekannter_master_rc2(umgebung, capsys):
    assert cli.main(["wechsel", "gemini"]) == 2


def test_cli_status_hat_masterzeile(umgebung, capsys):
    cli.main(["wechsel", "claude"])
    capsys.readouterr()
    assert cli.main(["status"]) == 0
    zeilen = capsys.readouterr().out.splitlines()
    assert any(z.startswith("Master: Claude · Lage ") for z in zeilen)


def test_cli_master_zeigt_besetzung_bei_bekannter_lage(umgebung, capsys):
    ende = 4102444800  # 2100
    from master_schalter import signale
    signale.claude_schreiben({"five_hour": {"used_percentage": 10, "resets_at": ende},
                              "seven_day": {"used_percentage": 20, "resets_at": ende}})
    sitz = umgebung.parent / "codex" / "2026" / "10" / "14"
    sitz.mkdir(parents=True)
    (sitz / "rollout-x.jsonl").write_text(json.dumps({
        "timestamp": "2026-10-14T10:00:00.000Z",
        "payload": {"type": "token_count", "rate_limits": {
            "limit_id": "codex",
            "primary": {"used_percent": 5.0, "resets_at": ende},
            "secondary": {"used_percent": 6.0, "resets_at": ende}}}}) + "\n", encoding="utf-8")
    cli.main(["wechsel", "claude"])
    capsys.readouterr()
    assert cli.main(["master"]) == 0
    aus = capsys.readouterr().out
    assert "Lage 1" in aus
    assert "Thinker" in aus and "Reviewer" in aus and "Worker" in aus
