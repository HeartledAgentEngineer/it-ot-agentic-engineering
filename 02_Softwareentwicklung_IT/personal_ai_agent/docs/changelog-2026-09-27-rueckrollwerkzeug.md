# Rückroll-Werkzeug für die pCloud-Foto-Sortierung (Auftrag N2)

> ⚠️ **ÜBERHOLT (27.09.2026, ~05:30).** Dieser Text beschreibt die **erste**,
> parallel entstandene Fassung des Rückroll-Werkzeugs (`tools/pcloud/pcloud_manifest.py`
> plus Schreibmethoden im Lesedienst). Sie wurde zugunsten **einer** Fassung
> aufgegeben: `tools/pcloud/pcloud_bewegungen.py` + `pcloud_rueckrollen.py`
> (Trockenlauf ist Standard, echte Aktion nur mit `--wirklich`, Positivliste der
> erlaubten API-Methoden, **kein** Schreibweg im Dienst). Der Lesedienst wurde auf
> den Nur-Lese-Stand zurückgesetzt, `pcloud_manifest.py` entfernt (Referenzfreiheit
> geprüft; Sicherung unter `%TEMP%\n2-kollision-2026-09-27\`). Dieser Text bleibt
> als **Spur der Kollision** stehen — nicht als gültige Bauanleitung.

> **Datum:** 27.09.2026 · **Auftrag:** Nachtlauf N2 — ein Werkzeug, mit dem jede
> schreibende Aktion der pCloud-Foto-Sortierung wieder rückgängig gemacht werden
> kann. **Reiner Code, kein Netzaufruf, kein Löschen.**

## Warum

Ab jetzt darf die Foto-Sortierung auf der pCloud **Ordner und Dateien
verschieben** (Stufe B). Jede Schreiboperation ist damit erst dann
verantwortbar, wenn sie umkehrbar ist. Deshalb protokolliert die Sortierung
jede Aktion in ein **Manifest** (JSON Lines, `~/foto_sortierung/manifest.jsonl`)
und dieses Werkzeug fährt aus dem Manifest **rückwärts** — der jüngste Schritt
zuerst, bis der alte Zustand wiederhergestellt ist.

**Grundregel im Code:** Rückrollen ist **ausschließlich Verschieben**. Löschen
gibt es nirgends — weder als Methode noch auskommentiert.

## Was neu ist

| Datei | Art | Inhalt |
|---|---|---|
| `tools/pcloud/pcloud_manifest.py` | neu | Manifest lesen/schreiben, Kehrzug bilden (nur Standardbibliothek) |
| `tools/pcloud/pcloud_rueckrollen.py` | neu | CLI `--zeigen` / `--rueckwaerts N` / `--trocken` / `--manifest PFAD` |
| `backend/app/services/pcloud_service.py` | erweitert | `verschiebe_ordner` (`/renamefolder`), `verschiebe_datei` (`/renamefile`) |
| `backend/tests/test_pcloud_rueckrollen.py` | neu | 15 Tests, ohne Netz |
| `backend/tests/test_pcloud_service.py` | erweitert | +5 Tests (Verschieben-Methoden, keine Löschmethode) |

### Manifest (eine Zeile pro Aktion)

Beispielzeile — **erfundene Werte** (dieses Dokument enthält bewusst keine
Namen oder Kennungen aus Sebastians echtem Konto):

```json
{"zeit":"2026-01-02T10:00:00+00:00","art":"movefile","von_id":1,"nach_id":2,"name":"Beispiel_2025-01-02_10-00-00_1.jpg","datei_id":1234567890}
```

| Feld | Bedeutung |
|---|---|
| `art` | `movefolder`, `movefile` oder `createfolder` |
| `von_id` / `nach_id` | Ordner-Kennung (folderid) **vorher** / **nachher** (Elternordner) |
| `datei_id` | Kennung des bewegten Elements — bei einer Datei die `fileid`, bei einem **Ordner die `folderid`** |
| `name` | lesbarer Name für die Ausgabe |

`kehrzug(eintrag)` dreht `movefolder`/`movefile` um (von/nach getauscht).
`createfolder` liefert `None` + Klartext (`kehrzug_grund`): ein angelegter
Ordner ließe sich nur durch Löschen rückgängig machen — verboten.

### Dienst (nur zwei bewegende Methoden)

```python
verschiebe_ordner(folderid, ziel_folderid)  # GET /renamefolder -> {"ok":True,"art":"ordner","id":…,"neuer_ordner":…}
verschiebe_datei(fileid,   ziel_folderid)   # GET /renamefile   -> {"ok":True,"art":"datei", "id":…,"neuer_ordner":…}
```

Beide laufen über `self._api(...)`: Fehler kommen wie überall als `PCloudFehler`,
ohne Token als `PCloudNichtKonfiguriert`. **Löschmethoden gibt es nicht** (ein
Test prüft, dass `deletefile`/`deletefolder`/`delete_*`/`loesche_*` fehlen).

## So fährt man rückwärts

```bash
# 1) Ansehen, was drin steht (schreibt NICHTS) — letzte 10 Einträge + Kehrzüge
backend/.venv/Scripts/python.exe tools/pcloud/pcloud_rueckrollen.py --zeigen
backend/.venv/Scripts/python.exe tools/pcloud/pcloud_rueckrollen.py --zeigen 25

# 2) Trockenlauf: zeigt nur, was passieren würde (ruft NICHTS auf)
backend/.venv/Scripts/python.exe tools/pcloud/pcloud_rueckrollen.py --rueckwaerts 5 --trocken

# 3) Echt rückwärts: die letzten 5 UMKEHRBAREN Einträge, jüngster zuerst
backend/.venv/Scripts/python.exe tools/pcloud/pcloud_rueckrollen.py --rueckwaerts 5

# --manifest PFAD  überschreibt den Standardpfad (~/foto_sortierung/manifest.jsonl)
```

**Exit-Codes:** `0` ok · `2` kein/leeres Manifest · `3` pCloud nicht
konfiguriert (kein Token → klare Meldung, **kein** Netzaufruf, **kein**
Stacktrace) · `4` Ausführungsfehler.

**Der Token wird nie ausgegeben und nie geloggt.**

## Beleg — tatsächlich ausgeführter Prüfbefehl

```
cd backend && .venv/Scripts/python.exe -m pytest tests/ -q
  -> 545 passed, 3 warnings in 66.42s
     Exit-Code 0
```

**Zahl ehrlich aufgeschlüsselt** (im selben Arbeitsbaum entstanden parallel
weitere Tests, die **nicht** zu diesem Auftrag gehören):

| Stand | Tests |
|---|---|
| Baseline **vor** dieser Änderung | 500 |
| **dieses Werkzeug (N2)** | **+20** (15 in `test_pcloud_rueckrollen.py`, 5 in `test_pcloud_service.py`) |
| parallel, andere Aufgabe (Werkzeug `tools/foto_sortierung/foto_themen.py` + `tests/test_foto_themen.py`, 25 Tests) | +25 |
| Ergebnis nach der Änderung | **545 passed, Exit 0** |

Zusätzlich der Rauchtest der CLI — **selbst gefahren** (27.09.2026) gegen ein
**erfundenes** Manifest in `%LOCALAPPDATA%\Temp`, ohne Netz und ohne Token.
Die Beispieldaten enthalten bewusst keine Namen oder Kennungen aus dem Konto:

```
$ pcloud_rueckrollen.py --zeigen 3 --manifest <erfundenes Manifest>
Manifest: 3 lesbare Eintraege, 0 uebersprungen.
  2026-01-02T10:00:00+00:00  createfolder Agent/Fotos/2025   (0 -> 77)
      nicht umkehrbar: createfolder — ein angelegter Ordner liesse sich nur durch Loeschen rueckgaengig machen; Loeschen ist in diesem Projekt verboten.
  2026-01-02T10:00:01+00:00  movefolder   Beispielordner_A   (9 -> 8)
      Kehrzug: (8 -> 9)
  2026-01-02T10:00:02+00:00  movefile     Beispiel_2025-01-02_10-00-00_1.jpg   (1 -> 2)
      Kehrzug: (2 -> 1)
                                                                     -> Exit 0

$ pcloud_rueckrollen.py --rueckwaerts 2 --trocken --manifest <…>
Ruecklauf: 2 Eintraege (juengster zuerst) von 2 gewuenschten.
Trockenlauf — es wird NICHTS ausgefuehrt.
  wuerde ausfuehren: Beispiel_2025-01-02_10-00-00_1.jpg  2 -> 1
  wuerde ausfuehren: Beispielordner_A  8 -> 9
                                                                     -> Exit 0

$ pcloud_rueckrollen.py --zeigen --manifest <fehlt>
Kein Manifest oder leer: …                                          -> Exit 2
```

## Was ausdrücklich **NICHT** passiert

- **Kein Löschen.** Keine `deletefile`/`deletefolder`-Methode, kein
  auskommentierter Entwurf, auch nicht im CLI (`deletefile`/`deletefolder`
  kommen im Quelltext von `pcloud_rueckrollen.py` nicht vor — Test).
- **`Crypto Folder` wird nicht berührt** — das Werkzeug liest nur das Manifest
  und ruft die zwei Verschiebe-Methoden auf; es durchsucht nichts.
- **Kein Netzaufruf ohne Token.** `--zeigen` und `--trocken` rufen die pCloud
  gar nicht auf; ohne Token bricht `--rueckwaerts` mit Exit 3 und Klartext ab.
- **Nichts überschreiben:** das Manifest wird nur angehängt (`append`).
- **Keine Secrets, keine Fotos, keine Chatarchive** angefasst.

## Abweichung vom Auftrag (bewusste Entscheidung)

Der Auftrag beschrieb den Kehrzug als „`von_id` und `nach_id` getauscht“,
ließ aber offen, wo die **Kennung des bewegten Elements** steht. Für einen
Ordner ist ein sauberer Kehrzug nur mit einer festen Element-Kennung möglich
(der reine Tausch von zwei Ordner-IDs wäre keine Umkehrung). Deshalb gilt:

> **`von_id`/`nach_id` sind immer der alte/neue Eltern-Ordner; die Kennung des
> bewegten Elements steht immer in `datei_id` — bei einer Datei die `fileid`,
> bei einem Ordner die `folderid`.**

Das ist die einzige Auslegung, bei der „rückwärts fahren“ die Aktion wirklich
umkehrt. Der Manifest-**Schreiber** der Foto-Sortierung muss `datei_id` daher
auch bei `movefolder` füllen. Fehlt `datei_id`, meldet die CLI den Eintrag als
„nicht ausführbar“ und überspringt ihn — statt zu raten.

Sonst keine Abweichungen: Methodennamen (`verschiebe_ordner`,
`verschiebe_datei`), API-Pfade (`/renamefolder`, `/renamefile`), Exit-Codes und
Rückgabeform entsprechen exakt dem Auftrag.

## Offene Punkte

- **Kein Live-Lauf gegen die echte pCloud.** Es wurde nichts verschoben — die
  Verschiebe-Methoden sind nur mit httpx-Attrappen getestet, die CLI nur mit
  einer Dienst-Attrappe. Ein echter `/renamefolder`/`/renamefile`-Aufruf steht
  noch aus (und bleibt bewusst ungetestet, bis eine echte Sortierung läuft).
- **Manifest-Schreiber fehlt hier.** Dieses Werkzeug *liest* das Manifest; die
  Foto-Sortierung (separater Auftrag) muss es mit `pcloud_manifest.anhaengen`
  füllen und dabei `datei_id` wie oben füllen.
- **Nur Dateiname, keine Pfad-Prüfung:** die Umkehrung verlässt sich auf die im
  Manifest festgehaltenen IDs; ein von Hand verbogenes Manifest führt zu einem
  klaren Fehler (Exit 4), nicht zu einem stillen Fehlverschieben.
- **Kein Live-Test unter Termux/Handy.**
