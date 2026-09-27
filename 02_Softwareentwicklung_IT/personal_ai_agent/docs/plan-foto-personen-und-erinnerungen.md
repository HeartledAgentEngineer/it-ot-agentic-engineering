# Plan: Fotos + Videos sortieren, Personen clustern, Erinnerungen speichern

> **Stand:** 26.09.2026 · **Auftrag:** Sebastian
> „Bilder und Videos clustern, sortieren — alle Fotos und Videos. Danach das
> Cluster für die **Personen mit Referenzen** aufbauen, damit ich später nur
> noch **benennen** muss, weil die Personen sind alle noch nicht benannt.
> Später kommt mein **Fotobuch aus der Kindheit** dazu, und dann erzähle ich
> pro **Event, Urlaub, Person, Tag, Szene** — und wir müssen überlegen, wie wir
> diese **Erinnerungen zu den Bilddaten** speichern."

Diese Datei ist der Rahmen. Was fertig ist, trägt ein ✅ mit Beleg; was offen
ist, ein ⬜.

---

## Stufe 1 — Sortierschlüssel ✅ (fertig, `59cd11b`)

`tools/foto_sortierung/sortierschluessel.py` liest **nur Namen und Größen** im
pCloud-Upload-Ordner (kein Bild geöffnet, pCloud unverändert) und schreibt eine
CSV **außerhalb des Repos** (`~/foto_sortierung/sortierschluessel.csv`).

Gemessen (1,44 s): **9.430 Dateien**, 8.302 mit Datum, 1.128 offen (49,1 GB,
überwiegend Videos). Fenster **2022–2026: 7.792 Dateien ≈ 45,5 GB**.
2023 liegt fast ganz beim OnePlus (Gerätewechsel).

## Stufe 2 — Themen-Clustering: Fotos **und Videos** 🟡 (fast fertig: Werkzeuge stehen, Massenlauf offen)

Ziel: `Agent/Fotos/<Jahr>/<Thema>/…` (Vorgabe B von Sebastian) — als **Kopie**,
Originale bleiben unberührt.

1. **Vorschaubilder statt Originale.** Über die API (`getthumbs`, 120×120) —
   das ist der Grund, warum der Zugang (Stufe 0) so wichtig war: 9.430 × ~10 KB
   statt 45 GB Downloads. **✅ live gemessen** (N4): 4–6 KB je Vorschau, Videos
   (mp4) und HEIC bekommen ebenfalls ein JPEG; ein echter erster Frame per
   `ffmpeg` bleibt unnötig für die Themen-Stufe (nur für später notiert).
2. **Kontaktbögen** (Kacheln mit Nummern) je Tag/Anlass, nicht je Bild.
   **✅ N4:** `tools/foto_sortierung/foto_themen.py`, 25 Prüfungen, zwei Bögen
   live gebaut (1382×362 mit 10 Kacheln, 1382×872 mit 36 Kacheln).
3. **Vision-Blick** auf den Bogen → eine Zeile je Kachel + Markerzeile der
   Treffer. **✅ N5/N6:** einmal gesehen (Nummern 1–36 einwandfrei lesbar, Thema
   je Bogen erkennbar, unbrauchbare Kacheln werden benannt) und als Werkzeug
   gebaut: `tools/foto_sortierung/foto_themen_vision.py`, 53 Prüfungen.
4. **Thema je Anlass** statt je Bild (gleiche Minute = gleicher Anlass).
   **✅ N6:** ein Vision-Aufruf je Anlass statt je Bild; live an zwei Anlässen
   gemessen (0,0023–0,0044 $ je Anlass, 3,6–6,8 s). Für alle **2.128 Anlässe**
   ist der Massenlauf offen (`themen.jsonl` ist der Fortsetzungspunkt).
5. **Kopie** in die Zielstruktur, `INDEX.md` + Kontaktbogen als Übersicht. ⬜ offen
   (nächste Schritte N7 Probelauf / N8 echtes Sortieren im Nachtlauf-Plan).

Kosten: Vision-Calls **je Bogen**, nicht je Bild. Nichts wird ins Backend
kopiert — Bilder leben nur im Speicher des Analyse-Calls (Sebastians Regel).

## Stufe 3 — Personen clustern (unnamed first) ⬜

Bereits vorhanden **auf dem Handy**: `backend/face_infer.py` (YuNet-Erkennung +
SFace-Erkennung, ONNX, mit EXIF-Drehung), `gesichter_service.py`,
`face_service.py`, `router/gesichter.py`, `gesicht_quiz.py` (Quiz-Fragen
JA/NEIN je Gesicht), `sortiere_gesichter.py`, `trainiere_gesichter.py`.
Arbeitet heute nur auf `~/storage/dcim/Lieblingsbilder` (455 Bilder, gezählt).

**Ablauf, wie Sebastian ihn will:**

1. **Alle Gesichter finden** (Fotos aus dem pCloud-Bestand, in Jahres-Stapeln,
   weil Gesichtserkennung echte Auflösung braucht — Vorschaubilder reichen nicht).
2. **Unbenannte Gruppen bilden**: SFace-Vektoren clustern (DBSCAN/HDBSCAN),
   Schwellwert an echten Daten einstellen, nicht raten.
3. **Stabile Kennungen** vergeben: `Person_001`, `Person_002`, … —
   **noch ohne Namen**.
4. **Je Gruppe eine Referenzseite** (5–10 beste Gesichter) — das ist die
   „Referenz", die später nur noch benannt werden muss.
5. **Benennen später**: Quiz/App zeigt Gruppe → Sebastian sagt den Namen →
   Katalog (`gesichter_katalog.json`, lokal, nie im Repo) bekommt den Namen.
   **Wichtig:** Die Kennung bleibt, nur der Name kommt dazu — sonst zeigen
   bereits erzählte Erinnerungen ins Leere.

**Offene Entscheidung:** Wo rechnen — **Handy** (Modelle + Katalog + Quiz sind
dort) oder **PC** (hat `P:\`, mehr Rechenleistung, aber Modelle/Katalog müssten
dorthin)? Vorschlag: **PC rechnet, Handy benennt** — Clustern über die API
in Jahres-Stapeln, Naming im Quiz auf dem Handy.

## Personen-Regeln: Massen- vs. Gruppenfotos (verbindlich, Sebastian 27.09.2026)

> Wörtlich: „Da muss natürlich keine Person verpixelt werden — eine große Masse,
> wie bei Konzerten. Aber nur, wenn es Gruppenfotos sind und die Personen nicht
> so weit weg sind. Also Massenfotos: im Vordergrund gucken, ob da bekannte
> Personen sind — sonst weglassen."

1. **Menschenmengen** (viele Personen, weit entfernt, nicht identifizierbar —
   Konzerte, Veranstaltungen, volle Hallen): **keine Verpixelung nötig.**
   Sie dürfen thematisch sortiert und im Kontaktbogen gezeigt werden.
   **Aber:** kein Gesichts-Anlernen, **kein Personen-Cluster, keine
   Referenzseiten** aus Mengen.
2. **Gruppen-/Nahaufnahmen** (Gesichter groß und erkennbar): wie geplant —
   unbekannte Gesichter werden **geclustert und später benannt** (Sebastians
   Wunsch), bekannte dem Katalog zugeordnet. Biometrische Daten (Vektoren)
   bleiben **ausschließlich lokal** (nie ins Repo, nie an ein Fremd-LLM).
3. **Vordergrund-Prüfung bei Mengen:** Enthält ein Massenfoto im **Vordergrund**
   eine **bekannte** Person (Katalog) → wird diesem Menschen zugeordnet
   (normales Foto). Enthält es **nur** fremde Menge → **weglassen**: nicht ins
   Clustering, keine Referenz, nur thematisch einsortieren.
4. **Schwelle statt Gefühl:** „Menge oder Gruppe" entscheidet der **Code** über
   **Gesichtsgröße** (Anteil der Bildfläche) und **Anzahl** erkannter Gesichter —
   nicht der Augenschein. Der Schwellwert wird an einer Stichprobe eingestellt
   und im Changelog dokumentiert.
5. **Reihenfolge bleibt:** Kein Gesicht wird benannt, bevor Sebastian es
   bestätigt hat. Fremde Gesichter erzeugen **unbenannte** Gruppen
   (`Person_001` …) — nur so, wie er es will.

## Stufe 4 — Sebastians Erinnerungen zu den Bildern ⬜ (Design)

Sebastian erzählt pro **Event / Urlaub / Person / Tag / Szene**. Diese Texte
sind der eigentliche Schatz („Memorial LifeBrain") und brauchen ein eigenes
Zuhause — **nicht** in der Foto-Ablage, **nicht** im Repo.

**Vorschlag: getrennte Ablage, strukturiert + durchsuchbar.**

| Feld | Inhalt |
|---|---|
| `id` | stabile Kennung der Erinnerung |
| `art` | `event` \| `urlaub` \| `person` \| `tag` \| `szene` |
| `titel` | kurze Bezeichnung („Usedom 2023") |
| `text` | **Sebastians Erzählung im Wortlaut** — nie überschreiben, nie glätten |
| `zeitraum` | von/bis, wenn bekannt |
| `personen` | Kennungen aus Stufe 3 (`Person_004` — Name kommt später) |
| `fotos` | **pCloud-IDs** (`fileid`) — keine Bilddateien, kein Kopieren |
| `ort` | wenn genannt |
| `quelle` | `Sebastian-Diktat` + Datum |
| `version` / `history` | wie im Gedächtnis-Dienst: neue Fassung aktiv, alte bleibt |

**Ablage:** eigene Datei **außerhalb des Repos** (z. B.
`~/foto_erinnerungen/erinnerungen.jsonl`) + Einbettungen für die semantische
Suche über **OpenRouter** (wie die Erinnerungen heute: „nur die Suchanfrage
verlässt das Gerät, keine Bilder, keine Archive").

**Warum so und nicht im Gedächtnis-Dienst:** Der Gedächtnis-Dienst ist für
**Fakten und Zustände** gebaut („Ich habe einen Hund namens Rex"), nicht für
lange Erzählungen mit Bildbezug. Trennung hält beides sauber — und die Suche
kann später beides verbinden („zeig mir Usedom 2023" → Erinnerung + Fotos).

**Sicherheitskanten (bleiben):** Fotos werden nie ins Backend kopiert; Inhalte
gehen nie an ein Fremd-LLM (auch nicht an Codex/Claude/OpenAI); das Archiv und
diese Erinnerungen sind **nicht** Teil des Repos.

## Reihenfolge (verbindlich)

1. **Stufe 2** (Themen) — Voraussetzung: Cloud-Zugang im Backend (läuft) + API-Vorschau.
2. **Stufe 3** (Personen) — parallel vorbereitbar: Cluster-Verfahren + Referenzseiten.
3. **Naming-Durchgang** mit Sebastian (Quiz) — erst danach ist „Person_004" ein Mensch.
4. **Stufe 4** (Erinnerungen) — jederzeit möglich, braucht nur die Ablage.
5. **Fotobuch aus der Kindheit** — späterer, eigener Import (Scanner-Fotos ohne
   EXIF: Aufnahmedatum muss erzählt oder geschätzt und als Schätzung markiert werden).
