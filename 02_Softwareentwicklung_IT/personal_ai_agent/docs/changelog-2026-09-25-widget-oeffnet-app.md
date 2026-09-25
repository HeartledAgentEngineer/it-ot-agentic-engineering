# Changelog 25.09.2026 — Widget öffnet die App (nicht mehr den Browser)

## Der Wunsch (Sebastian, 25.09.2026)

> „Es war ja vorher so, dass das Widget immer den Tab in meinem Chrome-Browser … geöffnet hat.
> Und da soll jetzt ja unsere eigene App geöffnet werden, damit die auch quasi über das
> Task-Menü … geschlossen werden kann."

## Was am Handy gemessen wurde

| Prüfung | Ergebnis |
|---|---|
| Server läuft (Termux) | `{"status":"ok",…,"memory_count":175}` |
| Frontend ist eine installierbare App | `manifest.json`, `icon-192.png`, `icon-512.png`, `sw.js` vorhanden; Manifest: `name: Personal AI Agent`, `short_name: AI Agent`, `display: standalone` |
| Installation über Chrome („Installieren und Verknüpfung erstellen" → **Installieren**) | Paket **`org.chromium.webapk.a6e9dff4c545552e2_v2`** |
| Start-Activity | `org.chromium.webapk.shell_apk.h2o.H2OOpaqueMainActivity` |
| Eigenes Fenster? | **0 Browser-Leisten-Elemente** gefunden (keine Adressleiste, kein „Neuer Tab") — bestätigt: eigenes Fenster ohne Tabs |

Damit ist die Oberfläche eine **echte App auf dem Startbildschirm** — eigene Aufgabe im Task-Menü,
dort schließbar, kein Browser-Tab.

## Die Grenze (und warum es trotzdem geht)

Eine Web-App kann den Server **nicht** starten: sie ist reiner Browser-Inhalt, hat keinen nativen
Code und keine Shell — sie kommt an Termux nicht heran. **Deshalb macht es das Startskript
herum.**

## Die Änderung

**Datei:** `start-termux.sh`

1. Der Server läuft jetzt **im Hintergrund** (`&` + `wait`), damit das Skript nach dem Start
   noch etwas tun kann — die Termux-Session hängt wie vorher am Server, **Strg+C beendet ihn
   weiterhin direkt**.
2. Das Skript **wartet, bis der Port antwortet** (max. ~20 s, statt blind zu öffnen).
3. Danach öffnet es **die installierte App** (Paket wird gesucht: `pm list packages` → erstes
   `org.chromium.webapk*`) über ihre Start-Activity. Erst wenn keine App installiert ist, geht
   die Adresse an den **Browser** (Rückfallweg).
4. Jeder Fall wird im Klartext gemeldet:
   - `✔ App geöffnet: <Paket> (eigenes Fenster, im Task-Menü schließbar)`
   - `⚠ App-Start fehlgeschlagen — versuche Browser.`
   - `ℹ Keine installierte App gefunden — im Browser geöffnet: …`

## Prüfung

```
bash -n start-termux.sh        # Syntaxprüfung → Exit 0
```

Der Ende-zu-Ende-Beleg ist die Protokollzeile `✔ App geöffnet: …` **nach einem Widget-Tipp** —
das kann nur auf dem Gerät entstehen.

## Reihenfolge auf dem Handy (so ist es gedacht)

| Tipp | Was passiert |
|---|---|
| **Widget „agent"** | Git-Abgleich → Archiv-Index nach `~/` → alter Server aus → Server an → **App öffnet sich** |
| **App „AI Agent"** | Oberfläche im eigenen Fenster (kein Browser-Tab), im Task-Menü schließbar |

Die App allein startet den Server **nicht** — dafür bleibt das Widget zuständig. Eine echte
APK (Stufe C der Roadmap) könnte später auch das: sie darf Termux per Intent ansprechen.
