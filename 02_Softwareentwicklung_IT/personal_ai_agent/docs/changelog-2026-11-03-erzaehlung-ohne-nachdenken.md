# 03.11.2026 — KI-Erzählung: Nachdenken abgeschaltet

## Befund (Sebastian, Handy)
Die Anlassgeschichte wirkte „per Schema zusammengeklatscht": Bildbeschreibungen und Erinnerungen
aufgelistet, im Wortlaut der Notizen — also die Vorlage, nicht die KI. Gestern: nur ein Satz.

## Ursache (gemessen am PC, erfundene Testdaten)
`MODELL_FLASH` (`deepseek/deepseek-v4-flash-0731`) ist ein Denk-Modell. Bei `max_tokens=500`
gingen **385 Tokens ins Nachdenken**, `finish_reason: length`, Text nach 409 Zeichen mitten im
Satz abgeschnitten. Mit echten Anlassdaten (viele Beschreibungen, lange Notizen) reicht das
Budget nicht mehr für Text: ein Satz oder gar keiner → leere Antwort → stiller Rückfall auf die
Vorlage. Der Schlüssel war nicht das Problem (Chat und Erzählung lesen denselben).

## Änderung
- `geschichte_erzaehlen_ki.py`: `"reasoning": {"enabled": False}` im Aufruf.
  Gegenprobe: 6 vollständige Sätze, `finish_reason: stop`, 221 Tokens, halbe Kosten.
- Test `test_nachdenken_ist_abgeschaltet` (rot → grün).

## Offen
- Die Vorlage greift weiterhin still; die Zählzeile sollte den Grund nennen.
- Das Modell schmückt aus (z. B. Gerüche), obwohl der Prompt Erfinden verbietet.
