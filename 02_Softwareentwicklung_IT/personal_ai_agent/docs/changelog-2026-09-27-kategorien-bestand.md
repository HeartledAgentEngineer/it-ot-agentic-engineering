# Sebastians Bild-Kategorien — Bestandsaufnahme und was daraus folgt

> **Stand:** 27.09.2026 · **Anlass:** Sebastian: „Du kannst ja meine Kategorien bei
> Videos und Bilder in der pCloud sehen — sortiere auf Tags und Blöcke, die man
> dann Events zuordnet (Geburtstage, Familienveranstaltungen, Ausflüge, Urlaube)."
>
> **Wichtig zur Veröffentlichung:** Diese Datei beschreibt nur **Struktur und
> Muster**. Die konkreten Ordnernamen enthalten **Namen Dritter** und Orte — sie
> liegen **lokal** in `~/foto_sortierung/kategorien.json` und kommen **nicht**
> ins Repo (Regel: Archivinhalte bleiben privat).

## Was in der pCloud schon sortiert ist

Ordner `Bilder & Videos` — **18 Kategorien, 113 Unterordner**, davon 10 mit
Unterordnern. Kategorien mit Unterordnern: Ausflüge, Familie, Freunde, Hobbys,
Konzerte_Party, **Urlaub**, Schule, Screenshots, WG, Demos.

Die übrigen Kategorien sind flache Sammlungen (Dateien direkt im Ordner),
u. a. Phasen (BFD, Duales Studium), Lieblingsbilder und einzelne Themen.

## Die drei Namensmuster, die Sebastian selbst benutzt

| Muster | Beispiel-Form (ohne konkrete Namen) | Bedeutung für den Agenten |
|---|---|---|
| **Jahr + Ort/Anlass** | „2015 Ostseeküsten-Fahrradtour", „2021_07 Usedom" | **Event** = Zeitraum + Ort. Aus unseren Datums-Blöcken ableitbar |
| **Jahr_Monat + Ereignis** | „2018_07 …", „2019_03_08 …" (Band/Termin) | Konzert-/Party-Events sind **datierbar** → Block ↔ Ordner zuordenbar |
| **Jahr + Person** | Jahres-Ordner mit Namen, „2021 … bei Timmy" | **Personen** sind Teil des Event-Namens → Hinweise für die Personen-Stufe |

**Nebenbefund, der viel Arbeit spart:** Die bereits sortierten Ordner sind eine
**fertige Lehrprobe** — Motiv-Thema + Datum + Ort ergeben genau die Kategorie,
die Sebastian selbst gewählt hat. Der Agent muss die Kategorien also nicht
erfinden, sondern **nachbauen**.

## Was daraus folgt (neue Schritte im Nachtlauf-Plan)

* **N6d — Zielkatalog aus Sebastians Ordnern.** Die 53 erfundenen Themen bleiben
  als **Motiv-Erkennung** (was ist zu sehen), kommen aber **nicht** als
  Zielordner in Frage. Zielordner sind ausschließlich **seine** Kategorien.
* **N6e — Event-Abgleich.** Je Datums-Block prüfen, ob ein bestehender
  Event-Ordner desselben Zeitraums existiert (Urlaub/Ausflüge/Konzerte_Party
  tragen Jahr/Monat). Treffer → **Vorschlag** „Ordner X" statt Neubau.
* **N7/N8 unverändert**, aber Zielstruktur:
  `Agent/Fotos/<Jahr>/<Kategorie>/<Eventname>` — **verschieben**, nie löschen,
  jede Bewegung im Manifest.
* **N9 — Namens-Hinweise:** Ordnernamen liefern Kandidaten-Namen für
  Gesichtsgruppen. Sie werden **nur als Vorschlag** geführt und erst nach
  Sebastians Bestätigung zugewiesen (Biometrie bleibt lokal).

## Was das für „Event-Clustern" bedeutet (Stand heute, ehrlich)

| Ebene | Stand |
|---|---|
| Datums-Blöcke (Tag/Anlass) | ✅ läuft (2.128 Anlässe, Motiv-Themen werden gesetzt) |
| Sebastians Kategorien | 🔜 sofort machbar (Vorlage vorhanden) |
| Event-Namen („Usedom 2021") | 🔜 ableitbar über Zeitraum-Abgleich; Rest über Sebastians Erzählung (Stufe 4) |
| Personen/Freunde clustern | ❌ noch nicht gebaut — Originale + Gesichterkette + Bestätigung nötig |

## Wiederholbar

`tools/foto_sortierung/foto_kategorien.py` (geplant, N6d) liest diesen Bestand
**nur lesend** und schreibt ihn nach `~/foto_sortierung/kategorien.json`.
Ergebnis-Zahlen von heute: **18 Kategorien · 113 Unterordner · 10 mit
Unterordnern · 17 Urlaubs-Ordner**.
