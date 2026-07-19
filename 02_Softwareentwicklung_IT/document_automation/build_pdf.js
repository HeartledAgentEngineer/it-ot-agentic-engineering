// build_pdf.js
// Rendert cv_preview.html und anschreiben_muster.html mit Puppeteer zu A4-PDFs im output-Ordner.
// Voraussetzung: npm install puppeteer

const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

const outputDir = path.join(__dirname, 'output');
if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
}

const htmlFileCV     = path.resolve(__dirname, 'cv_preview.html');
const pdfOutCV       = path.join(outputDir, 'muster_lebenslauf.pdf');

const htmlFileLetter = path.resolve(__dirname, 'anschreiben_muster.html');
const pdfOutLetter   = path.join(outputDir, 'muster_anschreiben.pdf');

(async () => {
    try {
        console.log('Starte Puppeteer-Browser...');
        const browser = await puppeteer.launch({
            args: ['--no-sandbox', '--disable-setuid-sandbox'] // Stabilität in Sandboxen
        });
        const page = await browser.newPage();

        // 1. CV rendern
        if (fs.existsSync(htmlFileCV)) {
            console.log('Rendere Lebenslauf...');
            await page.goto('file://' + htmlFileCV, { waitUntil: 'networkidle0' });
            await page.pdf({
                path: pdfOutCV,
                format: 'A4',
                printBackground: true,           // Hintergrundfarben mit drucken
                preferCSSPageSize: true,         // @page-Regel aus CSS verwenden
                margin: { top: 0, right: 0, bottom: 0, left: 0 },
            });
            console.log('Lebenslauf-PDF erstellt:', pdfOutCV);
        } else {
            console.error('cv_preview.html nicht gefunden!');
        }

        // 2. Anschreiben rendern
        if (fs.existsSync(htmlFileLetter)) {
            console.log('Rendere Anschreiben...');
            await page.goto('file://' + htmlFileLetter, { waitUntil: 'networkidle0' });
            await page.pdf({
                path: pdfOutLetter,
                format: 'A4',
                printBackground: true,
                preferCSSPageSize: true,
                margin: { top: 0, right: 0, bottom: 0, left: 0 },
            });
            console.log('Anschreiben-PDF erstellt:', pdfOutLetter);
        } else {
            console.error('anschreiben_muster.html nicht gefunden!');
        }

        await browser.close();
        console.log('\n=========================================');
        console.log('ERFOLG: Alle PDFs wurden lokal in ./output/ generiert!');
        console.log('=========================================');
    } catch (err) {
        console.error('Fehler bei der PDF-Generierung:', err);
    }
})();
