# Lücken benennen statt nur zählen — Bestandsprüfung nennt Kennung und Grund (10.10.2026)

## Warum

Der Nachweis `tools/foto_sortierung/bestand_pruefen.py` konnte seit dem 10.10. sagen,
**wie viele** Fotos in keiner Beschreibungsdatei stehen (8 von 23.916). Er konnte aber
nicht sagen, **welche** — die acht Kennungen waren von Hand nachgerechnet. Genau das
schließt „fertig ist, was verifiziert ist" aus: eine Zahl, die das Werkzeug nicht selbst
reproduziert, ist kein Nachweis.

## Was jetzt gilt

Fehlende Fotos werden **mit Kennung und Grund** benannt (`--luecken-details N`,
Voreinstellung 20; `0` schaltet die Einzelheiten ab und zählt nur wie früher). Die Gründe
sind mechanisch aus den vorhandenen Dateien abgeleitet, nichts ist geraten:

| Grund | Bedeutung |
|---|---|
| `keine Vektorzeile` | für dieses Bild gibt es keine Zeile im Gesichtslauf |
| `ohne Bildmasse` | Vektorzeile ohne Breite/Höhe — das Bild war **nicht ladbar** (keine Vorschau, defekte Datei) |
| `Bild geladen, kein Beschreibungseintrag` | Zeile mit Maßen da, Beschreibung fehlt trotzdem (offener Rest) |
| `; Name mehrfach im Plan (Dublette)` | derselbe Dateiname steht bei mehreren Kennungen — **Hinweis**, keine belegte Ursache |

Zwei neue Bestandteile im Werkzeug:

- `masse_da(zeile)` — prüft Breite/Höhe einer Vektorzeile (`0`/fehlend = nicht ladbar).
  `foto_vektoren_lesen()` führt die Bilder mit echten Maßen als `mit_massen` mit.
- `gesamtplan_lesen()` ermittelt zusätzlich `namen_doppelt` (Kennungen, deren Dateiname
  mehrfach im Plan steht) und `luecken_details(...)` formt daraus den Bericht.

Ausgegeben werden **nur Kennungen und Gründe** — nie ein Dateiname (der Test
`test_bestand_gibt_keine_inhalte_aus` hält das fest).

## Messung am echten Bestand (frisch, Exit 0)

```
Gesamtplan sortierplan_reich_gesamt.json: 28.796 Eintraege = 23.916 Fotos + 1.666 Videos + 3.214 ohne Namen
  Beschreibungen:   23.908 von 23.916 Fotos (100,0 %) - in keiner Beschreibungsdatei fehlen 8
  Fehlende Fotos (8), mit Kennung und Grund:
    53604110021: ohne Bildmasse (Bild nicht ladbar, keine Vorschau)
    53632318755: ohne Bildmasse (…); Name mehrfach im Plan (Dublette)
    53632324873: Bild geladen, kein Beschreibungseintrag; Name mehrfach im Plan (Dublette)
    53634269404: ohne Bildmasse (…); Name mehrfach im Plan (Dublette)
    53634285933: Bild geladen, kein Beschreibungseintrag; Name mehrfach im Plan (Dublette)
    56226931906: Bild geladen, kein Beschreibungseintrag
    56226934998: Bild geladen, kein Beschreibungseintrag
    93186947452: Bild geladen, kein Beschreibungseintrag; Name mehrfach im Plan (Dublette)
  Ursachen: 0 ohne Vektorzeile, 3 ohne Bildmasse, 5 ohne Beschreibungseintrag; 5 mit mehrfach vorkommendem Namen
```

Damit ist die Lücke aus Journal 6 geschlossen: **3 der 8 Fotos sind nicht ladbar**
(Maße 0×0 = keine Vorschau in pCloud), **5 sind geladen, aber ohne Beschreibungseintrag**.

## Was das NICHT erklärt (ehrlich)

- Für die 5 „Bild geladen, kein Beschreibungseintrag" gibt es **keine Ursache in den
  Daten**: die Beschreibungsläufe haben kein Protokoll hinterlassen. Der Verdacht
  „doppelter Dateiname" ist **widerlegt**: `plan_zeilen_lesen()` in
  `bild_beschreiben.py` entdoppelt ausschließlich über `fileid`, nie über den Namen.
  Ob es ein Download-Fehler im pCloud war, lässt sich nachträglich nicht mehr belegen.
- Ein Nachzieh-Lauf für die 5 wäre ein **kostenpflichtiger** Lauf — bleibt Sebastians
  Entscheidung, hier nicht gestartet.

## Prüfung

- `tests/test_bestand_und_handy_uebergabe.py`: **20 passed** (vier neue Tests:
  `test_gesamtplan_luecke_wird_benannt_mit_grund`,
  `test_luecken_details_klassifiziert_masse_und_dubletten`,
  `test_luecken_details_deckelt_die_ausgabe`, plus die erweiterte Grund-Erkennung).
- Lauf am echten Bestand: Exit 0, Zeile „Fehlende Fotos (8), mit Kennung und Grund:".
- Nur lesend: es wird weiterhin nichts geschrieben (`test_bestand_schreibt_nichts`).
