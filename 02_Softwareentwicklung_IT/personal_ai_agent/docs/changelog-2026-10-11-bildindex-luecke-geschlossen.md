# Changelog 11.10.2026 — Die 889 ohne Vektor sind geschlossen (Ursache gemessen)

## Warum

Im vorigen Lauf (10.10., 20:2x) hat der neue Nachweis-Abschnitt „Bildindex (Bildsuche)“
eine Lücke gefunden: **889 beschriebene Fotos hatten keinen Vektor** in
`bild_index.db` — die Bildsuche wäre für sie unvollständig. Die **Ursache stand
ehrlich offen** („keine Kombination der vier Beschreibungsdateien ergibt 25.352“).

Dieser Lauf hat die Ursache **gemessen statt geraten** und die Lücke geschlossen
— ohne Bild, nur über den bestehenden Einbettungsweg des Projekts.

## Der Befund (gemessen, nur lesend)

Trockenlauf des Werkzeugs `bild_index_einbetten.py` über den Altspeicher:

```
Beschreibungen : ...\bild_beschreibungen.jsonl
Datenbank      : ...\bild_index.db
Modus          : Trockenlauf | Modell: openai/text-embedding-3-small | Budget: 1.00 USD
  Beschreibungen gelesen : 19065 (verworfen: 0, Dubletten: 0)
  schon im Index        : 18176
  neu eingebettet       : 0 von 889 offenen
  Token (schaetzung)    : 14691
```

Damit ist die Ursache **belegt**: die 889 Zeilen sind **keine Ausschusszeilen**
(`verworfen: 0`, `Dubletten: 0`) — sie wurden beim Bau des Index schlicht **nie
eingebettet** (der Bau-Lauf endete vorher / deckte sie nicht ab). Es war **kein
Datenfehler, sondern ein unfertiger Lauf**. Der frühere Verdacht „andere Quelle“
ist damit erledigt: die Quelle war die richtige, sie war nur nicht abgearbeitet.

Nebenbei gemessen (Gegenrichtung, 0): der Index enthielt **nichts**, das keine
Beschreibungsdatei kennt.

## Was gemacht wurde

Ein **Nachlauf ausschließlich der 889 fehlenden Texte** über denselben Weg,
mit harter Kostengrenze:

```
./backend/.venv/Scripts/python.exe tools/foto_sortierung/bild_index_einbetten.py \
    --jsonl .../bild_beschreibungen.jsonl --db .../bild_index.db \
    --budget 0.05 --schreiben
```

```
→ Einbetten (offen: 889, Schaetzung 0.000294 USD)
  neu eingebettet       : 889 von 889 offenen
  Token (gezaehlt)      : 16496
  Kosten                : 0.000330 USD (Grenze 0.05 USD, 0.02 USD/1M Token)
  Dauer                 : 21.5 s
```

* **Keine Bilder verlassen das Gerät** — eingebettet wurden nur die bereits
  vorhandenen Beschreibungstexte (Textsuche, kein Vision-Aufruf).
* **Wiederholbar (Idempotenz belegt):** der zweite Lauf meldet
  `schon im Index: 19065`, `neu eingebettet: 0 von 0 offenen`.

## Beleg nach dem Lauf (Nachweis am echten Bestand, Exit 0)

```
Bildindex (Bildsuche): bild_index.db: 26.241 Bilder, 26.241 mit Vektor, 26.241 mit Beschreibung
  openai/text-embedding-3-small; 1536 Dimensionen; 964.275 Token; 0,02 USD; Stand 2026-10-10T22:30:25+00:00
  Beschrieben, aber ohne Vektor im Index: 0; im Index, aber nicht beschrieben: 0
...
Ergebnis: 4 Luecke(n)
  - sortierplan.json: 3 Fotos ohne Beschreibung
  - sortierplan_bildervideos.json: 25 Videos ohne Gesichter-Lauf
  - sortierplan_bildervideos.json: 5 Fotos ohne Beschreibung
  - sortierplan_reich_gesamt.json: 8 Fotos ohne Beschreibung
```

Die Lücke **„bild_index.db: 889 beschriebene Fotos ohne Vektor“** ist **weg**
(5 → 4 Lücken); der Index hat jetzt **26.241** Einträge, alle mit Vektor.

## Ehrlich offen (unverändert)

* 8 Fotos ohne Beschreibung und 25 Videos ohne Gesichter-Lauf — beides
  kostenpflichtig bzw. >300 MB und damit **Sebastians Entscheidung**.
* WhatsApp-Verdrahtung braucht das Gerät (Handy am Kabel).

## Geänderte Dateien

* `docs/changelog-2026-10-11-bildindex-luecke-geschlossen.md` (diese Datei)

Kein Code geändert: Werkzeug und Index-Aufbau sind unverändert; es wurde nur die
fehlende Arbeit nachgeholt. Der Nachweis (Journal 12) hatte die Lücke gefunden —
das ist genau sein Zweck.
