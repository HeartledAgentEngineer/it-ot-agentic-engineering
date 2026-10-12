"""Pruefkreis Schritt 1 (12.10.2026): automatische Gegenpruefung durch Codex oder Hermes.

Die Pruefer laufen hier nie echt: ``starte`` wird durch eine Attrappe ersetzt,
die je Fall eine Antwort liefert. Geprueft wird die Logik drumherum -
Prueferwahl, Urteilszeile, Fehlerfaelle, Protokoll und die Sperre fuer
sensible Inhalte.
"""
import importlib.util
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
