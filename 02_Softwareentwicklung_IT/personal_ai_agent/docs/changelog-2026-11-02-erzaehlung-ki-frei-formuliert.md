# Changelog 02.11.2026 — Erzählung: KI formuliert frei statt Vorlagen-Stakkato

## Wunsch (Sebastian)
Die Bild-/Anlassgeschichte soll das KI-Modell aus den KI-Bildbeschreibungen, den Personen und der
eigenen Erinnerung zu EINER zusammenhängenden Geschichte verweben. Die bisherige Fassung wirkte
„stakkato" bzw. „zusammengereimt" — sie wurde aus einer festen Vorlage zusammengesetzt
(`verschmelze_geschichte`), nicht frei formuliert. Entscheidung Sebastian: KI formuliert frei,
ersetzt die Vorlage.

## Änderung (nur Backend — kein Frontend, kein Cache-Bump)
Die Generierung läuft serverseitig; das Frontend zeigt schon `res.geschichte` an. Deshalb genügte
der Umbau im Dienst.

### Neu: `backend/app/services/geschichte_erzaehlen_ki.py`
- `erzaehle_geschichte(...)` stellt EINEN Aufruf über den vorhandenen `OpenRouterZDRClient`
  (ZDR erzwungen, `data_collection: deny` zusätzlich im Aufruf). Modell `MODELL_FLASH`
  (`deepseek/deepseek-v4-flash-0731`, günstig + flink). Zeitgrenze 45 s, `max_tokens` 500,
  `temperature` 0.7.
- `baue_nachricht(...)` (rein, testbar) baut die Nutzer-Nachricht aus den Angaben: Titel, Zeit, Ort,
  Personen, Bildbeschreibung(en) und „Meine Erinnerung dazu". Leere Felder werden weggelassen
  (das Modell erfindet nichts zu Platzhaltern). Perspektive wählbar: Ich-Form oder Erzählersicht.
- Prompt-Regeln: fließender Fließtext (kein Stakkato, keine Aufzählung), nur die gegebenen Angaben,
  keine erfundenen Namen/Orte/Ereignisse, **englische Bildbeschreibungen werden in deutsche Prosa
  umgeschrieben**, keine Anführungszeichen um die Erinnerung.
- Fehler als `{ok: false, grund}` (Zeitgrenze/HTTP/Verbindung/leer/kein Schlüssel) — nie mit
  Schlüssel, URL oder Ausnahmetext. Log nur Modell/Dauer/Zeichenzahl/Kosten — nie Text, nie Namen,
  nie die Erinnerung. Es wird NICHTS gespeichert (wie beim Vision-Vorschlag).
- `verfuegbar()` meldet, ob ein OpenRouter-Schlüssel da ist.

### `backend/app/services/erzaehl_service.py`
- Neu `_erzaehle_text(...)`: ruft erst das KI-Modell (wenn `verfuegbar()`), bei Fehler, Ausnahme
  oder fehlendem Schlüssel **die Vorlage** (`verschmelze_geschichte`) als sicheren Rückfall — die
  Oberfläche bleibt nie ohne Geschichte. Rückgabe `(text, quelle, kosten_usd)` mit `quelle` ∈
  {`ki`, `vorlage`}.
- `ki_geschichte_generieren` und `anlass_geschichte_generieren` nutzen jetzt `_erzaehle_text` statt
  direkt die Vorlage. In `daten` kommen zwei Felder dazu: `erzaehlquelle` und `kosten_usd`.
- `verschmelze_geschichte` bleibt unverändert als Rückfall erhalten.

### Tests (offline, erfundene Daten)
- Neu `tests/test_geschichte_erzaehlen_ki.py` (8): `baue_nachricht` enthält die Fakten und
  unterscheidet die Perspektive; Erfolg mit eingespielter Client-Attrappe (Text, Modell, Kosten aus
  `usage.cost`); ZDR-Härtung (`data_collection: deny`) im Aufruf; die Fakten stehen in der gesendeten
  Nachricht; ohne Schlüssel/ohne Client kein Netzaufruf; Zeitgrenze/leere Antwort ehrlich ohne
  Geheimnis.
- Neu `tests/test_erzaehlen_ki_einbindung.py` (4): `_erzaehle_text` nimmt die KI bei Schlüssel, fällt
  bei fehlendem Schlüssel, Ausnahme oder `ok:false` verlässlich auf die Vorlage zurück.
- Neu in `tests/conftest.py`: autouse-Fixture `_keine_echten_erzaehl_modellaufrufe` — **kein Test
  ruft je das echte Modell** (auf einem Rechner mit Schlüssel sonst echte, teure, nicht
  reproduzierbare Aufrufe). In Tests gilt der Rückfall (Vorlage) als Standard; wer den KI-Pfad prüft,
  spielt `verfuegbar`/`erzaehle_geschichte` selbst ein.

## Beleg Rot vor Grün
- `tests/test_geschichte_erzaehlen_ki.py` gegen den Stand ohne das Modul: Sammelfehler
  `ImportError: cannot import name 'geschichte_erzaehlen_ki'`. Nach dem Modul: 8 passed.
- Regression ohne die conftest-Absicherung: 5 Alt-Tests rot
  (`test_erzaehlen_ki_geschichte.py` 3, `test_erzaehlen_bilder_info_erweitert.py` 1,
  `test_erzaehlen_geschichte_trennung.py` 1) — Ursache: auf diesem Rechner liegt ein OpenRouter-
  Schlüssel, deshalb nahmen sie plötzlich den echten LLM-Pfad (Netzaufruf, nichtdeterministischer
  Text; Laufzeit des Teil-Laufs 168 s). Mit der autouse-Fixture: dieselben Dateien + die beiden
  neuen → **92 passed in 6,2 s**, ohne Netz.

## Offen / nächste Schritte
- Vorlese-/Stopp-Knopf überall als Umschalter (Anhalten) — eigener Slice.
- Löschen einer Geschichte gibt es serverseitig (`DELETE /api/erzaehlen/geschichten/{id}`,
  revisionssicher) und „neu generieren" ruft die Generierung erneut — die Verdrahtung in der
  Oberfläche (Löschen/Neu-Erzählen sichtbar) ist noch zu prüfen.
- Kostenschätzung pro Erzählung aus echten `usage.cost`-Werten nachmessen.
