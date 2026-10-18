# 18.10.2026 – Zitate aus den Chat-Archiven nennen den Tag in ORTSZEIT

Anlass: To-do-Liste „Ältere offene Punkte" (Sebastian, 16.10.2026):
„**Quellen-Abgleich/Formatierung:** Datum (UTC-Tag, 8,7 % betroffen),
Zeitfenster (WhatsApp 34 %), ChatGPT-Referenzen ohne Fluss." Der dritte Teil
(Fluss) ist erledigt (Dokument `changelog-2026-10-10-archiv-gespraechsfluss.md`),
der erste ist dieser Schritt.

## Befund (am echten Index gemessen, 18.10.2026, nur lesend)

Quelle: `Chats von GPT, GEMINI, Claude/db/archiv_index.db` (447 MB),
52.679 Abschnitte (`chunks`), alle mit lesbarem `beginn`.

| Quelle | Abschnitte | Orts-Tag ≠ UTC-Tag | Anteil |
|---|---|---|---|
| claude-code | 3.185 | 461 | 14,5 % |
| chatgpt | 19.443 | 1.859 | 9,6 % |
| gemini | 4.537 | 379 | 8,4 % |
| claude-ai | 3.280 | 191 | 5,8 % |
| whatsapp | 21.788 | 338 | 1,6 % |
| google-kalender | 403 | 0 | 0,0 % |
| google-notizen | 43 | 2 | 4,7 % |
| **gesamt** | **52.679** | **3.230** | **6,13 %** |

Die Abweichung tritt **ausschliesslich in den UTC-Stunden 22 und 23** auf
(1.300 bzw. 1.930 Fälle) — also bei Gesprächen zwischen 00:00 und 01:59
Ortszeit. Genau dort nannte das Zitat den **Vortag**.

**Ehrlich dazu:** Die in der To-do-Liste genannten Zahlen liessen sich **nicht**
reproduzieren. Gemessen sind es 6,13 % (nicht 8,7 %); die mehrtaegigen
WhatsApp-Abschnitte sind 42,2 % (nicht 34 %) — dieselbe Grösse wie in der
Messung vom 10.10.2026 (42,1 %).

## Ursache (belegt, nicht vermutet)

Die Stempel stehen in **UTC**. Der WhatsApp-Import rechnet Epoch-Millisekunden
ausdrücklich nach UTC um (`backend/scripts/whatsapp_db_import.py:120-130`,
`fromtimestamp(ms/1000, tz=timezone.utc)`); die Zeitspanne der importierten
Zeilen ist im Changelog vom 28.09. ebenfalls als UTC dokumentiert. Die vier
Anzeigewege kürzten den Stempel aber mit `[:10]` — also auf den **UTC-Tag**.

## Änderung

- **`backend/app/services/archiv_service.py`:** neu `ortstag(zeitstempel)`
  (Tag in Ortszeit, nie eine Ausnahme) sowie `ortszeit_versatz(utc)` und
  `_letzter_sonntag(...)` als die eine Regel dafür. `zeitraum_kurz()` nennt
  beide Enden der Spanne über `ortstag()`.
- **`backend/app/services/archiv_suche.py`:** `_datum_kurz()` rechnet mit
  `_ortstag()` (derselben kleinen Regel im Modul; das Suchmodul muss ohne den
  Dienst auskommen). Damit nennen alle vier Wege dasselbe:
  `router/chat._archiv_tool`, `router/chat._archiv_treffer`,
  `llm_service._build_archiv_context` und die Chronik aus `archiv_suche`.

**Zeitzone bewusst ohne `zoneinfo`/`tzdata`:** im Backend ist kein
Zeitzonenpaket installiert (gemessen: `ModuleNotFoundError: tzdata`), und
`astimezone()` scheitert auf Windows an Zeitstempeln vor 1970 (`OSError:
[Errno 22]`) — der Index enthält Google-Kalender-Einträge ab 1940. Deshalb die
EU-Sommerzeit-Regel direkt im Code (letzter Sonntag im März 01:00 UTC bis
letzter Sonntag im Oktober 01:00 UTC → +2 h, sonst +1 h). Vorteil: auf Handy,
PC und in Tests dasselbe Ergebnis, auch für alte Daten.

## Belege (in diesem Lauf selbst ausgeführt)

- neu `backend/tests/test_archiv_ortstag.py` — **20 Prüfungen**, u. a.
  Sommer-/Winterzeit, beide Umstellungstage, Datum 1940 (keine Ausnahme),
  leere/unlesbare Werte, Übereinstimmung beider Zitat-Wege, Verdrahtung in
  Chat-Notiz und System-Prompt.
- `backend/tests/test_archiv_datum_und_status.py` **10 passed** (vier
  Erwartungen nachgezogen: der Tag am Spannenende ist jetzt der Ortstag) und
  `test_archiv_gespraechsfluss.py` **6 passed** (eine Erwartung nachgezogen);
  die drei Dateien zusammen **36 passed**.
- Prüfbefehl (in diesem Lauf selbst ausgeführt):
  `cd backend && .venv/Scripts/python -m pytest tests/ -q` →
  **4802 passed, 3 skipped, Exit 0** in 540,36 s (Baseline des Vorlaufs:
  4782 passed, 3 skipped).

## Grenzen (bewusst)

- Nur der **Tag** wird genannt, nicht die Uhrzeit — Sebastian liest Zitate mit
  Datum, die Uhrzeit wäre eine zweite Änderung.
- Die Zeitzone ist **fest Europe/Berlin** (Sebastians Arbeitsplatz). Läuft der
  Server einmal in einer anderen Zone, bleibt die Rechnung bei Hamburg — das ist
  gewollt und hier festgehalten, statt still die Systemzeitzone zu nehmen.
- Unberührt: Ereignis-Datumsfelder (`erzaehl_service`), Aufnahmedaten von Fotos
  (`gruppen_quiz`) und die Archiv-Zeiträume selbst — dort werden keine
  UTC-Stempel gekürzt.

## Umkehrweg

`git revert <Commit>` — es sind nur Formatierungsfunktionen und Tests
betroffen, kein Datenbestand, keine Schreibzugriffe.
