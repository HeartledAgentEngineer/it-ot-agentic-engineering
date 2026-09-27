# Screenshot-Vorsortierung: brauchbar oder Müll? (N6-Fortsetzung)

> **Datum:** 27.09.2026 · **Auftrag:** „Im pCloud-Bestand sind Screenshots als
> Anlässe klassifiziert — sind die brauchbar oder Müll? Kann man sie
> vorsortieren (Müll / brauchbar) und nach Themen ordnen?"
> Rahmen: `docs/plan-foto-personen-und-erinnerungen.md` (Foto-Sortierung).
> **Nur lesend:** kein Löschen, kein Verschieben, kein Download der Originale.

## Warum es diesen Schritt gibt

Der Screenshot-Bestand in `Bilder & Videos/Screenshots` wird bei der
Anlass-Bildung als Sammel-Anlass geführt. Für die Zielstruktur
`Agent/Fotos/<Jahr>/<Thema>/` ist aber vor allem eine Frage offen: **welche
Screenshots will Sebastian überhaupt behalten** — und welche sind Systemdialog,
Fehlermeldung oder Versehen? Dieses Werkzeug beantwortet das mit EINEM
Vision-Blick je Screenshot (billigste Stufe zuerst) und einer festen, kleinen
Auswahl statt freier Beschreibungen.

## Was gebaut wurde

| Datei | Inhalt |
|---|---|
| `tools/foto_sortierung/screenshots_triage.py` | Screenshot-Ordner lesen, **je Bild ein** Vision-Aufruf, Einordnung + Thema + Befund in eine JSONL |
| `backend/tests/test_screenshots_triage.py` | **31 Prüfungen** — alles ohne Netz (pCloud-Attrappe, Vision-Attrappe, httpx gesperrt, Ausgaben nach `tmp_path`) |
| `backend/app/services/pcloud_service.py` | **additiv:** erlaubte Vorschaugrößen um `480x480` und `800x800` erweitert (live geprüft 27.09.2026) |
| `backend/app/router/cloud.py` | **additiv:** dasselbe Größenmuster für `/api/cloud/thumb` (Vorgabe bleibt `120x120`) |
| `backend/tests/test_pcloud_service.py`, `test_pcloud_router.py` | je 1 Prüfung für die größeren Vorschaubilder (**+2**) |

## Rechenweg (je Bild, billigste Stufe zuerst)

1. **Ordner finden:** `listfolder` ab der Wurzel → `Bilder & Videos` →
   `Screenshots`; Unterordner (live: einer mit 6 Bildern) werden mitgenommen.
   Je Ebene genau **eine** Anfrage, keine rekursiven Kontoscans. Nicht-Bilder
   (z. B. `desktop.ini`) werden übersprungen: **149 Bilddateien** gefunden.
2. **Nur das Vorschaubild** über den bestehenden Dienst:
   `pcloud_service.thumb(fileid, groesse)` — **kein Original-Download**.
3. **Nur im Arbeitsspeicher:** Bytes → base64 → `data:`-URL in **einem**
   `POST {basis}/chat/completions` (Vision-Modell, Standard
   `google/gemini-2.5-flash`; Temperatur 0). Das Bild wird nicht kopiert, nicht
   zwischengespeichert, nicht auf Platte gelegt.
4. **Antwort zerlegen** (JSON-Zäune/Text davor/danach; kaputt = Fehlerzeile,
   kein Raten) und in die feste Auswahl normalisieren.

Der OpenRouter-Weg (Transport mit Wiederholungen, Zerlegung, Schlüssel-Schutz,
Kostenrechnung, Schlüssel-Suche) ist **aus `foto_themen_vision.py`
wiederverwendet** — kein zweiter Kopfsatz, sondern dasselbe Modul per Pfad
geladen.

### Vorschaugröße: 800x800 statt 120x120 (gemessen, nicht geraten)

Die erste Stichprobe lief mit der bisher einzig sinnvollen Größe `120x120`.
Ergebnis (25 Bilder): **11 von 25 „unklar"**, im Befund durchweg „Text nicht
lesbar" — Screenshots bestehen überwiegend aus Text, 120x120 reicht zum Lesen
nicht. Vorher live geprüft (27.09.2026, `getthumbs`): der Endpunkt liefert auch
`480x480` und `800x800` in **derselben** Textzeile
(`fileid|0|masse|data:image/jpeg;base64,…`), Auflösung z. B. 515x800 statt
77x120. Deshalb wurden die **erlaubten** Größen des Dienstes additiv erweitert
(Vorgabe des Dienstes bleibt `120x120`, die App ändert sich nicht) und das
Werkzeug nutzt `800x800` als Standard. Mehrkosten je Bild: ~2 000 statt ~400
Eingabe-Tokens, also Bruchteile eines Cents (siehe Messung unten). Weiterhin
ein Vorschaubild, weiterhin kein Original.

## Die fünf Klassen (feste Grenzen)

| Klasse | Bedeutung (so steht es im Prompt) |
|---|---|
| `muell` | Systemdialog, Fehlermeldung, versehentlich aufgenommen, Statusleiste, leerer Bildschirm, Einstellungen ohne Nutzen |
| `behalten-nuetzlich` | Ticket, Termin, Bestätigung, Rechnung, Adresse, Rezept, Karte, Fahrplan — etwas, das später gebraucht wird |
| `behalten-persoenlich` | Chat mit Menschen, Meme, Foto, Sprachnachricht-Screenshot, Profil, wichtiger Moment |
| `unklar` | nicht entscheidbar — **auch jede Antwort, deren Klasse nicht in der Liste steht** |

**Themen** (ebenfalls fest, WORT FÜR WORT im Prompt): `Chat | Ticket | Termin |
Rechnung | Karte | Meme | Systemdialog | Fehlermeldung | Einkauf | Rezept | Foto
| Video | Sonstiges`. Unbekanntes wird `Sonstiges`.

**Befund:** eine Zeile, höchstens 100 Zeichen, ohne Namen von Personen, ohne
Adressen, ohne Telefonnummern (so steht es im Prompt; der Befund wird zusätzlich
auf eine Zeile gekürzt und über `geheimnis_entfernen` entschärft).

## Kostenbremse

* `--kosten-obergrenze` (Standard **0.10 USD**): **vor jedem Bild** wird geprüft,
  ob die aufgelaufenen Kosten die Grenze erreicht haben; dann **sauberer
  Abbruch** mit deutscher Meldung — alles Bearbeitete steht vollständig in der
  Ausgabe, Exit-Code bleibt 0, die restlichen Bilder macht der nächste Lauf.
* `0` (oder kleiner) schaltet die Bremse **ausdrücklich ab**.
* Preise je 1 Mio Tokens: Standard sind die **live von OpenRouter `/models`
  gelesenen** Preise von `google/gemini-2.5-flash` (`0.30` ein / `2.50` aus,
  Stand 27.09.2026); `--preis-ein`/`--preis-aus` überschreiben sie. Bei einem
  **anderen** Modell ohne eigene Preise warnt das Werkzeug, dass die Kostenzahl
  eine Annahme ist.
* Bezahlt wird nur, was läuft: bereits eingeordnete Bilder werden
  übersprungen (Fortsetzungspunkt), `--wiederholen` erzwingt einen neuen Blick.

## Ausgabe (ausschließlich außerhalb des Repos)

`~/foto_sortierung/screenshots_triage.jsonl` — **anhangend**, eine Zeile je
Bild, sofort geflusht:

```json
{"datei": "Screenshot 2023-04-03 175707.png", "fileid": 53971499832,
 "ordner": "", "zeit": "2026-09-27T22:24:33",
 "klasse": "behalten-nuetzlich", "thema": "Rechnung",
 "befund": "Eine Tabelle mit der Aufschlüsselung von Miete und Nebenkosten …",
 "tokens": 2235, "tokens_ein": 2177, "tokens_aus": 58,
 "kosten_usd": 0.000798, "modell": "google/gemini-2.5-flash"}
```

Fehlerzeilen (Netz, fehlendes Vorschaubild) haben statt `klasse` ein Feld
`fehler` und werden beim nächsten Lauf **erneut** versucht — nur eine Zeile
ohne `fehler` **und** mit `klasse` gilt als erledigt. Der Schrägstrich-Schutz
bleibt: zeigt `--ausgabe` ins Repo (Groß-/Kleinschreibung und Schräg-/
Rückwärtsstrich egal), bricht der Lauf mit Exit 2 ab, bevor etwas geholt,
gesendet oder geschrieben wird — auch bei `--trocken`.

## Was ausdrücklich NICHT passiert

* **Kein Löschen, kein Verschieben** — im Quelltext gibt es keinen solchen
  Befehl (eine Prüfung sucht danach), und der pCloud-Dienst des Backends kennt
  keine Schreibmethode. Gegenüber der pCloud wird nur gelesen
  (`liste` + `thumb`).
* **Keine Bilddatei auf der Platte** — geschrieben wird genau eine Textzeile je
  Bild. Zwei Prüfungen belegen das: eine im Quelltext (kein
  `open(..., "wb"/"ab")`) und eine zur Laufzeit (im Ausgabeordner liegt danach
  keine Datei mit Bildendung).
* **Kein Original-Download**, kein zweiter Anbieter, kein Codex.
* **Kein Name Dritter** im Befund (Prompt-Regel) — und der Schlüssel bleibt
  geheim (nie geloggt, nie gedruckt, aus Antworten entfernt).

## Messung (echter Lauf, 27.09.2026)

Stichprobe: `--grenze 25` auf 149 gefundenen Bilddateien (erste 25 in
Sortierreihenfolge: Ordner, dann Name — reproduzierbar).

| Lauf | Klassen | Themen | Kosten | Dauer |
|---|---|---|---|---|
| **Pilot 120x120** | 13× behalten-nützlich, 11× unklar, 1× behalten-persönlich, **0× Müll** | Rechnung 2, Chat 1, Einkauf 1, Sonstiges 21 | **0.009620 USD** | 44.4 s |
| **Standard 800x800** (mit `--wiederholen`, dieselben 25) | 23× behalten-nützlich, 1× behalten-persönlich, 1× unklar, **0× Müll** | Rechnung 5, Ticket 1, Chat 1, Sonstiges 18 | **0.018756 USD** | 58.8 s |

Lesart: bei 800x800 fällt „unklar" von 44 % auf 4 %, die Befunde werden konkret
(„Strom- und Nebenkostenabrechnung für eine Wohngemeinschaft", „Reisebuchung
mit Flugdaten, Hoteldetails und Gesamtpreis"). **0× `muell`** unter den ersten
25 Dateien (2022–2023) — die ältesten Screenshots sind überwiegend Studium
(Diagramme, Formeln, Schaltpläne) und WG-Abrechnungen, also behaltenswert. Ob
weiter hinten im Bestand Systemdialoge/Fehlermeldungen liegen, beantwortet der
Restlauf (siehe unten). **Keine Bilddatei** wurde dabei geschrieben — der
Ausgabeordner enthält nur die JSONL (50 Zeilen = beide Läufe, anhangend).

## Beleg-Neustartbefehl

```bash
cd backend
.venv/Scripts/python -m pytest tests/test_screenshots_triage.py -q     # 31 grün, ohne Netz
.venv/Scripts/python ../tools/foto_sortierung/screenshots_triage.py --trocken
.venv/Scripts/python ../tools/foto_sortierung/screenshots_triage.py --grenze 25
```

Pilot mit der alten Vorschaugröße wiederholbar:
`--grenze 25 --wiederholen --groesse 120x120`.
Rest des Bestands (149 Bilder, ~0.11 USD, also **Grenze anheben**):
`--grenze 0 --kosten-obergrenze 0.20`.

## Offene Reste

* **Nur die ersten 25 angesehen** (Auftrag war die Stichprobe). Der Rest sind
  124 Bilder ≈ 0.10–0.12 USD; ob dort `muell` auftaucht, ist damit noch offen.
* **Themenliste passt auf Studium/Technik schlecht**: „Diagramm", „Formel",
  „Notizen" fehlen — 18 der 25 landen deshalb in `Sonstiges`. Die Liste ist
  Vorgabe; eine Erweiterung wäre ein eigener, kleiner Schritt.
* **Kein Verschieben** ist Absicht: das Werkzeug sortiert nur auf Papier
  (JSONL). Ein späteres Einsortieren in `Agent/Fotos/` gehört in einen eigenen
  Auftrag mit Manifest und Trockenlauf (Muster `pcloud_bewegungen.py`).
* Die Stichprobe ist nach Namen sortiert, nicht nach Datum; die ältesten
  Dateien (2022/2023) kommen also zuerst. Für eine Stichprobe über den ganzen
  Bestand wäre ein Zufallsmuster (oder `--grenze 0`) nötig.
