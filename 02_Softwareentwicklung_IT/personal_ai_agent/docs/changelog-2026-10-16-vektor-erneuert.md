# Ehrliche Rückmeldung beim Speichern eines Gesichts-Rahmens (16.10.2026)

Punkt 0 des Auftrags „Gesichtskorrektur im Detailbild": Das Speichern einer
verschobenen Gesichts-Box meldete Erfolg, auch wenn der Vektor der Referenz
**alt** blieb. Belegter Weg im Befundlauf
(`.hermes/plans/2026-10-16_befund-punkt0-speicherweg.md`): eine Box läuft über
zwei Schreibwege, in beiden rechnete der Server den Vektor nur, wenn
`bild_pfad` vorhanden **und** die Gesichts-Engine verfügbar war; sonst lief der
Aufruf mit `embedding=None` weiter, `if embedding:` griff nicht, und die
Antwort meldete trotzdem `ok: true`.

## Verhalten

- `POST /api/gesichter/referenzen/{name}/{ref_id}/bbox` antwortet zusätzlich mit
  `vektor_erneuert` (bool) und `vektor_grund` (Text, leer wenn `true`).
  `vektor_erneuert` ist die Wahrheit aus der **Speicherung**: `true` nur, wenn
  der Vektor der gespeicherten Referenz in diesem Aufruf wirklich ersetzt wurde
  (`gesichter_service.referenz_bbox_aktualisieren` gibt es zurück).
- `vektor_grund` nennt den ehrlichen Grund in Klartext, wenn kein neuer Vektor
  entstanden ist:
  - „Vektor-Aktualisierung nicht angefordert" (`embedding_erneuern=false` —
    dann wird die Engine gar nicht erst gefragt),
  - „Referenz hat keinen Bildpfad — der Ausschnitt kann nicht neu eingebettet
    werden" (Fall D des Befundlaufs),
  - „Gesichts-Engine (Debian) antwortet nicht" (Fall A),
  - „Ausschnitt-Einbettung fehlgeschlagen — die Engine lieferte keinen Vektor“
    (Fall B),
  - „kein neuer Vektor gespeichert" als Rückfall.
- Unverändert: Rahmen (`bbox`), normalisierter Rahmen (`bbox_norm`) und die
  stabile `ref_id` werden in jedem Fall gespeichert, die Person bleibt dieselbe,
  andere Referenzen derselben Person bleiben erhalten. Auch bei fehlendem neuen
  Vektor ist die Antwort also `ok: true` — jetzt aber mit dem Zusatz, dass der
  Vektor alt ist.

## Tests

`backend/tests/test_gesicht_quiz_fortschritt.py` (Abschnitt 4) prüft die vier
Fälle des Befundlaufs mit erfundenem Katalog in `tmp_path`:

- Fall C (Normalfall): `vektor_erneuert: true`, `vektor_grund` leer, und der
  **Wirkungsnachweis** liest die gespeicherte Katalogdatei roh aus — der neue
  Vektor steht darin, der alte ist weg.
- Fall A: `verfuegbar() == False` → `false` mit Grund „Engine"; die Engine wird
  gar nicht aufgerufen (`pytest.fail` als Wächter), der alte Vektor bleibt.
- Fall B: Engine verfügbar, `embedding_fuer_bbox` liefert `None` → `false` mit
  Grund „Einbettung"; alter Vektor bleibt.
- Fall D: Referenz ohne `bild_pfad` → `false` mit Grund „Bildpfad"; alter Vektor
  bleibt.
- Gegenproben: `embedding_erneuern=false` schreibt keinen Vektor und meldet es;
  der Service allein liefert dieselbe Aussage mit und ohne Vektor.

Die bestehenden Rahmen-Roundtrip-Tests (`-k bbox`) bleiben grün.

## Grenzen

- Die Oberfläche nutzt die neuen Felder seit demselben Tag aus (Schritt A,
  `docs/changelog-2026-10-16-rahmen-anzeige-ehrlich.md`): der Gesichter-Weg
  behauptet eine neue Referenz nur noch im Zweig `if (d.vektor_erneuert)` und
  nennt sonst den Klartext aus `vektor_grund`; der Quiz-/Gruppenweg behauptet
  keine Referenz mehr. Offen bleibt dort der **Inhalt** — der Quiz-Weg speichert
  den erkannten statt des verschobenen Rahmens und meldet den Zustand gar nicht;
  das ist Schritt **A3** (gesperrt, siehe Plan).
- **Welcher** der Fälle A/B/D Sebastians Feldausfall ist, ist ohne einen
  Gerätemesswert offen. Der PC kann die Geräte-Referenzen nicht lesen
  (`gesichter_katalog.json` ist am PC nur eine leere Hülle, 16 Byte).
- Kein Live-Lauf am Gerät: die Wirkung im Feld (Referenz im Katalog verschieben
  und speichern) ist am PC nicht sichtbar und bleibt Sebastians Abnahme.
