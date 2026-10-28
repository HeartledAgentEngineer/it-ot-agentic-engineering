"""Sammelbefehl `alle`: alle Themen nach Kontingent und wieder zurück (Plan Fassung 4, 28.10.2026)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from master_schalter import alle, besitz, modi, paare, zustand

A, B, C = "thema-a", "thema-b", "thema-c"


def _umgebung(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, themen=(A, B, C)) -> Path:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    for i, thema in enumerate(themen, 1):
        paare.setzen(thema, f"00000000-0000-4000-8000-00000000000{i}", paare.laufend_bilden(thema), aktiv=True)
    return repo


def _marke(repo: Path, thema: str) -> Path:
    return besitz.pfad(repo, paare.laufend_bilden(thema))


def _merk() -> dict:
    return json.loads(alle.merkdatei().read_text(encoding="utf-8"))["themen"]


def test_auf_kontingent_merkt_feste_rollen_und_laesst_hermes_aus(tmp_path, monkeypatch):
    repo = _umgebung(tmp_path, monkeypatch)
    modi.master_setzen(A, "claude", repo=repo)
    modi.master_setzen(B, "hermes", repo=repo)
    modi.master_setzen(C, "codex", repo=repo)
    hermes_marke = _marke(repo, B).read_bytes()

    bericht = alle.auf_kontingent(repo=repo)

    assert bericht.offen == 0
    assert _merk() == {A: "claude", C: "codex"}
    assert modi.profil(A).master == modi.profil(C).master == modi.KONTINGENT
    assert modi.profil(B).master == "hermes" and _marke(repo, B).read_bytes() == hermes_marke
    assert f"{B}: ausgelassen (Hermes)" in bericht.zeilen


def test_hermes_besitz_unter_kontingent_bleibt_in_beide_richtungen(tmp_path, monkeypatch):
    repo = _umgebung(tmp_path, monkeypatch, themen=(A,))
    besitz.schreiben(_marke(repo, A), "hermes 2026-10-28T00:00:00+00:00")
    vorher = _marke(repo, A).read_bytes()
    assert alle.auf_kontingent(repo=repo).zeilen == [f"{A}: ausgelassen (Hermes)"]
    assert _marke(repo, A).read_bytes() == vorher

    alle._merken(alle.merkdatei(), {A: "claude"})
    bericht = alle.zurueck(repo=repo)
    assert bericht.offen == 1 and _merk() == {A: "claude"}
    assert _marke(repo, A).read_bytes() == vorher


def test_abgebrochener_wechsel_zu_hermes_bleibt_in_beide_richtungen(tmp_path, monkeypatch):
    repo = _umgebung(tmp_path, monkeypatch, themen=(A,))
    marke = modi.zwischenmarke(A, "hermes", "2026-10-28T00:00:00+00:00")
    besitz.schreiben(_marke(repo, A), marke)
    vorher = _marke(repo, A).read_bytes()
    assert alle.auf_kontingent(repo=repo).zeilen == [f"{A}: ausgelassen (Hermes)"]
    alle._merken(alle.merkdatei(), {A: "claude"})
    assert alle.zurueck(repo=repo).offen == 1
    assert _marke(repo, A).read_bytes() == vorher


def test_fremde_zwischenmarke_bleibt_offen(tmp_path, monkeypatch):
    repo = _umgebung(tmp_path, monkeypatch, themen=(A,))
    besitz.schreiben(_marke(repo, A), modi.zwischenmarke(A, "codex", "2026-10-28T00:00:00+00:00"))
    vorher = _marke(repo, A).read_bytes()
    bericht = alle.auf_kontingent(repo=repo)
    assert bericht.offen == 1 and "unvollständiger Wechsel zu codex" in bericht.zeilen[0]
    assert _marke(repo, A).read_bytes() == vorher


def test_zweiter_aufruf_verliert_nichts_und_neue_feste_rolle_wird_gemerkt(tmp_path, monkeypatch):
    repo = _umgebung(tmp_path, monkeypatch)
    modi.master_setzen(A, "claude", repo=repo)
    alle.auf_kontingent(repo=repo)
    modi.master_setzen(B, "codex", repo=repo)            # inzwischen von Hand fest gesetzt
    alle.auf_kontingent(repo=repo)
    assert _merk() == {A: "claude", B: "codex"}
    modi.master_setzen(A, "codex", repo=repo)            # neue feste Rolle ersetzt den Eintrag, nie „kontingent“
    alle.auf_kontingent(repo=repo)
    assert _merk() == {A: "codex", B: "codex"}


def test_merken_geschieht_unter_der_themensperre_fuer_denselben_zustand(tmp_path, monkeypatch):
    repo = _umgebung(tmp_path, monkeypatch, themen=(A,))
    echt = modi.master_setzen_wenn

    def mit_aenderung(thema, master, pruefung, *a, **k):
        modi.master_setzen(thema, "codex", repo=repo)     # zwischen Themenliste und Sperre fest gesetzt
        return echt(thema, master, pruefung, *a, **k)
    monkeypatch.setattr(modi, "master_setzen_wenn", mit_aenderung)
    alle.auf_kontingent(repo=repo)
    assert _merk() == {A: "codex"}
    assert modi.profil(A).master == modi.KONTINGENT


def test_halbfertiger_wechsel_wird_bei_wiederholung_abgeschlossen(tmp_path, monkeypatch):
    repo = _umgebung(tmp_path, monkeypatch, themen=(A,))
    modi.master_setzen(A, "claude", repo=repo)
    echt = besitz.vergleiche_und_schreibe
    aufrufe = []

    def zweiter_scheitert(datei, erwartet, neu):
        aufrufe.append(neu)
        if len(aufrufe) == 2:                             # Zielmarke nach gespeichertem Profil
            return False
        return echt(datei, erwartet, neu)
    monkeypatch.setattr(besitz, "vergleiche_und_schreibe", zweiter_scheitert)
    assert alle.auf_kontingent(repo=repo).offen == 1
    assert modi.ist_zwischenmarke(besitz.lesen(_marke(repo, A)), A)
    monkeypatch.setattr(besitz, "vergleiche_und_schreibe", echt)

    bericht = alle.auf_kontingent(repo=repo)
    assert bericht.offen == 0 and "halbfertigen Wechsel abgeschlossen" in bericht.zeilen[0]
    assert not modi.ist_zwischenmarke(besitz.lesen(_marke(repo, A)), A)
    assert _merk() == {A: "claude"}


def test_zurueck_stellt_her_und_archiviert_statt_zu_loeschen(tmp_path, monkeypatch):
    repo = _umgebung(tmp_path, monkeypatch)
    modi.master_setzen(A, "claude", repo=repo)
    modi.master_setzen(C, "codex", repo=repo)
    alle.auf_kontingent(repo=repo)

    bericht = alle.zurueck(repo=repo)

    assert bericht.offen == 0
    assert modi.profil(A).master == "claude" and modi.profil(C).master == "codex"
    assert besitz.besitzer(besitz.lesen(_marke(repo, C))) == besitz.CODEX
    assert not alle.merkdatei().exists()
    archiv = list(alle.merkdatei().parent.glob("alle-vorher.*.json"))
    assert len(archiv) == 1 and json.loads(archiv[0].read_text(encoding="utf-8"))["themen"] == {A: "claude", C: "codex"}
    assert alle.zurueck(repo=repo).zeilen == ["Nichts gemerkt – nichts zu tun."]


def test_zurueck_laesst_inzwischen_geaenderte_rolle(tmp_path, monkeypatch):
    repo = _umgebung(tmp_path, monkeypatch, themen=(A,))
    modi.master_setzen(A, "claude", repo=repo)
    alle.auf_kontingent(repo=repo)
    modi.master_setzen(A, "codex", repo=repo)
    bericht = alle.zurueck(repo=repo)
    assert bericht.zeilen == [f"{A}: bleibt codex (inzwischen geändert)"] and bericht.offen == 0
    assert modi.profil(A).master == "codex" and not alle.merkdatei().exists()


def test_zurueck_teilfehler_laesst_rest_stehen(tmp_path, monkeypatch):
    repo = _umgebung(tmp_path, monkeypatch, themen=(A, B))
    modi.master_setzen(A, "claude", repo=repo)
    modi.master_setzen(B, "codex", repo=repo)
    alle.auf_kontingent(repo=repo)
    echt = modi.master_setzen_wenn

    def b_scheitert(thema, *a, **k):
        if thema == B:
            raise modi.ModusFehler("synthetisch")
        return echt(thema, *a, **k)
    monkeypatch.setattr(modi, "master_setzen_wenn", b_scheitert)
    assert alle.zurueck(repo=repo).offen == 1
    assert _merk() == {B: "codex"} and modi.profil(A).master == "claude"
    monkeypatch.setattr(modi, "master_setzen_wenn", echt)
    assert alle.zurueck(repo=repo).offen == 0 and modi.profil(B).master == "codex"


def test_fehler_in_einem_thema_stellt_die_anderen_um(tmp_path, monkeypatch):
    repo = _umgebung(tmp_path, monkeypatch, themen=(A, B))
    modi.master_setzen(A, "claude", repo=repo)
    modi.master_setzen(B, "claude", repo=repo)
    echt = modi.master_setzen_wenn

    def a_scheitert(thema, *a, **k):
        if thema == A:
            raise modi.ModusFehler("synthetisch")
        return echt(thema, *a, **k)
    monkeypatch.setattr(modi, "master_setzen_wenn", a_scheitert)
    bericht = alle.auf_kontingent(repo=repo)
    assert bericht.offen == 1 and bericht.zeilen[0] == f"{A}: offen: synthetisch"
    assert modi.profil(A).master == "claude" and modi.profil(B).master == modi.KONTINGENT


def test_merkfehler_verhindert_umschalten(tmp_path, monkeypatch):
    repo = _umgebung(tmp_path, monkeypatch, themen=(A,))
    modi.master_setzen(A, "claude", repo=repo)

    def kaputt(*_):
        raise OSError("Platte voll")
    monkeypatch.setattr(alle, "_merken", kaputt)
    assert alle.auf_kontingent(repo=repo).offen == 1
    assert modi.profil(A).master == "claude"


@pytest.mark.parametrize("inhalt", ["kein json", '{"version": 2, "themen": {}}',
                                    '{"version": 1, "themen": {"thema-a": "kontingent"}}',
                                    '{"version": 1, "themen": {"../x": "claude"}}'])
def test_ungueltige_merkdatei_aendert_nichts(tmp_path, monkeypatch, inhalt):
    repo = _umgebung(tmp_path, monkeypatch, themen=(A,))
    modi.master_setzen(A, "claude", repo=repo)
    alle.merkdatei().write_text(inhalt, encoding="utf-8")
    for aufruf in (alle.auf_kontingent, alle.zurueck):
        with pytest.raises(alle.AlleFehler):
            aufruf(repo=repo)
    assert modi.profil(A).master == "claude"
    assert alle.merkdatei().read_text(encoding="utf-8") == inhalt


def test_belegte_sperre_aendert_nichts(tmp_path, monkeypatch):
    repo = _umgebung(tmp_path, monkeypatch, themen=(A,))
    modi.master_setzen(A, "claude", repo=repo)
    with zustand.instanz_sperre("alle") as frei:
        assert frei
        with pytest.raises(alle.AlleFehler, match="läuft schon"):
            alle.auf_kontingent(repo=repo)
    assert modi.profil(A).master == "claude" and not alle.merkdatei().exists()


# --- Anbindung: CLI und `kurz` ------------------------------------------------------------

def test_cli_alle_rundreise_und_kurz_zeile(tmp_path, monkeypatch, capsys):
    from master_schalter import cli, kurz
    repo = _umgebung(tmp_path, monkeypatch, themen=(A, B))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    modi.master_setzen(A, "claude", repo=repo)
    modi.master_setzen(B, "hermes", repo=repo)

    assert cli.main(["alle", "kontingent"]) == 0
    aus = capsys.readouterr().out
    assert f"{A}: claude → Kontingent (gemerkt)" in aus and f"{B}: ausgelassen (Hermes)" in aus
    assert "Gemerkt für „alle zurueck“: thema-a claude" in kurz.sammeln()

    assert cli.main(["alle", "zurueck"]) == 0
    assert f"{A}: → claude" in capsys.readouterr().out
    assert not any(z.startswith("Gemerkt") for z in kurz.sammeln())
    assert modi.profil(A).master == "claude" and modi.profil(B).master == "hermes"


def test_cli_alle_exitcodes(tmp_path, monkeypatch, capsys):
    from master_schalter import cli, kurz
    repo = _umgebung(tmp_path, monkeypatch, themen=(A,))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    alle.merkdatei().write_text("kaputt", encoding="utf-8")
    assert cli.main(["alle", "zurueck"]) == 2
    assert "Nicht geändert" in capsys.readouterr().err
    assert "Gemerkt: Merkdatei ungültig – `masterwechsel alle zurueck` nennt den Grund" in kurz.sammeln()
    alle.merkdatei().unlink()
    with zustand.instanz_sperre("alle"):
        assert cli.main(["alle", "kontingent"]) == 1
    assert "läuft schon" in capsys.readouterr().err


def test_merkdatei_mit_kaputter_kodierung_ist_ungueltig_statt_absturz(tmp_path, monkeypatch, capsys):
    from master_schalter import cli, kurz
    repo = _umgebung(tmp_path, monkeypatch, themen=(A,))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    alle.merkdatei().write_bytes(b'{"version": 1, "themen": {"thema-a": "\xff"}}')
    with pytest.raises(alle.MerkFehler, match="unlesbar"):
        alle.gemerkt()
    assert cli.main(["alle", "zurueck"]) == 2
    assert "Gemerkt: Merkdatei ungültig – `masterwechsel alle zurueck` nennt den Grund" in kurz.sammeln()


def test_kurz_gemerkt_zeile():
    from master_schalter import kurz
    assert kurz.gemerkt_zeile(None) is None and kurz.gemerkt_zeile({}) is None
    assert kurz.gemerkt_zeile({"b": "codex", "a": "claude"}) == "Gemerkt für „alle zurueck“: a claude, b codex"
