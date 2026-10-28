"""Pruefkreis Schritt 1 (12.10.2026): automatische Gegenpruefung durch Codex oder Hermes.

Die Pruefer laufen hier nie echt: ``starte`` wird durch eine Attrappe ersetzt,
die je Fall eine Antwort liefert. Geprueft wird die Logik drumherum -
Prueferwahl, Urteilszeile, Fehlerfaelle, Protokoll und die Sperre fuer
sensible Inhalte.
"""
import importlib.util
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

HIER = Path(__file__).resolve().parents[2] / "tools" / "pruefkreis"


def _lade():
    spec = importlib.util.spec_from_file_location("pruefkreis_test", HIER / "pruefkreis.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def pk(tmp_path, monkeypatch):
    monkeypatch.setenv("PRUEFKREIS_DIR", str(tmp_path / "protokoll"))
    monkeypatch.setenv("PRUEFKREIS_CODEX", "codex-attrappe")
    monkeypatch.setenv("PRUEFKREIS_HERMES", "hermes-attrappe")
    monkeypatch.setenv("PRUEFKREIS_BESITZ_DIR", str(tmp_path / "besitz"))
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "schalter"))   # nie die echte Codex-Messung
    # Standardthema "probe" gehoert Claude - ohne bekannten Master bricht pruefen ab.
    (tmp_path / "besitz").mkdir()
    (tmp_path / "besitz" / "probe.master").write_text("claude 2026-10-27T00:00:00+00:00 modus probe", encoding="utf-8")
    mod = _lade()
    mod.aufrufe = []
    return mod


@pytest.fixture
def vorlage(tmp_path):
    datei = tmp_path / "plan.md"
    datei.write_text("# Plan\n1. Schritt\n", encoding="utf-8")
    return str(datei)


def _attrappe(pk, monkeypatch, antwort="Alles belegt.\nURTEIL: FREI", exitcode=0, nutzung=None, stderr=""):
    """Ersetzt ``starte``: Codex schreibt in -o, Hermes auf stdout + Nutzungsdatei."""
    def starte(befehl, zeitgrenze):
        pk.aufrufe.append(befehl)
        if "-o" in befehl:
            Path(befehl[befehl.index("-o") + 1]).write_text(antwort, encoding="utf-8")
            return exitcode, "", stderr
        if nutzung is not None:
            Path(befehl[befehl.index("--usage-file") + 1]).write_text(nutzung, encoding="utf-8")
        return exitcode, antwort, stderr
    monkeypatch.setattr(pk, "starte", starte)


def test_frei_von_codex_mit_protokoll(pk, vorlage, monkeypatch):
    _attrappe(pk, monkeypatch)
    erg = pk.pruefen(vorlage, "probe")
    assert erg["status"] == "frei" and erg["pruefer"] == "codex" and erg["runde"] == 1
    befehl = pk.aufrufe[0]
    assert befehl[:3] == ["codex-attrappe", "exec", "--ephemeral"]
    assert befehl[befehl.index("-s") + 1] == "read-only"
    text = Path(erg["protokoll"]).read_text(encoding="utf-8")
    assert text.startswith("# Pruefkreis: probe") and "## Runde 1" in text and "**Status: FREI**" in text


def test_einwand_und_rundenzaehlung(pk, vorlage, monkeypatch):
    _attrappe(pk, monkeypatch, antwort="Fehler in Zeile 3.\nURTEIL: EINWAND")
    assert pk.pruefen(vorlage, "probe")["status"] == "einwand"
    _attrappe(pk, monkeypatch)
    erg = pk.pruefen(vorlage, "probe")
    assert erg["runde"] == 2 and erg["status"] == "frei"
    text = Path(erg["protokoll"]).read_text(encoding="utf-8")
    assert text.count("## Runde ") == 2 and "Pruefrunde 2" in pk.aufrufe[1][-1]


@pytest.mark.parametrize("antwort", [
    "Sieht gut aus.",                       # keine Urteilszeile
    "URTEIL: FREI\nNachsatz",               # Urteil nicht in der letzten Zeile
    "URTEIL: VIELLEICHT",                   # unbekanntes Urteil
    "",                                     # leere Antwort
])
def test_ohne_gueltige_urteilszeile_ist_fehler(pk, vorlage, monkeypatch, antwort):
    _attrappe(pk, monkeypatch, antwort=antwort)
    erg = pk.pruefen(vorlage, "probe")
    assert erg["status"] == "fehler" and erg["grund"] == "keine Urteilszeile am Ende"


def test_absturz_ist_fehler_auch_mit_urteil(pk, vorlage, monkeypatch):
    _attrappe(pk, monkeypatch, exitcode=3)
    erg = pk.pruefen(vorlage, "probe")
    assert erg["status"] == "fehler" and "Exit 3" in erg["grund"]


def test_zeitgrenze_ist_fehler(pk, vorlage, monkeypatch):
    _attrappe(pk, monkeypatch, exitcode=-1, antwort="")
    erg = pk.pruefen(vorlage, "probe", zeitgrenze=5)
    assert erg["status"] == "fehler" and "Zeitgrenze 5 s" in erg["grund"]


def test_echte_zeitgrenze_beendet_den_prozess(pk):
    import sys
    code, _, _ = pk.starte([sys.executable, "-c", "import time; time.sleep(30)"], zeitgrenze=1)
    assert code == -1


def test_fehlergrund_steht_im_protokoll(pk, vorlage, monkeypatch):
    """Echter Fall 12.10.2026: Codex-Limit erreicht, Exit 1 - der Grund muss lesbar sein."""
    limit = "OpenAI Codex v0.162\nERROR: You've hit your usage limit. Try again at 7:38 PM.\n"
    _attrappe(pk, monkeypatch, antwort="", exitcode=1, stderr=limit)
    erg = pk.pruefen(vorlage, "probe")
    assert erg["status"] == "fehler" and "usage limit" in erg["grund"]
    assert "usage limit" in Path(erg["protokoll"]).read_text(encoding="utf-8")


def _attrappe_codex_gesperrt(pk, monkeypatch, hermes_antwort="Belegt.\nURTEIL: FREI"):
    """Codex meldet das Nutzungslimit (echter Text 12.10.2026), Hermes antwortet."""
    limit = "ERROR: You've hit your usage limit. Upgrade to Pro or try again at 7:38 PM.\n"

    def starte(befehl, zeitgrenze):
        pk.aufrufe.append(befehl)
        if "-o" in befehl:
            return 1, "", limit
        Path(befehl[befehl.index("--usage-file") + 1]).write_text(
            '{"session_id": "20261012_190000_ersatz", "estimated_cost_usd": 0.01}', encoding="utf-8")
        return 0, hermes_antwort, ""
    monkeypatch.setattr(pk, "starte", starte)


def test_codex_gesperrt_hermes_prueft_ersatzweise(pk, vorlage, monkeypatch):
    """Sebastian 12.10.2026: ist Codex gesperrt, prueft Hermes - nicht warten."""
    _attrappe_codex_gesperrt(pk, monkeypatch)
    erg = pk.pruefen(vorlage, "probe")
    assert [b[0] for b in pk.aufrufe] == ["codex-attrappe", "hermes-attrappe"]
    assert erg["pruefer"] == "hermes" and erg["status"] == "frei"
    assert erg["sitzung"] == "20261012_190000_ersatz"
    text = Path(erg["protokoll"]).read_text(encoding="utf-8")
    assert "Ersatzpruefer: Hermes statt Codex - Codex gesperrt" in text and "usage limit" in text
    assert "Pruefer hermes" in text


def test_codex_gesperrt_einwand_von_hermes_zaehlt(pk, vorlage, monkeypatch):
    _attrappe_codex_gesperrt(pk, monkeypatch, hermes_antwort="Fehler.\nURTEIL: EINWAND")
    assert pk.main(["pruefen", "--vorlage", vorlage, "--thema", "probe"]) == 1


def test_codex_gesperrt_ohne_hermes_bleibt_fehler(pk, vorlage, monkeypatch):
    _attrappe_codex_gesperrt(pk, monkeypatch)
    monkeypatch.setattr(pk, "hermes_programm", lambda: None)
    erg = pk.pruefen(vorlage, "probe")
    assert erg["status"] == "fehler" and erg["pruefer"] == "codex"
    assert "Hermes nicht gefunden" in erg["ersatz"] and len(pk.aufrufe) == 1


@pytest.mark.parametrize("stderr", ["ERROR: Sandbox kaputt", "ERROR: model not supported", ""])
def test_anderer_codex_fehler_loest_keinen_ersatz_aus(pk, vorlage, monkeypatch, stderr):
    _attrappe(pk, monkeypatch, antwort="", exitcode=1, stderr=stderr)
    erg = pk.pruefen(vorlage, "probe")
    assert erg["pruefer"] == "codex" and erg["status"] == "fehler" and not erg["ersatz"]
    assert len(pk.aufrufe) == 1


def test_protokoll_nennt_modell_und_planfassung(pk, vorlage, monkeypatch, tmp_path):
    """Plan Schritt 1: Protokoll mit Runde, Pruefer, Modell, Planfassung, Urteil, Kosten (Einwand Hermes R2)."""
    _attrappe(pk, monkeypatch)
    text = Path(pk.pruefen(vorlage, "probe")["protokoll"]).read_text(encoding="utf-8")
    assert "Modell: Codex-App-Standard (Denkstufe high) · Planfassung: nicht angegeben" in text
    mit_fassung = tmp_path / "auftrag.md"
    mit_fassung.write_text("Plan (Fassung 4, freigegeben)\n", encoding="utf-8")
    erg = pk.pruefen(str(mit_fassung), "probe", gruendlich=True)
    assert "Modell: gpt-6-astra · Planfassung: 4" in Path(erg["protokoll"]).read_text(encoding="utf-8")
    erg = pk.pruefen(str(mit_fassung), "probe", pruefer="hermes", planfassung="5b")
    assert f"Modell: {pk.HERMES_MODELL} · Planfassung: 5b" in Path(erg["protokoll"]).read_text(encoding="utf-8")


def test_ersatz_traegt_das_hermes_modell_ein(pk, vorlage, monkeypatch):
    _attrappe_codex_gesperrt(pk, monkeypatch)
    erg = pk.pruefen(vorlage, "probe", gruendlich=True)
    assert erg["modell"] == pk.HERMES_MODELL


def test_codex_zeitgrenze_loest_keinen_ersatz_aus(pk):
    assert not pk.codex_gesperrt(-1, "usage limit")
    assert pk.codex_gesperrt(1, "HTTP 429 Too Many Requests")
    assert not pk.codex_gesperrt(1, "Zeile 4290 kaputt")


def test_fehlergrund_bei_sensibel_verschwiegen(pk, vorlage, monkeypatch):
    _attrappe(pk, monkeypatch, antwort="", exitcode=1, stderr="ERROR: Inhalt GEHEIMNAME\n")
    erg = pk.pruefen(vorlage, "probe", sensibel=True)
    assert erg["status"] == "fehler" and erg["grund"] == "Pruefer endete mit Exit 1"
    assert "GEHEIMNAME" not in Path(erg["protokoll"]).read_text(encoding="utf-8")


def test_startfehler_ist_fehler(pk):
    code, out, err = pk.starte(["gibt-es-nicht-pruefkreis.exe"], zeitgrenze=5)
    assert code == -2 and out == "" and err


def test_sensibel_verweigert_codex(pk, vorlage, monkeypatch):
    _attrappe(pk, monkeypatch)
    with pytest.raises(pk.PruefkreisFehler, match="ausschliesslich Hermes"):
        pk.pruefen(vorlage, "probe", pruefer="codex", sensibel=True)
    assert pk.aufrufe == []
    assert pk.main(["pruefen", "--vorlage", vorlage, "--thema", "probe", "--pruefer", "codex", "--sensibel"]) == 2


def test_sensibel_nimmt_hermes_und_gibt_nur_das_urteil_weiter(pk, vorlage, monkeypatch):
    nutzung = '{"session_id": "20261012_200000_abcdef", "estimated_cost_usd": 0.0123}'
    _attrappe(pk, monkeypatch, antwort="Person GEHEIMNAME steht in Zeile 4.\nURTEIL: EINWAND", nutzung=nutzung)
    erg = pk.pruefen(vorlage, "probe", sensibel=True)
    assert erg["pruefer"] == "hermes" and erg["status"] == "einwand"
    assert erg["sitzung"] == "20261012_200000_abcdef" and erg["kosten_usd"] == 0.0123
    befehl = pk.aufrufe[0]
    assert befehl[befehl.index("-m") + 1] == pk.HERMES_MODELL
    assert befehl[befehl.index("-t") + 1] == "file,todo"
    text = Path(erg["protokoll"]).read_text(encoding="utf-8")
    assert "GEHEIMNAME" not in text and "GEHEIMNAME" not in erg["ausgabe"]
    assert "URTEIL: EINWAND" in text and "20261012_200000_abcdef" in text and "0.0123 USD" in text


def test_hermes_ohne_nutzungsdatei_bricht_nicht(pk, vorlage, monkeypatch):
    _attrappe(pk, monkeypatch, nutzung="kein json")
    erg = pk.pruefen(vorlage, "probe", pruefer="hermes")
    assert erg["status"] == "frei" and "sitzung" not in erg


def test_gruendlich_waehlt_astra(pk, vorlage, monkeypatch):
    _attrappe(pk, monkeypatch)
    pk.pruefen(vorlage, "probe", gruendlich=True)
    befehl = pk.aufrufe[0]
    assert befehl[befehl.index("-m") + 1] == "gpt-6-astra"
    pk.pruefen(vorlage, "probe")
    assert "model_reasoning_effort=high" in pk.aufrufe[1]


@pytest.mark.parametrize("thema", ["../flucht", "Gross", "mit leer", "", "a" * 81])
def test_thema_wird_dateiname_und_ist_streng(pk, vorlage, thema):
    with pytest.raises(pk.PruefkreisFehler):
        pk.pruefen(vorlage, thema)


def test_fehlende_vorlage(pk, tmp_path):
    with pytest.raises(pk.PruefkreisFehler, match="Vorlage nicht gefunden"):
        pk.pruefen(str(tmp_path / "gibtsnicht.md"), "probe")


def test_fehlendes_programm(pk, vorlage, monkeypatch):
    monkeypatch.setattr(pk, "codex_programm", lambda: None)
    with pytest.raises(pk.PruefkreisFehler, match="Programm fuer codex"):
        pk.pruefen(vorlage, "probe")


def test_exitcodes_der_kommandozeile(pk, vorlage, monkeypatch, capsys):
    _attrappe(pk, monkeypatch)
    assert pk.main(["pruefen", "--vorlage", vorlage, "--thema", "probe"]) == 0
    _attrappe(pk, monkeypatch, antwort="URTEIL: EINWAND")
    assert pk.main(["pruefen", "--vorlage", vorlage, "--thema", "probe"]) == 1
    _attrappe(pk, monkeypatch, antwort="nichts")
    assert pk.main(["pruefen", "--vorlage", vorlage, "--thema", "probe"]) == 2
    ausgabe = capsys.readouterr().out
    assert "## Runde 3" in ausgabe and "Protokoll:" in ausgabe


def test_auftrag_verlangt_nur_lesen_und_urteilszeile(pk):
    text = pk.auftrag_text("plan.md", 2, sensibel=False)
    assert "NUR LESEN" in text and "URTEIL: FREI" in text and "Pruefrunde 2" in text
    assert "persoenlichen" in pk.auftrag_text("plan.md", 1, sensibel=True)


def test_codex_programm_nimmt_das_neueste(tmp_path, monkeypatch):
    import os
    monkeypatch.delenv("PRUEFKREIS_CODEX", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    alt = tmp_path / "OpenAI" / "Codex" / "bin" / "aaa" / "codex.exe"
    neu = tmp_path / "OpenAI" / "Codex" / "bin" / "bbb" / "codex.exe"
    for datei, zeit in ((alt, 1_000_000), (neu, 2_000_000)):
        datei.parent.mkdir(parents=True)
        datei.write_text("x")
        os.utime(datei, (zeit, zeit))
    assert _lade().codex_programm() == str(neu)


def test_codex_master_wird_von_hermes_geprueft(pk, vorlage, monkeypatch):
    _attrappe(pk, monkeypatch)
    erg = pk.pruefen(vorlage, "probe", master="codex")
    assert erg["pruefer"] == "hermes" and pk.aufrufe[0][0] == "hermes-attrappe"
    assert "Master ist Codex" in erg["ersatz"]
    assert "Master ist Codex" in Path(erg["protokoll"]).read_text(encoding="utf-8")


def test_codex_master_lehnt_codex_als_pruefer_ab(pk, vorlage, monkeypatch):
    _attrappe(pk, monkeypatch)
    with pytest.raises(pk.PruefkreisFehler, match="Codex-Masters"):
        pk.pruefen(vorlage, "probe", pruefer="codex", master="codex")
    assert pk.aufrufe == []
    assert pk.main(["pruefen", "--vorlage", vorlage, "--thema", "probe", "--pruefer", "codex", "--master", "codex"]) == 2


@pytest.mark.parametrize("master", [None, "claude", "hermes"])
def test_anderer_master_behaelt_codex_als_standard(pk, vorlage, monkeypatch, master):
    _attrappe(pk, monkeypatch)
    erg = pk.pruefen(vorlage, "probe", master=master)
    assert erg["pruefer"] == "codex" and erg["ersatz"] == ""


def test_unbekannter_master_ist_fehler(pk, vorlage):
    with pytest.raises(pk.PruefkreisFehler, match="Unbekannter Master"):
        pk.pruefen(vorlage, "probe", master="gpt")


def _besitz(tmp_path, name, inhalt):
    ordner = tmp_path / "besitz"
    ordner.mkdir(exist_ok=True)
    (ordner / f"{name}.master").write_text(inhalt, encoding="utf-8")


def test_master_aus_besitzdatei_codex_wird_von_hermes_geprueft(pk, vorlage, monkeypatch, tmp_path):
    _attrappe(pk, monkeypatch)
    _besitz(tmp_path, "master-schalter", "codex 2026-10-27T19:48:37+00:00 modus master-schalter\n")
    erg = pk.pruefen(vorlage, "master-schalter-kurz")
    assert erg["pruefer"] == "hermes" and erg["master"] == "codex"
    text = Path(erg["protokoll"]).read_text(encoding="utf-8")
    assert "Master: codex (master-schalter.master)" in text and "Master ist Codex" in text


def test_besitzdatei_codex_lehnt_codex_als_pruefer_ab(pk, vorlage, monkeypatch, tmp_path):
    _attrappe(pk, monkeypatch)
    _besitz(tmp_path, "probe", "codex 2026-10-27T19:48:37+00:00 modus probe")
    with pytest.raises(pk.PruefkreisFehler, match="Codex-Masters"):
        pk.pruefen(vorlage, "probe", pruefer="codex")
    assert pk.aufrufe == []


def test_laengster_passender_name_gewinnt(pk, tmp_path):
    _besitz(tmp_path, "master", "claude x modus master")
    _besitz(tmp_path, "master-schalter", "codex x modus master-schalter")
    assert pk.master_ermitteln("master-schalter-kurz-r2", None) == ("codex", "master-schalter.master")
    assert pk.master_ermitteln("master-anderes", None) == ("claude", "master.master")


def test_name_passt_nur_an_bindestrich_grenze(pk, tmp_path):
    _besitz(tmp_path, "master-schalter", "codex x modus master-schalter")
    assert pk.master_ermitteln("master-schalterx", None) == (None, "unbekannt (keine Besitzdatei)")


def test_leere_besitzdatei_heisst_claude(pk, vorlage, monkeypatch, tmp_path):
    _attrappe(pk, monkeypatch)
    _besitz(tmp_path, "portfolio-optimierung", "")
    erg = pk.pruefen(vorlage, "portfolio-optimierung")
    assert erg["master"] == "claude" and erg["pruefer"] == "codex" and erg["ersatz"] == ""


def test_unbekannter_besitzer_bricht_ab(pk, vorlage, monkeypatch, tmp_path):
    _attrappe(pk, monkeypatch)
    _besitz(tmp_path, "probe", "gpt x modus probe")
    with pytest.raises(pk.PruefkreisFehler, match="nennt keinen bekannten Master.*--master"):
        pk.pruefen(vorlage, "probe")
    assert pk.aufrufe == []


def test_ohne_besitzdatei_bricht_ab_bis_master_angegeben(pk, vorlage, monkeypatch):
    _attrappe(pk, monkeypatch)
    assert pk.main(["pruefen", "--vorlage", vorlage, "--thema", "ohne-datei"]) == 2
    assert pk.aufrufe == []
    erg = pk.pruefen(vorlage, "ohne-datei", master="claude")
    assert erg["pruefer"] == "codex"
    assert "Master: claude (angegeben)" in Path(erg["protokoll"]).read_text(encoding="utf-8")


def test_sensibel_braucht_keinen_master(pk, vorlage, monkeypatch):
    _attrappe(pk, monkeypatch)
    erg = pk.pruefen(vorlage, "ohne-datei", sensibel=True)
    assert erg["pruefer"] == "hermes" and erg["master"] is None


def test_haupt_repo_aus_worktree(tmp_path):
    pk = _lade()
    haupt = tmp_path / "haupt"
    (haupt / ".git" / "worktrees" / "w").mkdir(parents=True)
    (haupt / ".git" / "worktrees" / "w" / "commondir").write_text("../..\n", encoding="utf-8")
    baum = tmp_path / "baum"
    baum.mkdir()
    (baum / ".git").write_text(f"gitdir: {haupt / '.git' / 'worktrees' / 'w'}\n", encoding="utf-8")
    assert pk.haupt_repo(baum) == haupt.resolve()
    assert pk.haupt_repo(haupt) == haupt
    (baum / ".git").write_text("kaputt", encoding="utf-8")
    assert pk.haupt_repo(baum) == baum


def test_ausdruecklicher_master_geht_vor_besitzdatei(pk, vorlage, monkeypatch, tmp_path):
    _attrappe(pk, monkeypatch)
    _besitz(tmp_path, "probe", "codex x modus probe")
    erg = pk.pruefen(vorlage, "probe", master="claude")
    assert erg["pruefer"] == "codex" and erg["master_quelle"] == "angegeben"


def _messung(tmp_path, prozent, *, alter_s=60, reset_in_s=3600, fenster="5h"):
    jetzt = time.time()
    werte = {"5h": {"used_percent": 10.0, "resets_at": jetzt + 7200},
             "Woche": {"used_percent": 20.0, "resets_at": jetzt + 86400}}
    werte[fenster] = {"used_percent": prozent, "resets_at": jetzt + reset_in_s}
    ordner = tmp_path / "schalter"
    ordner.mkdir(exist_ok=True)
    gelesen = datetime.fromtimestamp(jetzt - alter_s, timezone.utc).isoformat()
    (ordner / "codex-kontingent.json").write_text(json.dumps({"version": 1, "gelesen_um": gelesen, "fenster": werte}),
                                                  encoding="utf-8")


@pytest.mark.parametrize("fenster", ["5h", "Woche"])
def test_gemessenes_limit_nimmt_gleich_hermes(pk, vorlage, monkeypatch, tmp_path, fenster):
    _attrappe(pk, monkeypatch)
    _messung(tmp_path, 100.0, fenster=fenster)
    erg = pk.pruefen(vorlage, "probe")
    assert erg["pruefer"] == "hermes" and [b[0] for b in pk.aufrufe] == ["hermes-attrappe"]
    assert f"Codex {fenster} 100 %" in erg["ersatz"] and "kein Fehlversuch" in erg["ersatz"]
    assert "kein Fehlversuch" in Path(erg["protokoll"]).read_text(encoding="utf-8")


@pytest.mark.parametrize("prozent, alter_s, reset_in_s", [
    (99.0, 60, 3600),       # knapp unter dem Limit
    (100.0, 20 * 60, 3600),  # Messung zu alt
    (100.0, 60, -60),        # Reset schon vorbei
])
def test_ohne_frisches_limit_bleibt_codex(pk, vorlage, monkeypatch, tmp_path, prozent, alter_s, reset_in_s):
    _attrappe(pk, monkeypatch)
    _messung(tmp_path, prozent, alter_s=alter_s, reset_in_s=reset_in_s)
    erg = pk.pruefen(vorlage, "probe")
    assert erg["pruefer"] == "codex" and erg["ersatz"] == ""


def test_kaputte_oder_fehlende_messung_bleibt_codex(pk, vorlage, monkeypatch, tmp_path):
    _attrappe(pk, monkeypatch)
    assert pk.codex_im_limit() is None
    (tmp_path / "schalter").mkdir()
    (tmp_path / "schalter" / "codex-kontingent.json").write_text("{kaputt", encoding="utf-8")
    assert pk.codex_im_limit() is None
    assert pk.pruefen(vorlage, "probe")["pruefer"] == "codex"


def test_ausdruecklich_codex_versucht_trotz_messung(pk, vorlage, monkeypatch, tmp_path):
    _attrappe(pk, monkeypatch)
    _messung(tmp_path, 100.0)
    erg = pk.pruefen(vorlage, "probe", pruefer="codex")
    assert erg["pruefer"] == "codex" and pk.aufrufe[0][0] == "codex-attrappe"


def test_codex_master_bleibt_beim_familienvermerk(pk, vorlage, monkeypatch, tmp_path):
    _attrappe(pk, monkeypatch)
    _messung(tmp_path, 100.0)
    erg = pk.pruefen(vorlage, "probe", master="codex")
    assert erg["pruefer"] == "hermes" and "Master ist Codex" in erg["ersatz"]


@pytest.mark.parametrize("reset", [1e100, float("inf")])
def test_nicht_darstellbarer_reset_faellt_auf_codex_zurueck(pk, vorlage, monkeypatch, tmp_path, reset):
    _attrappe(pk, monkeypatch)
    _messung(tmp_path, 100.0)
    datei = tmp_path / "schalter" / "codex-kontingent.json"
    roh = json.loads(datei.read_text(encoding="utf-8"))
    roh["fenster"]["5h"]["resets_at"] = reset
    datei.write_text(json.dumps(roh), encoding="utf-8")
    assert pk.codex_im_limit() is None
    erg = pk.pruefen(vorlage, "probe")
    assert erg["pruefer"] == "codex" and erg["ersatz"] == ""


@pytest.mark.parametrize("prozent", [10 ** 400, 100.5, -1, float("nan"), True])
def test_ungueltiger_prozentwert_faellt_auf_codex_zurueck(pk, vorlage, monkeypatch, tmp_path, prozent):
    _attrappe(pk, monkeypatch)
    _messung(tmp_path, 100.0)
    datei = tmp_path / "schalter" / "codex-kontingent.json"
    roh = json.loads(datei.read_text(encoding="utf-8"))
    roh["fenster"]["5h"]["used_percent"] = prozent
    roh["fenster"]["Woche"]["used_percent"] = 20.0
    datei.write_text(json.dumps(roh), encoding="utf-8")
    assert pk.codex_im_limit() is None
    assert pk.pruefen(vorlage, "probe")["pruefer"] == "codex"


@pytest.mark.parametrize("feld, wert", [("used_percent", 100.5), ("used_percent", None), ("resets_at", 1e100),
                                         ("resets_at", "morgen"), ("resets_at", None)])   # None bei 20 % = kaputt
def test_kaputtes_zweites_fenster_macht_die_ganze_messung_ungueltig(pk, vorlage, monkeypatch, tmp_path, feld, wert):
    _attrappe(pk, monkeypatch)
    _messung(tmp_path, 100.0, fenster="5h")          # erstes Fenster zeigt ein gültiges Limit
    datei = tmp_path / "schalter" / "codex-kontingent.json"
    roh = json.loads(datei.read_text(encoding="utf-8"))
    roh["fenster"]["Woche"][feld] = wert
    datei.write_text(json.dumps(roh), encoding="utf-8")
    assert pk.codex_im_limit() is None
    assert pk.pruefen(vorlage, "probe")["pruefer"] == "codex"


def test_fehlendes_fenster_macht_die_messung_ungueltig(pk, tmp_path):
    _messung(tmp_path, 100.0)
    datei = tmp_path / "schalter" / "codex-kontingent.json"
    roh = json.loads(datei.read_text(encoding="utf-8"))
    del roh["fenster"]["Woche"]
    datei.write_text(json.dumps(roh), encoding="utf-8")
    assert pk.codex_im_limit() is None


def test_leeres_fenster_ohne_reset_ist_gueltig_und_das_andere_zaehlt(pk, vorlage, monkeypatch, tmp_path):
    # Wie der Master-Schalter: 0 % ohne Rücksetzzeit ist ein gültiges, nicht offenes Fenster.
    _attrappe(pk, monkeypatch)
    _messung(tmp_path, 100.0, fenster="Woche")
    datei = tmp_path / "schalter" / "codex-kontingent.json"
    roh = json.loads(datei.read_text(encoding="utf-8"))
    roh["fenster"]["5h"] = {"used_percent": 0, "resets_at": None}
    datei.write_text(json.dumps(roh), encoding="utf-8")
    assert "Codex Woche 100 %" in (pk.codex_im_limit() or "")
    assert pk.pruefen(vorlage, "probe")["pruefer"] == "hermes"


@pytest.mark.parametrize("form", ["z", "ohne_zone"])
def test_messzeit_mit_z_oder_ohne_zone_gilt_als_utc(pk, tmp_path, form):
    _messung(tmp_path, 100.0)
    datei = tmp_path / "schalter" / "codex-kontingent.json"
    roh = json.loads(datei.read_text(encoding="utf-8"))
    utc = datetime.fromtimestamp(time.time() - 60, timezone.utc).replace(tzinfo=None).isoformat()
    roh["gelesen_um"] = utc + "Z" if form == "z" else utc
    datei.write_text(json.dumps(roh), encoding="utf-8")
    assert "Codex 5h 100 %" in (pk.codex_im_limit() or "")


# --- „Wartet worauf“ während eines Prüflaufs (28.10.2026) ----------------------


def _wartet(tmp_path, name="probe"):
    return tmp_path / "schalter" / "wartet" / f"{name}.json"


def test_laufende_pruefung_steht_als_wartemeldung_und_verschwindet(pk, vorlage, monkeypatch, tmp_path):
    _besitz(tmp_path, "master-schalter", "claude x modus master-schalter")
    gesehen = []

    def starte(befehl, zeitgrenze):
        gesehen.append(json.loads(_wartet(tmp_path, "master-schalter").read_text(encoding="utf-8"))["text"])
        Path(befehl[befehl.index("-o") + 1]).write_text("ok\nURTEIL: FREI", encoding="utf-8")
        return 0, "", ""
    monkeypatch.setattr(pk, "starte", starte)
    pk.pruefen(vorlage, "master-schalter-kurz")
    assert gesehen == ["Prüfung R1 läuft (pruefkreis, master-schalter-kurz)"]
    assert not _wartet(tmp_path, "master-schalter").exists()


def test_fremde_wartemeldung_bleibt_unberuehrt(pk, vorlage, monkeypatch, tmp_path):
    _attrappe(pk, monkeypatch)
    _wartet(tmp_path).parent.mkdir(parents=True)
    _wartet(tmp_path).write_text('{"text": "Freigabe Vibe-Modus", "zeit": "2026-10-28T00:00:00+00:00"}', encoding="utf-8")
    pk.pruefen(vorlage, "probe")
    assert json.loads(_wartet(tmp_path).read_text(encoding="utf-8"))["text"] == "Freigabe Vibe-Modus"


def test_waehrend_des_laufs_geaenderte_meldung_bleibt(pk, vorlage, monkeypatch, tmp_path):
    def starte(befehl, zeitgrenze):
        _wartet(tmp_path).write_text('{"text": "Sebastian: Rueckfrage", "zeit": "2026-10-28T00:00:00+00:00"}',
                                     encoding="utf-8")
        Path(befehl[befehl.index("-o") + 1]).write_text("URTEIL: FREI", encoding="utf-8")
        return 0, "", ""
    monkeypatch.setattr(pk, "starte", starte)
    pk.pruefen(vorlage, "probe")
    assert json.loads(_wartet(tmp_path).read_text(encoding="utf-8"))["text"] == "Sebastian: Rueckfrage"


def test_wartemeldung_wird_auch_bei_abbruch_entfernt(pk, vorlage, monkeypatch, tmp_path):
    monkeypatch.setattr(pk, "codex_programm", lambda: None)
    with pytest.raises(pk.PruefkreisFehler):
        pk.pruefen(vorlage, "probe")
    assert not _wartet(tmp_path).exists()


def test_ausdruecklicher_master_ohne_wartemeldung(pk, vorlage, monkeypatch, tmp_path):
    def starte(befehl, zeitgrenze):
        assert not (tmp_path / "schalter" / "wartet").exists()
        Path(befehl[befehl.index("-o") + 1]).write_text("URTEIL: FREI", encoding="utf-8")
        return 0, "", ""
    monkeypatch.setattr(pk, "starte", starte)
    assert pk.pruefen(vorlage, "probe", master="claude")["status"] == "frei"


def test_wartemeldung_ohne_harte_links_laeuft_weiter_und_hinterlaesst_nichts(pk, vorlage, monkeypatch, tmp_path):
    def kein_link(quelle, ziel):
        raise OSError("keine harten Links")
    monkeypatch.setattr(pk.os, "link", kein_link)
    _attrappe(pk, monkeypatch)
    assert pk.pruefen(vorlage, "probe")["status"] == "frei"
    assert list((tmp_path / "schalter" / "wartet").iterdir()) == []


def test_verschachtelte_wartemeldung_ueberschreibt_die_erste_nie(pk, monkeypatch, tmp_path):
    echter_link = pk.os.link
    innen = []

    def link(quelle, ziel):
        if not innen:   # ein zweiter Aufruf fuer dasselbe Thema kommt dem ersten zuvor
            innen.append(None)
            innen[0] = pk.wartet_melden("probe", "B")
        echter_link(quelle, ziel)
    monkeypatch.setattr(pk.os, "link", link)
    assert pk.wartet_melden("probe", "A") is None
    assert innen == ["B"]
    assert json.loads(_wartet(tmp_path).read_text(encoding="utf-8"))["text"] == "B"
    assert [p.name for p in _wartet(tmp_path).parent.iterdir()] == ["probe.json"]
