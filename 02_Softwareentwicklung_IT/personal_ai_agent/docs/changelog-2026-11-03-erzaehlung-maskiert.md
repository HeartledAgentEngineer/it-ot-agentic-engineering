# 03.11.2026 — KI-Erzählung schickt Namen und Ort nur maskiert

## Problem
Die frei formulierte KI-Erzählung (`geschichte_erzaehlen_ki.py`, seit 02.11.) schickte Personennamen,
Ort und die eigene Erinnerung im Klartext an OpenRouter. ZDR war erzwungen, aber Sebastians Regel lautet:
Namen und private Angaben werden vor dem Senden maskiert.

## Lösung
- Neu `baue_schild(personen, ort)`: ein `PIIShield` pro Aufruf. Registriert jeden Namen samt Namensteilen
  ab 3 Zeichen (die Erinnerung nennt oft nur den Vornamen) und den Ort.
- Die Nutzer-Nachricht geht maskiert raus (`[PERSON_01]`, `[LOC_01]`), die Antwort wird lokal zurückübersetzt.
- Der Systemprompt weist das Modell an, Platzhalter unverändert zu übernehmen.
- Bewusst `PIIShield` direkt statt `chat_shielded`: Dieses liefert nur Text, die Kostenangabe ginge verloren.

## Grenze
Maskiert wird, was bekannt ist (Personen des Bildes, Ort). Namen, die nur frei in der Erinnerung stehen und
keiner Person des Bildes gehören, bleiben Klartext.

## Tests
`tests/test_geschichte_erzaehlen_ki.py`: drei neue Tests (nichts Klartext im Aufruf, Rückübersetzung,
Platzhalter-Anweisung); der alte Test, der den Namen im Aufruf verlangte, prüft jetzt nur noch den Text ohne Namen.
