// Kommandozeile: Lebenslauf-JSON prüfen -> HTML rendern -> per Puppeteer zu einem A4-PDF drucken.
//   node build.js [daten.json] [--nur-html]
// Exit-Code: 0 = erzeugt · 1 = Daten ungültig · 2 = Aufruf- oder Druckfehler.
'use strict';

const fs = require('fs');
const path = require('path');
const { pruefeLebenslauf } = require('./src/cv_model');
const { renderLebenslauf } = require('./src/render_html');

async function main(argv) {
  const nurHtml = argv.includes('--nur-html');
  const datei = argv.find((a) => !a.startsWith('--')) || path.join(__dirname, 'data', 'beispiel_person.json');

  let daten;
  try {
    daten = JSON.parse(fs.readFileSync(datei, 'utf-8'));
  } catch (e) {
    console.error(`Daten nicht lesbar: ${datei} (${e.message})`);
    return 2;
  }
  const fehler = pruefeLebenslauf(daten);
  if (fehler.length) {
    fehler.forEach((f) => console.error(`  ✘ ${f}`));
    return 1;
  }

  const ausgabe = path.join(__dirname, 'output');
  fs.mkdirSync(ausgabe, { recursive: true });
  const html = renderLebenslauf(daten);
  const htmlDatei = path.join(ausgabe, 'lebenslauf.html');
  fs.writeFileSync(htmlDatei, html, 'utf-8');
  console.log(`HTML: ${htmlDatei}`);
  if (nurHtml) return 0;

  // Erst hier geladen: Prüfen und Rendern (und deren Tests) brauchen keinen Browser.
  let puppeteer;
  try {
    puppeteer = require('puppeteer');
  } catch {
    console.error('Puppeteer fehlt: erst "npm install" ausführen (oder --nur-html nutzen).');
    return 2;
  }
  const browser = await puppeteer.launch();
  try {
    const seite = await browser.newPage();
    await seite.setContent(html, { waitUntil: 'load' });
    const pdfDatei = path.join(ausgabe, 'lebenslauf.pdf');
    await seite.pdf({ path: pdfDatei, format: 'A4', printBackground: true, preferCSSPageSize: true });
    console.log(`PDF:  ${pdfDatei}`);
  } catch (e) {
    console.error(`PDF-Druck fehlgeschlagen: ${e.message}`);
    return 2;
  } finally {
    await browser.close();
  }
  return 0;
}

if (require.main === module) {
  main(process.argv.slice(2)).then((code) => process.exit(code));
}

module.exports = { main };
