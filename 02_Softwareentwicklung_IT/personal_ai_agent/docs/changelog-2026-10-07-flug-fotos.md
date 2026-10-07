# Änderungsprotokoll 07.10.2026 — Fotos aus dem Flugzeug: „Während des Flugs" (Issue #4, A4)

Übergabe Hermes (Issue #4, A4): Die Regel „Flug-Fotos = während des Flugs" soll auch in der
Ortszuordnung gelten. Fensterfotos aus dem Flugzeug haben meist kein GPS, weil der Flugmodus an ist.
Bekommen sie trotzdem eines, liegt der „nächste Ort" irgendwo unter der Flugroute. Beides ergab
falsche Orte.

## Änderung (`tools/foto_sortierung/orte_aus_karte.py`, Betriebsart `--zuordnen`)

Die reine Funktion `flug_bilder(punkte)` erkennt Fotos, die während eines Flugs entstanden sind.

**Abschnitte bilden.** Je zwei zeitlich aufeinanderfolgende Fotos **mit** GPS bilden einen
Abschnitt. Ein **Flugabschnitt** liegt vor, wenn beide Bedingungen gelten:
- Die Fotos liegen mindestens 50 km auseinander (Großkreis-Entfernung).
- Der Schnitt liegt zwischen 250 und 1.100 km/h.

**Grenzen.**

| Fall | Schnitt | Ergebnis |
|---|---|---|
| Autobahn, ICE | unter 250 km/h | kein Flug |
| schneller als ein Linienflug | über 1.100 km/h | GPS-Fehler, kein Flug |
| Sprung unter 50 km | – | Rauschen, kein Flug |

**Welche Fotos als Flug gelten.**
- Fotos **ohne** GPS, die zeitlich innerhalb eines Flugabschnitts liegen. Das ist der Fensterblick
  im Flugmodus.
- Fotos **mit** GPS nur dann, wenn beide angrenzenden Abschnitte Flugabschnitte sind. Start- und
  Zielfoto bleiben damit am Boden.

**Ergebnis in `bild_orte.csv`.** Statt Adresse und Landmarke steht dort
`landmarke = Während des Flugs`, `landmarke_art = flug`. Die Konsole meldet die Anzahl
(„während des Flugs: N"), keine Orte.

Das Erzählen zeigt diese Bilder mit „📍 Ort: Während des Flugs" (`erzaehlOrtText`, seit
`1c2122a`).

Nicht geändert: `orte_zuordnen.py` (GeoNames, `orte.jsonl`). Die Datei wird nur angehängt, und eine
Flug-Markierung bräuchte alle Fotos zugleich. Das bleibt offen, bis `orte.jsonl` neu gebaut wird.

## Prüfung

- `backend/tests/test_orte_aus_karte.py`, 4 neue Tests:
  - Hamburg → Palma mit Fotos ohne GPS dazwischen ergibt Flug. Abflug, Ankunft und das Foto nach
    der Landung bleiben am Boden.
  - Bahnfahrt Hamburg → Berlin ist kein Flug, ein GPS-Sprung ebenfalls nicht.
  - Ein Foto mit GPS mitten im Flug wird als Flug erkannt.
  - Die Zuordnung schreibt „Während des Flugs".
  - Alle 24 Tests der Datei sind grün.
- Prüfbefehl: siehe Commit.
