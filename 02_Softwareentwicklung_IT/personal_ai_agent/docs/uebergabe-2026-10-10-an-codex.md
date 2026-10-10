# Übergabe an Codex — 10.10.2026, 13 Uhr

**Anlass:** Codex übernimmt die Leitung am Projekt `personal_ai_agent`. Diese Datei enthält
alles, was dafür nötig ist — Stand, Regeln, laufende Arbeiten, offene Schritte, Fallen.
Sie setzt **keine** Kenntnis des bisherigen Gesprächsverlaufs voraus.

---

## 1. Die bindenden Regeln (nicht verhandelbar)

**Prüfbefehl vor jedem Commit:**

```
cd 02_Softwareentwicklung_IT/personal_ai_agent/backend
.venv/Scripts/python -m pytest tests/ -q      # muss Exit 0 liefern
```

Der Prüfbefehl läuft als Haken automatisch vor jedem Commit (`tools/gate/tor.py`) und dauert
**8 bis 12 Minuten**. Nicht abbrechen, nicht mit `--no-verify` umgehen.

**Committen:**

- Niemals `git add -A`, niemals `git commit -a`. Es liegen oft fremde, halbfertige Änderungen
  im Baum. Immer `git commit --only <ausdrücklich genannte Pfade>`.
- **Code und Doku gehören in denselben Commit** (Changelog unter `docs/`, Zeile im
  Änderungsprotokoll der Projekt-`CLAUDE.md`).
- Nach grünem Prüfbefehl: **autonom pushen** (stehende Freigabe), danach
  `git rev-list --left-right --count origin/main...HEAD` auf `0 0` prüfen.
- Bei abgelehntem Push: `git pull --rebase`, erneut versuchen. **Niemals `--force`.**

**Was niemals passiert:**

- **Nichts löschen.** Nur kopieren und verschieben. Vor jedem Ersetzen eine Sicherung.
- Keine privaten Daten ins Repository: keine Bilder, keine Chatarchive, keine Schlüssel.
  `Chats von GPT, GEMINI, Claude/` bleibt gesperrt.
- Keine Zugangsdaten ausgeben (Schlüssel liegen in `.env`-Dateien, nur lesend verwenden).

**Sprachen:** Code-Kommentare, Doku und Berichte **deutsch**; Bezeichner, Feldnamen,
Modellnamen **englisch**.

**Fertig ist, was verifiziert ist:** Vor jeder Aussage „fertig", „grün", „läuft" den Beleg
frisch ausführen und die Ausgabe nennen. Frühere Läufe und Erfolgsmeldungen anderer Agenten
sind keine Belege.

---

## 2. Was gerade läuft (Stand 13:00)

| Arbeit | wie prüfen | Stand |
|---|---|---|
| Gesichtserkennung Papas Fotos (6.336) | `wc -l ~/foto_sortierung/personen_vektoren_papa.jsonl` | über 4.500 von 6.336 |
| Kartenauswertung (Orte) | `ls ~/foto_sortierung/osm/csv/` — Unterordner `*-latest` | 7 Gebiete fertig |

**Alle Beschreibungsläufe sind abgeschlossen** (siehe Abschnitt 3) — es läuft dort nichts mehr.

**Fortschritt anzeigen:** `werkzeuge/fortschritt/fortschritt.py --terminal` (Wahrheit:
`status.json`, HTML: `.hermes/widgets/fortschritt.html`, Cron alle 2 Minuten).

**Wichtig:** Läuft ein Beschreibungs- oder Gesichterlauf, ist die Maschine ausgelastet — die
Testsuite braucht dann länger als sonst. Das ist kein Fehler.

---

## 3. Was fertig ist (mit Zahlen)

- **Bildbeschreibungen auf neuem Niveau: ABGESCHLOSSEN — 25.352 Bilder für 9,66 USD.**
  Dateien: `bild_beschreibungen_reich.jsonl` (17.428 · 6,67 USD),
  `bild_beschreibungen_papa_reich.jsonl` (6.336 · 2,37 USD),
  `bild_beschreibungen_rest_reich.jsonl` (984 · 0,39 USD),
  `bild_beschreibungen_altbestand_reich.jsonl` (604 · 0,24 USD).
  Die letzten drei Läufe endeten mit **0 Fehlern**; die 5 fehlgeschlagenen Bögen des ersten
  Laufs sind nachgelaufen. Diese Dateien liegen **neben** dem alten Bestand
  `bild_beschreibungen.jsonl` (19.065 kurze Stichworte) — **nicht überschreiben**, Sebastian
  entscheidet später, was gilt. **889 Bilder** existieren nur noch im alten Bestand
  (in der Cloud nicht mehr auffindbar) — ihre alten Stichworte bleiben erhalten.
- **Ortsnamen: 8.530 Bilder** (`orte.jsonl`), lokal und kostenlos nachgetragen.
- **Papas 32 Archive entpackt**, 6.336 Dateien (16,1 GB).
- **Der Modellvergleich ist entschieden:** `google/gemini-3.8-flash`, gemessen
  **0,0003412 USD je Bild**. Verworfen: `ling-3.0-flash-vl` (46× billiger, aber Subjektfehler),
  `gemini-2.5-flash-lite` (formelhaft).
- **Ein Startweg fürs Handy** (Commit `7082e48`): App-Knopf und Widget rufen dieselbe
  Ablaufdatei `termux/start-vorbereiten.sh` (Pull → Einrichtung → Wissensdatei → Start).
- **Wissensdatei-Übernahme** (Commit `307a938`): sichert vor dem Ersetzen, kopiert nur bei
  abweichender Prüfsumme, protokolliert belegbar.
- **Zwei lebende Fortschrittsbalken** im Dashboard (Commit `75b2f0d`).

---

## 4. Die offene Kette (in dieser Reihenfolge)

Jeder Schritt gilt als fertig, wenn sein Prüfkriterium erfüllt ist.

1. **Gesichter fertig laufen lassen.** Prüfkriterium: `personen_vektoren_papa.jsonl` hat
   **6.336 Zeilen**. Danach Ortsnamen nachtragen:
   `backend/.venv/Scripts/python.exe tools/foto_sortierung/orte_zuordnen.py --eingabe "<die Datei>" --schreiben`
   Prüfkriterium: `orte.jsonl` wächst um den GPS-Anteil; zweiter Lauf = 0 neu.
2. **Gruppen andocken** (NICHT neu gruppieren — das zerreisst die 644 benannten Gruppen):
   `tools/foto_sortierung/personen_gruppieren.py --nachtragen "<vektordatei>" --schreiben`
   Vorher die Handy-Vorgaben holen (`tools/handy/namen_aus_sicherung.py --uebernehmen`).
   Prüfkriterium: zweiter Lauf meldet 0 neu.
3. **Anlässe** für Papas Fotos: `ereignisse_ordner_bauen.py`
   (`ereignisse_bauen.py` geht hier NICHT — braucht eine Anlässe-Liste im Plan).
4. **Bildsuche aufbauen — für ALLEN Bestand, sie fehlt komplett:**
   `tools/foto_sortierung/bild_index_einbetten.py`. Es gibt **keine** `bild_index.db`.
   Ohne sie findet der Agent kein Bild über seinen Inhalt. Kosten deutlich unter 0,10 USD.
5. **Standort aus der Karte** (wenn der Kartenstapel durch ist):
   `orte_aus_karte.py --zusammenfassen` und `--zuordnen --ordner …/osm/csv`. Ergebnis ist
   `bild_orte.csv` — die es derzeit **nirgends** gibt. Bringt „nächste Straße, nächste Stadt,
   nächste Landmarke" je Bild.
6. **Doppelte prüfen** (nur Prüfsumme, es wird nichts gelöscht):
   `tools/pcloud/pcloud_duplikate.py`. **Nicht parallel** zu einem anderen pCloud-Lauf.
7. **Übergabe ans Handy** und **Nachweis**: `tools/handy/…`, `bestand_pruefen.py`.

**Nicht parallel:** Schritte 2 und 3 brauchen fertige Vektoren; 6 nicht neben einem
pCloud-Schwall; 7 erst ganz am Ende.

---

## 5. Fallen, die heute teuer gelernt wurden

- **Ein vereinter Plan kann still verkleinert werden.** Aus 28.796 Einträgen wurden beim Lauf
  nur 17.604 — Papas 6.336 fielen heraus, **ohne Fehlermeldung**. Lehre: Nach jedem Lauf die
  abgedeckten Bildkennungen gegen den Plan stellen, nicht der Zusammenfassung glauben.
- **Zwei Feldnamen-Formen in Plänen:** `von_name`/`von_ordner` **oder** `name`/`ordner`.
  Einträge ohne Namen werden verworfen. `gedreht_plan.json` und `fotobuch_plan.json` enthalten
  **nur** `fileid` — sie sind für dieses Werkzeug unbrauchbar, bis Namen ergänzt sind.
- **Die Tokengrenze je Kachel hängt an der Prompt-Fassung.** Zu knapp gesetzt wirken die
  Antworten abgeschnitten und sehen wie schlechte Modellqualität aus (so wurde ein Modell zu
  Unrecht verworfen). Reiche Fassung: `MAX_TOKENS_JE_KACHEL_BILDGESCHICHTE = 160`.
- **Preise müssen zum Modell passen** (`--preis-ein/--preis-aus`), sonst rechnet die Budgetgrenze
  falsch. Gemessene Werte siehe Abschnitt 3.
- **Wackler in der Testsuite:** `test_widget_agent_start.py` (lief in eine zu knappe
  20-Sekunden-Frist, inzwischen auf 90 gesetzt) und selten `test_chat_endpoint.py`
  (Windows-Dateisperre). Bei Rot **nur dort**: isoliert dreimal laufen lassen und im Bericht
  nennen — nicht umgehen.
- **Das Handy:** Der Termux-Heimordner ist per Kabel **nicht** lesbar. Server anhalten mit
  `input keycombination 113 31`, danach **prüfen** (`/api/health` muss 000 liefern) — bleibt sie
  200, ist die Eingabeaufforderung nicht frei, dann **nicht** weitertippen.

---

## 6. Was Sebastian noch tun muss

**Am Handy ist die Einrichtung erledigt und geprüft** (10.10., 12:58). Ablauf am Gerät, belegt
im Protokoll:

- Brücke angelegt: `~/agent-ensure.sh` → `<Projekt>/termux/agent-ensure.sh` (die alte Kopie
  kann nicht mehr veralten)
- `allow-external-apps=true` gesetzt — der App-Knopf darf Termux befehlen
- **Wissensdatei übernommen: 123,6 MB → 230,4 MB**, Prüfsumme Quelle = Ziel (`2ac72bf3…`),
  alte Fassung gesichert als `~/memory.db.vor_2026-10-10`
- Server gestartet, antwortet mit **200**

**Damit ist WhatsApp erstmals im Zugriff des Agenten** (241.402 Nachrichten, 481 Gespräche —
der Import war immer vollständig, es fehlte nur die Übernahme in den Heimordner).

Offen für Sebastian:

1. **Im Chat ausprobieren, was jetzt durch WhatsApp möglich ist** — vorher wusste der Agent
   davon nichts.
2. Optional: neues APK installieren (`android/app/build/outputs/apk/debug/app-debug.apk`).
3. Laufende Arbeiten laufen lassen; das Dashboard zeigt den Fortschritt.

Ab jetzt genügt der **App-Knopf**: Stand holen, Wissensdatei übernehmen, Server starten.
Beleg bei jedem Antippen in `/sdcard/Download/hermes_diag/wissensdatei_uebernahme.log`.

---

## 7. Nicht anfassen

- `~/foto_sortierung/bild_beschreibungen.jsonl` (der alte Bestand) — nur lesen.
- Die gesperrten Chatarchive, `.hermes/` (interne Arbeitsweise), Bewerbungsunterlagen.
- Laufende Prozesse anderer Agenten (Fortschritts-Cron, Nachtlauf) — nicht neu starten,
  nicht beenden.
