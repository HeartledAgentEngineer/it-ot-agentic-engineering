from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest

from master_schalter import besitz, modelle, modi, paare, vorgaenge


THEMA = "personal-ai-agent"
THREAD = "00000000-0000-4000-8000-000000000001"


def _paar(repo: Path) -> None:
    paare.setzen(THEMA, THREAD, paare.laufend_bilden(THEMA), aktiv=True)


def _umgebung(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Datenordner und Repo mit angelegtem Paar; Rückgabe ist die Repo-Wurzel."""
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    return repo


def _master_datei(repo: Path) -> Path:
    return besitz.pfad(repo, paare.laufend_bilden(THEMA))


def test_fehlt_modusdatei_ist_kontingent(tmp_path: Path) -> None:
    datei = tmp_path / "themenmodi.json"
    assert modi.lesen(datei) == {}
    assert modi.modus(THEMA, datei) == modi.KONTINGENT


def test_modus_roundtrip_erhaelt_andere_themen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)

    modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    assert modi.modus(THEMA) == modi.HERMES_CODEX
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    assert besitz.besitzer(besitz.lesen(master)) == besitz.HERMES
    paare.setzen("anderes-thema", "00000000-0000-4000-8000-000000000002",
                 paare.laufend_bilden("anderes-thema"), aktiv=True)
    modi.setzen("anderes-thema", modi.HERMES_CODEX, repo=repo)
    assert modi.lesen() == {THEMA: modi.Profil("hermes", "codex", "gpt-6-luna"),
                            "anderes-thema": modi.Profil("hermes", "codex", "gpt-6-luna")}


def test_hermes_kontingent_rundreise_entwertet_offenen_vorgang(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(
        "synthetisch-1", THEMA, "lauf-1", "gesendet", "2026-10-16T00:00:00+00:00")])

    modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    modi.setzen(THEMA, modi.KONTINGENT, repo=repo)

    v = vorgaenge.finden("synthetisch-1")
    assert v is not None and v.phase == "entwertet"
    assert modi.modus(THEMA) == modi.KONTINGENT
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    assert besitz.besitzer(besitz.lesen(master)) == besitz.CLAUDE
    assert "modus-reset" in besitz.lesen(master)
    assert not modi.geschuetzt(THEMA, repo=repo)


def test_wiederholung_von_hermesmodus_repariert_fehlende_besitzmarke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    modi._speichern(modi.datei(), THEMA, modi.HERMES_CODEX)

    modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)

    assert besitz.besitzer(besitz.lesen(master)) == besitz.HERMES
    assert modi.geschuetzt(THEMA, repo=repo)


def test_aktivierung_nach_markenfehler_bleibt_geschuetzt_und_wiederholbar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    original = modi._speichern
    fehler = True

    def einmalig(datei_pfad: Path, thema: str, wert: str) -> None:
        nonlocal fehler
        if fehler:
            fehler = False
            raise OSError("synthetischer Schreibfehler")
        original(datei_pfad, thema, wert)

    monkeypatch.setattr(modi, "_speichern", einmalig)
    with pytest.raises(modi.ModusFehler, match="Umschaltung unvollständig"):
        modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    assert modi.geschuetzt(THEMA, repo=repo)
    modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    assert modi.modus(THEMA) == modi.HERMES_CODEX


def test_entwerten_fehler_laesst_eigene_zwischenmarke_stehen_und_profil_unveraendert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Abbruch zwischen Zwischenmarke und Entwerten: Profil unberührt, eigene Zwischenmarke steht und
    schützt fail-closed. Die Wiederholung nach diesem Abbruch führen die Aktivierungs- und
    Absturztests anderweitig aus (u. a. test_absturz_nach_zwischenmarke_...)."""
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    besitz.schreiben(master, "codex vorgang-1 2026-10-16")

    def fehler(*_args, **_kwargs):
        raise OSError("synthetischer Fehler beim Entwerten")

    monkeypatch.setattr(modi, "_offene_entwerten", fehler)
    with pytest.raises(modi.ModusFehler, match="offene Vorgänge nicht entwertet"):
        modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)

    assert modi.lesen() == {}                                       # Modusdatei unverändert
    marke = besitz.lesen(master)
    assert marke.startswith(f"reserviert modus {THEMA} hermes ")    # eigene Zwischenmarke steht
    assert modi.ist_zwischenmarke(marke, THEMA)
    assert modi.geschuetzt(THEMA, repo=repo)                        # fail-closed geschützt


def test_aktivierung_nach_besitzmarken_schreibfehler_bleibt_unveraendert_und_wiederholbar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    besitz.schreiben(master, "codex vorgang-1 2026-10-16")
    original = besitz.schreiben
    fehler = True

    def einmalig(datei: Path, text: str) -> None:
        nonlocal fehler
        if fehler and text.startswith("hermes "):
            fehler = False
            raise OSError("synthetischer Hermes-Markenfehler")
        original(datei, text)

    monkeypatch.setattr(besitz, "schreiben", einmalig)
    with pytest.raises(modi.ModusFehler, match="Hermes-Besitzmarke nicht gespeichert"):
        modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)

    assert modi.lesen() == {THEMA: modi.Profil("hermes", "codex", "gpt-6-luna")}
    assert besitz.lesen(master).startswith(f"reserviert modus {THEMA} hermes ")
    assert modi.geschuetzt(THEMA, repo=repo)
    modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    assert besitz.besitzer(besitz.lesen(master)) == besitz.HERMES
    assert modi.geschuetzt(THEMA, repo=repo)


def test_parallele_moduswechsel_verschiedener_themen_verlieren_keinen_eintrag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    paare.setzen("anderes-thema", "00000000-0000-4000-8000-000000000002",
                 paare.laufend_bilden("anderes-thema"), aktiv=True)

    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs = [
            executor.submit(modi.setzen, THEMA, modi.HERMES_CODEX, repo=repo),
            executor.submit(modi.setzen, "anderes-thema", modi.HERMES_CODEX, repo=repo),
        ]
        for job in jobs:
            job.result(timeout=10)

    assert modi.lesen() == {THEMA: modi.Profil("hermes", "codex", "gpt-6-luna"),
                            "anderes-thema": modi.Profil("hermes", "codex", "gpt-6-luna")}


def test_rueckstellung_nach_source_reset_fehler_bleibt_geschuetzt_und_wiederholbar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    original = besitz.schreiben
    fehler = True

    def einmalig(datei: Path, text: str) -> None:
        nonlocal fehler
        if fehler and text.startswith("claude ") and "modus-reset" in text:
            fehler = False
            raise OSError("synthetischer Resetfehler")
        original(datei, text)

    monkeypatch.setattr(besitz, "schreiben", einmalig)
    with pytest.raises(modi.ModusFehler, match="Besitzmarke noch nicht zurückgesetzt"):
        modi.setzen(THEMA, modi.KONTINGENT, repo=repo)
    assert modi.modus(THEMA) == modi.KONTINGENT
    assert modi.geschuetzt(THEMA, repo=repo)
    modi.setzen(THEMA, modi.KONTINGENT, repo=repo)
    assert not modi.geschuetzt(THEMA, repo=repo)


@pytest.mark.parametrize("stufe,erwarteter_modus,erwarteter_besitzer,meldung", [
    ("hermes-marke", modi.HERMES_CODEX, besitz.RESERVIERT, "Hermes-Besitzmarke nicht gespeichert"),
    ("hermes-modus", modi.KONTINGENT, besitz.RESERVIERT, "eigene Modusmarke steht"),
    ("kontingent-modus", modi.HERMES_CODEX, besitz.RESERVIERT, "eigene Modusmarke steht"),
    ("besitz-reset", modi.KONTINGENT, besitz.RESERVIERT, "Besitzmarke noch nicht zurückgesetzt"),
])
def test_spaeter_schreibfehler_meldet_auch_dauerhafte_entwertung(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    stufe: str, erwarteter_modus: str, erwarteter_besitzer: str, meldung: str,
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    if stufe in ("kontingent-modus", "besitz-reset"):
        modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(
        "offen-vor-fehler", THEMA, "lauf-1", "gesendet", "2026-10-16T00:00:00+00:00")])

    if stufe in ("hermes-marke", "besitz-reset"):
        original = besitz.schreiben

        def besitz_fehler(datei: Path, text: str) -> None:
            if stufe == "hermes-marke" and text.startswith("hermes "):
                raise OSError("synthetischer Besitzfehler")
            if stufe == "besitz-reset" and text.startswith("claude ") and "modus-reset" in text:
                raise OSError("synthetischer Besitzfehler")
            original(datei, text)

        monkeypatch.setattr(besitz, "schreiben", besitz_fehler)
    else:
        monkeypatch.setattr(modi, "_speichern", lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("synthetischer Modusfehler")))

    ziel = modi.HERMES_CODEX if stufe in ("hermes-marke", "hermes-modus") else modi.KONTINGENT
    with pytest.raises(modi.ModusFehler) as fehler:
        modi.setzen(THEMA, ziel, repo=repo)

    text = str(fehler.value)
    assert "offene Vorgänge entwertet" in text
    assert meldung in text
    assert vorgaenge.finden("offen-vor-fehler").phase == "entwertet"
    assert modi.modus(THEMA) == erwarteter_modus
    assert besitz.besitzer(besitz.lesen(master)) == erwarteter_besitzer


def test_kontingent_noop_beruehrt_offenen_codex_vorgang_nicht(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    besitz.schreiben(master, "codex vorgang-1 2026-10-16")
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(
        "vorgang-1", THEMA, "lauf-1", "gesendet", "2026-10-16T00:00:00+00:00")])

    modi.setzen(THEMA, modi.KONTINGENT, repo=repo)

    assert vorgaenge.finden("vorgang-1").phase == "gesendet"
    assert besitz.besitzer(besitz.lesen(master)) == besitz.CODEX


def test_fremde_reservierung_wird_vor_jeder_nebenwirkung_abgelehnt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    fremd = "reserviert fremder-lauf 2026-10-16"
    besitz.schreiben(master, fremd)

    with pytest.raises(modi.ModusFehler, match="fremd reserviert"):
        modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)

    assert modi.lesen() == {}
    assert besitz.lesen(master) == fremd


def test_unlesbare_besitzdatei_ist_keine_fehlende_claude_marke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    _paar(repo)
    master = besitz.pfad(repo, paare.laufend_bilden(THEMA))
    original = Path.read_text

    def nicht_lesbar(datei: Path, *args, **kwargs):
        if datei == master:
            raise PermissionError("synthetisch nicht lesbar")
        return original(datei, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", nicht_lesbar)
    with pytest.raises(modi.ModusFehler, match="Besitzstatus nicht lesbar"):
        modi.geschuetzt(THEMA, repo=repo)
    with pytest.raises(modi.ModusFehler, match="Besitzstatus nicht lesbar"):
        modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)

    assert not modi.datei().exists()
    assert vorgaenge.lesen() == []


@pytest.mark.parametrize("thema", ["../privat", "Upper", "", "a" * 81])
def test_ungueltiges_thema_wird_abgelehnt(tmp_path: Path, thema: str) -> None:
    with pytest.raises((modi.ModusFehler, paare.PaarFehler)):
        modi.modus(thema, tmp_path / "themenmodi.json")


def test_beschaedigtes_schema_wird_nicht_als_kontingent_verschluckt(tmp_path: Path) -> None:
    datei = tmp_path / "themenmodi.json"
    datei.write_text(json.dumps({"version": 3, "themen": {}}), encoding="utf-8")
    with pytest.raises(modi.ModusFehler):
        modi.lesen(datei)


def test_setzen_unbekanntes_thema_ohne_paar_wird_abgelehnt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    daten = tmp_path / "daten"
    daten.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(modi.ModusFehler):
        modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)


# --- Themenprofile v2 und sichere Rollenwechsel (Paket B, v0.4.0) --------------

JETZT = datetime(2026, 10, 16, 6, 0, tzinfo=timezone.utc)


def _katalog(provider: str, *ids: str, fehler: str | None = None, veraltet: bool = False):
    return modelle.Katalog(provider, tuple(modelle.Modell(kennung, kennung) for kennung in ids),
                           zeit=JETZT, fehler=fehler, veraltet=veraltet)


def test_v1_datei_wird_als_v2_profil_gelesen_ohne_schreiben(tmp_path: Path) -> None:
    datei = tmp_path / "themenmodi.json"
    datei.write_text(json.dumps({"version": 1, "themen": {
        THEMA: modi.HERMES_CODEX, "anderes-thema": modi.KONTINGENT}}), encoding="utf-8")
    vorher = datei.read_bytes()

    profile = modi.lesen(datei)

    assert profile == {THEMA: modi.Profil("hermes", "codex", "gpt-6-luna"),
                       "anderes-thema": modi.Profil("kontingent", "workflow", None)}
    assert modi.profil(THEMA, datei) == profile[THEMA]
    assert modi.modus(THEMA, datei) == modi.HERMES_CODEX
    assert datei.read_bytes() == vorher          # Lesen migriert nicht


def test_v2_datei_wird_gelesen_und_fehlende_themen_bleiben_grundwerte(tmp_path: Path) -> None:
    datei = tmp_path / "themenmodi.json"
    datei.write_text(json.dumps({"version": 2, "themen": {THEMA: {
        "master": "hermes", "worker": "codex", "modell": "gpt-6-luna"}}}), encoding="utf-8")
    assert modi.profil(THEMA, datei) == modi.Profil("hermes", "codex", "gpt-6-luna")
    assert modi.profil("fehlendes-thema", datei) == modi.Profil("kontingent", "workflow", None)


@pytest.mark.parametrize("roh", [
    {"version": 3, "themen": {}},                                                       # fremde Version
    {"version": 2, "themen": {}, "extra": 1},                                           # fremder Schlüssel oben
    {"version": 2},                                                                     # themen fehlt
    {"version": 2, "themen": {THEMA: "hermes-codex"}},                                  # v1-Wert in v2-Datei
    {"version": 2, "themen": {THEMA: {}}},                                              # Profil unvollständig
    {"version": 2, "themen": {THEMA: {"master": "kontingent", "worker": "workflow"}}},
    {"version": 2, "themen": {THEMA: {"master": "gemini", "worker": "workflow", "modell": None}}},
    {"version": 2, "themen": {THEMA: {"master": "kontingent", "worker": "opus", "modell": None}}},
    {"version": 2, "themen": {THEMA: {"master": "kontingent", "worker": "workflow", "modell": "gpt-6-luna"}}},
    {"version": 2, "themen": {THEMA: {"master": "kontingent", "worker": "hermes", "modell": None}}},
    {"version": 2, "themen": {THEMA: {"master": "kontingent", "worker": "hermes", "modell": "gpt-6-luna"}}},
    {"version": 2, "themen": {THEMA: {"master": "kontingent", "worker": "codex", "modell": 7}}},
    {"version": 2, "themen": {THEMA: {"master": "kontingent", "worker": "codex", "modell": "a" * 201}}},
    {"version": 2, "themen": {THEMA: {"master": "kontingent", "worker": "codex", "modell": "mit\nZeile"}}},
    {"version": 2, "themen": {THEMA: {"master": "kontingent", "worker": "codex", "modell": "eins", "extra": "x"}}},
    {"version": 1, "themen": {THEMA: "unbekannt"}},
    {"version": 1, "themen": {THEMA: {"master": "hermes"}}},
    "kaputt",
])
def test_kaputte_oder_unbekannte_modusdateien_werden_strikt_abgelehnt(tmp_path: Path, roh) -> None:
    datei = tmp_path / "themenmodi.json"
    datei.write_text(json.dumps(roh), encoding="utf-8")
    with pytest.raises(modi.ModusFehler):
        modi.lesen(datei)


def test_zwischenmarke_wird_nur_streng_und_mit_gleichem_thema_erkannt() -> None:
    marke = modi.zwischenmarke(THEMA, "hermes", JETZT.isoformat())
    assert marke == f"reserviert modus {THEMA} hermes {JETZT.isoformat()}"
    assert modi.ist_zwischenmarke(marke, THEMA)
    assert not modi.ist_zwischenmarke(marke, "anderes-thema")                  # anderes Thema
    assert not modi.ist_zwischenmarke(marke + " extra", THEMA)                 # zu viele Felder
    assert not modi.ist_zwischenmarke(f"reserviert {THEMA} hermes {JETZT.isoformat()}", THEMA)
    assert not modi.ist_zwischenmarke(
        f"reserviert modus {THEMA} gemini {JETZT.isoformat()}", THEMA)         # unbekannte Zielrolle
    assert not modi.ist_zwischenmarke(f"reserviert modus {THEMA} hermes kein-datum", THEMA)
    assert not modi.ist_zwischenmarke(f"reserviert lauf-1 {JETZT.isoformat()}", THEMA)
    assert not modi.ist_zwischenmarke("", THEMA)


def test_erster_schreibvorgang_migriert_v1_und_erhaelt_andere_themen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _umgebung(tmp_path, monkeypatch)
    datei = modi.datei()
    datei.write_text(json.dumps({"version": 1, "themen": {
        THEMA: modi.HERMES_CODEX, "anderes-thema": modi.HERMES_CODEX}}), encoding="utf-8")

    modi.setzen(THEMA, modi.KONTINGENT, repo=repo)

    roh = json.loads(datei.read_text(encoding="utf-8"))
    assert roh["version"] == 2
    assert roh["themen"][THEMA] == {"master": "kontingent", "worker": "workflow", "modell": None}
    assert roh["themen"]["anderes-thema"] == {"master": "hermes", "worker": "codex",
                                              "modell": "gpt-6-luna"}


@pytest.mark.parametrize("master", ["claude", "codex", "hermes"])
def test_master_setzen_aendert_nur_die_masterrolle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, master: str
) -> None:
    repo = _umgebung(tmp_path, monkeypatch)
    modi.worker_setzen(THEMA, "codex", repo=repo)
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(
        "offen-1", THEMA, "lauf-1", "gesendet", "2026-10-16T00:00:00+00:00")])

    ergebnis = modi.master_setzen(THEMA, master, repo=repo)

    assert ergebnis == modi.Profil(master, "codex", None)      # Masterwechsel erhält die Workerauswahl
    assert modi.profil(THEMA) == ergebnis
    assert vorgaenge.finden("offen-1").phase == "entwertet"     # offene Mastervorgänge entwertet
    assert besitz.besitzer(besitz.lesen(_master_datei(repo))) == \
        {"claude": besitz.CLAUDE, "codex": besitz.CODEX, "hermes": besitz.HERMES}[master]


@pytest.mark.parametrize("master", ["claude", "codex", "hermes"])
@pytest.mark.parametrize("worker", ["claude", "codex", "hermes"])
def test_alle_neun_expliziten_kombinationen_sind_setzbar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, master: str, worker: str
) -> None:
    repo = _umgebung(tmp_path, monkeypatch)

    modi.master_setzen(THEMA, master, repo=repo)
    profil = modi.worker_setzen(THEMA, worker, repo=repo)

    assert (profil.master, profil.worker) == (master, worker)
    assert profil.modell == (modi.HERMES_MODELL if worker == "hermes" else None)
    roh = json.loads(modi.datei().read_text(encoding="utf-8"))
    assert roh["themen"][THEMA] == {"master": master, "worker": worker, "modell": profil.modell}
    assert besitz.besitzer(besitz.lesen(_master_datei(repo))) == \
        {"claude": besitz.CLAUDE, "codex": besitz.CODEX, "hermes": besitz.HERMES}[master]


def test_workerwechsel_ohne_besitz_oder_ack_nebenwirkung(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _umgebung(tmp_path, monkeypatch)
    master_datei = _master_datei(repo)
    modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    vorgaenge.aendern(lambda alt: [*alt, vorgaenge.Vorgang(
        "offen-2", THEMA, "lauf-2", "gesendet", "2026-10-16T00:00:00+00:00")])
    profil_vorher = modi.datei().read_bytes()
    marke_vorher = master_datei.read_bytes()
    liste_vorher = vorgaenge.lesen()

    profil = modi.worker_setzen(THEMA, "claude", repo=repo)

    assert (profil.master, profil.worker, profil.modell) == ("hermes", "claude", None)
    assert modi.datei().read_bytes() != profil_vorher       # nur das Profil ändert sich
    assert master_datei.read_bytes() == marke_vorher        # .master-Marke bytegleich
    assert vorgaenge.lesen() == liste_vorher                # keine Vorgangs-Nebenwirkung


def test_workerwechsel_ohne_besitzdatei_erzeugt_keine_besitzdatei(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _umgebung(tmp_path, monkeypatch)
    master_datei = _master_datei(repo)
    assert not master_datei.exists()

    modi.worker_setzen(THEMA, "claude", repo=repo)

    assert not master_datei.exists()                        # reine Workerauswahl schreibt nie Besitz


def test_modellwechsel_laesst_masterfeld_und_besitzmarke_bytegleich(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _umgebung(tmp_path, monkeypatch)
    master_datei = _master_datei(repo)
    modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    modi.worker_setzen(THEMA, "claude", repo=repo)
    marke_vorher = master_datei.read_bytes()

    profil = modi.modell_setzen(THEMA, "claude-opus-5-5", repo=repo,
                                katalog=_katalog("claude", "claude-opus-5-5"))

    assert (profil.master, profil.worker, profil.modell) == ("hermes", "claude", "claude-opus-5-5")
    assert master_datei.read_bytes() == marke_vorher


def test_modell_setzen_workflow_nur_ohne_festes_modell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _umgebung(tmp_path, monkeypatch)

    with pytest.raises(modi.ModusFehler, match="kein festes Modell"):
        modi.modell_setzen(THEMA, "gpt-6-luna", repo=repo)
    assert modi.profil(THEMA) == modi.Profil()               # nichts geändert
    assert modi.modell_setzen(THEMA, None, repo=repo) == modi.Profil()


def test_modell_setzen_hermes_genau_das_feste_modell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _umgebung(tmp_path, monkeypatch)
    modi.worker_setzen(THEMA, "hermes", repo=repo)
    assert modi.profil(THEMA).modell == modi.HERMES_MODELL   # Providerwechsel setzt den Standard

    assert modi.modell_setzen(THEMA, modi.HERMES_MODELL, repo=repo).modell == modi.HERMES_MODELL
    for falsch in ("gpt-6-luna", None):
        with pytest.raises(modi.ModusFehler):
            modi.modell_setzen(THEMA, falsch, repo=repo)
    assert modi.profil(THEMA).modell == modi.HERMES_MODELL


def test_modell_setzen_validiert_gegen_den_erfolgreichen_katalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F2 Punkt 4: veralteter/fehlerhafter Katalog lehnt die Auswahl ab, nach Refresh gelingt sie."""
    repo = _umgebung(tmp_path, monkeypatch)
    modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)
    modi.worker_setzen(THEMA, "codex", repo=repo)
    assert modi.modell_setzen(THEMA, None, repo=repo).modell is None
    master_datei = _master_datei(repo)
    profil_vorher = modi.datei().read_bytes()
    marke_vorher = master_datei.read_bytes()

    veraltet = _katalog("codex", "gpt-6-luna", veraltet=True)
    with pytest.raises(modi.ModusFehler, match="veraltet"):
        modi.modell_setzen(THEMA, "gpt-6-luna", repo=repo, katalog=veraltet)
    assert modi.datei().read_bytes() == profil_vorher        # Profil bytegleich
    assert master_datei.read_bytes() == marke_vorher         # .master bytegleich

    fehlerhaft = _katalog("codex", "gpt-6-luna", fehler=modelle.ZEITUEBERSCHREITUNG)
    with pytest.raises(modi.ModusFehler, match="nicht erfolgreich ermittelt"):
        modi.modell_setzen(THEMA, "gpt-6-luna", repo=repo, katalog=fehlerhaft)

    frisch = _katalog("codex", "gpt-6-luna")
    with pytest.raises(modi.ModusFehler, match="nicht im"):
        modi.modell_setzen(THEMA, "gpt-7-mond", repo=repo, katalog=frisch)

    assert modi.datei().read_bytes() == profil_vorher        # weiterhin nichts geändert
    assert modi.modell_setzen(THEMA, "gpt-6-luna", repo=repo, katalog=frisch).modell == "gpt-6-luna"


def test_modell_setzen_ohne_katalog_liest_den_gespeicherten_katalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _umgebung(tmp_path, monkeypatch)
    modi.worker_setzen(THEMA, "codex", repo=repo)
    gerufen: list[str] = []
    frisch = _katalog("codex", "gpt-6-luna")

    def lesen(provider: str, **_kwargs):
        gerufen.append(provider)
        return frisch

    monkeypatch.setattr(modi.modelle, "lesen", lesen)
    assert modi.modell_setzen(THEMA, "gpt-6-luna", repo=repo).modell == "gpt-6-luna"
    assert gerufen == ["codex"]


@pytest.mark.parametrize("modell", ["", "   ", "a" * 201, "mit\nZeile"])
def test_modell_setzen_lehnt_kaputte_kennungen_ab(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, modell: str
) -> None:
    repo = _umgebung(tmp_path, monkeypatch)
    modi.worker_setzen(THEMA, "codex", repo=repo)
    with pytest.raises(modi.ModusFehler):
        modi.modell_setzen(THEMA, modell, repo=repo, katalog=_katalog("codex", "gpt-6-luna"))


@pytest.mark.parametrize("master,marke", [
    (modi.KONTINGENT, "claude 2026-10-16T05:00:00+00:00"),
    ("claude", "claude 2026-10-16T05:00:00+00:00"),
    ("codex", "codex vorgang-1 2026-10-16T05:00:00+00:00"),
    ("hermes", f"hermes 2026-10-16T05:00:00+00:00 modus {THEMA}"),
])
def test_konsistente_gleiche_masterwahl_ist_noop_und_erhaelt_die_zielmarke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, master: str, marke: str
) -> None:
    repo = _umgebung(tmp_path, monkeypatch)
    master_datei = _master_datei(repo)
    modi._speichern(modi.datei(), THEMA, modi.Profil(master, "workflow", None))
    besitz.schreiben(master_datei, marke)
    vorher = master_datei.read_bytes()

    ergebnis = modi.master_setzen(THEMA, master, repo=repo)

    assert ergebnis == modi.Profil(master, "workflow", None)
    assert master_datei.read_bytes() == vorher               # bytegleich – kein Neustempeln


def test_kontingentwahl_setzt_vorhandene_hermes_marke_zurueck(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _umgebung(tmp_path, monkeypatch)
    master_datei = _master_datei(repo)
    modi._speichern(modi.datei(), THEMA, modi.Profil("kontingent", "workflow", None))
    besitz.schreiben(master_datei, f"hermes 2026-10-16T05:00:00+00:00 modus {THEMA}")

    modi.master_setzen(THEMA, modi.KONTINGENT, repo=repo)

    text = besitz.lesen(master_datei)
    assert text.startswith("claude ") and "modus-reset" in text
    assert not modi.geschuetzt(THEMA, repo=repo)


def test_master_setzen_lehnt_fremde_reservierung_ab(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _umgebung(tmp_path, monkeypatch)
    master_datei = _master_datei(repo)
    fremd = f"reserviert fremder-lauf {JETZT.isoformat()}"
    besitz.schreiben(master_datei, fremd)

    with pytest.raises(modi.ModusFehler, match="fremd reserviert"):
        modi.master_setzen(THEMA, "hermes", repo=repo)

    assert modi.lesen() == {}
    assert besitz.lesen(master_datei) == fremd


@pytest.mark.parametrize("master", ["hermes", "claude"])
def test_absturz_nach_zwischenmarke_wird_bei_wiederholung_sicher_vervollstaendigt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, master: str
) -> None:
    """F2 Punkt 2: Absturz nach der Zwischenmarke vor dem Profilspeichern – Marke bleibt, Wiederholung repariert."""
    repo = _umgebung(tmp_path, monkeypatch)
    master_datei = _master_datei(repo)
    original = modi._speichern
    fehler = True

    def einmalig(datei_pfad: Path, thema: str, profil) -> None:
        nonlocal fehler
        if fehler:
            fehler = False
            raise OSError("synthetischer Absturz vor dem Profilspeichern")
        original(datei_pfad, thema, profil)

    monkeypatch.setattr(modi, "_speichern", einmalig)
    with pytest.raises(modi.ModusFehler, match="Umschaltung unvollständig"):
        modi.master_setzen(THEMA, master, repo=repo)

    marke = besitz.lesen(master_datei)
    assert marke.startswith(f"reserviert modus {THEMA} {master} ")
    assert modi.ist_zwischenmarke(marke, THEMA)
    assert modi.lesen() == {}                                # Profil nicht gespeichert
    assert modi.geschuetzt(THEMA, repo=repo)                 # fail-closed geschützt

    modi.master_setzen(THEMA, master, repo=repo)             # Wiederholung vervollständigt

    assert modi.profil(THEMA) == modi.Profil(master, "workflow", None)
    assert besitz.besitzer(besitz.lesen(master_datei)) == master
    assert not modi.ist_zwischenmarke(besitz.lesen(master_datei), THEMA)


def test_parallele_masterwechsel_zweier_themen_verlieren_keinen_eintrag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _umgebung(tmp_path, monkeypatch)
    paare.setzen("anderes-thema", "00000000-0000-4000-8000-000000000002",
                 paare.laufend_bilden("anderes-thema"), aktiv=True)

    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs = [
            executor.submit(modi.master_setzen, THEMA, "hermes", repo=repo),
            executor.submit(modi.master_setzen, "anderes-thema", "claude", repo=repo),
        ]
        for job in jobs:
            job.result(timeout=10)

    assert modi.profil(THEMA) == modi.Profil("hermes", "workflow", None)
    assert modi.profil("anderes-thema") == modi.Profil("claude", "workflow", None)


def test_besitzpfadpruefung_toleriert_windows_laengenpraefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Synthetisch: resolve() liefert ein `\\\\?\\`-Präfix (Windows-Race) – die Prüfung bleibt korrekt."""
    repo = _umgebung(tmp_path, monkeypatch)
    echt = Path.resolve

    def praefix(datei: Path, *args, **kwargs):
        ziel = echt(datei, *args, **kwargs)
        if str(ziel).endswith(".master"):
            return Path("\\\\?\\" + str(ziel))
        return ziel

    monkeypatch.setattr(Path, "resolve", praefix)

    modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)         # kein ModusFehler trotz Präfix
    assert modi.geschuetzt(THEMA, repo=repo)


def test_echter_pfad_ausserhalb_bleibt_modusfehler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _umgebung(tmp_path, monkeypatch)
    aussen = tmp_path / "aussen"
    aussen.mkdir()
    monkeypatch.setattr(modi.besitz, "pfad", lambda wurzel, laufend: aussen / "fremd.master")

    with pytest.raises(modi.ModusFehler, match="außerhalb"):
        modi.setzen(THEMA, modi.HERMES_CODEX, repo=repo)

    assert modi.lesen() == {}

