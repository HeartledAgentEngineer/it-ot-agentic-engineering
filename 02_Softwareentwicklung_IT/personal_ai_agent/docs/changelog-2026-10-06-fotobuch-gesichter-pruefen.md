# Änderungsprotokoll 06.10.2026 — Prüfwerkzeug: Fotobuch-Fotos in Erkennung und Gruppen?

Meldung Sebastian: Auf den ersten Fotobuch-Seiten (erste Wochen nach seiner Geburt, mit Vater und
Mutter) zeigt das Erzählen „niemand erkannt". Am Handy gezählt (nur Zahlen): **0 von 849**
Fotobuch-Fotos hängen an einer Gesichter-Gruppe (1.106 Gruppen insgesamt).

Die Ursache liegt in Sebastians Daten am PC (`~/foto_sortierung`, für Claude gesperrt). Die Kette
hat zwei Glieder, an denen es reißen kann: die Gesichtererkennung (`gesicht_erkennen.py` arbeitet
eine Auswahlliste ab, Ergebnis `personen_vektoren*.jsonl`) und die Gruppierung
(`personen_gruppieren.py` liest drei bestimmte Vektordateien, Ergebnis
`personen_gruppen/gesicht_zuordnung.jsonl`).

## Neu

`tools/foto_sortierung/fotobuch_gesichter_pruefen.py` — nur lesend, kein Netz, kein Modell. Zählt
für die Fotos aus `fotobuch_ereignisse.jsonl`: Zeile je Vektordatei, davon mit Gesichtern, Zahl der
Gesichter; Fotos mit Gruppe und Zahl der Gruppen; dazu ein Befund-Satz, wo die Kette reißt
(nicht erkannt / keine Gesichter / nicht gruppiert / teilweise / alles da → Handy hat alten Stand).
Ausgabe **nur Zahlen** — keine Kennungen, Namen oder Titel.

Aufruf (PowerShell, aus dem Projektordner):

```powershell
& backend\.venv\Scripts\python.exe tools\foto_sortierung\fotobuch_gesichter_pruefen.py
```

## Prüfung

- Neu `backend/tests/test_fotobuch_gesichter_pruefen.py` (5 Tests, erfundene Kennungen): Zählung je
  Kettenglied, Befund-Sätze, Ausgabe ohne Kennungen/Namen, fehlende Fotobuch-Datei → Exit 2,
  fehlende Zuordnung ohne Wurf.
- Prüfbefehl: siehe Commit.
