# Abschlussbericht Nachtlauf 10./11.10.2026 — Papas Fotos, Chat, Personen

Auftrag (Sebastian, 10.10. ca. 05:05): „Lass dich die Nacht noch weiter laufen, wenn das
sinnvoll ist." Regeln: `AGENTS.md`, Abschnitt „Dauerlauf / Nachtarbeit" — keine Rückfragen,
jeden Schritt einzeln verifizieren und committen, nichts löschen, keine kostenpflichtigen
Massenläufe ohne Entscheidung, kein Geräteeingriff am Handy.

Plandatei mit allen Schritten und dem Journal: `.hermes/plans/2026-10-10_nachtlauf-papas-fotos-und-chat.md`.
Alle Zahlen hier stammen aus echten Läufen dieses Werkzeugsatzes (Exit 0), nicht aus
Erfolgsmeldungen.

## Die nummerierten Schritte

| # | Schritt | Stand |
|---|---|---|
| 1 | Papas restliche Archive entpacken | **erledigt** — 32/32, 6.336 Dateien, 16,1 GB |
| 2 | Chat-Layout-Fehler messbar machen | **erledigt** — Wächter misst jetzt auch den Verlauf |
| 3 | Personen-Daten im Chat anbinden (A + B) | **erledigt** |
| 4 | Hey-Agent-App bauen (nur bauen) | **erledigt** — APK 9.723.147 Byte, nicht installiert |
| 5 | Bildbeschreibungen: Preistabelle + Modellwahl | **erledigt** — Entscheidung `google/gemini-3.8-flash` |
| 6 | Abschlussbericht | **dieses Dokument** |
| 7 | Anlässe einer Person | **erledigt** — Verknüpfung Gesicht → Ereignis steht |

## Papas Fotos — die Kette ist durch

Was aus dem Stand „32 Archive, 6.336 Dateien" geworden ist:

| Stufe | Ergebnis (gemessen) |
|---|---|
| Gesichtserkennung | **6.336 von 6.336 (100,0 %)**, 6.090 mit Gesicht, 0 Fehler |
| Beschreibungen (reiche Fassung) | **6.336 von 6.336 (100,0 %)**, Eigenkosten 2,37 USD |
| Gruppen | **9.821 Gesichter an 202 bestehende Gruppen angedockt**, 373 neue Gruppen |
| Anlässe | **779 der 2.268 Anlässe** enthalten Papa-Fotos |
| Gesamtdeckung Beschreibungen | 23.908 von 23.916 Fotos (100,0 %) in allen vier Dateien zusammen |

Der wichtigste Fund des Laufs steckt in der Gesichtserkennung: Der Lauf war um 14:56 bei
**6.311 von 6.336** stehengeblieben, die Nachläufe meldeten „Loecher: 24, Fehler: 0" — nur
eine Zahl. **Ursache belegt:** Die 24 Fotos sind 9,2–15,2 MB groß und überschritten die feste
Kachelgrenze `KACHEL_MAX_BYTES = 8 MB` (`PCloudZuGross`); `kachel_holen` verwarf sie still als
`None`. Die Dateien existieren (`getfilelink` result=0) und sind ladbar (`datei_bytes` liefert
9–13 MB) — **kein Datenverlust, eine Konstante.** Mit `--max-bytes 25165824` kamen alle 24
herein. Das Werkzeug nennt den Grund jetzt und zeigt den Nachholweg
(`changelog-2026-10-10-kachelgrenze-luecke.md`).

Zweiter Fund: Der Nachweis `bestand_pruefen.py` meldete „8 Fotos ohne Beschreibung" nur als
**Zahl**; die Kennungen waren von Hand nachgerechnet. Jetzt benennt er sie mit Kennung und
Grund — **3 ohne Bildmasse** (nicht ladbar), **5 geladen ohne Beschreibungseintrag**
(`changelog-2026-10-10-luecken-benannt.md`). Der Verdacht „doppelter Dateiname" ist dabei
widerlegt: `plan_zeilen_lesen()` entdoppelt nur über `fileid`.

## Was noch offen ist (ehrlich)

1. **25 Videos ohne Gesichter-Lauf** (`sortierplan_bildervideos.json`). Nachgemessen: **alle 25
   sind größer als die 300-MB-Grenze des Werkzeugs** (320 MB bis 2,5 GB, zusammen rund 15 GB);
   das Werkzeug meldete korrekt `zu_gross: 25`. Sie wären kostenlos, aber 15 GB Download plus
   Frame-Auswertung — bewusst **nicht** in dieser Nacht gefahren. Daneben: 96 weitere Videos
   sind als „fertig" markiert (`.videos_fertig`), haben aber keine Vektorzeilen — die
   naheliegende Erklärung ist „verarbeitet, kein Gesicht erkannt", belegt ist sie nicht.
2. **8 Fotos ohne Beschreibung** — die 5 „geladen, kein Eintrag" haben kein Protokoll; ein
   Nachzieh-Lauf wäre **kostenpflichtig** und ist Sebastians Entscheidung. Kein solcher Lauf
   wurde gestartet.
3. **OSM / `bild_orte.csv` (Schritt 3c):** 14 Gebiete fertig ausgewertet, **bayern läuft**
   (letztes); danach fehlen noch `--zusammenfassen` und `--zuordnen` (erzeugt `bild_orte.csv`).
   Die Datei existiert weiterhin **nirgends** — die frühere Annahme „liegt auf dem Handy" ist
   widerlegt.
4. **Übergabe ans Handy (Schritt 9)** — `gesicht_zuordnung.jsonl`, `personen_beispiele.json`,
   `kennungen.json` sind neu/gewachsen, `ordner_ereignisse.jsonl` ist neu. Das ist ein
   Geräteeingriff und bleibt bei Sebastian.
5. **WhatsApp-Verdrahtung** — braucht Messung am Handy (Kabel), nicht am PC.
6. **673 Gruppen mit Zwillingsverdacht** (vorher 382) — nur zur Sichtung markiert, nie
   automatisch zusammengelegt.
7. **`bild_index.db`** (Einbettung der Beschreibungen) und **`personen_register`/`bild_person.jsonl`**
   existieren weiterhin nicht.

## Prüfstand dieses Laufs

- Prüfbefehl (Hook-erzwungen): `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  → **3.703 passed, 2 skipped, Exit 0** (letzter Lauf dieses Berichts).
- `bestand_pruefen.py` am echten Bestand: **Exit 0**, Ergebnis „4 Luecke(n)" — die vier oben
  benannten, jede mit Kennung/Grund bzw. als Video-Lücke.
- `personen_gruppieren.py --nachtragen`: zweiter Lauf **0 neu** (idempotent).
- `ereignisse_ordner_bauen.py`: zweiter Lauf **„unverändert"** (idempotent).
- Gesichtslauf: 6.336 Zeilen, 24 nachgeholt, 0 Löcher, 0 Fehler.

## Commits dieses Laufs (alle gepusht, lokal = remote `0 0`)

| Commit | Inhalt |
|---|---|
| `a9b451c` | `bestand_pruefen.py` benennt fehlende Fotos mit Kennung und Grund |
| `464a0de` | Kachelquelle nennt den Grund, wenn ein Bild nicht geladen wird |
| (Doku) | Papas Gruppen/Anlässe + dieser Abschlussbericht |

Es wurde immer **nur** mit `git commit --only <Pfade>` gearbeitet — nie `git add -A`; fremde
Änderungen im Baum (typeFREE, docs/experimente, status.json, Rechercheseiten,
`pcloud_agent_schreiber.py`) blieben unangetastet.
