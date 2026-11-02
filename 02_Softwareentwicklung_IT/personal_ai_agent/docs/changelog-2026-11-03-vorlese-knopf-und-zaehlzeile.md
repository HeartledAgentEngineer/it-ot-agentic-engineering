# 03.11.2026 — Vorlese-Knopf schaltet wirklich auf Stopp; Zählzeile unter der Anlassgeschichte

## Befund (Sebastian, Handy)
1. Der 🔊-Knopf wurde beim Vorlesen nicht zu „⏹ Stopp".
2. Die KI-Anlassgeschichte war nur ein Satz; Bildbeschreibungen und Notizen schienen zu fehlen.

## Ursachen
1. `vorlesen(quelleId, knopf)` nahm den Knopf an, reichte ihn aber nicht an `vorlesenText` weiter
   (Fehler aus bc33ea6). Betroffen: alle sieben Knöpfe über `vorlesen(...)`. Zusätzlich las die App nach dem
   Erzeugen einer Bild-/Anlassgeschichte automatisch vor — ganz ohne Knopf, also ohne Stopp.
   Der Test von gestern prüfte nur die Verdrahtung der Knöpfe, nicht die Weitergabe in `vorlesen`.
2. Noch offen. Der Code sammelt Beschreibungen aller Bilder und alle Notizen des Anlasses (auch Bildnotizen,
   wenn sie mit der Anlass-Kennung gespeichert sind; belegt durch `test_f_anlassweg_*`). Ob am Handy die
   Beschreibungen der Fotobuch-Bilder fehlen (`bild_beschreibungen*.jsonl`, `life_archive.db`), lässt sich
   ohne die echten Daten nicht sehen — deshalb zeigt die App jetzt selbst die Zahlen.

## Änderung
- `frontend/erzaehlen.js`: `vorlesen` reicht den Knopf weiter; automatisches Vorlesen nach dem Erzeugen nutzt
  den 🔊-Knopf der Geschichte (`erzaehl-anlassgeschichte-vorlesen` / `erzaehl-bildgeschichte-vorlesen`).
  Neu `erzaehlDatenZeile(daten)`: „KI · 14 Bilder · 2 Beschreibungen · 3 Notizen · 2 Personen" (nur Zahlen).
  `geschichteErzeugen` gibt `daten` der Antwort weiter.
- `frontend/index.html`: `#erzaehl-anlassgeschichte-daten` unter der Anlassgeschichte; `erzaehlen.js?v=20261103A`.
- `backend/app/services/erzaehl_service.py`: `daten.anzahl_notizen` in der Anlassgeschichte.
- Tests: neu `frontend/tests/test_erzaehlen_datenzeile.js` (rot → grün), `test_erzaehlen_vorlese_stopp.js`
  prüft die Weitergabe (rot → grün), neuer Backend-Test `test_f_anlassweg_zaehlt_die_verwendeten_notizen`.
  Drei Tests mit festem Cache-Pin `20261102E` prüfen jetzt „mindestens" (kein Nachziehen bei jedem Bump mehr).
