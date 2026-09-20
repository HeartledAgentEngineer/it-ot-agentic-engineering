// REINE LOGIK-TESTS der Rahmen-Geometrie — gegen den ECHTEN Quelltext (app.js).
// Die Funktionen werden wie in test_quiz_ende.js direkt ausgeschnitten und in
// einer minimalen Stub-Umgebung ausgefuehrt; es wird nichts nachgebaut.
//   Aufruf: node tests/test_quiz_geo.js app.js
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');

function extractFn(name) {
  const i = src.indexOf('function ' + name + '(');
  if (i === -1) throw new Error('nicht gefunden: ' + name);
  let depth = 0, k = src.indexOf('{', i);
  for (; k < src.length; k++) {
    if (src[k] === '{') depth++;
    else if (src[k] === '}') { depth--; if (depth === 0) { k++; break; } }
  }
  return src.slice(i, k);
}

const FUNKTIONEN = [
  'bboxNormVonPixeln', 'bboxPixelVonNorm', 'bboxNormClampen', 'bboxClampen',
  'bboxRotieren', 'bboxNormRotieren', 'anzeigeMasse', 'bboxVerschieben',
  'bboxSkalieren', 'bboxAnzeigeRahmen', 'bboxDeltaDrehen', 'bboxFlaecheAnteil',
  'bboxExifDrehSchritte', 'bboxRegionSchluessel',
];
for (const f of FUNKTIONEN) eval(extractFn(f));

let fails = 0;
const ck = (name, ist, soll) => {
  const gleich = (JSON.stringify(ist) === JSON.stringify(soll));
  if (gleich) console.log('  OK   ' + name + ' (= ' + JSON.stringify(ist) + ')');
  else { console.log('  FAIL ' + name + ': erwartet ' + JSON.stringify(soll) + ', war ' + JSON.stringify(ist)); fails++; }
};
const ckn = (name, ist, cmp, soll) => {
  if (cmp(ist, soll)) console.log('  OK   ' + name + ' (' + ist + ')');
  else { console.log('  FAIL ' + name + ': ' + ist + ' erfuellt nicht ' + cmp.name + ' ' + soll); fails++; }
};
const nah = (a, b) => Math.abs(a - b) < 1e-9;

// Hochformat 100x200 und Querformat 400x300
const IW = 100, IH = 200;
const B = [10, 20, 30, 40];      // Gesicht [x,y,w,h] in NATIVEN Pixeln

console.log('\n1) Hin- und Rueckrechnung normiert <-> Pixel');
{
  const n = bboxNormVonPixeln(B, IW, IH);
  ck('norm aus Pixeln', n.map(v => +v.toFixed(4)), [0.1, 0.1, 0.3, 0.2]);
  ck('zurueck in Pixel = Original', bboxPixelVonNorm(n, IW, IH), B);
  const q = bboxNormVonPixeln([40, 60, 120, 90], 400, 300);
  ck('Querformat zurueck = Original', bboxPixelVonNorm(q, 400, 300), [40, 60, 120, 90]);
  ck('leere Eingabe -> null', [bboxNormVonPixeln([], IW, IH), bboxPixelVonNorm(null, IW, IH)],
     [null, null]);
}

console.log('\n2) Clamping (nie aus dem Bild)');
{
  ck('Clamp innen unveraendert', bboxClampen(B, IW, IH), B);
  ck('weit rechts -> randbuendig, Groesse bleibt', bboxClampen([80, 20, 50, 40], IW, IH), [50, 20, 50, 40]);
  ck('weit unten -> randbuendig, Groesse bleibt', bboxClampen([10, 180, 30, 40], IW, IH), [10, 160, 30, 40]);
  ck('negative Position auf 0', bboxClampen([-5, -7, 30, 40], IW, IH), [0, 0, 30, 40]);
  ck('Mindestgroesse 1px', bboxClampen([99, 199, 0, 0], IW, IH), [99, 199, 1, 1]);
  ck('groesser als das Bild wird geschrumpft', bboxClampen([-5, -5, 500, 500], IW, IH), [0, 0, 100, 200]);
  ck('norm: Clamp im Einheitsquadrat', bboxNormClampen([-0.2, 0.5, 1.4, 0.9]), [0, 0.5, 1, 0.5]);
  ck('norm: Mindestgroesse 0.5 %', bboxNormClampen([1, 1, 0, 0]), [1, 1, 0.005, 0.005]);
}

console.log('\n3) Drehen (bboxRotieren / bboxNormRotieren)');
{
  ck('1x 90 Grad CW', bboxRotieren(B, IW, IH, 1), [IH - (20 + 40), 10, 40, 30]);
  ck('2x 180 Grad', bboxRotieren(B, IW, IH, 2), [IW - (10 + 30), IH - (20 + 40), 30, 40]);
  ck('4x = Ausgangslage', bboxRotieren(B, IW, IH, 4), B);
  ck('negative Schritte = 3x', bboxRotieren(B, IW, IH, -1), bboxRotieren(B, IW, IH, 3));
  // Rueckrichtung: 4x gedreht und dann (4-n)x zurueck ergibt wieder das Original
  const einmal = bboxRotieren(B, IW, IH, 1);
  ck('Rueckrichtung 1x zurueck', bboxRotieren(einmal, IH, IW, 3), B);

  const norm = bboxNormVonPixeln(B, IW, IH);
  const n1 = bboxNormRotieren(norm, IW, IH, 1);
  ck('norm 1x stimmt mit Pixel-Drehung ueberein',
     n1.map(v => +v.toFixed(6)),
     bboxNormVonPixeln(bboxRotieren(B, IW, IH, 1), IH, IW).map(v => +v.toFixed(6)));
  ck('norm 4x = Ausgangslage',
     bboxNormRotieren(norm, IW, IH, 4).map(v => +v.toFixed(6)), norm.map(v => +v.toFixed(6)));
  // Rueckrichtung der Anzeige-Drehung
  for (const d of [0, 1, 2, 3]) {
    const hin = bboxNormRotieren(norm, IW, IH, d);
    const masse = anzeigeMasse(IW, IH, d);
    const zurueck = bboxNormRotieren(hin, masse[0], masse[1], (4 - d) % 4);
    ckn('norm ' + d + 'x hin + ' + ((4 - d) % 4) + 'x zurueck = Original',
        zurueck.every((v, i) => nah(v, norm[i])), () => true, true);
  }
  // Ein gedrehter Rahmen bleibt vollstaendig im Einheitsquadrat
  const rand = bboxNormRotieren([0.0, 0.0, 0.5, 0.5], IW, IH, 1);
  ckn('gedrehter Rand-Rahmen bleibt in 0..1',
      rand.every(v => v >= 0 && v <= 1), () => true, true);
  ck('Anzeigemasse bei ungerader Drehung vertauscht', anzeigeMasse(IW, IH, 1), [IH, IW]);
  ck('Anzeigemasse bei gerader Drehung gleich', anzeigeMasse(IW, IH, 2), [IW, IH]);
}

console.log('\n4) Ziehen: Verschieben wird am Rand begrenzt');
{
  ck('normales Verschieben', bboxVerschieben(B, 5, 7, IW, IH), [15, 27, 30, 40]);
  ck('Ziehen ueber den linken Rand -> x=0', bboxVerschieben(B, -50, 0, IW, IH), [0, 20, 30, 40]);
  ck('Ziehen ueber den rechten Rand -> ganz im Bild',
     bboxVerschieben(B, 500, 0, IW, IH), [70, 20, 30, 40]);
  ck('Ziehen ueber den unteren Rand -> ganz im Bild',
     bboxVerschieben(B, 0, 900, IW, IH), [10, 160, 30, 40]);
  const weit = bboxVerschieben(B, 500, 900, IW, IH);
  ckn('Ergebnis immer innerhalb des Bildes',
      (weit[0] + weit[2] <= IW + 1e-9) && (weit[1] + weit[3] <= IH + 1e-9), () => true, true);
  // Hin und zurueck (soweit moeglich) ist stabil
  const hinUndZurueck = bboxVerschieben(bboxVerschieben(B, 20, 30, IW, IH), -20, -30, IW, IH);
  ck('hin und zurueck = Original', hinUndZurueck, B);
}

console.log('\n5) Groesse ziehen: Griffe, Mindestgroesse, Rand');
{
  ck('rechter Griff +10 breiter', bboxSkalieren(B, 'r', 10, 0, IW, IH), [10, 20, 40, 40]);
  ck('linker Griff +10 -> schmaler, x wandert', bboxSkalieren(B, 'l', 10, 0, IW, IH), [20, 20, 20, 40]);
  ck('unterer Griff +10 hoeher', bboxSkalieren(B, 'b', 0, 10, IW, IH), [10, 20, 30, 50]);
  ck('Ecke unten rechts', bboxSkalieren(B, 'br', 5, 5, IW, IH), [10, 20, 35, 45]);
  ck('Mindestgroesse 8px (links ueber den Rand gezogen)',
     bboxSkalieren(B, 'l', 999, 0, IW, IH), [32, 20, 8, 40]);
  ck('nie groesser als das Bild (rechts)',
     bboxSkalieren(B, 'r', 999, 0, IW, IH), [0, 20, 100, 40]);
  ck('nie groesser als das Bild (unten)',
     bboxSkalieren(B, 'b', 0, 999, IW, IH), [10, 0, 30, 200]);
  const unveraendert = bboxSkalieren(B, 'r', 0, 0, IW, IH);
  ck('Griff ohne Bewegung = Original', unveraendert, B);
}

console.log('\n6) Anzeige-Rahmen (Kopf mit, aber dezent) und Flaeche');
{
  const norm = bboxNormVonPixeln(B, IW, IH);
  const anzeige = bboxAnzeigeRahmen(norm);
  ckn('Anzeige-Rahmen ist groesser als das Gesicht',
      anzeige[2] > norm[2] && anzeige[3] > norm[3], () => true, true);
  ckn('Anzeige-Rahmen bleibt DEZENT (max 2x Flaeche)',
      (anzeige[2] * anzeige[3]) <= 2 * (norm[2] * norm[3]), () => true, true);
  ckn('Anzeige-Rahmen im Bild', anzeige.every(v => v >= 0 && v <= 1.0000001), () => true, true);
  const oben = bboxAnzeigeRahmen([0.00, 0.00, 0.30, 0.40]);
  ckn('Anzeige-Rahmen an der Ecke bleibt im Bild',
      oben.every(v => v >= 0 && v <= 1.0000001), () => true, true);
  // Alter Fehler (28 % oben) haette den Kasten fast verdoppelt
  ckn('frueherer 28%-Aufschlag ist weg',
      bboxAnzeigeRahmen(norm)[3] < norm[3] * 1.5, () => true, true);
  ck('Flaeche klein fuer ein Gesicht', bboxFlaecheAnteil(norm, 1, 1) === 0.06, true);
}

console.log('\n7) Zieh-Delta im gedrehten Anzeigeraum (Rueckrichtung)');
{
  ck('0 Grad: unveraendert', bboxDeltaDrehen(5, 7, 0), [5, 7]);
  ck('90 Grad: x wird -y, y wird x', bboxDeltaDrehen(5, 7, 1), [7, -5]);
  ck('180 Grad: beide negativ', bboxDeltaDrehen(5, 7, 2), [-5, -7]);
  ck('270 Grad: x wird y, y wird -x', bboxDeltaDrehen(5, 7, 3), [-7, 5]);
  let d = [13, -4];
  for (let i = 0; i < 4; i++) d = bboxDeltaDrehen(d[0], d[1], 1);
  ck('4x 90 Grad = Ausgangslage', d, [13, -4]);
  // Ein Zug am gedrehten Bild bewegt den Rahmen in dieselbe Bildrichtung
  const norm = bboxNormVonPixeln(B, IW, IH);
  const px = bboxPixelVonNorm(norm, IW, IH);
  const dOrg = bboxDeltaDrehen(10, 0, 1);          // 10 px nach rechts am gedrehten Bild
  const neu = bboxVerschieben(px, dOrg[0], dOrg[1], IW, IH);
  ck('90 Grad: Rechtszug senkt die Bild-Y-Position um 10', [neu[0] - px[0], neu[1] - px[1]], [0, -10]);
}

console.log('\n8) EXIF-Orientierung und Regions-Schluessel');
{
  ck('EXIF 6 = 90 Grad CW', bboxExifDrehSchritte(6), 1);
  ck('EXIF 3 = 180 Grad', bboxExifDrehSchritte(3), 2);
  ck('EXIF 8 = 270 Grad', bboxExifDrehSchritte(8), 3);
  ck('EXIF 1 = keine Drehung', bboxExifDrehSchritte(1), 0);
  ck('unbekannt -> 0', [bboxExifDrehSchritte(undefined), bboxExifDrehSchritte(99)], [0, 0]);
  ck('Regions-Schluessel 1%-Raster', bboxRegionSchluessel([0.104, 0.096, 0.3001, 0.2]),
     '0.10,0.10,0.30,0.20');
  ck('gleiche Region -> gleicher Schluessel',
     bboxRegionSchluessel([0.1, 0.1, 0.3, 0.2]) === bboxRegionSchluessel([0.101, 0.099, 0.299, 0.201]),
     true);
  ck('leer -> leerer Schluessel', bboxRegionSchluessel(null), '');
}

console.log('\n  --> Fehler: ' + fails);
process.exit(fails ? 1 : 0);
