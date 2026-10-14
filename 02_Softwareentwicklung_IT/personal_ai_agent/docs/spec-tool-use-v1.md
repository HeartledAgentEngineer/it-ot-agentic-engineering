# Spec: Tool Use v1 — der Agent wählt seine Werkzeuge selbst

Stand: 30.09.2026, Claude (Dauerlauf, Auftrag Sebastian 20:25: „Tool Use integrieren, damit der
Agent schlauer wird und nicht so in Fehler reinläuft"). Vorgänger: `.hermes/plans/2026-08-28_tool-use-architektur.md`
(damals geplant, nie umgesetzt).

## 1. Problem (belegt)

Heute sitzt vor dem Modell eine **Vorab-Weiche** in `router/chat.py` (Stream-Weg ab Z. ~2017):
`_archiv_tool` → sonst `_datei_tool` → sonst `_verlauf_tool` → `_gesicht_suche_tool` →
`_fotos_uebersicht_tool` → `_beziehungen_tool`. Jede rät aus Wörtern der Frage, ob sie zuständig
ist; die **erste** Trefferquelle hängt Text an die Frage, danach antwortet das Modell **einmal**.

Folgen, im Alltag gesehen:
- **Nur eine Quelle je Frage.** „Schau dir mein Foto an **und** such Beispiele im Verlauf" geht
  nicht: Wörter wie „Foto" schalten die Archivsuche ab (`_ARCHIV_AUSSCHLUSS`, `chat.py:1025/1169`)
  — 30.09.2026 morgens am Handy passiert.
- **Wortraten statt Verstehen.** Die Dateisuche vergleicht Stichwörter nur mit dem Dateinamen
  (`datei_suche.py:186`); „Foto von der Tabelle" sucht „tabelle" in `IMG_2026…jpg`.
- **Kein Nachfassen.** Findet die Weiche nichts, kann das Modell nicht selbst weitersuchen.

## 2. Ziel

Das Modell bekommt einen **Werkzeugkasten** (Namen, Beschreibung „wann benutzen", Parameter) und
entscheidet selbst, welche Werkzeuge es in welcher Reihenfolge aufruft — wie Claude Code, Hermes
oder Gemini. Das Backend führt aus, gibt das Ergebnis zurück, das Modell ruft weiter oder antwortet.

## 3. Entscheidungen

| # | Entscheidung | Begründung |
|---|---|---|
| E1 | **Natives Function-Calling** (OpenAI-Format `tools`/`tool_calls`), kein Text-Protokoll | Standardmodell `deepseek/deepseek-v4.1-flash` kann laut OpenRouter `/models` (30.09.2026) `tools` + `tool_choice` + Bildeingabe; 0,02 $/M Eingabe, 0,396 $/M Ausgabe. Damit entfällt Weg B aus dem Plan vom 28.08. |
| E2 | **Schalter `tool_use`, Standard AUS** (Konfiguration + je Anfrage `werkzeuge: true`) | Verhalten bleibt unverändert, bis Sebastian live getestet hat. Rückweg = Schalter aus. **Abgelöst 01.10.2026:** Standard AN, Knopf weg, Rückfall ohne Werkzeuge bei Fehler vor dem ersten Text (`docs/changelog-2026-10-01-werkzeuge-immer-an.md`). |
| E3 | **Nur lesende Werkzeuge** in v1 | Keine Schreib-, Lösch-, Sende- oder Kostenaktion ohne eigenen Beschluss. |
| E4 | Werkzeuge sind **dünne Hüllen um bestehende Dienste** | Kein neuer Datenzugriff, keine neue Datenquelle; erprobter Code (mit Tests) bleibt die Wahrheit. |
| E5 | Bei `werkzeuge=an` **entfällt die Vorab-Weiche** (Archiv/Datei/Verlauf/Gesicht/Fotos/Beziehungen) | Sonst doppelte Quellen und doppelte Kosten; das Modell entscheidet. Erinnerungen, Zusammenfassung, Uploads und Websuche bleiben wie bisher. |
| E6 | **Obergrenzen:** höchstens 5 Runden, 4 Aufrufe je Runde, 6.000 Zeichen je Ergebnis; Fehler kommen als Text zurück, nie als Absturz | Schutz vor Schleifen, Kosten und übergroßem Kontext. |
| E7 | **Sichtbar im Chat:** je Aufruf eine Statuszeile („🔧 durchsucht Handy-Dateien …") | Nachvollziehbar wie in Claude Code; Sebastian sieht, *warum* eine Antwort so ausfällt. |
| E8 | **Bilder aus Werkzeugen** gehen als Bild-Teil einer Folgenachricht an das Modell (Tool-Nachrichten tragen nur Text) | So verlangt es das Chat-Format; übliches Harness-Muster. |
| E9 | Dateipfade in `datei_ansehen` nur **innerhalb der freigegebenen Wurzeln** (`realpath`-Prüfung) | Das Modell könnte sonst beliebige Pfade vorschlagen (Pfad-Ausbruch). |
| E10 | Datenfluss **wie heute**: Ergebnisse gehen an das gewählte Modell über OpenRouter; `no_retention` wirkt weiter | Die Vorab-Weiche schickt dieselben Inhalte schon heute mit; Gesichtsvektoren verlassen das Gerät nie (kein Werkzeug liefert sie). |

## 4. Werkzeuge v1

| Name | Zweck (Beschreibung fürs Modell, gekürzt) | Dienst |
|---|---|---|
| `dateien_suchen` | Dateien auf dem Handy finden (Fotos, Screenshots, PDFs, Dokumente); Name, Art, neueste zuerst, Jahr, Tag | `datei_suche.suche_dateien` |
| `datei_ansehen` | Eine gefundene Datei öffnen: Text lesen oder Bild ansehen | `datei_suche.lese_datei_info` |
| `archiv_suchen` | Alte Gespräche (ChatGPT, Gemini, Claude …) nach Thema durchsuchen — **inklusive WhatsApp-Vollbestand** (Standardweg: voller Index zuerst, sonst der alte Dienst) | `archiv_standard.StandardArchiv.hybrid` |
| `notizen_suchen` | Sebastians **eigene** App-Notizen: Personen-Notizen (Beziehung, Beruf, Vorlieben) und Geschichten an Ereignissen; mit `person=Name` alle Notizen einer Person (07.10.2026) | `notizen_service.text_antwort` |
| `erinnerungen_suchen` | Gemerkte Fakten über Sebastian abrufen | `memory_service.retrieve_relevant_memories` |
| `fotos_uebersicht` | Übersicht der sortierten Fotos: Anlässe, Jahre, Zahlen | `foto_uebersicht.text_antwort` |
| `fotos_mit_person` | Fotos/Videos mit einer bestätigten Person: Datei, Aufnahmedatum, Ordner (aus dem Personen-Quiz; Notnagel: alte lokale Gesichtssuche) | `gruppen_quiz.bilder_mit` + Beschreibungs-Index (Notnagel `gesicht_fotos.suche_bilder_mit_person`) |
| `personen_liste` | Welche Personen der Agent kennt (aus dem Personen-Quiz; Notnagel: alter Katalog) | `gruppen_quiz.personen` (Notnagel `gesichter_service.liste_personen`) |
| `person_auskunft` | Alles über EINE Person: Beziehung, eigene Notizen, Geburtstag, Zahl der Fotos, Anlässe (10.10.2026) | `gruppen_quiz.person` + `gruppen_quiz.bild_kennungen_person` + `erzaehl_service.anlaesse_zu_kennungen` |
| `wer_war_wann` | Was an einem Datum belegt ist: wer mit wem, Fotos, Chats | `beziehungen_service.text_antwort` |

Bewusst **nicht** in v1: pCloud-Suche (`pcloud_service.suche` ist nicht rekursiv — eigener
Schritt), Verlaufssuche (Zusammenfassung + letzte Nachrichten liegen schon im Kontext), jede
schreibende Aktion (Erinnerung speichern, Datei anlegen, Hermes beauftragen).

## 5. Ablauf (Harness)

```
Frage → Nachrichten (System + Erinnerungen + Verlauf + Frage)
  ↳ Runde n (≤ 5): Modell mit tools=[…] aufrufen (gestreamt)
       Text-Häppchen      → sofort an die Oberfläche
       tool_calls (≤ 4)   → Status „🔧 …" → Werkzeug ausführen → Ergebnis als role=tool
                            (Bilder als eigene Nutzernachricht mit image_url)
       keine tool_calls   → fertig
  ↳ Runde 5 erreicht → letzter Aufruf mit tool_choice="none" (muss antworten)
```

Module:
- `app/services/werkzeuge.py` — Register: `Werkzeug(name, beschreibung, parameter, ausfuehren)`,
  `Ergebnis(text, bilder)`, `schemata()`, `ausfuehren(name, argumente_json)`.
- `app/services/werkzeug_schleife.py` — die Schleife; der Modellaufruf ist einsetzbar
  (Tests laufen mit einem simulierten Modell, ohne Netz).
- `llm_service.chat_stream(..., werkzeuge=True)` → nutzt die Schleife.
- `router/chat.py` (Stream-Weg) — bei `werkzeuge=an` keine Vorab-Weiche.

### Websuche mit Namensverbot (seit 14.10.2026, ersetzt die Themensperre)

- **Allgemeines, Orte und Adressen dürfen gesucht werden** (Wetter, Fahrzeit zu Oma und Opa,
  Öffnungszeiten). Verboten sind **Personennamen aus Sebastians Leben**.
- **Der Hauptaufruf sucht nie selbst:** `llm_service._extra_body` setzt weder das Plugin `web`
  noch `openrouter:web_search`. Einziger Weg ins Netz ist `app/services/web_suche.py::suchen`.
- **Kontextfrei:** `suchen(anfrage, nutzer_nachricht)` schickt einen eigenen OpenRouter-Aufruf mit
  genau einer Nachricht (dem geprüften Suchtext), Plugin `web`, `data_collection: deny` — kein
  Verlauf, keine Erinnerungen, kein Systemtext.
- **Modi:**
  - `auto` (Werkzeug-Weg): Das Modell bekommt das Werkzeug `web_suche(anfrage)`. Bei `off` und
    `manual` fehlt es im Schema; ein erfundener Aufruf antwortet „Websuche ist aus.“
  - `manual`: Vorab-Suche in `router/chat.py::_websuche_vorab` mit Sebastians eigenem Satz; das
    Ergebnis hängt als „[Websuche zu deiner Frage]“ an der Nachricht, Quellen gehen mit.
  - `auto` auf Wegen ohne Werkzeuge (`/chat`, Rückfall): keine Suche.
- **Namensprüfung** (`app/services/websuche_schutz.py`):
  - Bestand aus `werkzeuge.bekannte_namen_streng()`: bestätigte, zugeordnete und Profilnamen aus dem Quiz, der alte Katalog
    und WhatsApp-Kontakte mit mindestens zwei Wörtern (`whatsapp_zuordnung.json`).
  - Namensteile aus dem Personenbestand zählen ab 2 Zeichen, volle Namen immer; Kontakte nur als
    volle Folge. Umlaute ä/ae usw., Groß-/Kleinschreibung egal, Endungen `s`, `'s`.
  - Liste nicht lesbar, beschädigt **oder leer** (`None`) → keine Suche: `werkzeuge.bekannte_namen_streng()`
    liefert `None`, sobald eine vorhandene Quelle unlesbar ist oder der Bestand insgesamt leer ist
    (ein leerer Bestand ist von „nichts zu schützen“ nicht zu unterscheiden); `websuche_schutz.enthaelt_namen`
    sperrt dann jede Suche (`app/services/websuche_schutz.py`).
  - **Länge:** Vom **Modell** formulierte Suchtexte sind auf `web_suche.MAX_ANFRAGE_MODELL` = 200 Zeichen
    begrenzt; längere werden nicht gesucht („Suchanfrage zu lang (über 200 Zeichen) – nicht gesucht“,
    `app/services/web_suche.py`). Sebastians eigener Satz im Modus `manual` bleibt ohne diese Grenze.
  - **Freigabe** nur aus Sebastians eigener Nachricht mit Suchauftrag („Such im Internet nach
    Sebastian Fremdmann“): öffnet die Teile eines fremden vollen Namens, nie einen bekannten
    vollen Namen, nie einen bekannten Nachnamen. Modelltext gibt nie frei.
  - Bei Ablehnung: Statuszeile „🔒 …“, das Log nennt nur Zähler.
- **Weicher Riegel:** `werkzeuge.SYSTEM_HINWEIS`: „Suche im Internet nie nach Personennamen aus
  Sebastians Leben …“
- **Grenzen:** Namen nur aus Archiv/Erinnerungen, Vornamen allein aus Kontakten und andere
  Umschriften („Myller“) werden nicht erkannt; die Suchmaschine formuliert ihre Anfrage selbst
  (sie kennt aber nur den Suchtext); eine bewusste eigene Freigabe („Such im Internet nach Ida
  Geburtstag“) geht durch.
- **DSML-Filter:** Schickt DeepSeek einen Werkzeugaufruf als Text (`<｜DSML｜…`), zeigt die Schleife
  ihn nicht an.
  - Kam vorher noch kein Antworttext, wirft sie `DsmlAlsText`, und `chat_stream` antwortet ohne
    Werkzeuge.
  - Kam schon Text, erscheint eine Statuszeile.
  - Die Ursache für DSML im Text ist **nicht** geklärt; eine Messung steht aus.
- **Grenze:** Eine Suchanfrage, die schon gesendet wurde, lässt sich nicht zurückholen.

## 6. Prüfung

- Offline-Tests: Register (Schemata gültig, unbekanntes Werkzeug, kaputte Argumente, Pfad-Ausbruch),
  Schleife (0/1/mehrere Aufrufe, Obergrenzen, Bildweg, Fehler im Werkzeug, Text + Werkzeug gemischt),
  Schalter aus = alter Weg unverändert.
- Prüfbefehl `backend/.venv/Scripts/python.exe -m pytest tests/ -q` grün.
- **Live (mit Sebastian, Schalter an):** die Frage vom 30.09. morgens („Schau dir mein letztes Foto
  an und such im Archiv Beispiele dazu") ruft `dateien_suchen` → `datei_ansehen` → `archiv_suchen`;
  Kosten je Frage aus dem OpenRouter-Protokoll ablesen.

## 7. Danach (nicht v1)

- **v2:** pCloud rekursiv, Verlaufssuche, „merken"-Werkzeug mit Bestätigung.
- **Träumen / Konsolidierung:** nächtlicher Lauf (Anker: Nachtjob N23) — Tagesgespräche
  durchgehen, Fakten und Vorlieben verdichten, Fehlgriffe der Werkzeugwahl sammeln und die
  Werkzeug-Beschreibungen daraus verbessern.
- **Auswertung:** feste Fragenliste (20 Alltagsfragen) mit erwarteten Werkzeugen, damit Änderungen
  an Beschreibungen messbar besser oder schlechter werden.
