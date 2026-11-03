# Changelog 03.11.2026 — Alltagsprotokoll S2 (Rest): Rechenteil fürs Eintragen

Plan: `.hermes/plans/alltagsprotokoll.md`, Schritt S2. Die Schlafnächte der Uhr waren schon da
(#12). Es fehlten die Rechnungen, die S5 (API) und S7 (Pop-up) brauchen. Alles ist rein, ohne Modell
und ohne Speicherzugriff.

## Neu in `backend/app/services/alltag_rechnen.py`

- `stunden_verteilen(von, bis, zone=None)`: Jede angebrochene Stunde wird als Ortszeit mit Offset
  ausgegeben. Gezählt wird in echten Stunden, deshalb erscheint bei der Rückstellung 02:00 zweimal
  (+02:00 und +01:00). Ohne Zone gilt die Systemzeit. Das venv hat kein `tzdata`, im Test bildet
  eine kleine Zeitzone die Umstellung vom 25.10.2026 nach.
- `schlaf_aus_ereignissen(ereignisse)`: Nächte aus den Knöpfen „Ich gehe schlafen“, „Kann nicht
  schlafen“, „Gehe wieder schlafen“ und „Ich wache auf“. Ergebnis je Nacht: Dauer, Wachzeit, Schlaf
  und Wachphasen.
  - Verirrte Knöpfe und Doppeldruck werden ignoriert.
  - Liegt ein neues „schlafen“ mehr als 24 Stunden nach dem Beginn, bleibt die alte Nacht offen.
  - Wachliegen bis zum Aufstehen zählt als wach.
- `letzter_stand(eintraege, jetzt)`: liefert `{"letzter_eintrag", "schlaeft"}` für `/api/alltag/offen`.
  Ein späterer Stunden-Eintrag beendet den Schlaf, ein Schlaf-Knopf älter als 24 Stunden verfällt.
- `offene_stunden(letzter, jetzt, schlaeft)`: volle Stunden seit dem letzten Eintrag. Im Schlaf
  gibt sie 0, ohne jeden Eintrag 1.
- `fehlende_felder(eintrag)`: Stimmung (1–5), Anspannung (0–100), Gefühle und Aktivität.
  Ungültige Werte zählen als fehlend. Essen fehlt bewusst, weil es im Plan noch offen ist (Punkt D).

## Prüfung

- Neu: `test_alltag_rechnen_s2.py` (15), darunter der Plansatz „2 bis 5 geschlafen, um 3 kurz
  wach“ (180 Min. im Bett, 10 wach, 170 Schlaf), Mitternacht und Zeitumstellung. Vorher 15 rot.
- `test_alltag_rechnen.py` unverändert grün.
