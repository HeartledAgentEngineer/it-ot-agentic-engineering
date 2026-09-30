# Änderungsprotokoll 30.09.2026 — Büroklammer in der Hey-Agent-App

## Anlass

Sebastian am Handy (30.09.2026, morgens): In der neuen App tut die Büroklammer im Chat nichts —
kein Dialog, keine Meldung. Vermutung war eine fehlende Berechtigung („die App darf nur das
Mikrofon").

## Ursache (im Code belegt)

Keine Berechtigung, sondern fehlender Code: Die Büroklammer ist ein `<input type="file">`
(`frontend/index.html:121`). Eine Android-WebView zeigt dafür nur dann eine Auswahl, wenn die App
`WebChromeClient.onShowFileChooser` umsetzt. `MainActivity.kt` hatte diese Methode nicht
(`grep onShowFileChooser` im Ordner `android/`: 0 Treffer) — also passierte still nichts.
Im Browser (Comet/Chrome) ging es, weil der Browser die Auswahl selbst mitbringt.

## Änderung

- `android/app/src/main/java/de/sebastian/heyagent/MainActivity.kt`: `onShowFileChooser` öffnet
  die Android-Dateiauswahl (`ACTION_GET_CONTENT`, `CATEGORY_OPENABLE`), nur für das eigene
  Backend; Mehrfachauswahl nach `multiple`; Ergebnis über `StartActivityForResult`, Einzel- und
  Mehrfachauswahl (`clipData`) werden gelesen; offene Anfragen werden bei einer neuen Anfrage und in
  `onDestroy` mit `null` beantwortet, damit die Seite nicht hängen bleibt.
- Neu `DateiAuswahlRegel.kt` (reine Logik): `accept` → MIME-Typen, Intent-Typ, Rückgabe.
  Eigene Auswahl statt `FileChooserParams.createIntent()`, weil diese nur den ersten accept-Typ
  nimmt (PDF wäre nicht wählbar) und keine Mehrfachauswahl kennt.
- **Keine neue Berechtigung** im Manifest: Die Android-Auswahl gibt nur die gewählten Dateien frei.
- Neu `DateiAuswahlRegelTest.kt`: 10 JUnit-Tests, davon ein Wächter über die Grenze App ↔ Seite
  (liest `frontend/index.html` und prüft, dass die App jede erlaubte Dateiart kennt).
- `android/README.md`: Abschnitt „Büroklammer", Klassentabelle, WebView-Härtung, offene Punkte;
  veraltete Statuszeile („noch nie gebaut") berichtigt.

## Prüfung

`gradle --no-daemon testDebugUnitTest assembleDebug` → **BUILD SUCCESSFUL, Exit 0**;
JUnit **28/28 grün** (BackendStartLogik 12, DateiAuswahlRegel 10, MikrofonRegel 6).

## Offen

- Am Handy installieren und einmal echt anhängen (Foto aus der Galerie → erscheint im Chat).
  Erst das belegt den Upload Ende zu Ende; die WebView läuft mit `allowContentAccess=false`,
  was laut Android-Doku das Laden von `content://`-Adressen betrifft, nicht die Dateiauswahl.
