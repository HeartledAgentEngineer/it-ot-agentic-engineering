"""Tests für die Befehlszeile `masterwechsel`."""
import io
import json
from pathlib import Path

import pytest

from master_schalter import anzeige, automatik, cli, modi, modelle, paare, signale


@pytest.fixture
def daten(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    monkeypatch.setenv("MASTER_SCHALTER_CODEX_SESSIONS", str(tmp_path / "codex"))
    return tmp_path / "daten"


@pytest.fixture
def rollen(tmp_path, monkeypatch):
    """Synthetisches Thema mit Paar und Repository – keine echten Prozesse, kein Netz."""
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    paare.setzen("engineering", "01a12557-3bb3-7171-a021-53e6ac879534",
                 paare.laufend_bilden("engineering"), aktiv=True)
    return tmp_path


def _katalog_schreiben(provider, *eintraege, fehler=None, veraltet=False):
    from datetime import datetime, timedelta, timezone
    pfad = modelle.datei()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        roh = {"version": 1, "anbieter": {}}
    zeit = (datetime.now(timezone.utc) - timedelta(hours=25) if veraltet
            else datetime.now(timezone.utc)).isoformat()
    roh["anbieter"][provider] = {"zeit": zeit, "fehler": fehler,
                                 "modelle": [{"id": kennung, "name": name} for kennung, name in eintraege]}
    pfad.write_text(json.dumps(roh, ensure_ascii=False), encoding="utf-8")


def test_statuszeile_speichert_und_zeigt(daten, monkeypatch, capsys):
    eingabe = {"session_id": "geheim", "rate_limits": {
        "five_hour": {"used_percentage": 23.5, "resets_at": 4102444800},
        "seven_day": {"used_percentage": 41.2, "resets_at": 4102444800}}}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(eingabe)))

    assert cli.main(["statuszeile"]) == 0

    assert capsys.readouterr().out.strip() == "Claude 5h 24% · Wo 41%"
    gespeichert = json.loads((daten / "kontingent-claude.json").read_text(encoding="utf-8"))
    assert "session_id" not in json.dumps(gespeichert)


def test_statuszeile_stuerzt_nie_ab(daten, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("kein json"))
    assert cli.main(["statuszeile"]) == 0
    assert capsys.readouterr().out.strip() == "Claude: keine Daten"


def test_claude_kontingent_von_hand(daten, capsys):
    rc = cli.main(["claude-kontingent", "--fuenf", "79", "--woche", "58",
                   "--reset-fuenf", "2099-01-01T10:00:00+00:00", "--reset-woche", "2099-01-05T21:00:00Z"])
    assert rc == 0
    k = signale.claude_lesen(daten / "kontingent-claude.json")
    assert k.fenster_nach_name("5h").prozent == 79
    assert k.fenster_nach_name("Woche").reset.isoformat() == "2099-01-05T21:00:00+00:00"


def test_claude_kontingent_lehnt_unsinn_ab(daten, capsys):
    assert cli.main(["claude-kontingent", "--fuenf", "150", "--woche", "5",
                     "--reset-fuenf", "2099-01-01T10:00:00Z", "--reset-woche", "2099-01-01T10:00:00Z"]) == 2
    assert not (daten / "kontingent-claude.json").exists()


def test_status_zeigt_beide(daten, capsys):
    assert cli.main(["status"]) == 0
    aus = capsys.readouterr().out
    assert "Claude" in aus and "Codex" in aus and "keine Daten" in aus


def test_version(capsys):
    with pytest.raises(SystemExit) as ende:
        cli.main(["--version"])
    assert ende.value.code == 0
    assert "0.4.1" in capsys.readouterr().out


def test_claude_messen_cli_ruft_adapter_auf(daten, monkeypatch, capsys):
    aufrufe = []
    monkeypatch.setattr(cli.claude_messen, "messen", lambda **kw: aufrufe.append(kw) or True)

    assert cli.main(["claude-messen"]) == 0

    assert aufrufe == [{}]
    assert capsys.readouterr().out.strip() == "Claude-Kontingent aktualisiert."


def test_claude_messen_cli_zeigt_nur_sicheren_fehler(daten, monkeypatch, capsys):
    def fehler(**kw):
        raise cli.claude_messen.MessFehler("Claude-Anmeldung abgelaufen – Claude Code einmal starten")

    monkeypatch.setattr(cli.claude_messen, "messen", fehler)

    assert cli.main(["claude-messen"]) == 1

    aus = capsys.readouterr()
    assert "Claude-Anmeldung abgelaufen" in aus.err
    assert "Traceback" not in aus.out + aus.err


# --- Paare (v0.3.0) -----------------------------------------------------------

THREAD = "01a12557-3bb3-7171-a021-53e6ac879534"


def test_paar_setzen_und_paare_zeigen(daten, capsys):
    assert cli.main(["paar-setzen", "engineering", THREAD,
                     ".hermes/uebergabe/laufend/engineering.md"]) == 0
    assert "engineering" in capsys.readouterr().out
    assert cli.paare.lesen()[0].aktiv is True

    assert cli.main(["paare"]) == 0
    aus = capsys.readouterr().out
    assert f"engineering  an  {THREAD}  .hermes/uebergabe/laufend/engineering.md" in aus


def test_paar_setzen_lehnt_fremden_pfad_ab(daten, capsys):
    assert cli.main(["paar-setzen", "engineering", THREAD,
                     ".hermes/uebergabe/laufend/anderes.md"]) == 1
    assert "Paar nicht gespeichert" in capsys.readouterr().err
    assert cli.paare.lesen() == []


def test_paar_setzen_lehnt_ungueltige_kennung_ab(daten, capsys):
    assert cli.main(["paar-setzen", "engineering", "keine-uuid",
                     ".hermes/uebergabe/laufend/engineering.md"]) == 1
    assert cli.paare.lesen() == []


def test_paar_aktiv_an_und_aus(daten, capsys):
    cli.main(["paar-setzen", "engineering", THREAD, ".hermes/uebergabe/laufend/engineering.md"])
    capsys.readouterr()
    assert cli.main(["paar-aktiv", "engineering", "aus"]) == 0
    assert cli.paare.lesen()[0].aktiv is False
    assert cli.main(["paar-aktiv", "engineering", "an"]) == 0
    assert cli.paare.lesen()[0].aktiv is True


def test_paar_aktiv_unbekanntes_thema(daten, capsys):
    assert cli.main(["paar-aktiv", "gibtsnicht", "an"]) == 1
    assert "Paar nicht geändert" in capsys.readouterr().err


def test_paare_ohne_eintraege(daten, capsys):
    assert cli.main(["paare"]) == 0
    assert "Keine Paare angelegt." in capsys.readouterr().out


def test_automatik_pruefen_trocken_reicht_trocken_durch(daten, capsys, monkeypatch):
    aufrufe = []

    def attrappe(**kw):
        aufrufe.append(kw)
        return [cli.automatik.Stand("engineering", "bereit (trocken)")]

    monkeypatch.setattr(cli.automatik, "lauf", attrappe)

    assert cli.main(["automatik-pruefen", "--trocken"]) == 0

    assert aufrufe == [{"trocken": True}]
    assert capsys.readouterr().out.strip() == "engineering: bereit (trocken)"


def test_automatik_pruefen_ohne_automatik(daten, capsys):
    assert cli.main(["automatik-pruefen"]) == 0
    assert cli.automatik.STATUS_AUS in capsys.readouterr().out


def test_automatik_pruefen_meldet_fehler_statt_abzustuerzen(daten, capsys, monkeypatch):
    def kaputt(**kw):
        raise RuntimeError("unerwartet")

    monkeypatch.setattr(cli.automatik, "lauf", kaputt)

    assert cli.main(["automatik-pruefen"]) == 1
    aus = capsys.readouterr()
    assert "Automatikprüfung fehlgeschlagen" in aus.err
    assert "Traceback" not in aus.out + aus.err


def test_rueckgabe_ohne_ja_trockenlauf_ohne_wechsel(daten, monkeypatch, capsys):
    gerufen = {}

    def fake(trocken=False, **kw):
        gerufen["trocken"] = trocken
        return [automatik.Stand("engineering", "Trockenlauf: würde senden")]

    monkeypatch.setattr(cli.rueckgabe, "rueckgabe", fake)
    wechsel_aufrufe = []
    monkeypatch.setattr(cli.wechsel, "wechseln", lambda *a, **k: wechsel_aufrufe.append(a))
    assert cli.main(["rueckgabe"]) == 0
    aus = capsys.readouterr().out
    assert gerufen.get("trocken") is True and wechsel_aufrufe == []
    assert "Trockenlauf" in aus


def test_rueckgabe_mit_ja_wechselt_und_sendet(daten, monkeypatch, capsys):
    class E:
        art, master, paket, meldung = "gewechselt", "codex", Path("paket.md"), ""

    monkeypatch.setattr(cli.wechsel, "wechseln", lambda *a, **k: E())
    gerufen = []
    monkeypatch.setattr(cli.rueckgabe, "rueckgabe",
                        lambda **k: gerufen.append(k) or [automatik.Stand("engineering", "gesendet")])
    assert cli.main(["rueckgabe", "--ja", "engineering"]) == 0
    assert gerufen and gerufen[0]["themen"] == ["engineering"]
    assert "gesendet" in capsys.readouterr().out


def test_automatik_an_aus_cli(daten, capsys):
    assert cli.main(["automatik", "an"]) == 0
    assert anzeige.automatik_an() is True
    assert cli.main(["automatik", "aus"]) == 0
    assert anzeige.automatik_an() is False
    assert "an" in capsys.readouterr().out


# --- Rollenprofile, Ausführermodelle und Katalog-CLI (v0.4.0) ------------------


def test_profil_zeigt_master_ausfuehrer_und_modell(rollen, capsys):
    assert cli.main(["master-setzen", "engineering", "hermes"]) == 0
    assert cli.main(["worker-setzen", "engineering", "codex"]) == 0
    _katalog_schreiben("codex", ("gpt-6-luna", "GPT-6 Luna"))
    assert cli.main(["modell-setzen", "engineering", "gpt-6-luna"]) == 0
    capsys.readouterr()

    assert cli.main(["profil", "engineering"]) == 0

    aus = capsys.readouterr().out
    assert "engineering: Master Hermes · Ausführer Codex · Ausführermodell gpt-6-luna" in aus
    assert "ChatGPT-Abo" in aus and "keine Sitzung gestartet" in aus


def test_profil_json_ist_maschinenlesbar(rollen, capsys):
    assert cli.main(["worker-setzen", "engineering", "hermes"]) == 0
    capsys.readouterr()

    assert cli.main(["profil", "engineering", "--json"]) == 0

    daten = json.loads(capsys.readouterr().out)
    assert daten == {"thema": "engineering", "master": "kontingent", "worker": "hermes",
                     "modell": modi.HERMES_MODELL, "modell_standard": False, "geschuetzt": False}


def test_profil_json_standardmodell_und_schutz(rollen, capsys):
    cli.main(["worker-setzen", "engineering", "codex"])
    cli.main(["master-setzen", "engineering", "claude"])
    capsys.readouterr()

    assert cli.main(["profil", "engineering", "--json"]) == 0

    daten = json.loads(capsys.readouterr().out)
    assert (daten["master"], daten["worker"]) == ("claude", "codex")
    assert daten["modell"] is None and daten["modell_standard"] is True
    assert daten["geschuetzt"] is True


def test_master_setzen_cli_fehler_exit1_ohne_nebenwirkung(rollen, capsys):
    assert cli.main(["master-setzen", "engineering", "gemini"]) == 1
    aus = capsys.readouterr()
    assert "Master nicht gesetzt" in aus.err and "Traceback" not in aus.err
    assert modi.profil("engineering") == modi.Profil()
    assert cli.main(["master-setzen", "gibtsnicht", "hermes"]) == 1
    assert "Master nicht gesetzt" in capsys.readouterr().err


def test_worker_setzen_cli_meldet_standard_modell(rollen, capsys):
    cli.main(["master-setzen", "engineering", "hermes"])
    capsys.readouterr()

    assert cli.main(["worker-setzen", "engineering", "codex"]) == 0

    aus = capsys.readouterr().out
    assert "Ausführer Codex gespeichert" in aus and "Standard des Werkzeugs" in aus
    assert modi.profil("engineering") == modi.Profil("hermes", "codex", None)


def test_worker_setzen_cli_lehnt_unbekanntes_ab(rollen, capsys):
    assert cli.main(["worker-setzen", "engineering", "opus"]) == 1
    assert "Ausführer nicht gesetzt" in capsys.readouterr().err
    assert modi.profil("engineering") == modi.Profil()
    assert cli.main(["worker-setzen", "engineering", "workflow"]) == 0


def test_modell_setzen_cli_hermes_nur_die_feste_kennung(rollen, capsys):
    cli.main(["worker-setzen", "engineering", "hermes"])
    capsys.readouterr()

    assert cli.main(["modell-setzen", "engineering", "standard"]) == 1
    assert modi.HERMES_MODELL in capsys.readouterr().err
    assert cli.main(["modell-setzen", "engineering", modi.HERMES_MODELL]) == 0
    assert modi.profil("engineering").modell == modi.HERMES_MODELL


def test_modell_setzen_cli_veralteter_katalog_exit1_und_danach_gelingt(rollen, capsys):
    cli.main(["worker-setzen", "engineering", "codex"])
    capsys.readouterr()
    _katalog_schreiben("codex", ("gpt-6-luna", "GPT-6 Luna"), veraltet=True)
    vorher = modi.datei().read_bytes()

    assert cli.main(["modell-setzen", "engineering", "gpt-6-luna"]) == 1
    assert "veraltet" in capsys.readouterr().err
    assert modi.datei().read_bytes() == vorher

    _katalog_schreiben("codex", ("gpt-6-luna", "GPT-6 Luna"))
    assert cli.main(["modell-setzen", "engineering", "gpt-6-luna"]) == 0
    assert modi.profil("engineering").modell == "gpt-6-luna"


def test_profil_unlesbare_modusdatei_exit1(rollen, capsys):
    modi.datei().parent.mkdir(parents=True, exist_ok=True)
    modi.datei().write_text("{kaputt", encoding="utf-8")

    assert cli.main(["profil", "engineering"]) == 1
    assert "Profil nicht lesbar" in capsys.readouterr().err


def test_modelle_zeigt_kataloge_und_json(rollen, capsys):
    _katalog_schreiben("codex", ("gpt-6-luna", "GPT-6 Luna"), ("gpt-6-sol", "GPT-6 Sol"))

    assert cli.main(["modelle", "codex"]) == 0
    aus = capsys.readouterr().out
    assert "GPT-6 Luna  gpt-6-luna" in aus and "ChatGPT-Abo" in aus

    assert cli.main(["modelle", "codex", "--json"]) == 0
    daten = json.loads(capsys.readouterr().out)
    assert daten[0]["provider"] == "codex" and daten[0]["fehler"] is None
    assert daten[0]["modelle"] == [{"id": "gpt-6-luna", "name": "GPT-6 Luna"},
                                   {"id": "gpt-6-sol", "name": "GPT-6 Sol"}]

    assert cli.main(["modelle"]) == 0
    aus = capsys.readouterr().out
    assert "Codex" in aus and "Claude Code" in aus


def test_modelle_unbekannter_provider_exit1(rollen, capsys):
    assert cli.main(["modelle", "gemini"]) == 1
    assert "Unbekannter Modellprovider" in capsys.readouterr().err


def test_modelle_aktualisieren_ohne_prozess_und_fehler_exit1(rollen, monkeypatch, capsys):
    gerufen = []
    monkeypatch.setattr(cli.modelle, "alle_aktualisieren",
                        lambda: gerufen.append("alle") or {"claude": modelle.Katalog("claude"),
                                                           "codex": modelle.Katalog("codex")})

    assert cli.main(["modelle", "--aktualisieren"]) == 0
    assert gerufen == ["alle"]
    assert "Codex" in capsys.readouterr().out

    monkeypatch.setattr(cli.modelle, "aktualisieren",
                        lambda provider: gerufen.append(provider) or
                        modelle.Katalog(provider, fehler="Zeitüberschreitung"))
    assert cli.main(["modelle", "codex", "--aktualisieren"]) == 1
    aus = capsys.readouterr()
    assert gerufen == ["alle", "codex"]
    assert "Modellkatalog nicht ermittelt" in aus.err and "Zeitüberschreitung" in aus.err


def test_modelle_json_bei_leerem_cache_exit0(rollen, capsys):
    assert cli.main(["modelle", "--json"]) == 0
    daten = json.loads(capsys.readouterr().out)
    assert [eintrag["provider"] for eintrag in daten] == ["claude", "codex"]
    assert all(eintrag["modelle"] == [] and eintrag["veraltet"] is True for eintrag in daten)
