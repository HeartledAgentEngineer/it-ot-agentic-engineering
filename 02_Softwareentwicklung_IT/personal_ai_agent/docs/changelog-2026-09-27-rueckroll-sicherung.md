# Rückroll-Sicherung für pCloud-Bewegungen — Manifest, Aktions-Modul, Rückroll-Werkzeug

> **Datum:** 27.09.2026 · **Auftrag:** Nachtlauf-Schritt N8 (Fotos in
> `Agent/Fotos/<Jahr>/<Thema>/` verschieben) braucht ein Sicherheitsnetz:
> Jede Schreib-Operation kommt ins **Manifest** und ist **rückholbar**
> (AGENTS.md „Dauerlauf / Nachtarbeit": Manifest und Rückholbarkeit sind
> Pflicht). Dieses Changelog beschreibt **das Sicherheitsnetz selbst** — der
> echte Sortierlauf (N8) nutzt es erst danach.

## Warum

In diesem Projekt gibt es keinen erlaubten Löschweg in der pCloud. Jede
Bewegung ist deshalb nur zulässig, wenn sie (a) protokolliert und (b)
umkehrbar ist („Rückholbarkeit ist Pflicht — ‚Wie mache ich das rückgängig?'
wird **vor** der Operation beantwortet"). Das Sicherheitsnetz besteht aus
zwei eigenständigen Werkzeugen (kein Backend-Import) und ihren Tests:

- `tools/pcloud/pcloud_bewegungen.py` — die **einzigen drei Schreibwege**
  (Ordner anlegen, Datei verschieben, Ordner verschieben), jeder mit
  Manifest-Buchung und Sicherheitsprüfung.
- `tools/pcloud/pcloud_rueckrollen.py` — liest das Manifest und fährt die
  letzten Aktionen rückwärts: Verschiebungen zurück in den Quellordner;
  angelegte Ordner bleiben bestehen und werden nur gemeldet.

## Was neu ist

| Datei | Art | Inhalt |
|---|---|---|
| `tools/pcloud/pcloud_bewegungen.py` | neu | Manifest + die drei Schreibwege, Trockenlauf als Standard, Positivliste der API-Methoden |
| `tools/pcloud/pcloud_rueckrollen.py` | neu | `--zeigen`, `--rueckwaerts N [--wirklich]` |
| `backend/tests/test_pcloud_bewegungen.py` | neu | **29 Tests**, ohne Netz (httpx gemockt) |
| `backend/tests/test_pcloud_rueckrollen.py` | neu | **15 Tests**, ohne Netz |

### Das Manifest

Standard `~/foto_sortierung/manifest.jsonl` (per Argument `manifest_pfad=…`
oder Umgebungsvariable `PCLOUD_MANIFEST` änderbar). Ein Pfad **im Git-Repo
wird abgelehnt** — das Manifest gehört nie ins Repo (es trägt private
Ordnernamen und Kennungen). Eine JSON-Zeile je Aktion, **nur anhängen**
(nie überschreiben), Flush + fsync nach jeder Zeile:

```
zeit (ISO mit Zonenversatz) · art (movefile|movefolder|createfolder|rueckroll)
· name · fileid/folderid · von_folderid · nach_folderid · von_pfad · nach_pfad
```

Unbekanntes steht ehrlich als `null`; Zusatzfelder (z. B. `hinweis`) sind
erlaubt. Eine kaputte Zeile stoppt das Lesen mit Klartext + Zeilennummer —
wer zurückrollt, muss dem Manifest vertrauen können.

### Die Schreibwege (mehr gibt es nicht)

| Funktion | API-Methode | Besonderheit |
|---|---|---|
| `ordner_anlegen(ordner_id, name)` | `createfolder` | — |
| `datei_verschieben(fileid, ziel_id)` | `renamefile` | Zielordner wird vorher **gelesen** |
| `ordner_verschieben(ordner_id, ziel_id)` | `renamefolder` | Zielordner wird vorher **gelesen** |
| `zielordner_finden_oder_bauen(eltern_id, name)` | `listfolder` + `createfolder` | idempotent: vorhandenen Ordner nehmen, nie doppelt anlegen |

Alle haben **`trocken=True` als Standard**: ohne ausdrückliches
`trocken=False` wird nichts gesendet und nichts gebucht — nur der geplante
Eintrag kommt zurück. Vor jedem echten Verschieben wird der Zielordner
gelesen (nur lesend): Liegt dort schon ein gleichnamiges Element, wird
**nichts** verschoben, denn pCloud würde die Zieldatei laut API-Doku sonst
atomar ersetzen (Datenverlust). `von_folderid` ist bei echten Verschiebungen
Pflicht — ohne Quellordner-Id wäre die Aktion nicht rückholbar. Schlägt
pCloud trotzdem zu (Wettlauf), steht der Fall als Feld `hinweis` im
Manifest-Eintrag und es gibt einen lauten Fehler.

### Die Befehle des Rückroll-Werkzeugs

| Befehl | Was er macht |
|---|---|
| `python tools/pcloud/pcloud_rueckrollen.py --zeigen` | Manifest **nummeriert** anzeigen (Zeit, Art, Name, von → nach) + Zählung: wie viele Verschiebungen laut Manifest noch **rückholbar** sind, wie viele Ordner bestehen bleiben, wie viele Rückrollungen gebucht sind. Schreibt nichts, braucht keinen Token. |
| `... --rueckwaerts N` | **Trockenlauf**: listet die letzten N Aktionen in umgekehrter Reihenfolge und was passieren würde — sendet **NICHTS**, ändert nichts. |
| `... --rueckwaerts N --wirklich` | Fährt die letzten N Aktionen **rückwärts** (neueste zuerst): Verschiebungen zurück in den Quellordner; angelegte Ordner werden **nicht gelöscht**, sondern nur gemeldet (dafür gibt es keinen Weg). Jede echte Rückrollung wird selbst wieder ins Manifest gebucht (`art=rueckroll`). |
| `--manifest PFAD` | Anderes Manifest (auch per `PCLOUD_MANIFEST`). |

Jede echte Rückrollung prüft vorher per Leseabfrage, ob das Element **noch**
im Zielordner liegt; sonst wird nur gemeldet und nichts angefasst. Ein
Fehler stoppt den Rest nicht (Zählung am Ende, Exit-Code 3 bei
Fehlschlägen; 2 bei fehlendem/kaputtem Manifest).

## Regeln, die im Code gelten

- **Kein Löschweg.** `_api_senden` lässt nur eine **Positivliste** durch:
  `createfolder`, `renamefile`, `renamefolder`, `listfolder`. Alles andere
  wird abgewiesen, **bevor** etwas gesendet wird. Ein Suchtest über die
  eigenen Dateien prüft, dass die verbotenen Methodennamen nirgends im
  Quelltext vorkommen — auch nicht als Kommentar.
- **Manifest nur anhängen** — zwei Einträge = zwei Zeilen, Vorhandenes
  bleibt unangetastet.
- **Der Token** (Umgebung `PCLOUD_TOKEN` oder `backend/.env`) wird gelesen,
  aber nie ausgegeben und nie geloggt; durchgereichte Fehlertexte laufen
  zusätzlich durch einen `***`-Filter. **Vier Tests** suchen den Test-Token
  in Ausgaben, Fehlermeldungen und Manifest-Zeilen.
- **Nur verschieben** — kein Umbenennen, kein Datei-Upload, kein Löschen.

## Prüfbefehl und Zahlen

```
cd backend && .venv/Scripts/python -m pytest tests/test_pcloud_bewegungen.py tests/test_pcloud_rueckrollen.py -q
# -> 44 passed

cd backend && .venv/Scripts/python -m pytest tests/ -q
# -> 574 passed, Exit 0
```

## Was noch NICHT live geprüft ist

- **Kein einziger Schreibweg lief live gegen die pCloud** —
  `createfolder`/`renamefile`/`renamefolder` wurden bisher nur gegen
  Attrappen (httpx gemockt) ausgeführt. Grund: Nachtlauf-Regel „nichts in
  die pCloud schreiben"; die erste Live-Nutzung passiert in Schritt N8 —
  erst `trocken=True`-Vorschau, dann Stapel für Stapel.
- Auch die **Leseprüfung** vor dem Verschieben (Zielordner-Inhalt) ist live
  noch nicht gelaufen; sie nutzt dasselbe `listfolder`, das der lesende
  Dienst bereits live beherrscht.
- Das dokumentierte pCloud-Verhalten „renamefile ersetzt gleichnamige
  Zieldateien" ist **aus der API-Doku übernommen**, nicht live nachgestellt
  (bewusst — dafür hätte eine Zieldatei ersetzt werden müssen). Der Code
  hält den Fall doppelt ab: Prüfung **vorher** + lauter Hinweis, falls es
  doch passiert.
- Eine **echte Rückrollung** (`--wirklich`) wurde noch nicht live gefahren;
  sie ist ausschließlich in Tests mit Attrappen belegt.
