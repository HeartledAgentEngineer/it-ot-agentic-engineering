// Prüft Lebenslaufdaten, bevor etwas gerendert wird. Reine Funktion: keine Datei-, Netz- oder Browserzugriffe.
'use strict';

const MONAT = /^\d{4}-(0[1-9]|1[0-2])$/;

// Liefert eine Liste lesbarer Fehler; leer = gültig.
function pruefeLebenslauf(daten) {
  const fehler = [];
  if (!daten || typeof daten !== 'object') return ['Daten fehlen oder sind kein Objekt'];

  for (const feld of ['name', 'titel', 'profil']) {
    if (typeof daten[feld] !== 'string' || !daten[feld].trim()) fehler.push(`Pflichtfeld fehlt: ${feld}`);
  }
  if (!daten.kontakt || typeof daten.kontakt.email !== 'string' || !daten.kontakt.email.includes('@')) {
    fehler.push('kontakt.email fehlt oder ist ungültig');
  }
  if (!Array.isArray(daten.stationen) || daten.stationen.length === 0) {
    fehler.push('stationen: mindestens eine Station nötig');
  } else {
    daten.stationen.forEach((s, i) => {
      if (!MONAT.test(s.von || '')) fehler.push(`stationen[${i}].von: Format JJJJ-MM erwartet`);
      if (s.bis !== null && !MONAT.test(s.bis || '')) fehler.push(`stationen[${i}].bis: JJJJ-MM oder null erwartet`);
      if (s.bis && s.von && s.bis < s.von) fehler.push(`stationen[${i}]: Ende liegt vor dem Beginn`);
      if (!s.rolle || !s.firma) fehler.push(`stationen[${i}]: rolle und firma sind Pflicht`);
    });
  }
  if (daten.faehigkeiten !== undefined && !Array.isArray(daten.faehigkeiten)) {
    fehler.push('faehigkeiten muss eine Liste sein');
  }
  return fehler;
}

module.exports = { pruefeLebenslauf };
