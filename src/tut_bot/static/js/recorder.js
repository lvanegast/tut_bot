/**
 * AudioRecorder: Captura audio del micrófono y genera un archivo WAV
 * estándar a 16.000 Hz, 16-bit PCM, 1 canal (Mono), optimizado para Azure Speech SDK.
 */
class AudioRecorder {
    constructor() {
        this.audioContext = null;
        this.mediaStream = null;
        this.processor = null;
        this.source = null;
        this.recordedSamples = [];
        this.isRecording = false;
        this.targetSampleRate = 16000;
    }

    async start() {
        if (this.isRecording) return;
        this.recordedSamples = [];

        this.mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            }
        });

        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        this.audioContext = new AudioContextClass();
        this.source = this.audioContext.createMediaStreamSource(this.mediaStream);

        // Buffer size 4096 para procesamiento estable
        this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);

        this.processor.onaudioprocess = (e) => {
            if (!this.isRecording) return;
            const inputData = e.inputBuffer.getChannelData(0);
            this.recordedSamples.push(new Float32Array(inputData));
        };

        this.source.connect(this.processor);
        this.processor.connect(this.audioContext.destination);
        this.isRecording = true;
    }

    stop() {
        if (!this.isRecording) return null;
        this.isRecording = false;

        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
        }
        if (this.processor && this.source) {
            this.source.disconnect(this.processor);
            this.processor.disconnect(this.audioContext.destination);
        }

        const inputSampleRate = this.audioContext.sampleRate;
        if (this.audioContext.state !== 'closed') {
            this.audioContext.close();
        }

        // Concatenar todos los buffers capturados
        const totalLength = this.recordedSamples.reduce((acc, curr) => acc + curr.length, 0);
        const mergedBuffer = new Float32Array(totalLength);
        let offset = 0;
        for (const chunk of this.recordedSamples) {
            mergedBuffer.set(chunk, offset);
            offset += chunk.length;
        }

        // Remuestrear a 16000 Hz si el micrófono está en 44.1k/48k
        const resampledBuffer = this._resample(mergedBuffer, inputSampleRate, this.targetSampleRate);

        // Convertir a PCM de 16 bits y empaquetar cabecera WAV
        const wavBlob = this._encodeWAV(resampledBuffer, this.targetSampleRate);
        return wavBlob;
    }

    _resample(buffer, fromRate, toRate) {
        if (fromRate === toRate) return buffer;
        const ratio = fromRate / toRate;
        const newLength = Math.round(buffer.length / ratio);
        const result = new Float32Array(newLength);
        for (let i = 0; i < newLength; i++) {
            const index = i * ratio;
            const left = Math.floor(index);
            const right = Math.min(left + 1, buffer.length - 1);
            const fraction = index - left;
            result[i] = buffer[left] * (1 - fraction) + buffer[right] * fraction;
        }
        return result;
    }

    _encodeWAV(samples, sampleRate) {
        const buffer = new ArrayBuffer(44 + samples.length * 2);
        const view = new DataView(buffer);

        // RIFF chunk descriptor
        this._writeString(view, 0, 'RIFF');
        view.setUint32(4, 36 + samples.length * 2, true);
        this._writeString(view, 8, 'WAVE');

        // FMT sub-chunk
        this._writeString(view, 12, 'fmt ');
        view.setUint32(16, 16, true);          // Subchunk1Size (16 for PCM)
        view.setUint16(20, 1, true);           // AudioFormat (1 for PCM)
        view.setUint16(22, 1, true);           // NumChannels (1 = Mono)
        view.setUint32(24, sampleRate, true);  // SampleRate (16000)
        view.setUint32(28, sampleRate * 2, true); // ByteRate (SampleRate * NumChannels * BitsPerSample/8)
        view.setUint16(32, 2, true);           // BlockAlign (NumChannels * BitsPerSample/8)
        view.setUint16(34, 16, true);          // BitsPerSample (16 bits)

        // DATA sub-chunk
        this._writeString(view, 36, 'data');
        view.setUint32(40, samples.length * 2, true);

        // Escribir muestras PCM de 16 bits (clamping entre -1.0 y 1.0)
        let index = 44;
        for (let i = 0; i < samples.length; i++) {
            let s = Math.max(-1, Math.min(1, samples[i]));
            view.setInt16(index, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
            index += 2;
        }

        return new Blob([view], { type: 'audio/wav' });
    }

    _writeString(view, offset, string) {
        for (let i = 0; i < string.length; i++) {
            view.setUint8(offset + i, string.charCodeAt(i));
        }
    }
}

window.AudioRecorder = AudioRecorder;
