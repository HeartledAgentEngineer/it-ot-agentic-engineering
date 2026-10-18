# Video-Standbilder lassen sich markieren (Schritt S2, 18.10.2026)

Sebastians Befund (16.10.2026, To-do Punkt 11): „Personenbilder bzw. Standbilder, die zu einem
Video gehören, lassen sich **nicht markieren** — sie lassen sich nur vergrößern. Erwartet:
dieselbe Markierung/Auswahl wie bei normalen Bildern." Der Dauerlauf-Plan führt das als Schritt
**S2** und hält fest, dass dafür zuerst ein eigener **Schreib-/Auswertungsweg für Video-Kennungen**
zu schneiden ist (`VIDEO_GESPERRT`).

## Was vorher galt (gemessen, nicht vermutet)

- `backend/app/services/gruppen_quiz.py` lehnte Video-Kennungen in **drei** Funktionen pauschal ab
  (`ausschliessen`, `ausschliessen_person`, `zuordnen`, Konstante `VIDEO_GESPERRT`).
- `frontend/gruppen_quiz.js` baute Video-Kacheln ohne Pointer-Verdrahtung; ein kurzer Klick öffnete
  nur das Standbild (Zeile „Video-Kachel ohne Pointer-Verdrahtung", Beleg
  `docs/changelog-2026-10-16-kachelbedienung-auswahlmodus.md`).
- Der Grund für die Sperre stand im Modulkommentar: die Regeln brauchen eine Foto-`bild_id`, die
  Gruppierung kenne Standbilder nicht.

## Was der Code jetzt tut

Die Sperre ist weg — und zwar nicht durch „Markieren ohne Wirkung", sondern über dieselbe
Regel-Form wie bei Fotos:

- **Schlüssel eines Video-Gesichts ist seine `gid` `"<standbild_fileid>:<index>"`.** Das Standbild
  ist eine echte pCloud-Datei mit eigener Kennung. Wird sie als `bild_id` in
  `personen_vorgaben.json → "ausgeschlossen"` geschrieben, liest `ausgeschlossen_lesen()`
  (`gid = "<bild_id>:<index>"`) **genau diese** `gid` zurück. Ausschließen und Zuordnen wirken damit
  sofort in Liste, Belegen (Gruppenkopf) und Personenansicht.
- Neu `_video_gids_je_kennung(kennungen)` liefert `{kennung: {Video-gid, …}}`; die Prüfung
  „gehört das Gesicht zu diesem Vorschlag?" führt Foto- und Video-Kennungen zusammen
  (`ausschliessen`, `ausschliessen_person`, `zuordnen`).
- `gesichter(kennung)` blendet ausgeschlossene **Video**-Gesichter jetzt genauso aus wie Fotos;
  `gesichter_person(name)` berücksichtigt für Video-Gesichter Ausschluss **und** Um-Zuordnung.
  Damit erscheint ein von Hand zugeordnetes Standbild in der Personenansicht (`zugeordnet`), und
  `_video_teil(...)` lädt dafür auch die Kennungen fremder Zuordnungen mit.
- Ungültiges bleibt ungültig: eine Video-`gid`, die nicht zu diesem Vorschlag gehört, wird
  weiterhin abgelehnt („Gesicht gehört nicht (mehr) zu diesem Vorschlag"), und ein Video-Gesicht
  **ohne Standbild** hat keine `gid` und ist damit nicht markierbar (es bleibt als Zahl sichtbar).
- `frontend/gruppen_quiz.js`: alle Kacheln bekommen dieselbe Verdrahtung („kurzer Klick öffnet,
  Halten startet die Auswahl"); die Infozeile sagt statt „🎬 Video-Gesichter nur ansehen" jetzt
  „🎬 Video-Standbilder lassen sich genauso markieren". Cache-Schlüssel
  `gruppen_quiz.js?v=20261018A`, `index.html`.
- Die alte Konstante `VIDEO_GESPERRT` und ihr Kommentar sind entfernt (kein toter Text).

## Belege (in diesem Lauf ausgeführt)

- `backend/.venv/Scripts/python -m pytest tests/test_gruppen_quiz_video.py -q` → **30 passed**.
  Der Test, der die Sperre festhielt (`test_einzelaktionen_an_video_gesichtern_gesperrt`), ist
  durch sechs neue ersetzt: Ausschließen wirkt sofort **und** steht richtig in der Datei
  (`{"kennung": "Person_2001", "bild_id": "9001", "index": 0}`), Rückgängig stellt Beleg und Liste
  wieder her, Ausschließen über die Person, Zuordnen erscheint in der Personenansicht
  (`video: true`, `zugeordnet: true`), fremde/erfundene Kennung wird abgelehnt (Datei unverändert),
  und eine Video-Regel berührt **keine** Fotos.
- `node tests/test_gruppen_auswahl.js gruppen_quiz.js` (aus `frontend/`, Exit 0): langer Druck
  markiert das Video-Standbild, das Ausschließen geht mit `gesichter: ["a9"]` und `kennung: "G-1"`
  an den Server, außerhalb des Auswahlmodus öffnet der kurze Klick weiter das Standbild.
- `node tests/test_gruppen_quiz.js gruppen_quiz.js` (Exit 0): Infozeile und Quelltext-Wächter auf
  den neuen Stand gezogen; `node tests/test_gruppen_liste.js` ebenfalls Exit 0.
- **Gegenprobe gegen den alten Stand** (die HEAD-Fassungen von `app/` in einen Ordner **außerhalb
  des Repos** kopiert, Messskript `/tmp/altmess_video/gegenprobe.py`, dieselben erfundenen
  Dateien in beiden Läufen): **alt** `ausschliessen("Person_2001", ["9001:0"])` →
  `{'ok': False, 'fehler': 'Video-Gesichter lassen sich (noch) nicht einzeln ausschließen …'}`,
  **keine** Vorgaben-Datei entsteht, die Gesichterliste bleibt bei `['9001:0', '9002:0']` — die
  Fähigkeit gab es vorher nachweislich nicht. **neu** (dasselbe Skript) →
  `{'ok': True, 'ausgeschlossen': 1, 'gesamt': 1}`, die Vorgaben-Datei entsteht, danach ist die
  Liste `['9002:0']`.
- **Volles Tor** über den Commit-Haken: siehe Commit (Zahl im Journal des Dauerlauf-Plans).

## Ehrliche Grenzen

- **Der Gruppierlauf am PC kennt Standbilder weiterhin nicht.** `personen_gruppieren.py` trennt
  Video- und Fotozeilen; eine Video-Regel steht in der Datei, wirkt dort aber nicht. Sofort wirkt
  sie am Handy (Liste, Belege, Personenansicht).
- **Video-Gesichter ohne Standbild** bleiben unmarkierbar — ohne Standbild gibt es keine `gid`.
  Sie erscheinen weiterhin nur als Zahl („+ N aus Videos (noch ohne Standbild)").
- **Nicht geprüft:** die Bedienung mit dem Finger am echten Gerät (langer Druck auf einem
  Video-Standbild) — das bleibt Sebastians Abnahme am Handy.
- Kein Bild, kein Vision-Aufruf, keine echten Personennamen in neuen Dateien, Kosten 0 USD.
