"""Wache im Modus 'auftrag' (29.09.2026): frische Hermes-Einmal-Sitzung je 'task'.

Alles mit Attrappen: `subprocess.run` (schreibt eine Fake-Usage-Datei), `toast`,
`shutil.which`. Es wird nie ein echtes `hermes` gestartet.
"""
import importlib.util
import json
import os
import subprocess
import time
from pathlib import Path

HIER = Path(__file__).resolve().parents[2] / "tools" / "agentbus"


def _lade(name, datei):
    spec = importlib.util.spec_from_file_location(name, HIER / datei)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Aufbau:
    def __init__(self, tmp_path, monkeypatch, bericht=None, antwort_senden=True):
        monkeypatch.setenv("AGENTBUS_DIR", str(tmp_path))
        monkeypatch.delenv("WACHE_MODUS", raising=False)
        monkeypatch.delenv("WACHE_MODELL", raising=False)
        monkeypatch.delenv("WACHE_TAGESLIMIT_USD", raising=False)
        self.d = tmp_path
        self.bus = _lade("agentbus_test", "agentbus.py")
        self.wache = _lade("wache_test", "wache.py")
        monkeypatch.setattr(self.wache, "busmodul", lambda: self.bus)
        self.toasts, self.aufrufe = [], []
        self.bericht = bericht if bericht is not None else {
            "estimated_cost_usd": 0.0421, "input_tokens": 1200, "output_tokens": 300,
            "model": "deepseek/test", "api_calls": 3}
        self.antwort_senden = antwort_senden
        self.hermes_da = True
        monkeypatch.setattr(self.wache, "toast", lambda t, x: self.toasts.append((t, x)))
        monkeypatch.setattr(self.wache.shutil, "which",
                            lambda n: "C:/fake/hermes.exe" if self.hermes_da and n == "hermes" else None)
        monkeypatch.setattr(self.wache.subprocess, "run", self._run)
        self.bus.init(tmp_path)

    def _run(self, befehl, **kw):
        self.aufrufe.append((befehl, kw))
        if self.bericht is not False:
            Path(befehl[befehl.index("--usage-file") + 1]).write_text(
                json.dumps(self.bericht), encoding="utf-8")
        if self.antwort_senden:
            step = ""
            text = befehl[2]
            if "Step " in text:
                step = text.split("(Step ", 1)[1].split(")", 1)[0]
            self.bus.send(self.d, "hermes", "claude", "erledigt", "fertig 5 Dateien",
                          step=step)
        return subprocess.CompletedProcess(befehl, 0)

    def gelesen(self):
        p = self.d / "gelesen-hermes.txt"
        return p.read_text(encoding="utf-8").split() if p.exists() else []

    def kosten(self):
        p = self.d / "kosten.jsonl"
        return [json.loads(z) for z in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []

    def nachrichten(self):
        p = self.d / "messages.jsonl"
        return [json.loads(z) for z in p.read_text(encoding="utf-8").splitlines() if z.strip()]


def _lauf(a):
    return a.wache.wache(modus="auftrag")


def test_nur_task_loest_lauf_aus_und_info_bleibt_ungelesen(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch)
    info = a.bus.send(tmp_path, "claude", "hermes", "info", "nur zur Kenntnis")
    time.sleep(0.003)
    task = a.bus.send(tmp_path, "claude", "hermes", "task", "zaehle Dateien", step="N30")
    assert _lauf(a) == 0
    assert len(a.aufrufe) == 1
    assert a.gelesen() == [task["id"]]
    assert info["id"] in [m["id"] for m in a.bus._ungelesen(tmp_path, "hermes")]
    # info wurde nur gemeldet
    assert any("[info]" in x for _, x in a.toasts)


def test_nur_info_startet_keinen_lauf(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch)
    a.bus.send(tmp_path, "claude", "hermes", "frage", "was denkst du?")
    assert _lauf(a) == 0
    assert a.aufrufe == [] and a.gelesen() == []


def test_hoechstens_ein_lauf_je_aufruf_aelteste_zuerst(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch)
    t1 = a.bus.send(tmp_path, "claude", "hermes", "task", "erste", step="A1")
    time.sleep(0.003)
    t2 = a.bus.send(tmp_path, "claude", "hermes", "task", "zweite", step="A2")
    _lauf(a)
    assert len(a.aufrufe) == 1
    assert a.gelesen() == [t1["id"]]
    _lauf(a)
    assert len(a.aufrufe) == 2 and a.gelesen() == [t1["id"], t2["id"]]


def test_aufrufform_hermes_z_usage_in_modell(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch)
    monkeypatch.setenv("WACHE_MODELL", "test/modell")
    a.bus.send(tmp_path, "claude", "hermes", "task", "x", step="N30")
    _lauf(a)
    befehl, kw = a.aufrufe[0]
    assert befehl[0] == "C:/fake/hermes.exe" and befehl[1] == "-z"
    assert "--usage-file" in befehl and "--in" in befehl
    assert befehl[befehl.index("-m") + 1] == "test/modell"
    assert kw["timeout"] == 60 * 60
    assert Path(befehl[befehl.index("--usage-file") + 1]).parent == tmp_path / "kosten"


def test_ohne_modell_kein_m(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch)
    a.bus.send(tmp_path, "claude", "hermes", "task", "x", step="N30")
    _lauf(a)
    assert "-m" not in a.aufrufe[0][0]


def test_lock_verhindert_parallellauf(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch)
    (tmp_path / "wache-auftrag.lock").write_text("fremd", encoding="utf-8")
    a.bus.send(tmp_path, "claude", "hermes", "task", "x", step="N30")
    assert _lauf(a) == 0
    assert a.aufrufe == [] and a.gelesen() == []
    assert (tmp_path / "wache-auftrag.lock").exists()  # fremde Sperre bleibt


def test_verwaistes_lock_wird_uebernommen(tmp_path, monkeypatch, capsys):
    a = Aufbau(tmp_path, monkeypatch)
    lock = tmp_path / "wache-auftrag.lock"
    lock.write_text("alt", encoding="utf-8")
    alt = time.time() - 61 * 60
    os.utime(lock, (alt, alt))
    a.bus.send(tmp_path, "claude", "hermes", "task", "x", step="N30")
    _lauf(a)
    assert len(a.aufrufe) == 1
    assert "verwaist" in capsys.readouterr().out
    assert not lock.exists()  # nach dem Lauf entfernt


def test_lock_wird_auch_nach_fehler_entfernt(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch)

    def kaputt(befehl, **kw):
        raise subprocess.TimeoutExpired(befehl, 1)
    monkeypatch.setattr(a.wache.subprocess, "run", kaputt)
    a.bus.send(tmp_path, "claude", "hermes", "task", "x", step="N30")
    _lauf(a)
    assert not (tmp_path / "wache-auftrag.lock").exists()
    assert a.kosten()[0]["exit"] == -1


def test_kosten_zeile_korrekt(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch)
    t = a.bus.send(tmp_path, "claude", "hermes", "task", "x", step="N30")
    _lauf(a)
    z = a.kosten()
    assert len(z) == 1
    e = z[0]
    assert e["msg_id"] == t["id"] and e["step"] == "N30" and e["exit"] == 0
    assert e["kosten_usd"] == 0.0421 and e["tokens_in"] == 1200 and e["tokens_out"] == 300
    assert e["modell"] == "deepseek/test"
    assert isinstance(e["dauer_s"], float) and e["zeit"][:10] == time.strftime("%Y-%m-%d")
    assert "rohschluessel" not in e
    assert any("N30 fertig (0.04 $)" in t_ for t_, _ in a.toasts)


def test_unbekannte_berichtfelder_werden_null_mit_rohschluesseln(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch, bericht={"foo": 1, "bar": {"x": 2}})
    a.bus.send(tmp_path, "claude", "hermes", "task", "x", step="N30")
    _lauf(a)
    e = a.kosten()[0]
    assert e["kosten_usd"] is None and e["tokens_in"] is None and e["modell"] is None
    assert e["rohschluessel"] == ["bar", "foo"]


def test_fehlender_bericht_tolerant(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch, bericht=False)
    a.bus.send(tmp_path, "claude", "hermes", "task", "x", step="N30")
    assert _lauf(a) == 0
    assert a.kosten()[0]["kosten_usd"] is None


def test_tageslimit_stoppt(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch)
    heute = time.strftime("%Y-%m-%dT%H:%M:%S")
    (tmp_path / "kosten.jsonl").write_text(
        json.dumps({"zeit": heute, "kosten_usd": 0.6}) + "\n"
        + json.dumps({"zeit": heute, "kosten_usd": 0.5}) + "\n"
        + json.dumps({"zeit": "2001-01-01T00:00:00", "kosten_usd": 99}) + "\n", encoding="utf-8")
    t = a.bus.send(tmp_path, "claude", "hermes", "task", "x", step="N30")
    assert _lauf(a) == 0
    assert a.aufrufe == [] and a.gelesen() == []
    assert any("Tageslimit erreicht" in t_ for t_, _ in a.toasts)
    assert t["id"] in [m["id"] for m in a.bus._ungelesen(tmp_path, "hermes")]


def test_tageslimit_ueber_umgebung_und_alte_tage_zaehlen_nicht(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch)
    (tmp_path / "kosten.jsonl").write_text(
        json.dumps({"zeit": "2001-01-01T00:00:00", "kosten_usd": 99}) + "\n", encoding="utf-8")
    a.bus.send(tmp_path, "claude", "hermes", "task", "x", step="N30")
    _lauf(a)
    assert len(a.aufrufe) == 1
    monkeypatch.setenv("WACHE_TAGESLIMIT_USD", "0.01")  # 0.0421 aus dem Lauf > 0.01
    a.bus.send(tmp_path, "claude", "hermes", "task", "y", step="N31")
    _lauf(a)
    assert len(a.aufrufe) == 1


def test_fehlendes_hermes_markiert_nichts(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch)
    a.hermes_da = False
    a.bus.send(tmp_path, "claude", "hermes", "task", "x", step="N30")
    assert _lauf(a) == 1
    assert a.aufrufe == [] and a.gelesen() == []
    assert any("hermes fehlt" in t for t, _ in a.toasts)
    assert not (tmp_path / "wache-auftrag.lock").exists()


def test_fehlende_erledigt_meldung_erzeugt_ersatz_blockiert(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch, antwort_senden=False)
    a.bus.send(tmp_path, "claude", "hermes", "task", "x", step="N30")
    _lauf(a)
    b = [m for m in a.nachrichten() if m["typ"] == "blockiert"]
    assert len(b) == 1
    assert b[0]["von"] == "hermes" and b[0]["an"] == "claude" and b[0]["step"] == "N30"
    assert "Exit 0" in b[0]["text"]


def test_mit_erledigt_meldung_kein_ersatz(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch, antwort_senden=True)
    a.bus.send(tmp_path, "claude", "hermes", "task", "x", step="N30")
    _lauf(a)
    assert [m for m in a.nachrichten() if m["typ"] == "blockiert"] == []


def test_alte_erledigt_meldung_zum_selben_step_zaehlt_nicht(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch, antwort_senden=False)
    a.bus.send(tmp_path, "hermes", "claude", "erledigt", "alt", step="N30")
    time.sleep(0.01)
    a.bus.send(tmp_path, "claude", "hermes", "task", "x", step="N30")
    time.sleep(0.01)
    _lauf(a)
    assert len([m for m in a.nachrichten() if m["typ"] == "blockiert"]) == 1


def test_prompt_enthaelt_auftrag_pflichtzeile_und_keine_env(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch)
    monkeypatch.setenv("API_SERVER_KEY", "geheim-123-nicht-ausgeben")
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=sk-geheim\n", encoding="utf-8")
    a.bus.send(tmp_path, "claude", "hermes", "task", "zaehle die Dateien in X",
               step="N30", paths="a/b,c/d")
    _lauf(a)
    prompt = a.aufrufe[0][0][2]
    assert "Du bist Hermes, Daten-Arbeiter im Agentenbus" in prompt
    assert "zaehle die Dateien in X" in prompt and "N30" in prompt and "a/b, c/d" in prompt
    assert ("python tools/agentbus/agentbus.py send --from hermes --to claude "
            "--type erledigt") in prompt
    assert "--step N30" in prompt
    assert "HANDOVER-CLAUDE-CODE.md" in prompt and "agentbus-protokoll.md" in prompt
    assert ".hermes/plans/" in prompt and "nie loeschen" in prompt
    assert "geheim" not in prompt and "OPENROUTER" not in prompt
    assert len(prompt) < 2500


def test_melden_bleibt_standard(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch)
    a.bus.send(tmp_path, "claude", "hermes", "task", "x", step="N30")
    assert a.wache.wache() == 0
    assert a.aufrufe == [] and a.gelesen() == []
    assert len(a.toasts) == 1 and "1 Nachricht" in a.toasts[0][0]


def test_modus_ueber_umgebung(tmp_path, monkeypatch):
    a = Aufbau(tmp_path, monkeypatch)
    monkeypatch.setenv("WACHE_MODUS", "auftrag")
    a.bus.send(tmp_path, "claude", "hermes", "task", "x", step="N30")
    assert a.wache.wache() == 0
    assert len(a.aufrufe) == 1
