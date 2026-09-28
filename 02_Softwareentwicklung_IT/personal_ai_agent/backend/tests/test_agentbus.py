"""Offline-Pruefungen fuer den Agenten-Bus (tools/agentbus/agentbus.py).

Kein Netz, keine echten Agenten: nur Dateien in tmp_path.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

BUS = Path(__file__).resolve().parents[2] / "tools" / "agentbus" / "agentbus.py"


def _laden():
    spec = importlib.util.spec_from_file_location("agentbus", BUS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def bus(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTBUS_DIR", str(tmp_path / "bus"))
    return _laden()


# --- Grundlagen -------------------------------------------------------------

def test_init_legt_dateien_an(bus):
    gemacht = bus.init(bus.bus_dir())
    assert "messages.jsonl" in gemacht
    assert (bus.bus_dir() / "messages.jsonl").exists()
    assert (bus.bus_dir() / "claims").is_dir()


def test_init_ist_idempotent(bus):
    bus.init(bus.bus_dir())
    assert bus.init(bus.bus_dir()) == []


def test_send_haengt_an(bus):
    bus.init(bus.bus_dir())
    bus.send(bus.bus_dir(), "hermes", "claude", "task", "N27 Schritt 1", step="N27", paths="a.py,b.py")
    zeilen = (bus.bus_dir() / "messages.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(zeilen) == 1
    m = json.loads(zeilen[0])
    assert m["von"] == "hermes" and m["an"] == "claude" and m["typ"] == "task"
    assert m["pfade"] == ["a.py", "b.py"]


def test_unbekannter_typ_wird_abgelehnt(bus):
    bus.init(bus.bus_dir())
    with pytest.raises(SystemExit):
        bus.send(bus.bus_dir(), "hermes", "claude", "quatsch", "x")


# --- Lesen ------------------------------------------------------------------

def test_read_liefert_nur_ungelesene(bus):
    d = bus.bus_dir()
    bus.init(d)
    bus.send(d, "hermes", "claude", "task", "eins")
    erste = bus.read(d, "claude")
    assert len(erste) == 1
    assert bus.read(d, "claude") == []          # schon gelesen


def test_read_all_zeigt_auch_gelesenes(bus):
    d = bus.bus_dir()
    bus.init(d)
    bus.send(d, "hermes", "claude", "task", "eins")
    bus.read(d, "claude")
    assert len(bus.read(d, "claude", alles=True)) == 1


def test_read_adressat_wird_beachtet(bus):
    d = bus.bus_dir()
    bus.init(d)
    bus.send(d, "hermes", "claude", "task", "nur fuer claude")
    assert bus.read(d, "codex") == []


def test_read_all_erreicht_jeden(bus):
    d = bus.bus_dir()
    bus.init(d)
    bus.send(d, "hermes", "alle", "tip", "fuer alle")
    assert len(bus.read(d, "codex")) == 1


def test_gelesen_vermerk_ueberlebt_weiteren_send(bus):
    d = bus.bus_dir()
    bus.init(d)
    bus.send(d, "hermes", "claude", "task", "eins")
    bus.read(d, "claude")
    bus.send(d, "hermes", "claude", "task", "zwei")
    assert [m["text"] for m in bus.read(d, "claude")] == ["zwei"]


def test_read_laesst_nachrichtenlog_unveraendert(bus):
    # messages.jsonl bleibt rein anhaengend: ein paralleler send darf nie
    # durch ein Neuschreiben beim Lesen verloren gehen.
    d = bus.bus_dir()
    bus.init(d)
    bus.send(d, "hermes", "claude", "task", "eins")
    vorher = (d / "messages.jsonl").read_bytes()
    bus.read(d, "claude")
    assert (d / "messages.jsonl").read_bytes() == vorher


def test_alter_gelesen_vermerk_im_log_zaehlt_weiter(bus):
    d = bus.bus_dir()
    bus.init(d)
    alt = {"id": "m1", "zeit": "x", "von": "hermes", "an": "claude", "typ": "tip",
           "step": "", "pfade": [], "text": "alt", "gelesen": ["claude"]}
    (d / "messages.jsonl").write_text(json.dumps(alt) + "\n", encoding="utf-8")
    assert bus.read(d, "claude") == []


def test_bus_dir_haengt_nicht_vom_arbeitsordner_ab(tmp_path, monkeypatch):
    # Frueher: Path.cwd()/.hermes/bus -> Hermes und Claude landeten je nach
    # Startordner in zwei verschiedenen Briefkaesten.
    monkeypatch.delenv("AGENTBUS_DIR", raising=False)
    mod = _laden()
    monkeypatch.chdir(tmp_path)
    erster = mod.bus_dir()
    monkeypatch.chdir(BUS.parent)
    assert mod.bus_dir() == erster
    assert (erster.parent.parent / ".git").exists()


# --- Warten (Echtzeit-Ausloeser) --------------------------------------------

def test_wait_liefert_sofort_vorhandene_post(bus):
    d = bus.bus_dir()
    bus.init(d)
    bus.send(d, "hermes", "claude", "frage", "schon da")
    assert [m["text"] for m in bus.wait(d, "claude", timeout=5, intervall=0.05)] == ["schon da"]


def test_wait_endet_nach_timeout_leer(bus):
    d = bus.bus_dir()
    bus.init(d)
    assert bus.wait(d, "claude", timeout=0.2, intervall=0.05) == []


def test_wait_wacht_auf_wenn_post_eintrifft(bus):
    import threading
    d = bus.bus_dir()
    bus.init(d)
    threading.Timer(0.2, lambda: bus.send(d, "hermes", "claude", "tip", "neu")).start()
    assert [m["text"] for m in bus.wait(d, "claude", timeout=5, intervall=0.05)] == ["neu"]


def test_wait_ignoriert_eigene_und_fremde_post(bus):
    d = bus.bus_dir()
    bus.init(d)
    bus.send(d, "claude", "hermes", "tip", "an hermes")
    assert bus.wait(d, "claude", timeout=0.2, intervall=0.05) == []


def test_cli_wait_timeout_exit_3(bus, monkeypatch):
    monkeypatch.setenv("AGENTBUS_DIR", str(bus.bus_dir()))
    bus.main(["init"])
    assert bus.main(["wait", "--for", "claude", "--timeout", "0.2", "--intervall", "0.05"]) == 3


def test_cli_wait_mit_post_exit_0(bus, capsys, monkeypatch):
    monkeypatch.setenv("AGENTBUS_DIR", str(bus.bus_dir()))
    bus.main(["init"])
    bus.main(["send", "--from", "hermes", "--to", "claude", "--type", "frage", "--text", "hallo claude"])
    assert bus.main(["wait", "--for", "claude", "--timeout", "1"]) == 0
    assert "hallo claude" in capsys.readouterr().out


# --- Ansprueche (Kern: keine Kollision) -------------------------------------

def test_claim_legt_sperrdatei_an(bus):
    d = bus.bus_dir()
    bus.init(d)
    c = bus.claim(d, "claude", "N27", "a.py,b.py", "mache ich")
    assert c["agent"] == "claude" and c["pfade"] == ["a.py", "b.py"]
    assert (d / "claims" / "step-N27.json").exists()


def test_zweiter_agent_kann_nicht_uebernehmen(bus):
    d = bus.bus_dir()
    bus.init(d)
    bus.claim(d, "claude", "N27")
    with pytest.raises(SystemExit) as e:
        bus.claim(d, "hermes", "N27")
    assert "schon beansprucht" in str(e.value)


def test_nur_der_inhaber_gibt_frei(bus):
    d = bus.bus_dir()
    bus.init(d)
    bus.claim(d, "claude", "N27")
    with pytest.raises(SystemExit):
        bus.release(d, "hermes", "N27")
    assert "freigegeben" in bus.release(d, "claude", "N27")
    assert not (d / "claims" / "step-N27.json").exists()


def test_freigabe_ohne_anspruch_ist_ungueltig(bus):
    bus.init(bus.bus_dir())
    assert bus.release(bus.bus_dir(), "hermes", "N99") == "kein Anspruch vorhanden"


# --- Pruefrolle -------------------------------------------------------------

def test_arbeiter_darf_sich_nicht_selbst_pruefen(bus):
    d = bus.bus_dir()
    bus.init(d)
    bus.claim(d, "claude", "N27")
    with pytest.raises(SystemExit) as e:
        bus.verify(d, "claude", "N27", "gruen", "passt")
    assert "nicht der Arbeiter" in str(e.value)


def test_anderer_agent_prueft_und_ergebnis_wird_notiert(bus):
    d = bus.bus_dir()
    bus.init(d)
    bus.claim(d, "claude", "N27")
    msg = bus.verify(d, "hermes", "N27", "gruen", "Tor 2270")
    assert msg["ergebnis"] == "gruen"
    nachrichten = bus.read(d, "claude")
    assert any("[gruen]" in m["text"] for m in nachrichten)


def test_ungueltiges_pruefergebnis(bus):
    d = bus.bus_dir()
    bus.init(d)
    with pytest.raises(SystemExit):
        bus.verify(d, "hermes", "N27", "vielleicht")


# --- Uebersicht -------------------------------------------------------------

def test_status_zeigt_ansprueche_und_nachrichten(bus):
    d = bus.bus_dir()
    bus.init(d)
    bus.claim(d, "claude", "N27")
    bus.send(d, "hermes", "claude", "tip", "kleiner Tipp")
    st = bus.status(d)
    assert len(st["claims"]) == 1 and st["claims"][0]["step"] == "N27"
    assert len(st["letzte_nachrichten"]) == 1


def test_status_ohne_bus_ist_leer(bus):
    st = bus.status(bus.bus_dir())
    assert st["claims"] == [] and st["letzte_nachrichten"] == []


# --- Kommandozeile ----------------------------------------------------------

def test_cli_claim_und_status(bus, capsys, monkeypatch):
    monkeypatch.setenv("AGENTBUS_DIR", str(bus.bus_dir()))
    assert bus.main(["init"]) == 0
    assert bus.main(["claim", "--agent", "claude", "--step", "N19",
                     "--paths", "x.py", "--text", "suche umbauen"]) == 0
    assert bus.main(["status"]) == 0
    aus = capsys.readouterr().out
    assert "offene Ansprueche: 1" in aus and "N19" in aus


def test_cli_send_und_read(bus, capsys, monkeypatch):
    monkeypatch.setenv("AGENTBUS_DIR", str(bus.bus_dir()))
    bus.main(["init"])
    bus.main(["send", "--from", "hermes", "--to", "claude", "--type", "task",
              "--step", "N27", "--text", "Schritt 1 bauen"])
    bus.main(["read", "--for", "claude"])
    aus = capsys.readouterr().out
    assert "Schritt 1 bauen" in aus and "Step N27" in aus


def test_cli_pruefung(bus, capsys, monkeypatch):
    monkeypatch.setenv("AGENTBUS_DIR", str(bus.bus_dir()))
    bus.main(["init"])
    bus.main(["claim", "--agent", "claude", "--step", "N27"])
    assert bus.main(["verify", "--agent", "hermes", "--step", "N27",
                     "--result", "gruen", "--text", "2270 Tests"]) == 0
    assert "Pruefung gruen" in capsys.readouterr().out