# Sitzung überlebt den Server-Neustart (18.10.2026)

**Auftrag:** To-do-Punkt 13, Befund Sebastian (16.10.2026): „Anmeldung bitte ausblenden,
erscheint bei jedem Aktualisieren des Browsers."

**Ursache (belegt, im Plan so notiert):** Die Sitzungen aus dem Heim-WLAN (H2, 14.10.2026)
lagen **nur im Speicher** des Prozesses (`_SITZUNGEN` in `backend/app/router/auth.py`).
Der Server startet aber oft neu (App-Knopf, Update-Knopf, Dauerlauf) — danach war die
Anmeldung wieder fällig, obwohl die Sitzung 30 Tage gelten soll.

## Was gebaut ist

- **Neue Einstellung** `settings.sitzungen_datei` (`backend/app/config.py`), Vorgabe
  `.sitzungen.json` **neben dem Projektordner** (wie Sebastian es vorgeschlagen hat).
- **Ablage in `backend/app/router/auth.py`:**
  - `_sitzungen_schreiben()` legt den Stand **atomar** ab (Temp-Datei + `os.replace`).
  - `_sitzungen_lesen()` übernimmt ihn beim Start; Abgelaufenes, Einträge ohne
    sha256-Länge und kaputte Werte fallen weg und werden dabei gleich ausgeräumt.
  - `_sitzungen_sicherstellen()` lädt **einmal je Prozess** (erste Anfrage auf einem
    geschützten Weg); `require_api_key`, `sitzung_gueltig` und `_sitzung_anlegen` rufen es auf.
  - Geschrieben wird beim Anlegen einer Sitzung, beim Abmelden und beim Ausräumen
    Abgelaufener — **gelesen wird ohne Schreibzugriff**, solange nichts zu entfernen ist.
- **In der Datei steht nur der sha256-Wert des Cookies samt Ablauf** — nie das Cookie
  selbst. Wer die Datei liest, kann sich damit **nicht** anmelden. Sie ist per
  `.gitignore` draußen (`.sitzungen.json`, `.sitzungen.json.tmp`), das Repo ist öffentlich.
- **Fehlertolerant:** fehlt die Datei, ist sie kaputt, gesperrt oder hat ein unerwartetes
  Format, gilt weiter der alte Zustand (Sitzungen nur im Speicher) — die Anmeldung selbst
  funktioniert unverändert, es gibt nur eine Warnung im Protokoll.
- **Grenzen unverändert:** Anmelden weiter nur über HTTPS (403 sonst), Bremse nach 5
  Fehlversuchen, höchstens 50 Sitzungen (nach dem Neustart mitgezählt), Abmelden löscht
  den Eintrag auch aus der Ablage.

## Belege (in diesem Lauf selbst ausgeführt)

- Neuer Test `backend/tests/test_sitzung_ueberlebt_neustart.py` — **14 Tests**:
  - Kern: anmelden → „Neustart" (Speicher leer, Lade-Merker zurück) → geschützte Route
    ist **wieder** erreichbar; dreimal wiederholt (idempotent).
  - **Gegenprobe** im selben Test: Ablage gelöscht → dieselbe Sitzung ist nach dem
    Neustart **weg** (401). Damit ist belegt, dass die Datei die Sitzung trägt.
  - In der Datei steht nur der Hash (das Cookie selbst kommt im Text **nicht** vor).
  - Abgelaufenes kommt nicht zurück und wird ausgeräumt; kaputte Datei verhindert
    Anmelden nicht; unerwartetes Format und Einträge ohne sha256-Länge werden ignoriert.
  - Lesen ohne Anlass schreibt nichts neu (Datei bleibt zeichengleich).
  - Obergrenze 50 gilt nach dem Neustart weiter (ältester Eintrag fällt weg).
  - Abmelden räumt die Ablage; keine `.tmp` bleibt liegen.
  - Vorgabe-Ort = `.sitzungen.json` neben dem Projekt und in `.gitignore`.
- `pytest tests/test_sitzung_ueberlebt_neustart.py tests/test_anmelden_sitzung.py -q` →
  **36 passed** (die 22 bestehenden H2-Tests unverändert grün).
- **Gegenprobe gegen den alten Stand** (Kopie außerhalb des Repos mit den HEAD-Fassungen
  von `auth.py`/`config.py`/`conftest.py`, Messskript `gegenprobe_sitzung_probe.py`):
  alt → `anmelden: 200, vor Neustart: 200, nach Neustart: **401**`;
  neu → `anmelden: 200, vor Neustart: 200, nach Neustart: **200**`, Ablage-Datei mit
  genau einem 64-Zeichen-Hash. Die Fähigkeit gab es vorher nachweislich nicht.
- Prüfbefehl (voller Lauf über den Commit-Haken): siehe Commit-Nachricht dieses Schritts.
- **`backend/tests/conftest.py`:** neue autouse-Vorrichtung, die die Ablage in Tests in
  einen tmp-Ordner umbiegt — sonst schriebe jeder Anmelde-Test in die echte Datei neben
  dem Projekt und die Testdateien schöben sich gegenseitig Sitzungen unter.

## Ehrliche Grenzen

- **Der Klick am Gerät bleibt Sebastians Abnahme:** belegt ist, dass die Sitzung den
  Neustart übersteht (gemessen im Test und in der Gegenprobe), nicht das Verhalten
  seines Browsers am Handy.
- Das Laden ist **bedarfsgesteuert**, nicht beim Start: die Datei wird bei der ersten
  Anfrage auf einem geschützten Weg gelesen. Wer den Server ohne eine einzige Anfrage
  startet, hat danach im Speicher noch nichts geladen — funktional gleichwertig.
- **Nur die Neustart-Ursache** ist behoben. Bleibt im Browser das Cookie selbst weg
  (z. B. privates Fenster, „Cookies löschen"), ist weiterhin eine Anmeldung fällig.
- Nicht gebaut: die Alternative „Zugangsschutz ganz ausschalten" — das bleibt eine
  Entscheidung von Sebastian (Steht im To-do-Punkt 13 als Alternative beschrieben).
