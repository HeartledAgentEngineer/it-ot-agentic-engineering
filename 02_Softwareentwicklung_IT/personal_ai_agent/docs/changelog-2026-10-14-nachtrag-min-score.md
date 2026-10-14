# 14.10.2026 — Der Nachtrag ignorierte `--min-score` (und die 4.205 Gesichter sind erklärt)

Nachtlauf am Projekt `personal_ai_agent`. Nur lesend gemessen und lokal geschrieben; kein Netz,
kein Bild, kein Vision-Aufruf, keine Kosten, keine Geräteeingriffe.

## Der offene Punkt, den dieser Lauf schließt

Seit dem 13.10. stand im Plan-Journal (44) ehrlich offen: *„`personen_vektoren_n0929_voll.jsonl`
nennt 4.205 geeignete Gesichter ohne Zuordnungszeile — Ursache nicht abschließend belegt, bewusst
nicht nachgefahren."* Dieselbe Frage stand für `personen_vektoren_n0929_bildervideos.jsonl`.

## Was gemessen wurde (nur Zahlen, je Vektordatei)

Zählung **mit den Funktionen des Werkzeugs selbst** (`zeile_pruefen`, `bild_entscheidung`,
`gesichter_bewerten`, Schlüssel `(bild_id, index)`) gegen die 50.282 Zeilen der bestehenden
`personen_gruppen/gesicht_zuordnung.jsonl`:

| Vektordatei | gruppierbare Gesichter | mit Zeile | ohne Zeile | davon Score < 0,80 | davon ≥ 0,80 |
|---|---|---|---|---|---|
| personen_vektoren_n0929_voll.jsonl | 8.897 | 4.692 | **4.205** | 4.196 | 9 |
| personen_vektoren_n0929_bildervideos.jsonl | 13.426 | 7.598 | **5.828** | 5.812 | 16 |
| personen_vektoren_papa.jsonl | 17.773 | 17.773 | 0 | 0 | 0 |
| personen_vektoren_gedreht_neu.jsonl | 1.887 | 1.881 | 6 | 6 | 0 |
| personen_vektoren_fotobuch.jsonl | 1.934 | 1.934 | 0 | 0 | 0 |
| video_vektoren_bildervideos.jsonl | 9.659 | 9.659 | 0 | 0 | 0 |
| video_vektoren_upload.jsonl | 7.307 | 7.307 | 0 | 0 | 0 |
| **gesamt** | **60.883** | **50.844** | **10.039** | **10.014** | **25** |

**Die Ursache ist damit gemessen, nicht geraten:** 10.014 der 10.039 fehlenden Gesichter haben
einen Erkennungs-Score **unter 0,80**. Der volle Gruppen-Lauf vom 08.10. lief mit
`--min-score 0.8` (Plan: „Neugruppierung `--min-score 0.8`", Empfehlung seit 08.10., weil
Mischgruppen zu 81 % aus Funden unter 0,8 bestehen) — diese Funde wurden dort **bewusst**
draußen gelassen. Es fehlt also keine Zuordnung; die zwei September-Dateien sind einfach nie
erneut bei 0,6 gefahren worden.

## Der zweite Befund: der Schalter tat auf dem Nachtragen-Weg nichts

Nachgemessen mit demselben Aufruf, nur mit und ohne Schalter:

```
personen_gruppieren.py --nachtragen .../personen_vektoren_n0929_voll.jsonl              → Neue Gesichter: 4205
personen_gruppieren.py --nachtragen .../personen_vektoren_n0929_voll.jsonl --min-score 0.8 → Neue Gesichter: 4205
```

Beide Läufe meldeten **dieselben Zahlen**. Grund im Code: `_nachtragen_main()` rief
`gesichter_lesen(pfade, katalog)` **ohne** `min_score` — der Wert der Kommandozeile wurde
still verworfen. Die dokumentierte Schutzwirkung („Funde unter 0,8 bleiben ohne Gruppe") galt
damit nur für den vollen Lauf, nicht fürs Nachträgen.

## Die Änderung (klein, rückwärtsverträglich)

* `_nachtragen_main()` reicht `--min-score` an `gesichter_lesen()` weiter; die Zeile
  `Mindest-Erkennungssicherheit: 0,80 (Voreinstellung 0,60)` erscheint **nur**, wenn der
  Schalter gesetzt ist.
* **Voreinstellung bleibt 0,6** — ohne Schalter ändert sich nichts an bestehenden Aufrufen.
* Modulkopf und `--help` sagen es („gilt auch beim `--nachtragen`").

**Belege:** derselbe Trockenlauf wie oben, nach der Änderung:

```
personen_vektoren_n0929_voll.jsonl          --min-score 0.8 → Neue Gesichter: 9   (vorher 4205)
personen_vektoren_n0929_bildervideos.jsonl  --min-score 0.8 → Neue Gesichter: 16  (vorher 5828)
```

Beide Zahlen stimmen **exakt** mit der unabhängigen Zählung oben (9 und 16). Neue Testfunktion
`test_cli_nachtrag_beachtet_min_score_der_kommandozeile` in
`backend/tests/test_personen_gruppieren_nachtragen.py` (Datei 25 → **26 passed**) prüft beides:
ohne Schalter zählt ein Fund mit Score 0,70, mit `--min-score 0.8` bleibt er draußen.

## Ehrlich offen (Entscheidung, nicht Nachtarbeit)

Die Nachtrags-Läufe für Papas Fotos, die Videos und das Fotobuch liefen **mit der Voreinstellung
0,6** — der Personenkatalog trägt deshalb viele Gesichter unter 0,80 (gemessen, exakte Scores):
Papas Fotos **5.041 von 17.773**, Videos der Sammlung 4.474 von 9.659, Upload-Videos 3.417 von
7.307, Fotobuch 340 von 1.934, Neuausrichtung 1.008 von 1.881 — zusammen **14.781 von 50.844**.
Ob der Nachtrag künftig ebenfalls bei 0,8 fahren soll (und ob die vorhandenen Funde unter 0,8
herausgenommen werden), ist eine **Entscheidung für Sebastian**: ein Herausnehmen würde benannte
Gruppen verkleinern. Nichts davon wurde geändert — die Voreinstellung ist unverändert 0,6.

Nicht angefasst: `bestand_pruefen.py` (samt Testdatei) liegt weiterhin **fremd und halbfertig** im
Arbeitsbaum (Arbeit des Master-Chats zur ausgelieferten Frontend-Dateiliste) — die Prüfzeile
„Vektor-Gesichter gegen Zuordnungszeilen" gehört dorthin und bleibt deshalb blockiert. Nichts
gelöscht, nur eigene Pfade committet.
