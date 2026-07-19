# Document Automation — Bewerbungsmappen-Pipeline (Node.js)

## Was

Lokale Node.js-Pipeline für Bewerbungsunterlagen: erzeugt einen tabellarischen
Lebenslauf als Word-Dokument, rendert Anschreiben und Lebenslauf aus
HTML-Vorlagen zu A4-PDFs und fügt sie zusammen mit Zeugnis-PDFs zu einer
einzigen Bewerbungsmappe zusammen. Alles läuft auf dem eigenen Rechner —
es werden keine Daten an externe Dienste übertragen.

Im Portfolio dient das Projekt als Demonstrator für deklarative
Dokumentengenerierung und PDF-Verarbeitung; alle versionierten Dateien
enthalten neutrale Musterdaten („Max Mustermann“).

## Architektur

```
Daten im Skript ──▶ build_cv.js ───▶ output/muster_lebenslauf.docx      (docx / OpenXML)
HTML-Vorlagen ────▶ build_pdf.js ──▶ output/muster_lebenslauf.pdf
                                     output/muster_anschreiben.pdf      (Puppeteer / Headless Chrome)
Zeugnis-PDFs ─────▶ merge_pdfs.js ─▶ output/muster_bewerbungsmappe.pdf  (pdf-lib)
```

- **`build_cv.js` — deklarativer Word-Generator.** Der komplette Lebenslauf
  (Kontakt, Berufserfahrung, Ausbildung, Skills) ist als Datenstruktur mit
  Hilfsfunktionen im Skript definiert. Layout: zweiseitige A4-Tabelle mit
  farbiger Sidebar, Maße in DXA (OpenXML-Einheit, 1440 = 1 Zoll). Die
  Farbwerte sind mit `cv_preview.html` synchron gehalten, damit DOCX- und
  PDF-Fassung identisch aussehen.
- **`build_pdf.js` — HTML-zu-PDF-Renderer.** Lädt `cv_preview.html` und
  `anschreiben_muster.html` in Headless Chrome und druckt sie als A4-PDF
  (`printBackground` für Flächenfarben, `preferCSSPageSize` übernimmt die
  `@page`-Regel aus dem CSS). Die Gestaltung liegt vollständig im CSS.
- **`merge_pdfs.js` — Mappen-Zusammenführung.** Kopiert die Seiten aller
  Teil-PDFs in der für deutsche Bewerbungen üblichen Reihenfolge
  (Anschreiben → Lebenslauf → höchster Abschluss → Arbeitszeugnisse →
  Zertifikate) in ein Gesamt-PDF. Fehlende Dateien brechen den Lauf mit
  einer klaren Fehlermeldung ab.

## Entscheidungen

- **Lokale Skripte statt n8n-Cloud-Workflow.** Die erste Konzeption sah
  einen n8n-Workflow vor. Die Ablösung durch drei lokale Node.js-Skripte
  hat drei Gründe: keine laufenden Serverkosten, keine Übertragung von
  Bewerberdaten an Dritte und keine Abhängigkeit von einer
  No-Code-Plattform — die Pipeline läuft überall, wo Node.js installiert ist.
- **Deklaratives Layout statt manueller Word-Formatierung.** Schriften,
  Farben und Abstände sind im Code bzw. CSS definiert. Änderungen sind
  reproduzierbar und versionierbar; das Layout-Verrutschen beim manuellen
  Editieren in Word entfällt.
- **Trennung von Vorlagen und persönlichen Daten.** Versioniert sind nur
  Code und Muster-Vorlagen. Echte Dokumente bleiben lokal: Die zentrale
  `.gitignore` des Repos schließt für diesen Ordner `output/`, `*.docx`
  und `*.pdf` vom Tracking aus.

## Setup

Voraussetzung: Node.js ab Version 18.

```bash
npm install        # docx, puppeteer, pdf-lib
npm run build:cv   # → output/muster_lebenslauf.docx
npm run build:pdf  # → output/muster_lebenslauf.pdf + output/muster_anschreiben.pdf
npm run merge      # → output/muster_bewerbungsmappe.pdf
```

Hinweis zu `npm run merge`: Im Projektordner müssen drei Zeugnis-PDFs
liegen (`muster_bachelorzeugnis.pdf`, `muster_arbeitszeugnis.pdf`,
`muster_zertifikat.pdf`) — sie sind bewusst nicht versioniert. Für eigene
Unterlagen die Dateinamen im `files`-Array von `merge_pdfs.js` anpassen.
