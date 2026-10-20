# Änderungsprotokoll 20.10.2026: Gruppenübersicht nur bei „Offen“

## Anlass
Sebastian: „Gruppenübersicht nur als Unterkategorie bei Offen“. Der Knopf
`#gruppen-uebersicht` („☷ Gruppenübersicht“) erschien bisher auch im Reiter
„Benannt“ und in der Übersicht selbst, wo er keinen Zweck hat.

## Änderung
- `frontend/gruppen_quiz.js:1061-1064` (in `nurZeigen`, eine Stelle für alle
  Ansichtswechsel): `uebersicht.hidden = zustand.reiter === 'benannt' || name === 'liste'`.
  `reiterSetzen` setzt `zustand.reiter` vor dem `nurZeigen`-Aufruf; Startwert
  ist `'offen'`. Im Reiter „Offen“ bleibt der Knopf bei Quiz-Karte, Gruppen-Detail,
  „fertig“ und „Alle Gesichter“ sichtbar; „← Zum Quiz“ zeigt ihn wieder.
- Keine CSS-Änderung (Gestaltung als Unterpunkt bewusst weggelassen).

## Test
`frontend/tests/test_gruppen_liste.js`, Funktion `uebersichtKnopfNurInOffen`
(vorher rot: „Reiter Benannt – false !== true“). Prüft: Quiz sichtbar, Benannt
versteckt, zurück in Offen sichtbar, Übersicht offen versteckt, Detail sichtbar,
zurück in die Übersicht versteckt, „← Zum Quiz“ sichtbar, „Alle Gesichter“ sichtbar.
Lauf über `backend/tests/test_frontend_node.py`.

## Cache-Kennung
`frontend/index.html:716`: `gruppen_quiz.js?v=20261018F` → `?v=20261020A`.
`style.css` unverändert (`?v=20261018E`).
