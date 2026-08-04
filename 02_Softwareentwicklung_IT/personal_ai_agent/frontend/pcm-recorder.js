/**
 * AudioWorklet: greift die rohen PCM-Blöcke des Mikrofons ab.
 *
 * Hintergrund: MediaRecorder liefert im Browser nur WebM/Opus. Der
 * Transkriptions-Anbieter lehnt das mit HTTP 400 ab, während WAV/PCM-16
 * zuverlässig durchgeht (so macht es auch TypeFREE). Deshalb sammeln wir
 * hier die Rohdaten ein und bauen die WAV-Datei in app.js selbst zusammen.
 */
class PcmRecorder extends AudioWorkletProcessor {
    process(inputs) {
        const channel = inputs[0] && inputs[0][0];
        if (channel && channel.length) {
            // Kopie nötig – der Puffer wird nach process() wiederverwendet.
            this.port.postMessage(new Float32Array(channel));
        }
        // Es wird bewusst nichts in outputs geschrieben: Der Knoten hängt zwar
        // an destination (sonst zieht die Audio-Engine keine Daten), bleibt
        // dadurch aber stumm – kein Echo über den Lautsprecher.
        return true;
    }
}

registerProcessor('pcm-recorder', PcmRecorder);
