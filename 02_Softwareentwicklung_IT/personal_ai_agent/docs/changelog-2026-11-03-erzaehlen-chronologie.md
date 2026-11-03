# Changelog 03.11.2026 — Anlässe wirklich nach Datum sortiert

## Fehler (Rückmeldung von Sebastian am Handy)

Bei „↓ Neueste zuerst" standen die Anlässe nicht in Datumsfolge. Ein Anlass von 2024 erschien zum Beispiel an dritter Stelle.

## Ursache

- `_ereignisse_laden` hängt die Quellen aneinander: zuerst die Fotobuch-Seiten in Buchreihenfolge, dann `ereignisse.jsonl`. Sortiert wurde nur, wenn es auch Ordner-Anlässe gab.
- „Neueste zuerst" hat diese Liste nur umgedreht (`treffer.reverse()`).
- Anlässe ohne Datum und Jahr haben den Schlüssel „9999". Chronologisch stehen sie damit hinten, nach dem Umdrehen also ganz oben.

## Jetzt

- `ereignisse_liste` sortiert selbst nach Datum, über alle Quellen und in beiden Richtungen.
  - Hat ein Anlass nur ein Jahr, steht er am Ende dieses Jahres.
  - Bei gleichem Datum bleibt die Reihenfolge der Quellen.
- Anlässe **ohne Datum und Jahr stehen in beiden Richtungen am Ende**. Sie sind aus der Chronologie herausgenommen und können später von Hand eingeordnet werden.
- Filter (Jahr, Suche, Mindestzahl Bilder) und Blättern wirken wie bisher auf die sortierte Liste.

## Bewusst geänderte alte Tests

Zwei Tests in `test_ereignisse_ordner_bauen.py` hielten genau das fehlerhafte Verhalten fest:
- Eine Fotobuch-Seite ohne Datum stand ganz vorne. Jetzt steht sie am Ende.
- Ohne Ordner-Datei blieb die Dateireihenfolge erhalten, also 2019 vor 2015. Jetzt gilt die Datumsfolge. Der Test heißt jetzt `test_ohne_ordner_datei_wird_trotzdem_nach_datum_sortiert`.

## Prüfung

- 2 neue Tests in `test_erzaehlen_reihenfolge.py` (beide Richtungen, Fotobuch + Ereignisse + ein Anlass ohne Datum + einer nur mit Jahr), vorher rot. Die Ausgabe vorher zeigte genau das Symptom: ohne Datum auf Platz 2, 2024 ganz unten.
- Alle Erzähl-, Fotobuch- und Anlass-Tests grün (489).

## Noch offen (nicht Teil dieser Reparatur)

- „Viele Anlässe mit nur einem Bild": Das ist eine Frage der Gruppierung beim Erzeugen der Anlässe (`tools/foto_sortierung`), nicht der Sortierung. Sie muss getrennt untersucht werden.
