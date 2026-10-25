# 23.10.2026 — W1: Zielordner Ebene für Ebene anlegen

## Befund

Echter Lauf am Handy (`whatsapp_bilder_hochladen.py --schreiben --max 20`): alle 5.904 Bilder
meldeten den Fehler „abgelehnt 2002“, 0 wurden hochgeladen. Nach dem ersten Ordnerfehler
versuchte der Lauf es bei jedem weiteren Bild erneut (jede Datei wurde vorher gelesen und gehasht).

## Ursache

`Lauf._ordner_id` rief über `ordner_holen_sicher` → `ordner_holen_oder_anlegen`
(`tools/pcloud/uebergabe_hochladen.py`) `createfolderifnotexists` mit dem VOLLEN Pfad
(`/Agent/whatsapp_bilder/empfangen/2020`) auf. Die echte pCloud legt damit nur die LETZTE Ebene an;
fehlt ein Elternordner, antwortet sie mit 2002 („A component of parent directory does not exist“).
Die Test-Attrappe legte dagegen jeden Pfad samt Eltern an — deshalb waren die Tests grün.

## Änderung

- `tools/handy/whatsapp_bilder_hochladen.py` (der Altcode `uebergabe_hochladen.py` bleibt unverändert):
  - `Lauf._ordner_id` holt/legt die Ebenen von oben nach unten an, beginnend mit der ersten
    zulässigen Ebene direkt unter `ug.ERLAUBTE_WURZEL` (`/Agent/`), je Ebene über
    `ordner_holen_sicher` und mit Zwischenspeicher `self.ordner_ids` (jede Ebene höchstens einmal je Lauf).
  - **Annahme:** `/Agent` existiert bereits (`ziel_pfad_pruefen` erlaubt `/Agent` selbst nicht). Fehlt es,
    scheitert die erste Ebene mit „abgelehnt 2002“ und der Lauf bricht ab.
  - Früher Abbruch: Scheitert das Holen/Anlegen, wird der Fehler **einmal** gezählt (bestehende
    Fehlerart-Logik), das neue Kennzeichen `Lauf.ordner_abbruch` verhindert weitere Verarbeitung
    (`verarbeiten` kehrt zurück, die Hauptschleife bricht ab, es werden keine weiteren Bilder gelesen
    oder gehasht). Ausgabe: feste Zeile `abgebrochen: Zielordner nicht anlegbar, keine weiteren Uploads.`
    (ohne Pfad- oder pCloud-Fehlertext); Exit 1 über den bestehenden Weg (Fehlerzähler > 0).
  - Der Trockenlauf bleibt unverändert (keine schreibende Methode).

## Tests (`backend/tests/test_whatsapp_bilder_hochladen.py`)

- Attrappe realistisch: `createfolderifnotexists` liefert `{"result": 2002, ...}`, wenn der Elternordner
  fehlt. Ausgangszustand der Attrappe in `_welt`: `/` und `/Agent` (ausdrücklich vorab angelegt).
- Neu: `test_attrappe_legt_wie_die_echte_pcloud_nur_die_letzte_ebene_an`,
  `test_ziel_samt_zwischenordnern_fehlt_upload_gelingt` (7 Ebenen je genau einmal, von oben nach unten),
  `test_vorhandene_ordner_werden_nicht_doppelt_angelegt` (inkl. zweiter Lauf),
  `test_ordnerfehler_bricht_nach_dem_ersten_ab[False/True]` (genau 1 Fehler, 0 Uploads, 1 Ordneraufruf,
  1 gehashte Datei, kein Manifesteintrag, Exit 1, kein Pfad-/Fehlertext; True = `/Agent` fehlt, 2002),
  `test_trockenlauf_ruft_weiter_keine_schreibende_methode_auf`.
- Angepasst: `test_ordnerweg_zaehlt_die_fehlerart_mit_code` erwartet jetzt `abgelehnt 2000 x1` statt `x5`
  (Abbruch nach dem ersten Fehler); Trockenlauf-Test erwartet `{"/", "/Agent"}`;
  `ALTCODE_ZUORDNUNG` führt den neuen Altcode-Zugriff `ERLAUBTE_WURZEL`.
- Rot vor der Reparatur (alte Werkzeugdatei, neue Tests): `test_ziel_samt_zwischenordnern_fehlt_upload_gelingt`
  (`assert 1 == 0`, Exit 1), `test_vorhandene_ordner_werden_nicht_doppelt_angelegt`,
  `test_ordnerfehler_bricht_nach_dem_ersten_ab[…]` (`assert 5 == 1`), `test_ordnerweg_zaehlt_die_fehlerart_mit_code`
  (`x5` statt `x1`); mit der strengen Attrappe schlugen vorher außerdem 122 bestehende Schreibtests fehl.
- Grün danach: `test_whatsapp_bilder_hochladen.py`, `test_whatsapp_bilder_zaehlen.py`, `test_pcloud_uebergabe.py`:
  298 passed, 1 failed (bekannt: `test_skripte_sind_syntaxgeprueft_und_reine_lf`, CRLF im Worktree-Checkout,
  unabhängig von dieser Änderung).
