# Mehrfachbearbeitung der Rahmen mit Einzelmeldungen (Schritt C, 18.10.2026)

**Auftrag:** Rahmeneditor im Detailbild, Planfassung 13 (freigegeben 16.10. 13:18),
Abschnitt 4, **Schritt C**: „Markierte Rahmen werden nacheinander abgearbeitet; je Rahmen
ein Ergebnis."

**Was gebaut ist**

- **Neu `rahmenIndizes(e)`** (`frontend/app.js`): liefert die Indizes aller Plätze in
  `bbox_norm_live`, die einen **vollständigen** Rahmen tragen. Lücken aus der Erkennung
  (`null`) sind keine Rahmen und werden nicht mitgezählt.
- **Neu `speichereAlleRahmen(iw, ih, btn)`** — der Mehrfachweg. Er arbeitet die Rahmen
  **nacheinander** ab (je Rahmen ein `await`, kein gleichzeitiges Senden), sammelt je Rahmen
  ein **Ergebnis** `{ idx, ok, fehler, grund, meldung }` und schreibt **genau eine Meldung
  je Rahmen** („Rahmen 2 von 3: NICHT gespeichert — …") plus eine Zusammenfassung
  („2 von 3 Rahmen gespeichert"). Der Knopftext zeigt den Fortschritt (`… 2/3`).
- **`speichereEditorRahmen(...)` gibt jetzt ein Ergebnis zurück** und hat einen
  **Fehler-Fang** (`.catch`) im Quiz-Weg. Vorher endete ein gerissener Netzweg in einer
  unbehandelten Ablehnung — der sequenzielle Ablauf wäre danach stehengeblieben und die
  restlichen Rahmen wären nie erreicht worden.
- **`stillSammeln`** (optionaler fünfter Parameter): während der Mehrfachbearbeitung meldet
  der Einzelweg nicht selbst, sondern sammelt seinen Text ein. Sonst stünde jeder Rahmen
  zweimal in der Leiste.
- **Werkzeugleiste:** bei **zwei oder mehr** Rahmen entsteht neben „💾 Speichern" der Knopf
  **„💾 alle N"** — **nur im Zweig `speicherZiel.ok`**, der Riegel aus Schritt A2 gilt also
  unverändert. Bei einem einzigen Rahmen ist der Knopf überflüssig (derselbe Weg).
- Cache-Schlüssel `app.js?v=20261016F` → **`G`**.

**Prüfkriterium des Plans — Test mit drei Rahmen, davon einer kaputt**

Neuer Test `frontend/tests/test_quiz_rahmen_mehrfach.js` (6 Abschnitte A–F). Er **führt die
echten Funktionen aus** (Sandkasten mit Attrappen der Nachbarn) und zählt die Sendeversuche:

- **A** drei Rahmen, keiner kaputt → **3 von 3** gespeichert, genau 3 Sendeversuche,
  4 Meldungen (3 Einzelmeldungen + Zusammenfassung).
- **B** **drei Rahmen, der mittlere kaputt** (der zweite Sendeversuch wird abgelehnt) →
  **2 von 3** gespeichert, `sends === 3`: der Ablauf läuft nach dem Fehler **weiter**, der
  kaputte Rahmen meldet seinen Fehler **einzeln** („Rahmen 2 von 3: NICHT gespeichert —
  … Netz weg"). **Kein Rahmen verliert seine Markierung:** die Rahmenliste bleibt
  zeichengleich, auch der kaputte Rahmen behält seine Person-Markierung (sie wird vor dem
  Senden gesetzt).
- **C** Lücken in der Rahmenliste werden nicht als Rahmen gezählt (`[0,2]` bei drei Plätzen).
- **D** ohne Ziel wird für **jeden** Rahmen ehrlich gemeldet und **nichts** gesendet.
- **E** Gegenprobe: die alte Fassung ohne Fehler-Fang hätte nach dem ersten Fehler nur
  **1** Versuch erreicht — der Test misst also wirklich den Unterschied.
- **F** Verdrahtung: Knopf nur bei `rahmenZahl >= 2` und nur im Zweig `speicherZiel.ok`,
  `index.html` lädt mindestens `?v=20261016G`.

**Belege (in diesem Lauf selbst ausgeführt)**

- `node tests/test_quiz_rahmen_mehrfach.js app.js` → **Alle Prüfungen bestanden**, Exit 0.
- `backend/.venv/Scripts/python -m pytest tests/test_frontend_node.py -q` → **40 passed**
  (alle 39 Frontend-Tests + Wächter), Exit 0.
- Voller Prüfbefehl über den Commit-Haken (`cd backend && .venv/Scripts/python -m pytest
  tests/ -q`): Ergebnis und Exit-Code stehen im Tor-Protokoll dieses Commits
  (`.hermes/logs/commit-sC-mehrfach.log`).

**Ehrlich dazu**

- Der Test beweist den **Ablauf und die gemeldeten Daten**, **nicht** die Anzeige am Handy —
  das bleibt Sebastians Abnahme.
- Der Mehrfachweg nutzt weiterhin **eine** Zielperson für alle Rahmen des Bildes (die
  Person der offenen Quizrunde). Ein **Ziel-Personen-Menü je Rahmen** ist Schritt **G** und
  **nicht** gebaut.
- **Variante 2** („jedes Speichern erzeugt eine neue Referenz") bleibt ungebaut; die
  Schritte **D bis I** sind offen.
- Keine Bilder geöffnet oder gesendet, kein Vision- und kein Websuche-Aufruf, keine
  Geräteeingriffe, kein pCloud-Zugriff. **Kosten: 0 USD.**
