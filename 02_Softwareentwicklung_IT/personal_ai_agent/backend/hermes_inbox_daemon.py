#!/usr/bin/env python3
"""Inbox-Daemon fuer den 'aktiv'-Kanal (Wunsch Sebastian).

Der Server legt Track-C-Auftraege in ~/hermes_inbox/auftraege.jsonl (Kanal
'aktiv'). Dieser Daemon vertritt DIE EINE aktive Hermes-Session: er liest die
Auftraege, fuehrt sie ueber einen Hermes-Lauf mit dem Kontext der Session aus
und schreibt die Antwort in ~/hermes_inbox/antworten.jsonl. Der Server holt
sie dort (siehe stream_auftrag_aktiv) und liefert sie zurück.

So antwortet nur diese eine Hermes-Identität — keine weitere Instanz.

Live-Feedback (Stand 2026-09-15):
  * `hermes chat` laeuft mit dem konfigurierten Coding-Modell
    (HERMES_LOCAL_MODEL, Standard deepseek/deepseek-v4.1-flash).
  * Jede Ausgabezeile wird als Zwischengedanke nach status.jsonl geschrieben,
    aber GEBUENDELT (mehrere Zeilen pro Meldung, ~1,2s-Takt). Vorher erzeugte
    jede einzelne Zeile eine eigene Blase — das wirkte wie viele parallel
    tippende Nachrichten.
  * Der Lauf hat ein HARTES Zeitbudget (HERMES_AUFTRAG_TIMEOUT, Standard
    3600s) mit eigenem Lese-Thread. Vorher blockierte die Leseschleife
    unbegrenzt (kein Timeout griff), sodass ein haengender Lauf den Daemon
    dauerhaft lahmlegte und der Server nach 900s "keine Antwort" meldete.

Bedienung:
  python hermes_inbox_daemon.py          # startet den Poll-Loop
  python hermes_inbox_daemon.py --einmal # ein Durchgang, danach Ende
"""
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time

INBOX = os.path.expanduser(os.environ.get("HERMES_INBOX_DIR") or "~/hermes_inbox")
AUFTR = os.path.join(INBOX, "auftraege.jsonl")
ANTW  = os.path.join(INBOX, "antworten.jsonl")
STATUS = os.path.join(INBOX, "status.jsonl")

# Modell fuer den lokalen Hermes-Lauf (Coding-Agent). Wunsch Sebastian
# (2026-09-15): DeepSeek V4.1 Flash — dieselbe Kennung wie im Chat.
MODELL = (os.environ.get("HERMES_LOCAL_MODEL") or "deepseek/deepseek-v4.1-flash").strip()

# Hartes Gesamt-Zeitbudget eines Auftrags (Sekunden). 900s war zu kurz fuer
# Coding-Auftraege und Ursache der Abbruchmeldung.
TIMEOUT = int(os.environ.get("HERMES_AUFTRAG_TIMEOUT") or 3600)

# Buendelung: So lange sammeln wir Ausgabezeilen, bevor sie als EINE
# Zwischenmeldung geschrieben werden (weniger, dafuer zusammenhaengende
# Blasen statt vieler paralleler Einzelzeilen).
FLUSH_S = 0.8
FLUSH_MAX_ZEILEN = 4

# Rohausgabe (kein Antwort-Kasten erkannt): NICHT kuerzen, sondern in
# Zeitbloecken streamen, damit sie nach und nach mitlesbar ist
# (Wunsch Sebastian 2026-09-15).
ROH_BLOCK_ZEILEN = 4
ROH_BLOCK_PAUSE_S = 0.4
# Formular-Zeilen (Abfrage des Agenten: "1. …", "❯ 2. …") duerfen NICHT
# zeilenweise ausgesendet werden: sonst zerfaellt eine Rueckfrage in lauter
# einzelne "Antwort"-Blasen, und die Frage selbst steht in einer anderen Blase
# (Sebastian 2026-09-15: "12 Antworten untereinander, die Frage nicht mal
# dort"). Solange ein Formular laeuft, wird der Puffer zusammengehalten.
FORMULAR_MAX_ZEILEN = 40        # Not-Aus gegen ein endloses "Formular"
FORMULAR_IDLE_S = 2.0           # so lange ohne neue Zeile -> Formular senden


def _ist_formularzeile(zeile: str) -> bool:
    """Nummerierte Auswahlzeile einer Abfrage ('1. …', '❯ 2) …')."""
    return bool(re.match(r"^\s*[❯>»]?\s*\d+[.)]\s+\S", zeile or ""))


def _formular_haelt_puffer(puffer) -> bool:
    """True, wenn der Puffer mitten in einem Frage-/Options-Formular endet.

    Dann NICHT bündeln/aussetzen: Frage + Optionen sollen als EINE Meldung
    ankommen, damit das Frontend daraus ein Menü bauen kann. Ende des
    Formulars ist eine Zeile, die keine Auswahlzeile (und kein Umbruch einer
    solchen) mehr ist.
    """
    if not puffer:
        return False
    letzte = (puffer[-1][1] or "").strip()
    if _ist_formularzeile(letzte):
        return True
    # Umbrochene Auswahlzeile (CLI bricht bei ~80 Zeichen um): nur dann halten,
    # wenn die Zeile DAVOR eine Auswahlzeile war — sonst würde auch ein normaler
    # langer Absatz den Flush verzögern.
    if len(puffer) >= 2:
        vor = (puffer[-2][1] or "").strip()
        if (_ist_formularzeile(vor) and len(letzte) >= 40
                and not letzte.endswith((".", "?", "!", ":"))):
            return True
    return False


class _CliAusgabe:
    """Trennt die Rohausgabe von `hermes chat` in ANTWORT und internes Denken.

    Die Hermes-CLI rahmt jeden Abschnitt in einen Kasten (cli.py:
    `_emit_reasoning`/`_emit_stream_text`):

        Gedanken-Kasten:  ┌─ Reasoning ─────────────┐ … └────────────────┘
        Antwort-Kasten:   ╭─⚕ Hermes …─────────────╮ … ╰────────────────╯

    Grund (Sebastian 2026-09-15: „warum sehe ich das jetzt wieder so
    kryptisch?", „alles wieder in einer Blase"): Der Daemon behandelte JEDE
    Ausgabezeile als Antwort. Dadurch landete das rohe englische
    Modell-Reasoning (mitten im Wort umgebrochen, teils doppelt durch die
    TUI-Neuzeichnung) als 💬-Blase im Chat UND am Ende ALLES zusammen in einer
    einzigen, riesigen Antwort-Blase.

    Jetzt gilt:
      * Nur Zeilen aus dem ANTWORT-Kasten sind Antwort.
      * Der GEDANKEN-Kasten wird zu EINER kurzen Statuszeile verdichtet —
        kein Rohtext (das Reasoning ist englisch und unlesbar).
      * Rahmen-, Werkzeug- (`┊`) und Abschlusszeilen der CLI fallen weg.
      * Taucht gar kein Kasten auf (andere CLI-Fassung), wird wie bisher
        jede Zeile als Antwort genommen — es geht nichts verloren.
    """

    def __init__(self):
        self.kasten = ""             # "" | "gedanken" | "antwort"
        self.kasten_gesehen = False  # Rahmungs-Protokoll erkannt
        self.gedanke_gemeldet = False

    def zeile(self, s: str):
        """Ordnet eine Ausgabezeile ein: (art, text) mit art aus
        "antwort" | "gedanke" | "keine"."""
        if s.startswith("┌") or s.startswith("╭"):
            self.kasten_gesehen = True
            if "Reasoning" in s:
                self.kasten = "gedanken"
                if not self.gedanke_gemeldet:
                    self.gedanke_gemeldet = True
                    return ("gedanke", "🧠 Hermes denkt nach (internes Reasoning) …")
                return ("keine", "")
            self.kasten = "antwort"
            # Neuer Antwort-Kasten = neuer Durchgang: Denk-Meldung wieder frei.
            self.gedanke_gemeldet = False
            return ("keine", "")
        if s.startswith("└") or s.startswith("╰"):
            self.kasten = ""
            return ("keine", "")
        if (s.lstrip().startswith("┊") or s.startswith("Resume this session")
                or s.startswith("Query:") or s.startswith("Initializing")
                or s.startswith("  hermes") or s.startswith("session_id:")):
            return ("keine", "")   # Werkzeug-/Abschlusshinweis der CLI
        if self.kasten == "gedanken":
            return ("keine", "")   # Reasoning-Rohtext nicht ausliefern
        if self.kasten == "antwort":
            return ("antwort", s)
        return ("keine", "") if self.kasten_gesehen else ("antwort", s)


def _schreibe_status(aid: str, text: str) -> None:
    """Schreibt eine Live-Statusmeldung (was der Daemon gerade tut)."""
    try:
        with open(STATUS, "a", encoding="utf-8") as f:
            f.write(json.dumps(
                {"auftrag_id": aid, "text": text,
                 "zeit": time.strftime("%H:%M:%S")}, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[daemon] status schreiben fehlgeschlagen: {e}", flush=True)


def _gelesene_ids():
    """IDs, fuer die bereits eine Antwort existiert (vermied Doppelbearbeitung)."""
    ids = set()
    if os.path.exists(ANTW):
        with open(ANTW, encoding="utf-8") as f:
            for zeile in f:
                z = zeile.strip()
                if not z:
                    continue
                try:
                    ids.add(json.loads(z).get("auftrag_id"))
                except Exception:
                    pass
    return ids


def _schreibe_antwort(aid: str, text: str) -> None:
    """Schreibt die (finale) Antwort des Auftrags nach antworten.jsonl."""
    ant = {"auftrag_id": aid, "text": text}
    with open(ANTW, "a", encoding="utf-8") as f:
        f.write(json.dumps(ant, ensure_ascii=False) + "\n")


_RAHMEN_ZEICHEN = set("╭╮╰╯┌┐└┘─│┊├┤┬┴┼•·⎯ ")
# Eck-Zeichen: eine Zeile, die damit beginnt, ist IMMER ein Kastenrand —
# auch wenn er eine Beschriftung trägt ("╭─⚕ Hermes ────────────╮").
# Inhalt in einem Kasten beginnt dagegen mit "│" / "┊" und bleibt damit erhalten.
_RAHMEN_ANFANG = ("╭", "╮", "╰", "╯", "┌", "┐", "└", "┘")


def _ist_rahmenszeile(s: str) -> bool:
    """True, wenn die Zeile ein Kastenrand ist (nur Rahmenzeichen ODER Eck-Anfang)."""
    if not s:
        return False
    if s.startswith(_RAHMEN_ANFANG):
        return True
    return all(z in _RAHMEN_ZEICHEN for z in s)


def _roh_fallback(zeilen, block_writer=None) -> str:
    """Rohausgabe des lokalen Hermes, wenn kein Antwort-Kasten erkannt wurde.

    Warum (Sebastian 2026-09-15): Bei manchen CLI-Fassungen/Umgebungen kommt
    der Antwort-Kasten (Hermes-Kasten) nicht an. Dann blieb das Ergebnis leer
    und im Chat stand nur ein Strich - nicht unterscheidbar von "nichts
    gearbeitet".

    Wichtig: Die Rohausgabe wird NICHT gekuerzt, sondern in Zeitbloecken
    gestreamt (block_writer) - so kann Sebastian nach und nach mitlesen.
    Ohne block_writer (Tests/andere Aufrufer) kommt alles als EIN Text zurueck.

    Nachtrag (Sebastian 2026-09-25, Live-Test): Vorher war der RUECKGABEWERT
    nur der Hinweis "Rohausgabe vollstaendig: N Zeilen, oben in K Bloecken
    gestreamt." — der echte Text stand ausschliesslich in den Zwischenmeldungen
    (im Chat die "🧠 Gedanke"-Blasen). Ergebnis: Der Chat zeigte "✅ Hermes hat
    geantwortet." OHNE inhaltliche Antwort. Jetzt traegt die Antwort den
    vollstaendigen Text; die Bloecke bleiben als mitlesbare Zwischenmeldungen
    bestehen.
    """
    _noise = ("Resume this session", "Query:", "Initializing", "session_id:",
              "  hermes")
    nutzbar = [z for z in zeilen
               if not _ist_rahmenszeile(z) and not z.startswith(_noise)]
    if not nutzbar:
        return ("⚠️ Hermes hat den Auftrag bearbeitet, aber KEINE Ausgabe "
                "geliefert (kein Antwort-Text in der CLI-Ausgabe erkannt).\n"
                "Prüfen: tail -40 ~/hermes_inbox/daemon.log")

    _anzahl = len(nutzbar)
    kopf = "📄 Rohausgabe des lokalen Hermes (Antwort-Kasten nicht erkannt)"
    volltext = f"{kopf}:" + "\n" + "\n".join(nutzbar)
    if block_writer is None:
        return volltext

    bloecke = [nutzbar[i:i + ROH_BLOCK_ZEILEN]
               for i in range(0, _anzahl, ROH_BLOCK_ZEILEN)]
    block_writer(f"{kopf} — {_anzahl} Zeilen in {len(bloecke)} Bloecken:")
    for blk in bloecke:
        block_writer("\n".join(blk))
        time.sleep(ROH_BLOCK_PAUSE_S)
    # Die Antwort ist der vollstaendige Text (nicht nur ein Hinweis darauf) -
    # sonst sieht der Nutzer Zwischenmeldungen, aber keine Antwort.
    return volltext


def _stream_json_zeile(s: str):
    """Zerlegt eine Zeile der strukturierten CLI-Ausgabe (``--format stream-json``).

    Warum (Sebastian 2026-09-25): Ohne diese Auswertung landete die Rohtext-
    Ausgabe in der Antwort — samt dem internen englischen Reasoning des Modells
    ("The user just sent ... I should respond briefly ..."). Der Nutzer sah
    Denken dort, wo die Antwort stehen soll.

    Rueckgabe ``(art, text)`` mit ``art``:
      - ``"antwort"``  = Assistenten-Text (gehoert in die Antwort)
      - ``"fertig"``   = Abschlusszeile; ihr Text ist die vollstaendige Antwort
      - ``"gedanke"``  = anderes Ereignis (Werkzeug, Hinweis) → Zwischenmeldung
      - ``None``       = keine JSON-Zeile → die alte Erkennung uebernimmt
    """
    s = (s or "").strip()
    if not s.startswith("{"):
        return None
    try:
        daten = json.loads(s)
    except Exception:
        return None
    if not isinstance(daten, dict) or "type" not in daten:
        return None
    typ = str(daten.get("type") or "")
    if typ == "text":
        return ("antwort", str(daten.get("text") or ""))
    if typ == "result":
        return ("fertig", str(daten.get("text") or ""))
    inhalt = daten.get("text") or daten.get("message") or daten.get("content") or ""
    if isinstance(inhalt, dict):
        inhalt = inhalt.get("text") or ""
    if isinstance(inhalt, list):
        teile = [str(t.get("text") or "") if isinstance(t, dict) else str(t)
                 for t in inhalt]
        inhalt = " ".join(t for t in teile if t)
    return ("gedanke", str(inhalt))


def _art_und_text(s: str, ausgabe):
    """Eine Ausgabezeile einordnen: erst strukturiert, sonst wie bisher.

    Die strukturierte Ausgabe hat Vorrang. Sagt sie ``fertig``, wird das als
    ``("ende", text)`` gemeldet — der Aufrufer ersetzt damit die bisher
    gesammelte Antwort durch die verbindliche Fassung.
    """
    strukturiert = _stream_json_zeile(s)
    if strukturiert is None:
        return ausgabe.zeile(s)
    art, text = strukturiert
    if art == "fertig":
        return ("ende", text)
    return (art, text)


def _beantworte(auftrag):
    aid = auftrag.get("auftrag_id")
    text = (auftrag.get("text") or "").strip()
    kontext = (auftrag.get("kontext") or "").strip()
    if not aid or not text:
        return
    # Session-Kontext aus session_kontext.md (verabredete Infos/Codewort) dem
    # Hermes-Lauf mitgeben, damit eine frische Instanz den Kontext kennt.
    _kontext_file = os.path.join(INBOX, "session_kontext.md")
    try:
        if os.path.exists(_kontext_file):
            with open(_kontext_file, encoding="utf-8") as _kf:
                sess_kontext = _kf.read().strip()
        else:
            sess_kontext = ""
    except Exception:
        sess_kontext = ""
    teile = [text]
    if kontext:
        teile.append(f"[Kontext dieser Hermes-Session (Frontend):]\n{kontext}")
    if sess_kontext:
        teile.append(f"[Persistenter Session-Kontext (verabredet):]\n{sess_kontext}")
    payload = "\n\n".join(teile)
    # Sofortige Statusmeldung (schnelle Rueckmeldung "was der Hermes tut").
    _schreibe_status(
        aid, f"🔧 Hermes bearbeitet die Nachricht (Modell {MODELL})…")

    cmd = ["hermes", "chat"]
    if MODELL:
        cmd += ["-m", MODELL]
    # --format stream-json (Sebastian 2026-09-25): Die CLI gibt damit je Zeile
    # ein JSON-Objekt aus. Der eigentliche Gewinn: die ECHTE Antwort steht als
    # type=text / type=result SAUBER GETRENNT vom internen Reasoning. Vorher
    # wurde die Rohausgabe genommen, wenn der Antwort-Kasten nicht erkannt
    # wurde — dann landete das englische Denken des Modells in der Antwort.
    cmd += ["-q", payload, "-Q", "--format", "stream-json"]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, encoding="utf-8", errors="replace",
        )
    except Exception as e:
        _schreibe_status(aid, f"❌ Hermes-Start fehlgeschlagen: {e}")
        _schreibe_antwort(aid, f"[Fehler] Hermes-Start fehlgeschlagen: {e}")
        return

    # Lese-Thread: entkoppelt das Blockieren der Pipe vom Timeout-Waechter.
    # Vorher lief die for-Schleife direkt auf proc.stdout und konnte unbegrenzt
    # haengen — der 900s-Timeout griff dadurch nie.
    zeilen: "queue.Queue" = queue.Queue()

    def _leser():
        try:
            assert proc.stdout is not None
            for zeile in proc.stdout:
                zeilen.put(zeile)
        except Exception:
            pass
        finally:
            zeilen.put(None)   # EOF-Marker

    threading.Thread(target=_leser, daemon=True).start()

    puffer = []            # [(emoji, zeile), ...]
    ergebnis_zeilen = []
    roh_zeilen = []        # alle echten Ausgabezeilen (für den Not-Fallback)
    letzter_flush = time.time()
    deadline = time.time() + TIMEOUT
    abgebrochen = False
    ausgabe = _CliAusgabe()

    def _flush():
        """Gebündelte Zeilen als EINE Zwischenmeldung schreiben."""
        nonlocal letzter_flush
        if puffer:
            txt = "\n".join(f"{e} {z}" for e, z in puffer)
            _schreibe_status(aid, txt)
            puffer.clear()
        letzter_flush = time.time()

    while True:
        try:
            zeile = zeilen.get(timeout=0.5)
        except queue.Empty:
            zeile = ""
        if zeile is None:
            break
        if zeile:
            z = zeile.rstrip("\n").rstrip("\r")
            s = z.strip()
            if s:
                roh_zeilen.append(s)
                # ANTWORT oder internes Denken? Zuerst die strukturierte Ausgabe
                # auswerten (--format stream-json) — dort ist die Antwort sauber
                # vom Reasoning getrennt. Nur wenn die Zeile KEIN JSON ist,
                # greift die alte Kasten-Erkennung (_CliAusgabe).
                art, text = _art_und_text(s, ausgabe)
                if art == "antwort":
                    ergebnis_zeilen.append(text)
                    puffer.append(("💬", text))
                elif art == "ende":
                    # Die Abschlusszeile ist die verbindliche Fassung. Sie
                    # ERsetzt die bisher gesammelten Bruchstuecke, damit im
                    # Antwortfeld nur die Antwort steht (kein Denk-Text).
                    if text.strip():
                        hatte_blase = bool(ergebnis_zeilen)
                        ergebnis_zeilen[:] = [text.strip()]
                        if not hatte_blase:
                            puffer.append(("💬", text.strip()))
                elif art == "gedanke":
                    if text.strip():
                        puffer.append(("🧠", text.replace("🧠 ", "", 1)))
        # Buendeln: nach FLUSH_S oder bei genug Zeilen rausschreiben.
        if puffer and (time.time() - letzter_flush >= FLUSH_S
                       or len(puffer) >= FLUSH_MAX_ZEILEN):
            # Offene Rückfrage (Frage + "❯ 1. …"-Optionen) NICHT mittendrin
            # ausliefern — sonst zerfällt sie in Einzelblasen und das Frontend
            # kann keine klickbare Abfrage bauen. Not-Aus: FORMULAR_MAX_ZEILEN
            # bzw. FORMULAR_IDLE_S, damit der Puffer nie ewig hängt.
            if not (_formular_haelt_puffer(puffer)
                    and len(puffer) < FORMULAR_MAX_ZEILEN
                    and (time.time() - letzter_flush) < FORMULAR_IDLE_S):
                _flush()
        # Harte Zeitgrenze: Lauf beenden statt ewig warten.
        if time.time() > deadline:
            abgebrochen = True
            try:
                proc.kill()
            except Exception:
                pass
            break
    _flush()

    if abgebrochen:
        _schreibe_status(
            aid, f"⏱️ Zeitbudget von {TIMEOUT}s erreicht — Lauf beendet.")
        _schreibe_antwort(
            aid, f"[Timeout nach {TIMEOUT}s] Der Hermes-Lauf wurde beendet.")
        print(f"[daemon] timeout {aid[:8]}", flush=True)
        return

    try:
        proc.wait(timeout=30)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    # Reihenfolge (Sebastian 2026-09-15): erst die gepufferten
    # Zwischenmeldungen ('Gedanke ...') rausschreiben, DANN das Ergebnis.
    # Vorher erschien das Ergebnis oben und die Statuszeilen wurden
    # darunter nachgeschoben - wirkte wie 'alles auf einmal'.
    _flush()
    ergebnis = "\n".join(ergebnis_zeilen).strip()
    if not ergebnis:
        # KEIN erkannter Antwort-Kasten: statt des früheren „—" (Sebastian sah
        # damit „Hermes hat geantwortet" OHNE jede inhaltliche Ausgabe und
        # konnte nicht beurteilen, ob überhaupt gearbeitet wurde) wird jetzt
        # die echte Rohausgabe geliefert — oder ein Klartext-Grund.
        ergebnis = _roh_fallback(
                    roh_zeilen,
                    block_writer=lambda t: _schreibe_status(aid, t),
                )
    _schreibe_antwort(aid, ergebnis)
    _schreibe_status(aid, "✅ Hermes hat geantwortet.")
    print(f"[daemon] beantwortet {aid[:8]}: {ergebnis[:60]}", flush=True)


def durchgang():
    if not os.path.exists(AUFTR):
        return
    gelesen = _gelesene_ids()
    neue = []
    with open(AUFTR, encoding="utf-8") as f:
        for zeile in f:
            z = zeile.strip()
            if not z:
                continue
            try:
                auftrag = json.loads(z)
            except Exception:
                continue
            aid = auftrag.get("auftrag_id")
            if aid and aid not in gelesen:
                neue.append(auftrag)
    for auftrag in neue:
        _beantworte(auftrag)


def main():
    einmalig = "--einmal" in sys.argv
    print(f"[daemon] start (einmalig={einmalig}) inbox={INBOX} "
          f"modell={MODELL} timeout={TIMEOUT}s", flush=True)
    try:
        os.makedirs(INBOX, exist_ok=True)
    except Exception as e:
        print(f"[daemon] inbox anlegen: {e}", flush=True)
    while True:
        try:
            durchgang()
        except Exception as e:
            print(f"[daemon] throughlauf-fehler: {e}", flush=True)
        if einmalig:
            break
        time.sleep(3)


if __name__ == "__main__":
    main()