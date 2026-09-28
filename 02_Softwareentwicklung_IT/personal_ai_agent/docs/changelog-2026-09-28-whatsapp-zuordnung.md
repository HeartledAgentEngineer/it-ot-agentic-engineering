# Changelog 28.09.2026 — WhatsApp-Zuordnung: Chat <-> Telefonbuch

**Auftrag:** Jedem WhatsApp-Chat und jedem Gruppenmitglied eine Person aus
Sebastians Telefonbuch zuordnen — Bruecke ist die Telefonnummer. Ergebnis als
private JSON-Datei **ausserhalb** des Repos; im Bericht/Log nur Zahlen.

## Was gebaut wurde

- **`tools/whatsapp/zuordnung_bauen.py`** — neues Werkzeug, **nur lesend**:
  - Telefonbuch vom Handy per ADB (`content query` auf `data/phones`; Termine
    ueber `contact_event`, Geburtstag = Android-Typ 3). Alternativ laufen zuvor
    gespeicherte Rohausgaben (`--telefonbuch-datei`, `--events-datei`).
  - msgstore.db wird ueber `file:...?mode=ro` geoeffnet — kein Schreiben,
    kein Entschluesseln, kein Download.
  - Nummern-Normalisierung: nur Ziffern; `+49` / `0049` / `0` / `+49 (0)`
    werden auf dieselbe Form gebracht, der Vergleich laeuft ueber die
    Schnittmenge der Schreibvarianten. Kennungen unter 7 Ziffern gelten nicht
    als Nummer (Systemkontakt `0@s.whatsapp.net`).
  - Namen: Telefonbuch zuerst, sonst selbst gewaehlter WhatsApp-Name
    (`lid_display_name`), sonst `unbekannt`. LID-Aufloesung ueber `jid_map`.
- **Ausgabe:** `C:\Users\sebas\foto_sortierung\whatsapp_zuordnung.json`
  (ausserhalb des Repos). Je Chat: `chat_row_id`, Art, Telefonbuch-Namen,
  WhatsApp-Name, maskierte Nummer (nur letzte 4 Ziffern, `***1234`), bei
  Gruppen die Teilnehmerliste (Name bzw. `unbekannt` + Quelle). Dazu
  Statistik und Geburtstagsliste (Tag/Monat).

## Befund: `group_participant` fehlt in diesem Schema

`PRAGMA table_info(group_participant)` — die Tabelle existiert **nicht**. Die
Mitglieder kommen daher aus:

1. `group_participant_user` (4.224 Zeilen, 190 Gruppen) — Primaerquelle,
2. `group_participants` (Textform `gjid`/`jid`, 1.379 Zeilen) — Zusatz,
3. Ersatzweg: `message_system_chat_participant` (2.129 Zeilen) und die
   Absender aus `message` (`from_me = 0`) — Zusatz und Ersatz. Je Mitglied
   wird die Quelle mitgeschrieben (`gruppe` / `verlauf`).

## Gemessene Zahlen (Lauf vom 28.09.2026)

| Groesse | Wert |
|---|---|
| Telefonbuch-Eintraege | 985 (577 verschiedene Namen) |
| davon mit Geburtstag | 55 (21 ohne Jahr, 34 mit Jahr) |
| Chats gesamt | 2.471 |
| ... mit Kontakt-Treffer | 744 |
| ... ohne Kontakt-Treffer | 1.727 |
| Einzelchats | 1.953 (557 mit Treffer) |
| Gruppen (g.us) | 231 (187 mit mindestens einem Treffer) |
| Newsletter | 279 |
| Sonstige (Broadcast/Bot/Status/temp) | 8 |
| Gruppen vollstaendig / teilweise / unbekannt | 66 / 121 / 44 |
| davon ganz ohne Mitgliederdaten | 43 |
| Gruppenmitglieder gesamt | 6.242 |
| ... mit Telefonbuch-Treffer | 2.006 |
| ... nur WhatsApp-Name (+ Nummer) | 1.323 |
| ... nur WhatsApp-Name (ohne Nummer) | 572 |
| ... nur Nummer, nicht im Telefonbuch | 2.341 |
| Mitglieder-Herkunft | 4.581 Teilnehmer-Tabellen / 1.661 Verlauf |

## Gegenprobe (Stichproben)

Die JSON wurde unabhaengig nachgerechnet: Statistik aus der Chat-Liste
reproduziert; 10 Einzelchats und 10 Gruppen komplett gegen die Rohquellen
zurueckgerechnet — deckungsgleich. Kein Vollnummern-Leck im Text
(0 Ziffernfolgen mit 7+ Zeichen), alle Masken `***1234`-foermig, keine rohen
Jids im JSON.

## Tests

- Neu: **`backend/tests/test_whatsapp_zuordnung.py`** — 21 Offline-Tests
  (In-Memory-Schema nachgebaut, erfundene Beispieldaten; Randfaelle: Komma im
  Namen, `--MM-DD`, fehlende Tabellen, Ersatzweg ueber System-Nachrichten/
  Absender, Textform, Systemkontakt, Masken, Statistik, Bericht ohne private
  Details).
- Pruefbefehl: `cd backend && .venv/Scripts/python -m pytest tests/ -q`
  -> **1897 passed**, Exit 0.

## Geheimnis-Regeln (eingehalten)

- stdout/stderr und dieser Text nennen nur Zaehlungen — keine Namen, Nummern,
  Chatnamen oder Nachrichteninhalte.
- Die JSON liegt ausserhalb des Repos; der Datenbestand wurde nicht kopiert,
  geloescht oder veraendert (DB nur `mode=ro`). Kein git, kein Push.
