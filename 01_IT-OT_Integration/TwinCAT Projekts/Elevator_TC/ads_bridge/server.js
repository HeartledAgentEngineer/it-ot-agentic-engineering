'use strict';

// ════════════════════════════════════════════════════════════════
//  TwinCAT ADS ↔ WebSocket Bridge  —  Elevator Digital Twin
//
//  Architektur:
//    Browser (elevator_3d_demo.html)
//      ↕ WebSocket ws://localhost:3000
//    server.js  ← Physik-Simulation (fHeight, fDoor)
//      ↕ ADS
//    TwinCAT PLC (Elevator / MAIN.fbElevator)
//
//  Start:  cd ads_bridge && npm install && npm start
// ════════════════════════════════════════════════════════════════

const { Client }         = require('ads-client');
const { WebSocketServer} = require('ws');
const http               = require('http');

// ── Konfiguration ────────────────────────────────────────────────
const CFG = {
  amsNetId : '127.0.0.1.1.1',        // <- AMS Net ID der eigenen TwinCAT-Runtime eintragen
  adsPort  : 851,                     // SPS Task 1 (Elevator)
  wsPort   : 3000,                    // Browser WebSocket
  cycleMs  : 50,                      // Zyklus 50ms = 20 Hz
  retryMs  : 5000,                    // Reconnect-Pause
};

// ── E_ElevatorState Enum ────────────────────────────────────────
const STEP_NAMES = {
  0:  'Init',
  1:  'Idle',
  11: 'DoorClosing',
  20: 'DecideDir',
  30: 'MovingUp',
  31: 'MovingDown',
  38: 'Braking',
  40: 'DoorOpening',
  50: 'WaitAtFloor',
  99: 'Emergency',
};

// ── Physik-Simulation (Hardware-in-the-Loop) ────────────────────
//  Der Server simuliert die physikalische Welt:
//   fHeight  0..100   (0 = EG / Floor1,  100 = OG / Floor2)
//   fDoor    0..100   (0 = geschlossen,   100 = offen)
const phys = {
  fHeight     : 0.0,
  fDoor       : 0.0,
  speedLift   : 25.0,   // units/s  → 4 Sekunden EG↔OG
  speedDoor   : 100.0,  // units/s  → 1 Sekunde öffnen/schließen
  lastTick    : Date.now(),
};

// ── HMI-Befehle (kommen via WebSocket) ─────────────────────────
const cmd = {
  callEG      : false,   // Ruf EG (Impuls, wird nach einer Schreibung zurückgesetzt)
  callOG      : false,   // Ruf OG
  call2OG     : false,   // Ruf 2.OG
  stop        : false,   // Not-Halt (NC: false = ausgelöst)
  maint       : false,   // Wartungsmodus
  lightCurtain: false,   // Lichtgitter (Pegel, kein Impuls)
};

// ── Letzter bekannter PLC-Zustand (an HMI gesendet) ────────────
let plcOut = {
  bMotorUp     : false,
  bMotorDown   : false,
  bDoorOpenCmd : false,
  bDoorCloseCmd: false,
  bLightFloor1 : false,
  bLightFloor2 : false,
  bLightFloor3 : false,
};
let plcStatus = {
  eState       : 0,
  nCurrentFloor: 1,
  nTargetFloor : 0,
  arCallQueue  : [false, false, false],
};

// ────────────────────────────────────────────────────────────────
//  WebSocket Server
// ────────────────────────────────────────────────────────────────
let adsReady = false;

const httpServer = http.createServer((_, res) => {
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ status: 'ok', adsConnected: adsReady }));
});

const wss = new WebSocketServer({ server: httpServer });

function broadcast(payload) {
  const msg = JSON.stringify(payload);
  wss.clients.forEach(ws => {
    if (ws.readyState === ws.OPEN) ws.send(msg);
  });
}

function buildStateMsg() {
  const atEG  = phys.fHeight <= 2.0;
  const at1OG = phys.fHeight >= 48.0 && phys.fHeight <= 52.0;
  const at2OG = phys.fHeight >= 98.0;
  const doorOpen   = phys.fDoor >= 99.0;
  const doorClosed = phys.fDoor <= 1.0;

  const eStepNum = typeof plcStatus.eState === 'object'
    ? (plcStatus.eState?.value ?? 0)
    : (plcStatus.eState ?? 0);

  const cq = plcStatus.arCallQueue;

  return {
    type         : 'state',
    adsConnected : adsReady,

    // Physik
    fHeight      : phys.fHeight,
    fDoor        : phys.fDoor,

    // PLC-Schrittkette
    eStep        : STEP_NAMES[eStepNum] ?? `State${eStepNum}`,
    doorTimer    : 0,

    // Ausstehende Rufe (aus stElevator.arCallQueue)
    bMemCallEG   : cq[0] ?? false,  // Array-Index 0 = PLC arCallQueue[1]
    bMemCallOG   : cq[1] ?? false,  // Array-Index 1 = PLC arCallQueue[2]
    bMemCall2OG  : cq[2] ?? false,  // index 2 = PLC arCallQueue[3]

    // PLC-Ausgänge (Motorsteuerung)
    bMotorUp     : plcOut.bMotorUp,
    bMotorDown   : plcOut.bMotorDown,
    bMotorSlow   : false,                    // kein Langsamgang im GVL
    bDoorCmdOpen : plcOut.bDoorOpenCmd,
    bDoorCmdClose: plcOut.bDoorCloseCmd,

    // Lampen
    bAckEG       : plcOut.bLightFloor1,
    bAckOG       : plcOut.bLightFloor2,
    bAck2OG      : plcOut.bLightFloor3,
    bLampStop    : cmd.stop,
    bLampMaint   : cmd.maint,

    // Sensoren (aus Physik abgeleitet)
    bLimitEG     : atEG,
    bLimitOG     : at1OG,
    bLimit2OG    : at2OG,
    bDoorOpen    : doorOpen,
    bDoorClosed  : doorClosed,

    // HMI-Befehlsstatus
    bCallEG      : cmd.callEG,
    bCallOG      : cmd.callOG,
    bCall2OG     : cmd.call2OG,
    bStop        : cmd.stop,
    bMaint       : cmd.maint,
  };
}

wss.on('connection', (ws, req) => {
  const ip = req.socket.remoteAddress;
  console.log(`[WS]  Browser verbunden  (${ip})`);

  // Aktuellen Zustand sofort senden
  ws.send(JSON.stringify(buildStateMsg()));

  ws.on('message', (raw) => {
    let msg;
    try { msg = JSON.parse(raw); } catch { return; }

    if (msg.type !== 'write') return;

    switch (msg.key) {
      case 'callEG' : if (msg.value) cmd.callEG  = true; break;
      case 'callOG' : if (msg.value) cmd.callOG  = true; break;
      case 'call2OG': if (msg.value) cmd.call2OG = true; break;
      case 'stop'        : cmd.stop         = Boolean(msg.value); break;
      case 'maint'       : cmd.maint        = Boolean(msg.value); break;
      case 'lightCurtain': cmd.lightCurtain = Boolean(msg.value); break;
    }
  });

  ws.on('close', () => console.log(`[WS]  Browser getrennt   (${ip})`));
  ws.on('error', e => console.error('[WS] Fehler:', e.message));
});

// ────────────────────────────────────────────────────────────────
//  ADS Client
// ────────────────────────────────────────────────────────────────
const client = new Client({
  targetAmsNetId      : CFG.amsNetId,
  targetAdsPort       : CFG.adsPort,
  hideConsoleWarnings : true,
});

client.on('disconnect', () => {
  adsReady = false;
  console.warn('[ADS] Verbindung verloren — Reconnect in', CFG.retryMs / 1000, 's...');
  broadcast({ type: 'status', adsConnected: false });
  setTimeout(connectAds, CFG.retryMs);
});

// ────────────────────────────────────────────────────────────────
//  Hauptzyklus
// ────────────────────────────────────────────────────────────────
let cycleTimer = null;

async function runCycle() {
  const now = Date.now();
  const dt  = (now - phys.lastTick) / 1000;  // Sekunden seit letztem Zyklus
  phys.lastTick = now;

  try {
    // ── 1. PLC-Ausgänge lesen ───────────────────────────────────
    const [
      rMotorUp, rMotorDown, rDoorOpen, rDoorClose,
      rLight1, rLight2, rLight3,
      rStatus,
    ] = await Promise.all([
      client.readSymbol('GVL_Elevator.bMotorUp'),
      client.readSymbol('GVL_Elevator.bMotorDown'),
      client.readSymbol('GVL_Elevator.bDoorOpenCmd'),
      client.readSymbol('GVL_Elevator.bDoorCloseCmd'),
      client.readSymbol('GVL_Elevator.bLightFloor1'),
      client.readSymbol('GVL_Elevator.bLightFloor2'),
      client.readSymbol('GVL_Elevator.bLightFloor3'),
      client.readSymbol('GVL_Elevator.stElevator'),
    ]);

    plcOut = {
      bMotorUp     : rMotorUp.value,
      bMotorDown   : rMotorDown.value,
      bDoorOpenCmd : rDoorOpen.value,
      bDoorCloseCmd: rDoorClose.value,
      bLightFloor1 : rLight1.value,
      bLightFloor2 : rLight2.value,
      bLightFloor3 : rLight3.value,
    };

    const st = rStatus.value;
    plcStatus = {
      eState       : st?.eState       ?? 0,
      nCurrentFloor: st?.nCurrentFloor ?? 1,
      nTargetFloor : st?.nTargetFloor  ?? 0,
      arCallQueue  : Array.isArray(st?.arCallQueue) ? st.arCallQueue : [false, false, false],
    };

    // ── 2. Physik aktualisieren ─────────────────────────────────
    if (plcOut.bMotorUp)
      phys.fHeight = Math.min(100, phys.fHeight + phys.speedLift * dt);
    if (plcOut.bMotorDown)
      phys.fHeight = Math.max(0,   phys.fHeight - phys.speedLift * dt);

    if (plcOut.bDoorOpenCmd)
      phys.fDoor = Math.min(100, phys.fDoor + phys.speedDoor * dt);
    else if (plcOut.bDoorCloseCmd)
      phys.fDoor = Math.max(0,   phys.fDoor - phys.speedDoor * dt);

    // ── 3. Sensoren → PLC schreiben ─────────────────────────────
    const atEG     = phys.fHeight <= 2.0;
    const at1OG    = phys.fHeight >= 44.0 && phys.fHeight <= 56.0;
    const at2OG    = phys.fHeight >= 98.0;
    const doorOpen = phys.fDoor   >= 99.0;
    const doorClosed = phys.fDoor <= 1.0;

    await Promise.all([
      // Sensoren
      client.writeSymbol('GVL_Elevator.bSensorFloor1', atEG),
      client.writeSymbol('GVL_Elevator.bSensorFloor2', at1OG),
      client.writeSymbol('GVL_Elevator.bSensorFloor3', at2OG),
      // Tür-Endschalter
      client.writeSymbol('GVL_Elevator.bDoorIsOpen',   doorOpen),
      client.writeSymbol('GVL_Elevator.bDoorIsClosed', doorClosed),
      // Not-Halt (NC-Kontakt: TRUE = normal, FALSE = ausgelöst)
      client.writeSymbol('GVL_Elevator.bEmergency',    !cmd.stop),
      // Lichtgitter (Pegel)
      client.writeSymbol('GVL_Elevator.bLightCurtain', cmd.lightCurtain),
      // Ruftasten (Impulse)
      client.writeSymbol('GVL_Elevator.bCallFloor1', cmd.callEG),
      client.writeSymbol('GVL_Elevator.bCallFloor2', cmd.callOG),
      client.writeSymbol('GVL_Elevator.bCallFloor3', cmd.call2OG),
      // Kabinetasten nicht vom HMI bedient → immer false
      client.writeSymbol('GVL_Elevator.bCabinCall1', false),
      client.writeSymbol('GVL_Elevator.bCabinCall2', false),
      client.writeSymbol('GVL_Elevator.bCabinCall3', false),
      // Position zurück in PLC schreiben (für Monitoring)
      client.writeSymbol('GVL_Elevator.stElevator.rPosition', phys.fHeight),
    ]);

    // Ruf-Impulse zurücksetzen (R_TRIG in PLC hat reagiert)
    cmd.callEG  = false;
    cmd.callOG  = false;
    cmd.call2OG = false;

    // ── 4. HMI-Broadcast ────────────────────────────────────────
    broadcast(buildStateMsg());

  } catch (e) {
    console.error('[Zyklus] Fehler:', e.message);
  }
}

// ────────────────────────────────────────────────────────────────
//  ADS Verbinden
// ────────────────────────────────────────────────────────────────
async function connectAds() {
  try {
    await client.connect();
    adsReady = true;
    phys.lastTick = Date.now();

    console.log('[ADS] ✓ Verbunden');
    console.log(`      AMS Net ID : ${CFG.amsNetId}`);
    console.log(`      ADS Port   : ${CFG.adsPort}`);
    console.log('');

    broadcast({ type: 'status', adsConnected: true });

    cycleTimer = setInterval(runCycle, CFG.cycleMs);
    await runCycle();

  } catch (e) {
    adsReady = false;
    console.error('[ADS] ✗ Verbindung fehlgeschlagen:', e.message);
    console.log('[ADS]   Wiederhole in', CFG.retryMs / 1000, 's...\n');
    setTimeout(connectAds, CFG.retryMs);
  }
}

// ────────────────────────────────────────────────────────────────
//  Start
// ────────────────────────────────────────────────────────────────
httpServer.listen(CFG.wsPort, () => {
  console.log('');
  console.log('╔══════════════════════════════════════════════════╗');
  console.log('║   TwinCAT ADS ↔ WebSocket Bridge                ║');
  console.log(`║   WebSocket  :  ws://localhost:${CFG.wsPort}               ║`);
  console.log(`║   Zyklus     :  ${CFG.cycleMs}ms  (${1000 / CFG.cycleMs} Hz)                ║`);
  console.log('╠══════════════════════════════════════════════════╣');
  console.log(`║   ADS Ziel   :  ${CFG.amsNetId}    ║`);
  console.log(`║   ADS Port   :  ${CFG.adsPort}                             ║`);
  console.log('╚══════════════════════════════════════════════════╝');
  console.log('');
  console.log('[ADS] Verbinde mit TwinCAT...');
  connectAds();
});

process.on('SIGINT', async () => {
  console.log('\n[STOP] Bridge wird beendet...');
  if (cycleTimer) clearInterval(cycleTimer);
  try { await client.disconnect(); } catch {}
  process.exit(0);
});
