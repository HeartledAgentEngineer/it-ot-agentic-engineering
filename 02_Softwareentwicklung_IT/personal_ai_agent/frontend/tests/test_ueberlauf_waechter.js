// Überlauf-Wächter (01.10.2026): misst am Handy, wenn eine Antwort-Blase rechts
// herausragt, und meldet NUR Messwerte (nie Text) an Logcat + Backend.
//
// Aufruf (aus dem Ordner frontend):  node tests/test_ueberlauf_waechter.js
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(path.join(__dirname, '..', 'app.js'), 'utf8');
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

const ueberlaufTaeter = new Function(funktionAusschneiden(src, 'ueberlaufTaeter') + '; return ueberlaufTaeter;')();
const pruefen = funktionAusschneiden(src, 'ueberlaufPruefen');

let fehler = 0;
function pruefe(bed, text) {
    if (bed) { console.log('  ✓ ' + text); } else { console.log('  ✗ ' + text); fehler++; }
}

console.log('ueberlaufTaeter');
const el = [{ tag: 'p', rechts: 300 }, { tag: 'table', rechts: 520 }, { tag: 'a', rechts: 410 },
            { tag: 'code', rechts: 376 }, { tag: 'span', rechts: 999 }];
const t = ueberlaufTaeter(el, 375, 3);
pruefe(t.map(e => e.tag).join(',') === 'span,table,a', 'die drei am weitesten herausragenden, größter zuerst');
pruefe(ueberlaufTaeter(el, 375, 3).every(e => e.rechts > 376), '1 px Toleranz (376 zählt nicht)');
pruefe(ueberlaufTaeter([], 375).length === 0 && ueberlaufTaeter(null, 375).length === 0, 'leer bleibt leer');

console.log('Messung und Meldung');
pruefe(/visualViewport/.test(pruefen) && /scrollWidth/.test(pruefen), 'misst WebView-Zoom und Seitenbreite');
pruefe(/\/api\/diagnose\/ueberlauf/.test(pruefen) && /console\.warn\('\[UEBERLAUF\] '/.test(pruefen),
    'meldet an Backend und Logcat');
pruefe(!/textContent|innerText|innerHTML/.test(pruefen), 'nimmt NIE Text mit');
pruefe(/dataset\[merker\]/.test(pruefen), 'je Blase und Phase höchstens eine Meldung');
pruefe(/ueberlaufPruefen\(contentDiv, 'stream'\)/.test(src), 'prüft während des Streams');
pruefe(/ueberlaufPruefen\(contentDiv, 'fertig'\), 300\)/.test(src)
    && /ueberlaufPruefen\(contentDiv, 'spaeter'\), 2000\)/.test(src), 'prüft nach dem Abschluss zweimal');

console.log('Verlauf und Größenwechsel');
const allePruefen = funktionAusschneiden(src, 'ueberlaufAllePruefen');
pruefe(/querySelectorAll\('\.message-content'\)/.test(allePruefen), 'geht die vorhandenen Blasen durch');
pruefe(/ueberlaufPruefen\(contentDiv, phase\)/.test(allePruefen), 'misst je Blase mit der Phase');
pruefe(!/textContent|innerText|innerHTML/.test(allePruefen), 'nimmt auch hier NIE Text mit');
pruefe(/ueberlaufAllePruefen\('verlauf'\), 300\)/.test(src), 'misst den Verlauf nach dem Aufbau');
pruefe(/ueberlaufAllePruefen\('verlauf_spaeter'\), 2000\)/.test(src), 'misst den Verlauf noch einmal später');
pruefe(/ueberlaufAllePruefen\('verlauf_aelter'\)/.test(src), 'misst nachgeladene ältere Blasen');
pruefe(/addEventListener\('resize', ueberlaufBeiGroessenwechsel\)/.test(src)
    && /addEventListener\('orientationchange', ueberlaufBeiGroessenwechsel\)/.test(src),
    'misst beim Größenwechsel und beim Drehen');
pruefe(/'resize' \+ Math\.round\(W\)/.test(src), 'Phasenname trägt die Fensterbreite (Dedup je Breite)');

console.log('Cache-Bump');
const m = html.match(/app\.js\?v=(\d{8}[A-Z])/);
pruefe(m && m[1] >= '20261001B', 'app.js-Version 20261001B oder neuer');

if (fehler) { console.log(`\n${fehler} Prüfung(en) rot`); process.exit(1); }
console.log('\nalle Prüfungen grün');
