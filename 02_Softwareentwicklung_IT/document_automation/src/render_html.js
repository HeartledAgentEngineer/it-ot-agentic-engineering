// Lebenslaufdaten -> vollständiges HTML-Dokument (A4, druckfertig). Reine Funktion, jeder Wert wird maskiert.
'use strict';

// Maskiert die fünf HTML-Sonderzeichen: Daten können so nie Markup oder Skripte einschleusen.
function maskiere(wert) {
  return String(wert ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// "2021-04" -> "04/2021"; null -> "heute".
function monat(wert) {
  if (wert === null) return 'heute';
  const [jahr, mon] = wert.split('-');
  return `${mon}/${jahr}`;
}

function station(s) {
  const punkte = (s.punkte || []).map((p) => `<li>${maskiere(p)}</li>`).join('');
  return `<section class="station">
  <div class="zeit">${maskiere(monat(s.von))} – ${maskiere(monat(s.bis))}</div>
  <div><h3>${maskiere(s.rolle)}</h3><p class="firma">${maskiere(s.firma)}</p><ul>${punkte}</ul></div>
</section>`;
}

const STIL = `@page { size: A4; margin: 18mm; }
body { font-family: Inter, "Segoe UI", sans-serif; color: #1d2433; line-height: 1.45; }
h1 { margin: 0; font-size: 26pt; } .titel { color: #4a5a7a; margin: 2px 0 12px; }
h2 { border-bottom: 1px solid #cfd6e4; padding-bottom: 3px; font-size: 13pt; }
.station { display: grid; grid-template-columns: 42mm 1fr; gap: 6mm; margin-bottom: 4mm; }
.zeit { color: #4a5a7a; white-space: nowrap; } h3 { margin: 0; font-size: 11pt; } .firma { margin: 0; color: #4a5a7a; }`;

function renderLebenslauf(cv) {
  const faehigkeiten = (cv.faehigkeiten || []).map(maskiere).join(' · ');
  return `<!DOCTYPE html>
<html lang="de">
<head><meta charset="utf-8"><title>Lebenslauf – ${maskiere(cv.name)}</title><style>${STIL}</style></head>
<body>
<header><h1>${maskiere(cv.name)}</h1><p class="titel">${maskiere(cv.titel)}</p>
<p>${maskiere(cv.kontakt.email)} · ${maskiere(cv.kontakt.ort)}</p></header>
<main>
<h2>Profil</h2><p>${maskiere(cv.profil)}</p>
<h2>Stationen</h2>
${cv.stationen.map(station).join('\n')}
<h2>Fähigkeiten</h2><p>${faehigkeiten}</p>
</main>
</body>
</html>
`;
}

module.exports = { renderLebenslauf, maskiere, monat };
