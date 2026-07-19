const {
    Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
    PageBreak, AlignmentType, BorderStyle, WidthType, ShadingType, VerticalAlign, LevelFormat,
    ExternalHyperlink
} = require('docx');
const fs = require('fs');
const path = require('path');

// --- Farben (synchron mit cv_preview.html) ---
const C_DARK   = "1E3A5F";  // dunkelblau: Header, Sidebar-Header, Querstriche
const C_MED    = "3D5A85";  // Steel Blue: Akzente (Job-Rollen, Schulnamen, Bullets)
const C_SIDE   = "EBF0F5";  // hellblau-grau: Sidebar-Hintergrund
const C_WHITE  = "FFFFFF";
const C_TEXT   = "2D2D2D";
const C_MUTED  = "666666";
const C_TAG    = "9DB8D9";  // hellblau: Subtitle im Header

// --- Seitenmaße (A4, DXA: 1440 = 1 Zoll) ---
const PAGE_W   = 11906;
const PAGE_H   = 16838;
const MARGIN   = 512;        // ~0.9 cm
const CONT_W   = PAGE_W - 2 * MARGIN; // 10882
const SIDE_W   = 3280;
const MAIN_W   = CONT_W - SIDE_W;     // 7602

const nb  = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const nbs = { top: nb, bottom: nb, left: nb, right: nb, insideH: nb, insideV: nb };
const nbCell = { top: nb, bottom: nb, left: nb, right: nb };

// --- Hilfsfunktionen ---
function t(text, opts = {}) {
    return new TextRun({
        text,
        font: "Arial",
        size:    opts.size   ?? 20,
        bold:    opts.bold   ?? false,
        italic: opts.italic ?? false,
        color:   opts.color  ?? C_TEXT,
        underline: opts.underline ?? false,
    });
}

function sideHeader(label) {
    return new Paragraph({
        children: [t(label, { bold: true, color: C_WHITE, size: 19 })],
        spacing: { before: 180, after: 80 },
        shading: { fill: C_DARK, type: ShadingType.CLEAR },
        indent: { left: 120, right: 80 },
    });
}

function sideItem(text, opts = {}) {
    return new Paragraph({
        children: [t(text, { size: 18, color: opts.muted ? C_MUTED : C_TEXT, bold: opts.bold ?? false })],
        spacing: { before: opts.before ?? 40, after: 20 },
        indent: { left: 140 },
    });
}

function sideLinkedItem(text, url, opts = {}) {
    return new Paragraph({
        children: [
            new ExternalHyperlink({
                children: [
                    t(text, {
                        size: 18,
                        color: opts.color ?? C_DARK,
                        bold: opts.bold ?? false,
                        underline: opts.underline ?? true
                    })
                ],
                link: url,
            })
        ],
        spacing: { before: opts.before ?? 40, after: 20 },
        indent: { left: 140 },
    });
}

function mainHeader(label) {
    return new Paragraph({
        children: [t(label, { bold: true, color: C_DARK, size: 23 })],
        spacing: { before: 200, after: 80 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: C_DARK, space: 1 } },
    });
}

function jobEntry(company, period) {
    return new Paragraph({
        children: [
            t(company, { bold: true, size: 21 }),
            t("   " + period, { color: C_MUTED, size: 19 }),
        ],
        spacing: { before: 140, after: 20 },
    });
}

function jobRole(role) {
    return new Paragraph({
        children: [t(role, { color: C_MED, bold: true, size: 20 })],
        spacing: { before: 0, after: 40 },
    });
}

function bullet(text) {
    return new Paragraph({
        children: [t(text, { size: 19 })],
        numbering: { reference: "bullets", level: 0 },
        spacing: { before: 0, after: 24 },
    });
}

function eduEntry(degree, school, detail) {
    const children = [
        new Paragraph({ children: [t(degree, { bold: true, size: 21 })], spacing: { before: 120, after: 20 } }),
        new Paragraph({ children: [t(school, { color: C_MED, size: 19 })], spacing: { before: 0, after: 20 } }),
    ];
    if (detail) children.push(
        new Paragraph({ children: [t(detail, { color: C_MUTED, size: 18 })], spacing: { before: 0, after: 60 } })
    );
    return children;
}

// --- SIDEBAR SEITE 1 ---
const sidebar1 = [
    new Paragraph({ spacing: { before: 200, after: 200 } }), // Freiraum statt Foto
    sideHeader("KONTAKT"),
    sideItem("Musterstraße 1"),
    sideItem("12345 Musterstadt"),
    sideItem("+49 123 4567890", { before: 60 }),
    sideItem("max.mustermann@example.com"),
    sideItem("linkedin.com/in/max-mustermann", { before: 60 }),
    sideItem("01.01.1990", { before: 60 }),

    sideHeader("SYSTEMKOMPETENZ"),
    sideItem("Vernetztes Denken"),
    sideItem("KI-gestützte Entwicklung (Claude Code, LLMs)"),
    sideItem("Modulare & wartbare Softwareentwicklung"),
    sideItem("Systemüberblick: Maschine bis ERP"),
    sideItem("Echtzeit- & event-basierte Systeme"),
    sideItem("Systemanalyse & Systemoptimierung"),

    sideHeader("STEUERUNGSTECHNIK"),
    sideItem("IEC 61131-3 (ST, SFC, FUP)"),
    sideItem("Siemens TIA Portal / WinCC Unified"),
    sideItem("TwinCAT 3 / Beckhoff"),
    sideItem("Profinet / EtherCAT"),
    sideItem("OPC UA / Beckhoff ADS"),
];

// --- SIDEBAR SEITE 2 ---
const sidebar2 = [
    sideHeader("PROGRAMMIERUNG"),
    sideItem("Prozedurale Programmierung (C)"),
    sideItem("Objektorientierte Programmierung (Java)"),
    sideItem("Git-Versionierung"),
    sideItem("C# / .NET / WinForms"),
    sideItem("Visual Basic / VB.NET"),

    sideHeader("SPRACHEN"),
    sideItem("Deutsch — Muttersprache"),
    sideItem("Englisch — Fortgeschritten"),

    sideHeader("ZERTIFIKATE"),
    sideLinkedItem("KI-Manager", "https://example.com/verify/ki-manager", { bold: true }),
    sideItem("Musterakademie — 07/2026", { muted: true, before: 0 }),
    sideLinkedItem("Claude Code Masterclass", "https://example.com/verify/claude-code", { bold: true, before: 60 }),
    sideItem("Musterakademie — 07/2026", { muted: true, before: 0 }),

    sideHeader("ENGAGEMENT"),
    sideItem("Kulturelles & soziales Engagement im Stadtteilverein"),

    sideHeader("INTERESSEN"),
    sideItem("Kooperative Gesellschaftsspiele"),
    sideItem("Tischtennis & Yoga"),
    sideItem("Konzert- & Festivalbesuche"),
];

// --- HAUPT SEITE 1: Kurzprofil + Berufserfahrung ---
const main1 = [
    mainHeader("KURZPROFIL"),
    new Paragraph({
        children: [t(
            "Erfahrener Automatisierungsingenieur mit Bachelor in Elektro- und Informationstechnik. Ich denke in Gesamtsystemen und bringe fundierte Praxis in der Digitalisierung mit — von der Maschinenprogrammierung bis zur Büroautomation. Neben der SPS-Programmierung entwickle ich sehr gerne Software-Werkzeuge in verschiedenen Sprachen, um einen direkten Mehrwert für mein Kollegenumfeld zu bieten. Mein Fokus liegt an der Schnittstelle zwischen Unternehmensprozessen, Maschinen und Software.",
            { size: 19 }
        )],
        spacing: { before: 0, after: 60 },
    }),

    mainHeader("BERUFSERFAHRUNG"),

    jobEntry("Musterfirma Aerosol GmbH", "01/2026 – heute"),
    jobRole("Automatisierungsingenieur  –  Musterstadt"),
    bullet("Sondermaschinenbau und Montageanlagen: Konzeption und Inbetriebnahme"),
    bullet("Ablaufsteuerung in Strukturiertem Text mit parallelen Schrittketten; Signalanalyse mit Diagnose-Tools"),
    bullet("Visualisierungen und HMI-Oberflächen in Visual Basic mit ADS-Anbindung; Event- und Prozessdatenspeicherung"),
    bullet("Analyse, Weiterentwicklung und modularer Strukturaufbau von SPS-Code"),
    bullet("IPC-Setup auf Referenzprojektbasis, Softwareverteilung via PowerShell-Skripte"),

    jobEntry("Musterfirma Verfahrenstechnik KG", "08/2023 – 12/2025"),
    jobRole("Automatisierungsingenieur  –  Reinbek"),
    bullet("Maschinenbau in der Verfahrenstechnik von Schüttgütern"),
    bullet("PLC- & HMI-Programmierung im Siemens TIA Portal"),
    bullet("Entwicklung wiederverwendbarer Programm- und Visualisierungsbausteine inklusive Bibliotheksverwaltung"),
    bullet("Durchgängiger Anlagen-Workflow nach DIN EN 81346: P&ID, Betriebsmittellisten, Schaltpläne bis zur Steuerungslogik"),

    jobEntry("Musterfirma Verfahrenstechnik KG", "09/2019 – 07/2023"),
    jobRole("Dualer Student  –  Reinbek"),
    bullet("Schaltschrankbau und Verdrahtung"),
    bullet("Entwicklung von C#/.NET Add-ons zur Automatisierung des Workflows"),
    bullet("Optimierung von Arbeitsabläufen mit Excel- und Batch-Programmen"),
];

// --- HAUPT SEITE 2: Berufserfahrung Forts. + Ausbildung ---
const main2 = [
    mainHeader("BERUFSERFAHRUNG (FORTSETZUNG)"),

    jobEntry("Musterverein Spielemobil", "08/2018 – 08/2019"),
    jobRole("Bundesfreiwilligendienst  –  Mölln"),
    bullet("Betreuung des Spielemobils, Organisation und Reparatur von Gesellschaftsspielen"),
    bullet("Seminare zu Kommunikation, Psychologie, Pädagogik und Jugendarbeit"),

    mainHeader("AUSBILDUNG"),
    ...eduEntry(
        "Elektro- und Informationstechnik",
        "B.Sc. — Hochschule für angewandte Wissenschaften",
        "2019 – 2023  |  Vertiefung: Energie- und Automatisierungstechnik"
    ),
    ...eduEntry(
        "Abitur",
        "Technisches Gymnasium",
        "2015 – 2018  |  Erste Kenntnisse Elektro- & Informationstechnik"
    ),
    ...eduEntry(
        "Mittelstufe",
        "Gymnasium Musterstadt",
        "2009 – 2015"
    ),
];

// --- TABELLENSTRUKTUR ---
function makeHeaderRow(part) {
    return new TableRow({
        children: [new TableCell({
            columnSpan: 2,
            width: { size: CONT_W, type: WidthType.DXA },
            borders: nbCell,
            shading: { fill: C_DARK, type: ShadingType.CLEAR },
            margins: { top: 240, bottom: 220, left: 360, right: 360 },
            children: [
                new Paragraph({
                    children: [
                        t("Max Mustermann", { bold: true, size: 48, color: C_WHITE }),
                        t("        " + part, { size: 16, color: C_TAG, bold: true }),
                    ],
                    spacing: { before: 0, after: 60 },
                }),
                new Paragraph({
                    children: [t("Automatisierungsingenieur B.Sc.", { size: 22, color: C_TAG })],
                    spacing: { before: 0, after: 0 },
                }),
            ],
        })],
    });
}

function makeBodyRow(sideContent, mainContent) {
    return new TableRow({
        children: [
            new TableCell({
                width: { size: SIDE_W, type: WidthType.DXA },
                borders: nbCell,
                shading: { fill: C_SIDE, type: ShadingType.CLEAR },
                verticalAlign: VerticalAlign.TOP,
                margins: { top: 0, bottom: 200, left: 0, right: 0 },
                children: sideContent,
            }),
            new TableCell({
                width: { size: MAIN_W, type: WidthType.DXA },
                borders: nbCell,
                verticalAlign: VerticalAlign.TOP,
                margins: { top: 80, bottom: 200, left: 240, right: 160 },
                children: mainContent,
            }),
        ],
    });
}

const table1 = new Table({
    width: { size: CONT_W, type: WidthType.DXA },
    columnWidths: [SIDE_W, MAIN_W],
    borders: nbs,
    rows: [makeHeaderRow("TEIL 1 VON 2"), makeBodyRow(sidebar1, main1)],
});

const table2 = new Table({
    width: { size: CONT_W, type: WidthType.DXA },
    columnWidths: [SIDE_W, MAIN_W],
    borders: nbs,
    rows: [makeHeaderRow("TEIL 2 VON 2"), makeBodyRow(sidebar2, main2)],
});

// --- DOKUMENT ---
const doc = new Document({
    numbering: {
        config: [{
            reference: "bullets",
            levels: [{
                level: 0,
                format: LevelFormat.BULLET,
                text: "–",
                alignment: AlignmentType.LEFT,
                style: {
                    paragraph: { indent: { left: 320, hanging: 200 } },
                    run: { color: C_MED, font: "Arial", size: 19 },
                },
            }],
        }],
    },
    sections: [{
        properties: {
            page: {
                size: { width: PAGE_W, height: PAGE_H },
                margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
            },
        },
        children: [
            table1,
            new Paragraph({ children: [new PageBreak()] }),
            table2,
        ],
    }],
});

// Sicherstellen, dass das Ausgabeverzeichnis existiert
const outputDir = path.join(__dirname, "output");
if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
}

const localOutPath = path.join(outputDir, "muster_lebenslauf.docx");

Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync(localOutPath, buffer);
    console.log("Fertig Lokal:", localOutPath);
}).catch(err => {
    console.error("Fehler beim Generieren des Lebenslaufs:", err.message);
});
