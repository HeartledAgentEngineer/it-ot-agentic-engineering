// merge_pdfs.js
// Führt das Anschreiben, den Lebenslauf und die Zeugnisse in einem einzigen,
// professionell sortierten PDF-Dokument zusammen.
// Erfordert: npm install pdf-lib

const { PDFDocument } = require('pdf-lib');
const fs = require('fs');
const path = require('path');

const dir = __dirname;
const outputDir = path.join(dir, 'output');

// Professionelle Reihenfolge für deutsche Bewerbungsunterlagen:
// 1. Anschreiben
// 2. Lebenslauf (CV)
// 3. Höchster Bildungsabschluss (Bachelor-Zeugnis)
// 4. Arbeitszeugnisse
// 5. Fortbildungen / Zertifikate
const files = [
    path.join(outputDir, 'muster_anschreiben.pdf'),
    path.join(outputDir, 'muster_lebenslauf.pdf'),
    path.join(dir, 'muster_bachelorzeugnis.pdf'),
    path.join(dir, 'muster_arbeitszeugnis.pdf'),
    path.join(dir, 'muster_zertifikat.pdf')
];

const outFile = path.join(outputDir, 'muster_bewerbungsmappe.pdf');

(async () => {
    try {
        console.log('Starte das Zusammenfügen der PDFs...');
        const mergedPdf = await PDFDocument.create();

        for (const file of files) {
            if (!fs.existsSync(file)) {
                console.error(`Datei nicht gefunden: ${file}`);
                console.error('Bitte stelle sicher, dass du zuerst build_cv.js/build_pdf.js ausgeführt hast und die Zeugnis-Dummies existieren.');
                process.exit(1);
            }
            console.log(`Lese und kopiere Seiten aus: ${path.basename(file)}`);
            const pdfBytes = fs.readFileSync(file);
            const pdfDoc = await PDFDocument.load(pdfBytes);
            const copiedPages = await mergedPdf.copyPages(pdfDoc, pdfDoc.getPageIndices());
            copiedPages.forEach((page) => mergedPdf.addPage(page));
        }

        const mergedPdfBytes = await mergedPdf.save();
        fs.writeFileSync(outFile, mergedPdfBytes);
        console.log('\n=========================================');
        console.log('ERFOLG: Alle Dokumente zusammengefügt!');
        console.log('Mappe erstellt:', outFile);
        console.log('=========================================');
    } catch (err) {
        console.error('Fehler beim Zusammenfügen der PDFs:', err);
    }
})();
