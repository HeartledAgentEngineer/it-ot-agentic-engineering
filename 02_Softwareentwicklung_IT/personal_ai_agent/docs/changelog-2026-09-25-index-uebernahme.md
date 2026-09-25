# Changelog 25.09.2026 — Archiv-Index landet selbstheilend auf dem Handy

## Ausgangslage (gemessen)

Der neu gebaute Wissensspeicher-Index ist **262,7 MB** groß:

| Kennzahl | Wert |
|---|---|
| Nachrichten | **82.774** (davon 42.147 WhatsApp, 16.02.2020–12.08.2026) |
| Chunks / Vektoren | **33.312 / 33.312** |
| Gespräche | **1.111** |
| Kosten des Baus | **0,207989 $** (10.399.430 Token gezählt, 0,02 $/1M) |
| Baudauer | 680,9 s |
| Gegenprobe Volltext | „Fabia" **735 Treffer**, „Torsten" **16 Treffer** |

## Das Problem

1. Über Git ist die Datei nicht transportierbar (Archivordner ist absichtlich ausgeschlossen).
2. **ADB kann nicht in den Termux-Heimordner schreiben** (App-Sandbox) — der Index landet
   deshalb in `/sdcard/Download/`.
3. **ADB-Tippen erreicht Termux nicht.** Geprüft mit einem Testbefehl
   (`echo test > /sdcard/Download/termux-tipptest.txt`): die Testdatei **entstand nicht**.
   Termux' Terminal nimmt synthetische Tastatur-Ereignisse nicht an.
4. Der Server sucht den Index in `~/archiv_index.db` — von Hand verschieben war also
   bisher ein manueller Schritt für Sebastian.

## Die Änderung

**Datei:** `start-termux.sh` (gilt für jede Termux-Installation, auch auf anderen Geräten)

Neuer Abschnitt **„Archiv-Index übernehmen (selbstheilend)"** direkt nach
`termux-setup-storage`:

- Liegt `/sdcard/Download/archiv_index.db` (oder `~/storage/downloads/…`), wird er nach
  `~/archiv_index.db` **verschoben**.
- Ein **vorhandener** Index wird **nicht gelöscht**, sondern als
  `~/archiv_index_alt.db` beiseitegelegt — der Rückweg bleibt offen.
- Schlägt die Übernahme fehl, **bricht der Start nicht ab**; es steht eine Warnung im
  Protokoll und der Server läuft weiter.

Weil `~/.shortcuts/agent` ein **Symlink** auf dieses Skript ist, wirkt die Änderung nach
dem nächsten `git pull` — also nach **einem Widget-Tipp**. Derselbe Tipp holt auch den
aktuellen Code: der Handy-Server kannte die neue Archiv-Route noch nicht
(`/api/archiv/wissen/ueberblick` → `{"detail":"Not Found"}`), weil er mit älterem Stand lief.

## Prüfung

```
bash -n start-termux.sh        # Syntaxprüfung, Exit 0
```

Ein vollständiger Lauf auf dem Gerät ist erst nach dem Widget-Tipp möglich — der
Prüfbeleg dafür ist die Protokollzeile `✔ übernommen: ~/archiv_index.db (… MB)`.
