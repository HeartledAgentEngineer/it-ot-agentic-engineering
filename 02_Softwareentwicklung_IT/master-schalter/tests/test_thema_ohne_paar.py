"""Tests für Themen ohne Codex-Paar: `thema-anlegen`, `_paar_pruefen(ohne_paar=True)` und die Hauptbaum-Pflicht.

Alles synthetisch: Datenordner, Hauptarbeitsbaum und Worktree-Attrappe liegen unter `tmp_path`; kein Netz, keine
echten Dateien (`~/.master-schalter`, `.hermes/`).
"""
from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from master_schalter import (alle, arbeitsweise, assistent, assistent_vorgaenge, automatik, besitz, cli, kurz, modi, paare,
                             postfach, signale)

THEMA = "neues-thema"
PAAR_THEMA = "mit-paar"
THREAD = "00000000-0000-4000-8000-0000000000f1"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Datenordner und ein Hauptarbeitsbaum (`.git` ist ein Ordner); `MASTER_SCHALTER_REPO` zeigt darauf."""
    daten = tmp_path / "daten"
    daten.mkdir()
    haupt = tmp_path / "haupt"
    (haupt / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(haupt))
    return SimpleNamespace(daten=daten, haupt=haupt, tmp=tmp_path, monkeypatch=monkeypatch)


def _worktree(env, *, commondir_ok=True):
    """Worktree-Attrappe zum Hauptbaum; der Schalter wird ab jetzt aus ihr heraus gestartet."""
    verweis = env.haupt / ".git" / "worktrees" / "w"
    verweis.mkdir(parents=True, exist_ok=True)
    if commondir_ok:
        (verweis / "commondir").write_text("../..", encoding="utf-8")
    baum = env.tmp / "baum"
    baum.mkdir(exist_ok=True)
    (baum / ".git").write_text(f"gitdir: {verweis}", encoding="utf-8")
    env.monkeypatch.setenv("MASTER_SCHALTER_REPO", str(baum))
    return baum


def _besitz(wurzel, thema=THEMA):
    return besitz.pfad(wurzel, paare.laufend_bilden(thema))


def _bytes(pfad):
    return pfad.read_bytes() if pfad.exists() else None


def _alle_dateien(wurzel):
    return sorted((p.relative_to(wurzel).as_posix(), p.read_bytes()) for p in wurzel.rglob("*") if p.is_file())


# --- thema-anlegen --------------------------------------------------------------------------------------------------

def test_anlegen_schreibt_profil_und_besitzdatei_im_hauptbaum(env, capsys):
    baum = _worktree(env)                                              # Aufruf aus einer Worktree-Attrappe

    assert cli.main(["thema-anlegen", THEMA]) == 0

    aus = capsys.readouterr().out
    assert "angelegt" in aus and "ohne Codex-Paar" in aus
    assert modi.profil(THEMA) == modi.Profil("claude", "workflow", None)         # Standard-Master claude
    teile = _besitz(env.haupt).read_text(encoding="utf-8").split()
    assert teile[0] == "claude" and teile[2:] == ["modus", THEMA]                # claude <ISO-Zeit> modus <THEMA>
    assert not (baum / ".hermes").exists()                                       # nie im Worktree
    assert paare.lesen() == []                                                   # kein Paar angelegt


def test_anlegen_mit_master_vorgabe(env, capsys):
    assert cli.main(["thema-anlegen", THEMA, "--master", "kontingent"]) == 0
    assert modi.profil(THEMA).master == "kontingent"
    assert _besitz(env.haupt).read_text(encoding="utf-8").startswith("claude ")     # Besitz bei Anlage immer claude
    assert cli.main(["thema-anlegen", "anderes", "--master", "gemini"]) == 1
    assert "unbekannte Masterrolle" in capsys.readouterr().err
    assert not _besitz(env.haupt, "anderes").exists()


def test_doppeltes_anlegen_ist_fehler_und_aendert_nichts(env, capsys):
    assert cli.main(["thema-anlegen", THEMA]) == 0
    capsys.readouterr()
    vorher = (_bytes(modi.datei()), _alle_dateien(env.haupt))

    assert cli.main(["thema-anlegen", THEMA]) == 1
    assert "existiert schon" in capsys.readouterr().err
    assert (_bytes(modi.datei()), _alle_dateien(env.haupt)) == vorher


def test_anlegen_bei_vorhandenem_paar_ist_fehler(env, capsys):
    paare.setzen(PAAR_THEMA, THREAD, paare.laufend_bilden(PAAR_THEMA), aktiv=True)
    assert cli.main(["thema-anlegen", PAAR_THEMA]) == 1
    assert "existiert schon" in capsys.readouterr().err
    assert not _besitz(env.haupt, PAAR_THEMA).exists() and PAAR_THEMA not in modi.lesen()


def test_anlegen_ohne_hauptbaum_ist_fehler_vor_jeder_nebenwirkung(env, capsys):
    baum = _worktree(env, commondir_ok=False)                          # commondir fehlt: Auflösung scheitert
    assert cli.main(["thema-anlegen", THEMA]) == 1
    assert "Hauptarbeitsbaum nicht gefunden" in capsys.readouterr().err
    assert not modi.datei().exists() and not (baum / ".hermes").exists() and not (env.haupt / ".hermes").exists()


def test_unzulaessiger_name_wird_abgelehnt(env, capsys):
    assert cli.main(["thema-anlegen", "Böse/../Name"]) == 1
    assert not modi.datei().exists()


# --- Wiederaufnahme und Überschreibschutz (R1-4) ------------------------------------------------------------------------

def test_abbruch_nach_dem_profil_wird_bei_wiederholung_ergaenzt(env, capsys):
    echt = besitz.exklusiv_schreiben

    def kaputt(*_a, **_k):
        raise OSError("Platte voll")

    env.monkeypatch.setattr(besitz, "exklusiv_schreiben", kaputt)
    assert cli.main(["thema-anlegen", THEMA]) == 1
    assert "Befehl wiederholen" in capsys.readouterr().err
    assert THEMA in modi.lesen() and not _besitz(env.haupt).exists()            # nur das Profil steht
    profil_bytes = _bytes(modi.datei())

    env.monkeypatch.setattr(besitz, "exklusiv_schreiben", echt)
    assert cli.main(["thema-anlegen", THEMA]) == 0
    assert "Besitzdatei ergänzt" in capsys.readouterr().out
    assert _besitz(env.haupt).exists() and _bytes(modi.datei()) == profil_bytes   # Profil unberührt

    assert cli.main(["thema-anlegen", THEMA]) == 1                                  # jetzt vollständig: existiert schon
    assert "existiert schon" in capsys.readouterr().err


@pytest.mark.parametrize("inhalt", ["", "codex 2026-10-01T00:00:00+00:00 fremd"])
def test_vorhandene_besitzdatei_ohne_profil_wird_nie_ueberschrieben(env, capsys, inhalt):
    besitz_datei = _besitz(env.haupt)
    besitz_datei.parent.mkdir(parents=True)
    besitz_datei.write_text(inhalt, encoding="utf-8")
    vorher = besitz_datei.read_bytes()

    assert cli.main(["thema-anlegen", THEMA]) == 1

    assert "existiert ohne Profil" in capsys.readouterr().err
    assert besitz_datei.read_bytes() == vorher and not modi.datei().exists()


def test_altes_thema_nur_mit_profil_wird_ergaenzt_und_master_muss_passen(env, capsys):
    modi._speichern(modi.datei(), "weiterbildung", modi.Profil("kontingent", "workflow", None))
    profil_bytes = _bytes(modi.datei())

    assert cli.main(["thema-anlegen", "weiterbildung"]) == 1                      # Standard claude ≠ kontingent
    assert "Master 'kontingent'" in capsys.readouterr().err
    assert not _besitz(env.haupt, "weiterbildung").exists() and _bytes(modi.datei()) == profil_bytes

    assert cli.main(["thema-anlegen", "weiterbildung", "--master", "kontingent"]) == 0
    assert "Besitzdatei ergänzt" in capsys.readouterr().out
    assert _besitz(env.haupt, "weiterbildung").read_text(encoding="utf-8").startswith("claude ")
    assert _bytes(modi.datei()) == profil_bytes


def test_zwei_gleichzeitige_anlegen_ergeben_genau_eine_besitzdatei(env):
    start = threading.Barrier(2)
    ergebnisse = []

    def lauf():
        start.wait()
        try:
            ergebnisse.append(modi.thema_anlegen(THEMA))
        except modi.ModusFehler as fehler:
            ergebnisse.append(str(fehler))

    faeden = [threading.Thread(target=lauf) for _ in range(2)]
    for faden in faeden:
        faden.start()
    for faden in faeden:
        faden.join(timeout=30)

    assert sorted(ergebnisse, key=lambda e: e != "angelegt")[0] == "angelegt"
    assert sum(1 for e in ergebnisse if "existiert schon" in e) == 1
    assert [p.name for p in _besitz(env.haupt).parent.iterdir()] == [f"{THEMA}.master"]


def test_exklusiv_schreiben_ueberschreibt_nie(tmp_path):
    ziel = tmp_path / "x" / "a.master"
    assert besitz.exklusiv_schreiben(ziel, "claude 2026-10-28T00:00:00+00:00 modus a") is True
    assert besitz.exklusiv_schreiben(ziel, "anderer inhalt") is False
    assert ziel.read_text(encoding="utf-8") == "claude 2026-10-28T00:00:00+00:00 modus a"


# --- Themen ohne Paar in den Schreibwegen (R1-2, R1-3, R2-2) -------------------------------------------------------------

def test_master_setzen_ohne_paar_mit_profil_geht_ohne_beides_unbekannt(env, capsys):
    assert cli.main(["thema-anlegen", THEMA]) == 0
    capsys.readouterr()

    assert cli.main(["master-setzen", THEMA, "codex"]) == 0
    assert modi.profil(THEMA).master == "codex"
    assert besitz.besitzer(besitz.lesen(_besitz(env.haupt))) == "codex"

    assert cli.main(["master-setzen", "gibtsnicht", "codex"]) == 1
    assert "Thema unbekannt" in capsys.readouterr().err
    assert cli.main(["worker-setzen", "gibtsnicht", "claude"]) == 1
    assert cli.main(["modell-setzen", "gibtsnicht", "standard"]) == 1
    assert "Thema unbekannt" in capsys.readouterr().err


def test_worker_und_modell_setzen_ohne_paar_mit_profil(env, capsys):
    assert cli.main(["thema-anlegen", THEMA]) == 0
    besitz_vorher = _bytes(_besitz(env.haupt))

    assert cli.main(["worker-setzen", THEMA, "hermes"]) == 0
    assert cli.main(["modell-setzen", THEMA, modi.HERMES_MODELL]) == 0
    assert modi.profil(THEMA) == modi.Profil("claude", "hermes", modi.HERMES_MODELL)
    assert _bytes(_besitz(env.haupt)) == besitz_vorher                            # Besitz unverändert


def test_aus_einer_worktree_attrappe_schreibt_master_setzen_nur_im_hauptbaum(env, capsys):
    assert cli.main(["thema-anlegen", THEMA]) == 0
    baum = _worktree(env)
    attrappe = _besitz(baum)                                                       # Lockvogel im Worktree
    attrappe.parent.mkdir(parents=True)
    attrappe.write_text("claude 2026-10-01T00:00:00+00:00 lockvogel", encoding="utf-8")
    lockvogel = attrappe.read_bytes()
    capsys.readouterr()

    assert cli.main(["master-setzen", THEMA, "hermes"]) == 0

    assert besitz.besitzer(besitz.lesen(_besitz(env.haupt))) == "hermes"           # Hauptbaum geschrieben
    assert attrappe.read_bytes() == lockvogel                                      # Worktree nie
    assert sorted(p.name for p in attrappe.parent.iterdir()) == [f"{THEMA}.master"]


def test_worker_und_modell_setzen_lassen_alle_besitzdateien_bytegleich(env, capsys):
    assert cli.main(["thema-anlegen", THEMA]) == 0
    baum = _worktree(env)
    attrappe = _besitz(baum)
    attrappe.parent.mkdir(parents=True)
    attrappe.write_text("codex 2026-10-01T00:00:00+00:00 lockvogel", encoding="utf-8")
    vorher = (_alle_dateien(env.haupt), _alle_dateien(baum / ".hermes"))
    capsys.readouterr()

    assert cli.main(["worker-setzen", THEMA, "hermes"]) == 0
    assert cli.main(["modell-setzen", THEMA, modi.HERMES_MODELL]) == 0

    # alle Besitzdateien (Haupt- und Worktree) bytegleich; verändert hat sich nur das Profil im Datenordner
    assert [d for d in _alle_dateien(env.haupt) if d[0].endswith(".master")] == [d for d in vorher[0] if d[0].endswith(".master")]
    assert _alle_dateien(baum / ".hermes") == vorher[1]
    assert modi.profil(THEMA).worker == "hermes"


def test_gescheiterte_commondir_aufloesung_schreibt_nichts(env, capsys):
    assert cli.main(["thema-anlegen", THEMA]) == 0
    baum = _worktree(env, commondir_ok=False)
    vorher = (_bytes(modi.datei()), _alle_dateien(env.haupt))
    capsys.readouterr()

    for befehl in (["master-setzen", THEMA, "codex"], ["worker-setzen", THEMA, "hermes"],
                   ["modell-setzen", THEMA, "standard"]):
        assert cli.main(befehl) == 1
        assert "Hauptarbeitsbaum nicht gefunden" in capsys.readouterr().err
    assert (_bytes(modi.datei()), _alle_dateien(env.haupt)) == vorher
    assert not (baum / ".hermes").exists()


def test_assistent_und_postfach_verlangen_weiter_ein_paar(env, capsys):
    assert cli.main(["thema-anlegen", THEMA]) == 0
    with pytest.raises(modi.ModusFehler, match="Thema unbekannt"):
        postfach._markentext(THEMA, None)
    with pytest.raises(modi.ModusFehler, match="Thema unbekannt"):
        assistent._markentext(THEMA, None)
    with pytest.raises(assistent_vorgaenge.AssistentFehler):
        assistent.uebergeben(THEMA, "codex")
    with pytest.raises(modi.ModusFehler, match="Thema unbekannt"):
        modi.master_uebergeben_gesperrt(THEMA, "codex", vorgang_id="v-1")
    assert modi.profil(THEMA).master == "claude"


def test_legacy_modus_setzen_verlangt_weiter_ein_paar(env, capsys):
    assert cli.main(["thema-anlegen", THEMA]) == 0
    capsys.readouterr()
    assert cli.main(["modus", THEMA, "kontingent"]) == 1
    assert "Thema unbekannt" in capsys.readouterr().err


def test_automatik_ignoriert_themen_ohne_paar(env, capsys):
    assert cli.main(["thema-anlegen", THEMA]) == 0
    vorher = _alle_dateien(env.haupt)
    staende = automatik.lauf(trocken=True)
    assert all(getattr(s, "thema", None) != THEMA for s in staende)
    assert _alle_dateien(env.haupt) == vorher


def test_alle_stellt_auch_themen_ohne_paar_um(env, capsys):
    assert cli.main(["thema-anlegen", THEMA]) == 0                                  # Master claude
    bericht = alle.auf_kontingent(repo=env.haupt)
    assert bericht.offen == 0 and f"{THEMA}: claude → Kontingent (gemerkt)" in bericht.zeilen
    assert modi.profil(THEMA).master == "kontingent"
    assert alle.zurueck(repo=env.haupt).offen == 0 and modi.profil(THEMA).master == "claude"


# --- Schutz und Anzeige ---------------------------------------------------------------------------------------------------------

def test_fuehrt_geschuetzt_und_snapshot_kennen_themen_ohne_paar(env):
    modi._speichern(modi.datei(), THEMA, modi.Profil("kontingent", "workflow", None))
    assert modi.fuehrt(THEMA, repo=env.haupt) is None and modi.geschuetzt(THEMA, repo=env.haupt) is False
    besitz.schreiben(_besitz(env.haupt), "hermes 2026-10-28T00:00:00+00:00 modus neues-thema")
    assert modi.fuehrt(THEMA, repo=env.haupt) == "Hermes" and modi.geschuetzt(THEMA, repo=env.haupt) is True
    assert modi.snapshot([THEMA], repo=env.haupt)[THEMA] == ("kontingent", "hermes", True)
    with pytest.raises(modi.ModusFehler, match="Thema unbekannt"):
        modi.snapshot(["gibtsnicht"], repo=env.haupt)


def test_status_zeigt_themen_ohne_paar(env, monkeypatch, capsys):
    monkeypatch.setattr(signale, "alle_lesen", lambda jetzt=None: [signale.Kontingent("Claude", fehler="x"),
                                                                    signale.Kontingent("Codex", fehler="x")])
    assert cli.main(["thema-anlegen", THEMA]) == 0
    zeile = next(z for z in kurz.sammeln() if z.startswith(f"  {THEMA}:"))
    assert zeile.startswith(f"  {THEMA}: Master Claude (fest) · Besitz claude · ") and zeile.endswith("· ohne Codex-Paar")


# --- Ergebnisprüfung R1-2: Vorschau nennt für Themen ohne Paar keinen Worktree-Schreibweg -----------------------------

def test_vorschau_aus_worktree_ohne_hinweis_bei_thema_ohne_paar(env, capsys):
    assert cli.main(["thema-anlegen", THEMA]) == 0
    _worktree(env)
    capsys.readouterr()
    assert not any("Git-Worktree" in z for z in kurz.pruefer_vorschau(THEMA, "codex"))
    assert cli.main(["master-setzen", THEMA, "codex"]) == 0
    assert "Git-Worktree" not in capsys.readouterr().out
    assert _besitz(env.haupt).read_text(encoding="utf-8").startswith("codex ")      # geschrieben im Hauptbaum


def test_vorschau_aus_worktree_mit_hinweis_bei_thema_mit_paar(env):
    paare.setzen(PAAR_THEMA, THREAD, paare.laufend_bilden(PAAR_THEMA), aktiv=True)
    _worktree(env)
    assert any("Git-Worktree" in z for z in kurz.pruefer_vorschau(PAAR_THEMA, "codex"))


def test_vorschau_bei_vibe_mit_paar_aus_worktree_behaelt_den_hinweis(env):
    """Prüfertext (Vibe) und Worktree-Warnung sind unabhängig: Vibe darf die Warnung nicht verschlucken (R2)."""
    paare.setzen(PAAR_THEMA, THREAD, paare.laufend_bilden(PAAR_THEMA), aktiv=True)
    _worktree(env)
    zeilen = kurz.pruefer_vorschau(PAAR_THEMA, "codex", arbeitsweise.VIBE)
    assert zeilen[0] == f"  Jetzt: {kurz.VIBE_PRUEFER}"
    assert any("Git-Worktree" in z for z in zeilen) and not any("Sobald" in z for z in zeilen)
