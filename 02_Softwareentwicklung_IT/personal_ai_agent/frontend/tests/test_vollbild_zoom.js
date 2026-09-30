// Vollbild: mit zwei Fingern zoomen (30.09.2026).
//
// Befund (Sebastian, Handy): Ein Dokument-Foto im Vollbild liess sich nicht
// vergroessern. Ursache: Das Overlay faengt alle Gesten ab (touch-action:none,
// preventDefault gegen Pull-to-Refresh), die Seite ist user-scalable=no — der
// alte Kommentar „NATIV per Pinch zoombar" stimmte nie. Jetzt rechnet der Code
// den Zoom selbst. Dieser Test schneidet die reinen Funktionen aus dem echten
// app.js aus und prueft die Verdrahtung im Quelltext.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_vollbild_zoom.js
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(process.argv[2] || path.join(__dirname, '..', 'app.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

function funktionAusschneiden(quelle, name) {
    const start = quelle.indexOf('function ' + name + '(');
    if (start === -1) throw new Error('Funktion nicht gefunden: ' + name);
    let tiefe = 0;
    for (let i = quelle.indexOf('{', start); i < quelle.length; i++) {
        if (quelle[i] === '{') tiefe++;
        else if (quelle[i] === '}' && --tiefe === 0) return quelle.slice(start, i + 1);
    }
    throw new Error('Funktionsende nicht gefunden: ' + name);
}

const namen = ['zoomBegrenzen', 'zoomUmPunkt', 'zoomVerschiebungBegrenzen', 'istDoppeltipp'];
const f = new Function(namen.map((n) => funktionAusschneiden(src, n)).join('\n')
    + '; return { ' + namen.join(', ') + ' };')();

let fehler = 0;
function pruefe(bed, text) {
    if (bed) { console.log('  ✓ ' + text); } else { console.log('  ✗ ' + text); fehler++; }
}
const nah = (a, b) => Math.abs(a - b) < 1e-9;

console.log('zoomBegrenzen');
pruefe(f.zoomBegrenzen(0.5) === 1, 'unter 1 → 1 (nie kleiner als das ganze Bild)');
pruefe(f.zoomBegrenzen(3) === 3, '3 bleibt 3');
pruefe(f.zoomBegrenzen(40) === 6, 'über 6 → 6');
pruefe(f.zoomBegrenzen(NaN) === 1 && f.zoomBegrenzen(undefined) === 1, 'Unsinn → 1');

console.log('zoomUmPunkt: der Punkt unter den Fingern bleibt unter den Fingern');
{
    const mitte = [200, 400];
    const z0 = { s: 1, tx: 0, ty: 0 };
    const finger = [300, 500];
    const z = f.zoomUmPunkt(z0, mitte, finger, finger, 2);
    // Bildschirmort eines Box-Punkts p (relativ zur Mitte): mitte + t + s*p
    const p = [finger[0] - mitte[0], finger[1] - mitte[1]];   // bei s=1, t=0
    const ort = [mitte[0] + z.tx + z.s * p[0], mitte[1] + z.ty + z.s * p[1]];
    pruefe(z.s === 2, 'Stufe 2');
    pruefe(nah(ort[0], finger[0]) && nah(ort[1], finger[1]), 'Brennpunkt ortsfest beim Zoomen');
}
{
    const mitte = [200, 400];
    const z0 = { s: 2, tx: -50, ty: 30 };
    const f0 = [150, 420], f1 = [180, 380];
    const z = f.zoomUmPunkt(z0, mitte, f0, f1, 3);
    const p = [(f0[0] - mitte[0] - z0.tx) / z0.s, (f0[1] - mitte[1] - z0.ty) / z0.s];
    const ort = [mitte[0] + z.tx + z.s * p[0], mitte[1] + z.ty + z.s * p[1]];
    pruefe(nah(ort[0], f1[0]) && nah(ort[1], f1[1]), 'Zoomen + Verschieben in einer Geste: Punkt folgt der Fingermitte');
}
{
    const z = f.zoomUmPunkt({ s: 5, tx: 0, ty: 0 }, [0, 0], [10, 10], [10, 10], 50);
    pruefe(z.s === 6, 'Obergrenze gilt auch in der Geste');
}

console.log('zoomVerschiebungBegrenzen');
{
    const z = f.zoomVerschiebungBegrenzen({ s: 1, tx: 80, ty: -40 }, [400, 600], [400, 800]);
    pruefe(z.s === 1 && z.tx === 0 && z.ty === 0, 'Stufe 1 → immer mittig');
    // Box 400x600 bei s=2 → 800x1200 in Sicht 400x800: Spielraum x 200, y 200
    const g = f.zoomVerschiebungBegrenzen({ s: 2, tx: 999, ty: -999 }, [400, 600], [400, 800]);
    pruefe(g.tx === 200 && g.ty === -200, 'Rand bleibt am Rand (kein schwarzes Loch)');
    const innen = f.zoomVerschiebungBegrenzen({ s: 2, tx: 50, ty: 10 }, [400, 600], [400, 800]);
    pruefe(innen.tx === 50 && innen.ty === 10, 'innerhalb des Spielraums unverändert');
    // Querformat-Bild 400x200 bei s=2 → Höhe 400 < Sicht 800: senkrecht mittig
    const quer = f.zoomVerschiebungBegrenzen({ s: 2, tx: 0, ty: 120 }, [400, 200], [400, 800]);
    pruefe(quer.ty === 0, 'passt es in eine Richtung noch ganz hinein, bleibt es dort mittig');
}

console.log('istDoppeltipp');
pruefe(f.istDoppeltipp({ t: 1000, x: 100, y: 100 }, { t: 1200, x: 110, y: 105 }), 'kurz nacheinander, gleiche Stelle → ja');
pruefe(!f.istDoppeltipp({ t: 1000, x: 100, y: 100 }, { t: 1500, x: 100, y: 100 }), 'zu langsam → nein');
pruefe(!f.istDoppeltipp({ t: 1000, x: 100, y: 100 }, { t: 1100, x: 200, y: 100 }), 'andere Stelle → nein');
pruefe(!f.istDoppeltipp(null, { t: 1, x: 0, y: 0 }), 'erster Tipp → nein');

console.log('Verdrahtung im Vollbild');
const vb = funktionAusschneiden(src, 'zeigeBildVollbild');
pruefe(/touch-action:none/.test(vb) && /addEventListener\('touchmove', _keineBrowserGeste, \{ passive: false \}\)/.test(vb),
    'Pull-to-Refresh-Sperre bleibt (Browser übernimmt keine Geste)');
pruefe(/wrap\.addEventListener\('pointerdown'/.test(vb) && /wrap\.addEventListener\('pointermove'/.test(vb)
    && /wrap\.addEventListener\('pointerup', zeigerWeg\)/.test(vb) && /wrap\.addEventListener\('pointercancel', zeigerWeg\)/.test(vb),
    'Zeiger-Ereignisse am Bildbereich');
pruefe(/wrap\.addEventListener\('wheel'[\s\S]*?passive: false/.test(vb), 'Mausrad zoomt am PC');
pruefe(/bildBox\.style\.transform = /.test(vb), 'Zoom wirkt auf die bildBox (Bild + Rahmen gemeinsam)');
pruefe(/letzteBigW = rb\.width \/ zoom\.s; letzteBigH = rb\.height \/ zoom\.s;/.test(vb),
    'Rahmen-Geometrie rechnet ungezoomt (sonst doppelt skaliert)');
pruefe((vb.match(/\/ \(\(sk[wh] \|\| 1\) \* zoom\.s\)/g) || []).length === 4,
    'Rahmen verschieben + Größe ziehen teilen den Fingerweg durch den Zoom');
pruefe((vb.match(/if \(zeiger\.size > 1\) return;/g) || []).length === 2,
    'bei zwei Fingern wird kein Rahmen verschoben');
pruefe(/overflow:hidden;width:100%;height:100%;touch-action:none/.test(vb), 'Bildbereich scrollt nicht, er verschiebt');
pruefe(/max-width:100vw;max-height:100vh/.test(vb), 'hohe Bilder passen ganz auf den Schirm');
pruefe(!/NATIV per\s*\n?\s*\/\/\s*Zwei-Finger-Pinch/.test(src), 'falscher Kommentar „NATIV per Pinch" ist weg');

console.log('Cache-Bump');
const m = html.match(/app\.js\?v=(\d{8}[A-Z])/);
pruefe(m && m[1] >= '20260930C', 'app.js-Version 20260930C oder neuer (gefunden: ' + (m && m[1]) + ')');

if (fehler) { console.log(`\n${fehler} Prüfung(en) rot`); process.exit(1); }
console.log('\nalle Prüfungen grün');
