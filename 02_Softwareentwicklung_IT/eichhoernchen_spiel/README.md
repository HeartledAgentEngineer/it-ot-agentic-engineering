# Eichhörnchen-Spiel — Canvas-Quick-Prototype (eine HTML-Datei)

## Was

Ein HTML5-Canvas-Spiel mit umgekehrtem Spielprinzip: Nicht das Eichhörnchen
sammelt — **der Spieler ärgert das Eichhörnchen**. Per Tipp/Klick klaut man
ihm die Nuss aus der Baumkrone oder schüttelt einen Ast, sodass es
herunterfällt (und im South-Park-Stil mit „ICH BIN OKAY!!!" wieder aufsteht).
Je mehr Nüsse gestohlen werden, desto absurder wird es: Ab 25 Nüssen wird
das Eichhörnchen zu Frodo am Schicksalsberg, bei 100 wartet eine
Gollum-Überraschung, ab 150 startet der Shrek-Modus samt quasselndem Esel.

Entstanden ist das Ganze spontan als **Party-Spaßprojekt**: auf Zuruf remote
programmiert und als einzelne Datei über einen mobilen Kanal ausgeliefert.
Im Portfolio dient es als Beispiel für Rapid Prototyping mit nativen
Webtechnologien — ein komplettes Spiel ohne Framework, ohne Build-Schritt,
ohne einzige Asset-Datei.

## Architektur

Das gesamte Spiel (Markup, Styles, Logik, Grafik) steckt in einer einzigen
`index.html` (~560 Zeilen Vanilla-JavaScript, ES5):

```
index.html
 ├── Game Loop        requestAnimationFrame → update() + draw()
 ├── State-Machine    climb → crown → fall → dead → (zurück zu climb)
 ├── Level-System     Daten-Array LEVELS: Nuss-Schwellen → Skins
 │                    (Anfänger → Klaumeister → Frodo → Shrek)
 ├── Input            touchstart + click, Treffer-Test auf Nuss und Äste
 └── Rendering        100 % prozedural gezeichnet (Canvas-2D-API)
```

- **State-Machine statt verstreuter Flags.** Ein `state`-String steuert den
  Ablauf: Das Eichhörnchen klettert hoch (`climb`), turnt in der Krone
  (`crown`), fällt nach Ast-Schütteln (`fall`) und liegt kurz am Boden
  (`dead`), bevor der Zyklus neu beginnt. Jeder Zustand hat einen eigenen
  Block in `update()` — gut lesbar und leicht erweiterbar.
- **Skins als Daten, nicht als Code-Kopien.** Das Level-Array ordnet
  Nuss-Schwellen einem Skin-Schlüssel zu (`normal`/`cool`/`frodo`/`shrek`).
  Szene, Figur, Beute (Nuss/Ring/Zwiebel) und HUD fragen nur `skin()` ab
  und verzweigen im Zeichencode — dieselbe Spiellogik trägt alle vier Welten.
- **Prozedurale Grafik ohne Assets.** Baum, Himmel, Figuren, Partikel,
  Sprechblasen: alles wird zur Laufzeit mit Pfaden und Verläufen gezeichnet.
  Es gibt keine Bilddateien, daher auch nichts nachzuladen.
- **Festes logisches Koordinatensystem.** Das Canvas rechnet intern immer
  mit 480×640 Pixeln und wird per CSS auf die Bildschirmgröße skaliert;
  Touch-Koordinaten werden zurückgerechnet. Spiellogik und Treffer-Tests
  bleiben so komplett unabhängig vom Gerät.

## Entscheidungen

- **Eine Datei, null Abhängigkeiten.** Die Party-Situation verlangte
  Auslieferung über einen mobilen Kanal — eine einzelne HTML-Datei ist die
  robusteste Transporteinheit: kein Server, kein Build, kein CDN, läuft per
  Doppelklick. Diese Constraint erklärt auch den Verzicht auf Sprites
  (siehe prozedurale Grafik oben).
- **Eigene Bezier-Ovale statt `ctx.ellipse`.** Ältere Mobil-Browser
  (insbesondere iOS-WebViews) kennen `ctx.ellipse` nicht zuverlässig.
  Die Hilfsfunktion `oval()` approximiert Ellipsen aus vier Bezier-Kurven
  (Kappa ≈ 0,5523) — dieselbe Technik, die auch Vektorprogramme nutzen.
- **ES5-Syntax (`var`, Funktionsausdrücke).** Maximale Kompatibilität bis
  hinunter zu alten Android-Browsern auf Gäste-Handys — auf einer Party
  kontrolliert man die Endgeräte nicht.
- **Humor als Progression.** Statt Highscore-Druck belohnt das Spiel mit
  Eskalationsstufen (Filmzitate, Jumpscare, Esel-Dialoge). Die Specials
  hängen an denselben Nuss-Schwellen wie die Level — ein Zähler treibt
  das komplette Spielgefühl.

## Ausführung

Kein Webserver nötig — das Spiel ist vollständig clientseitig:

1. `02_Softwareentwicklung_IT/eichhoernchen_spiel/index.html` per
   Doppelklick im Browser öffnen (Desktop oder Smartphone).
2. **Nuss antippen/anklicken** → klauen (Zähler steigt, Eichhörnchen weint).
3. **Ast antippen/anklicken** → schütteln (Eichhörnchen fällt vom Baum).
4. Schwellen: 5 Nüsse → Klaumeister · 25 → Frodo-Modus · 100 → 👁 ·
   150 → Shrek-Modus.
