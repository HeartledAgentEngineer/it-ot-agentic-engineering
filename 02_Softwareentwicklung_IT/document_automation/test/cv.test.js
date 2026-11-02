// Tests ohne Abhängigkeiten (node:test): Datenprüfung, Maskierung, Rendern und Kommandozeile im HTML-Modus.
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { pruefeLebenslauf } = require('../src/cv_model');
const { renderLebenslauf, maskiere, monat } = require('../src/render_html');
const { main } = require('../build');

const BEISPIEL = path.join(__dirname, '..', 'data', 'beispiel_person.json');
const beispiel = () => JSON.parse(fs.readFileSync(BEISPIEL, 'utf-8'));

test('Beispieldaten sind gültig', () => {
  assert.deepEqual(pruefeLebenslauf(beispiel()), []);
});

test('fehlende Pflichtfelder werden einzeln gemeldet', () => {
  const fehler = pruefeLebenslauf({ kontakt: {}, stationen: [] });
  assert.ok(fehler.includes('Pflichtfeld fehlt: name'));
  assert.ok(fehler.includes('kontakt.email fehlt oder ist ungültig'));
  assert.ok(fehler.includes('stationen: mindestens eine Station nötig'));
});

test('Datumsformat und Reihenfolge werden geprüft', () => {
  const cv = beispiel();
  cv.stationen[0].von = '2021-13';
  cv.stationen[1].bis = '2016-01';
  const fehler = pruefeLebenslauf(cv);
  assert.ok(fehler.some((f) => f.startsWith('stationen[0].von')));
  assert.ok(fehler.includes('stationen[1]: Ende liegt vor dem Beginn'));
});

test('kein Objekt -> ein klarer Fehler statt Absturz', () => {
  assert.deepEqual(pruefeLebenslauf(null), ['Daten fehlen oder sind kein Objekt']);
});

test('maskiere entschärft HTML-Sonderzeichen', () => {
  assert.equal(maskiere(`<script>alert("x")</script> & 'y'`),
    '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; &#39;y&#39;');
});

test('eingeschleustes Markup erscheint nur maskiert im Dokument', () => {
  const cv = beispiel();
  cv.name = '<img src=x onerror=alert(1)>';
  const html = renderLebenslauf(cv);
  assert.ok(!html.includes('<img'));
  assert.ok(html.includes('&lt;img src=x onerror=alert(1)&gt;'));
});

test('Monatsangaben: JJJJ-MM wird MM/JJJJ, offenes Ende wird "heute"', () => {
  assert.equal(monat('2021-04'), '04/2021');
  assert.equal(monat(null), 'heute');
});

test('gerendertes Dokument enthält alle Abschnitte und Stationen', () => {
  const html = renderLebenslauf(beispiel());
  for (const teil of ['<h2>Profil</h2>', '<h2>Stationen</h2>', '<h2>Fähigkeiten</h2>',
    'Inbetriebnahme-Ingenieur', '04/2021 – heute']) {
    assert.ok(html.includes(teil), teil);
  }
});

test('Kommandozeile: ungültige Daten -> Exit 1, nichts gedruckt', async () => {
  const ordner = fs.mkdtempSync(path.join(os.tmpdir(), 'cv-'));
  const datei = path.join(ordner, 'kaputt.json');
  fs.writeFileSync(datei, JSON.stringify({ name: 'X' }));
  const stderr = console.error;
  console.error = () => {};
  try {
    assert.equal(await main([datei, '--nur-html']), 1);
  } finally {
    console.error = stderr;
  }
});

test('Kommandozeile: unlesbare Datei -> Exit 2', async () => {
  const stderr = console.error;
  console.error = () => {};
  try {
    assert.equal(await main([path.join(os.tmpdir(), 'gibt-es-nicht.json'), '--nur-html']), 2);
  } finally {
    console.error = stderr;
  }
});
