// =========================================================================
// tut_bot - Frontend Logic
// =========================================================================

let currentLanguage = 'de-DE';
let currentMode = 'curated'; // 'curated' | 'custom'
let exercises = [];
let currentIndex = 0;
let recorder = null;
let recordingTimerInterval = null;
let recordingSeconds = 0;
let lastEvaluation = null;

// Inicialización
document.addEventListener('DOMContentLoaded', async () => {
    recorder = new window.AudioRecorder();
    initInteractiveVowelChart();
    await checkHealth();
    await loadCategories();
    await loadExercises();
    await loadUserStats();
});

// Comprobar estado del backend y servicios
async function checkHealth() {
    const badge = document.getElementById('status-badge');
    const text = document.getElementById('status-text');
    const tgBadge = document.getElementById('telegram-badge');
    const tgText = document.getElementById('telegram-status-text');

    try {
        const res = await fetch('/api/health');
        const data = await res.json();
        if (data.mock_mode) {
            badge.className = "flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200";
            badge.querySelector('span').className = "w-2 h-2 rounded-full bg-amber-500 animate-pulse";
            text.textContent = "Modo Simulación (Mock)";
        } else {
            badge.className = "flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200";
            badge.querySelector('span').className = "w-2 h-2 rounded-full bg-emerald-500 animate-pulse";
            text.textContent = "Azure + Gemini Activos";
        }

        if (tgBadge && tgText) {
            if (data.telegram_configured) {
                tgBadge.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200";
                tgText.textContent = "Telegram Activo";
            } else {
                tgBadge.className = "hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-slate-100 text-slate-500 border border-slate-200";
                tgText.textContent = "Telegram (Configurar)";
            }
        }
    } catch (e) {
        badge.className = "flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200";
        badge.querySelector('span').className = "w-2 h-2 rounded-full bg-red-500";
        text.textContent = "Sin conexión al servidor";
    }
}

// Cambiar Idioma
async function setLanguage(lang) {
    if (currentLanguage === lang) return;
    currentLanguage = lang;

    // Actualizar botones de idioma
    const deBtn = document.getElementById('lang-de-btn');
    const enBtn = document.getElementById('lang-en-btn');

    if (lang === 'de-DE') {
        deBtn.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all bg-white text-slate-900 shadow-sm";
        enBtn.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all text-slate-600 hover:text-slate-900";
    } else {
        enBtn.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all bg-white text-slate-900 shadow-sm";
        deBtn.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all text-slate-600 hover:text-slate-900";
    }

    // Resetear resultados
    document.getElementById('results-card').classList.add('hidden');
    await loadCategories();
    await loadExercises();
}

// Cambiar Modo: Curado vs Práctica Libre
function setMode(mode) {
    currentMode = mode;
    const curatedTab = document.getElementById('tab-curated');
    const customTab = document.getElementById('tab-custom');
    const curatedView = document.getElementById('curated-view');
    const customView = document.getElementById('custom-view');
    const catContainer = document.getElementById('category-selector-container');
    const navBar = document.getElementById('exercise-nav-bar');
    const tipBox = document.getElementById('exercise-tip-box');

    if (mode === 'curated') {
        curatedTab.className = "px-4 py-2 rounded-xl text-sm font-bold bg-indigo-50 text-indigo-600 border border-indigo-200 transition-all";
        customTab.className = "px-4 py-2 rounded-xl text-sm font-bold text-slate-600 hover:bg-slate-100 transition-all";
        curatedView.classList.remove('hidden');
        customView.classList.add('hidden');
        catContainer.classList.remove('hidden');
        navBar.classList.remove('hidden');
        tipBox.classList.remove('hidden');
    } else {
        customTab.className = "px-4 py-2 rounded-xl text-sm font-bold bg-indigo-50 text-indigo-600 border border-indigo-200 transition-all";
        curatedTab.className = "px-4 py-2 rounded-xl text-sm font-bold text-slate-600 hover:bg-slate-100 transition-all";
        curatedView.classList.add('hidden');
        customView.classList.remove('hidden');
        catContainer.classList.add('hidden');
        navBar.classList.add('hidden');
        tipBox.classList.add('hidden');
    }
}

// Cargar Categorías
async function loadCategories() {
    try {
        const res = await fetch(`/api/categories?language=${currentLanguage}`);
        const categories = await res.json();
        const select = document.getElementById('category-select');
        select.innerHTML = '<option value="">Todas las categorías</option>';
        categories.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c;
            opt.textContent = c;
            select.appendChild(opt);
        });
    } catch (e) {
        console.error("Error cargando categorías:", e);
    }
}

// Filtrar por categoría seleccionada
async function filterByCategory() {
    await loadExercises();
}

// Cargar Ejercicios
async function loadExercises() {
    try {
        const cat = document.getElementById('category-select').value;
        let url = `/api/exercises?language=${currentLanguage}`;
        if (cat) url += `&category=${encodeURIComponent(cat)}`;

        const res = await fetch(url);
        exercises = await res.json();
        currentIndex = 0;
        renderExercise();
    } catch (e) {
        console.error("Error cargando ejercicios:", e);
    }
}

// Renderizar Ejercicio Actual
function renderExercise() {
    if (!exercises || exercises.length === 0) return;
    const ex = exercises[currentIndex];

    document.getElementById('exercise-level').textContent = ex.level;
    document.getElementById('exercise-category').textContent = ex.category;
    document.getElementById('target-sentence').textContent = ex.target_text;
    document.getElementById('target-ipa').textContent = ex.ipa ? `/${ex.ipa}/` : '';
    document.getElementById('target-translation').textContent = `"${ex.translation_es}"`;
    document.getElementById('exercise-tip').textContent = ex.tip;
    document.getElementById('exercise-counter').textContent = `Ejercicio ${currentIndex + 1} de ${exercises.length}`;

    // Renderizar fonemas clave
    const phonemesContainer = document.getElementById('focus-phonemes-container');
    phonemesContainer.innerHTML = '';
    (ex.focus_phonemes || []).forEach(p => {
        const span = document.createElement('span');
        span.className = "px-2 py-0.5 rounded-md text-xs font-mono font-bold bg-violet-100 text-violet-800 border border-violet-200";
        span.textContent = `/${p}/`;
        phonemesContainer.appendChild(span);
    });

    // Actualizar Atlas Fonético y Articulatorio Gráfico
    updateVisualAtlas(ex);

    // Ocultar resultados previos
    document.getElementById('results-card').classList.add('hidden');
}

// Siguiente Ejercicio
function nextExercise() {
    if (currentIndex < exercises.length - 1) {
        currentIndex++;
        renderExercise();
    } else {
        currentIndex = 0;
        renderExercise();
    }
}

// Ejercicio Anterior
function prevExercise() {
    if (currentIndex > 0) {
        currentIndex--;
        renderExercise();
    }
}

// Obtener el texto de referencia actual
function getReferenceText() {
    if (currentMode === 'curated') {
        return exercises[currentIndex]?.target_text || "";
    } else {
        return document.getElementById('custom-text-input').value.trim();
    }
}

// Reproducir Audio de Referencia (TTS)
async function playNativeAudio() {
    const text = getReferenceText();
    if (!text) {
        alert("Por favor introduce una frase para escuchar.");
        return;
    }

    const ttsBtn = document.getElementById('tts-btn');
    const ttsBtnText = document.getElementById('tts-btn-text');
    const originalText = ttsBtnText.textContent;
    ttsBtnText.textContent = "Reproduciendo...";
    ttsBtn.disabled = true;

    try {
        // Intentar primero con Azure TTS del backend
        const res = await fetch('/api/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text, language: currentLanguage })
        });

        if (res.ok) {
            const blob = await res.blob();
            const audioUrl = URL.createObjectURL(blob);
            const player = document.getElementById('tts-audio-player');
            player.src = audioUrl;
            player.onended = () => {
                ttsBtnText.textContent = originalText;
                ttsBtn.disabled = false;
            };
            player.play();
            return;
        }
    } catch (e) {
        console.warn("Fallo Azure TTS, usando Web Speech API del navegador...");
    }

    // Fallback nativo del navegador (SpeechSynthesis)
    if ('speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = currentLanguage;
        utterance.rate = 0.9;
        utterance.onend = () => {
            ttsBtnText.textContent = originalText;
            ttsBtn.disabled = false;
        };
        utterance.onerror = () => {
            ttsBtnText.textContent = originalText;
            ttsBtn.disabled = false;
        };
        window.speechSynthesis.speak(utterance);
    } else {
        alert("Tu navegador no soporta síntesis de voz.");
        ttsBtnText.textContent = originalText;
        ttsBtn.disabled = false;
    }
}

// Grabar / Detener Audio
async function toggleRecording() {
    const recordBtn = document.getElementById('record-btn');
    const recordBtnText = document.getElementById('record-btn-text');
    const recordIcon = document.getElementById('record-icon');
    const timerElem = document.getElementById('record-timer');

    if (!recorder.isRecording) {
        const refText = getReferenceText();
        if (!refText) {
            alert("Introduce o selecciona una frase antes de grabar.");
            return;
        }

        try {
            await recorder.start();
            startVisualizer();
            recordBtn.className = "w-full sm:w-auto px-8 py-3.5 rounded-2xl bg-red-600 hover:bg-red-700 text-white font-bold text-sm flex items-center justify-center gap-3 transition-all shadow-lg recording-pulse";
            recordBtnText.textContent = "Detener Grabación";
            recordIcon.className = "w-3.5 h-3.5 rounded-sm bg-white";
            timerElem.classList.remove('hidden');
            recordingSeconds = 0;
            timerElem.textContent = "00:00";

            recordingTimerInterval = setInterval(() => {
                recordingSeconds++;
                const mins = String(Math.floor(recordingSeconds / 60)).padStart(2, '0');
                const secs = String(recordingSeconds % 60).padStart(2, '0');
                timerElem.textContent = `${mins}:${secs}`;
            }, 1000);

        } catch (e) {
            alert("No se pudo acceder al micrófono: " + e.message);
        }

    } else {
        // Detener grabación
        clearInterval(recordingTimerInterval);
        stopVisualizer();
        timerElem.classList.add('hidden');
        recordBtn.className = "w-full sm:w-auto px-8 py-3.5 rounded-2xl bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white font-bold text-sm flex items-center justify-center gap-3 transition-all shadow-lg shadow-indigo-200";
        recordBtnText.textContent = "Grabar Mi Pronunciación";
        recordIcon.className = "w-3.5 h-3.5 rounded-full bg-red-400";

        const wavBlob = recorder.stop();
        if (wavBlob) {
            await submitForEvaluation(wavBlob);
        }
    }
}

// Enviar Audio a la API para Evaluación
async function submitForEvaluation(wavBlob) {
    const loadingCard = document.getElementById('loading-card');
    const resultsCard = document.getElementById('results-card');

    loadingCard.classList.remove('hidden');
    resultsCard.classList.add('hidden');

    const formData = new FormData();
    formData.append("audio", wavBlob, "recording.wav");
    formData.append("reference_text", getReferenceText());
    formData.append("language", currentLanguage);

    try {
        const response = await fetch('/api/evaluate', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`Error en el servidor (${response.status})`);
        }

        const data = await response.json();
        lastEvaluation = data;
        renderResults(data);
        await loadUserStats();

    } catch (err) {
        alert("Error evaluando pronunciación: " + err.message);
    } finally {
        loadingCard.classList.add('hidden');
    }
}

// Renderizar Resultados
function renderResults(data) {
    const resultsCard = document.getElementById('results-card');
    resultsCard.classList.remove('hidden');

    // Puntuación General
    const score = Math.round(data.overall_score);
    const scoreBadge = document.getElementById('overall-score-badge');
    const scoreStatus = document.getElementById('score-status-text');

    scoreBadge.textContent = score;
    if (score >= 80) {
        scoreBadge.className = "w-16 h-16 rounded-2xl bg-emerald-50 border-2 border-emerald-300 flex items-center justify-center font-extrabold text-2xl text-emerald-700 shadow-sm";
        scoreStatus.textContent = "Excelente";
        scoreStatus.className = "text-xs font-bold text-emerald-600";
    } else if (score >= 60) {
        scoreBadge.className = "w-16 h-16 rounded-2xl bg-amber-50 border-2 border-amber-300 flex items-center justify-center font-extrabold text-2xl text-amber-700 shadow-sm";
        scoreStatus.textContent = "Aceptable / Por pulir";
        scoreStatus.className = "text-xs font-bold text-amber-600";
    } else {
        scoreBadge.className = "w-16 h-16 rounded-2xl bg-rose-50 border-2 border-rose-300 flex items-center justify-center font-extrabold text-2xl text-rose-700 shadow-sm";
        scoreStatus.textContent = "Necesita Práctica";
        scoreStatus.className = "text-xs font-bold text-rose-600";
    }

    // Métricas secundarias
    document.getElementById('metric-accuracy').textContent = `${Math.round(data.accuracy_score)}/100`;
    document.getElementById('metric-fluency').textContent = `${Math.round(data.fluency_score)}/100`;
    document.getElementById('metric-prosody').textContent = data.prosody_score !== null ? `${Math.round(data.prosody_score)}/100` : "N/D";
    document.getElementById('metric-completeness').textContent = `${Math.round(data.completeness_score)}%`;

    // Renderizar desglose de palabras
    const wordsContainer = document.getElementById('words-container');
    wordsContainer.innerHTML = '';
    const phonemesDetailBox = document.getElementById('phonemes-detail-box');
    phonemesDetailBox.classList.add('hidden');

    (data.words || []).forEach((w, idx) => {
        const btn = document.createElement('button');
        let colorClass = "score-excellent";
        if (w.score < 60 || w.error_type !== 'None') colorClass = "score-poor";
        else if (w.score < 80) colorClass = "score-good";

        btn.className = `word-pill px-3.5 py-2 rounded-xl border text-sm font-bold shadow-xs ${colorClass}`;
        btn.innerHTML = `
            <span>${w.word}</span>
            <span class="text-[10px] opacity-80 font-mono mt-0.5">${Math.round(w.score)} pts</span>
        `;
        btn.onclick = () => showPhonemesForWord(w);
        wordsContainer.appendChild(btn);

        // Mostrar por defecto los fonemas de la primera palabra que tenga error
        if (idx === 0 || (w.score < 75 && phonemesDetailBox.classList.contains('hidden'))) {
            showPhonemesForWord(w);
        }
    });

    // Feedback Pedagógico de Gemini
    const geminiTextElem = document.getElementById('gemini-feedback-text');
    geminiTextElem.innerHTML = formatMarkdown(data.pedagogical_feedback || "No hay comentarios adicionales.");

    // Scroll suave hacia los resultados
    resultsCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Mostrar fonemas IPA de la palabra seleccionada
function showPhonemesForWord(wordObj) {
    const box = document.getElementById('phonemes-detail-box');
    const label = document.getElementById('selected-word-label');
    const container = document.getElementById('phonemes-container');

    box.classList.remove('hidden');
    label.textContent = wordObj.word;
    container.innerHTML = '';

    if (!wordObj.phonemes || wordObj.phonemes.length === 0) {
        container.innerHTML = '<span class="text-xs text-slate-500">Sin desglose de fonemas disponible.</span>';
        return;
    }

    wordObj.phonemes.forEach(p => {
        const pill = document.createElement('div');
        let colorClass = "bg-emerald-100 text-emerald-800 border-emerald-300";
        if (p.score < 60) colorClass = "bg-rose-100 text-rose-800 border-rose-300";
        else if (p.score < 80) colorClass = "bg-amber-100 text-amber-800 border-amber-300";

        pill.className = `flex flex-col items-center px-2.5 py-1 rounded-lg border text-xs font-mono font-bold ${colorClass}`;
        pill.innerHTML = `
            <span class="text-sm">/${p.phoneme}/</span>
            <span class="text-[9px] opacity-75">${Math.round(p.score)}</span>
        `;
        container.appendChild(pill);
    });
}

// Convertidor ligero de Markdown para la respuesta de Gemini
function formatMarkdown(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n- /g, '<br>• ');
}

// Reintentar ejercicio actual
function retryCurrentExercise() {
    document.getElementById('results-card').classList.add('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Cargar estadísticas acumuladas y fonemas críticos
async function loadUserStats() {
    try {
        const res = await fetch('/api/stats?user_id=web_default');
        if (!res.ok) return;
        const stats = await res.json();

        const attemptsBadge = document.getElementById('stats-attempts-badge');
        const avgBadge = document.getElementById('stats-avg-badge');
        const weakContainer = document.getElementById('stats-weak-phonemes-container');

        if (attemptsBadge) {
            attemptsBadge.textContent = `${stats.total_attempts} Práctica${stats.total_attempts === 1 ? '' : 's'}`;
        }
        if (avgBadge) {
            avgBadge.textContent = stats.total_attempts > 0 ? `Promedio: ${Math.round(stats.average_overall)}/100` : 'Promedio: --';
        }

        if (weakContainer) {
            if (!stats.weak_phonemes_top || stats.weak_phonemes_top.length === 0) {
                weakContainer.innerHTML = '<span class="text-slate-400 italic">Sin fonemas críticos detectados aún. ¡Excelente trabajo!</span>';
            } else {
                weakContainer.innerHTML = stats.weak_phonemes_top.map(item => `
                    <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 font-semibold text-xs">
                        <span class="font-mono">/${item.phoneme}/</span>
                        <span class="bg-rose-200/70 text-rose-900 px-1.5 py-0.5 rounded-md text-[10px] font-bold">${item.count} fallos</span>
                    </span>
                `).join('');
            }
        }
    } catch (e) {
        console.warn("No se pudieron cargar estadísticas:", e);
    }
}

// =========================================================================
// Visualizador de Ondas Acústicas en Tiempo Real (Web Audio API + Canvas)
// =========================================================================

let visualizerAnimFrame = null;

function startVisualizer() {
    const container = document.getElementById('visualizer-container');
    const canvas = document.getElementById('waveform-canvas');
    if (!container || !canvas || !recorder) return;

    container.classList.remove('hidden');
    const analyser = recorder.getAnalyser();
    if (!analyser) return;

    const ctx = canvas.getContext('2d');
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function renderFrame() {
        visualizerAnimFrame = requestAnimationFrame(renderFrame);
        analyser.getByteFrequencyData(dataArray);

        ctx.fillStyle = '#020617'; // slate-950
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        const totalBars = 48;
        const step = Math.floor(bufferLength / totalBars) || 1;
        const barWidth = (canvas.width / totalBars) - 2;

        for (let i = 0; i < totalBars; i++) {
            const val = dataArray[i * step] || 0;
            const barHeight = Math.max(4, (val / 255) * (canvas.height - 12));
            const x = i * (barWidth + 2);
            const y = canvas.height - barHeight - 4;

            const grad = ctx.createLinearGradient(0, canvas.height, 0, 0);
            grad.addColorStop(0, '#4f46e5'); // Indigo
            grad.addColorStop(0.5, '#9333ea'); // Purple
            grad.addColorStop(1, '#f43f5e'); // Rose neon

            ctx.fillStyle = grad;
            if (ctx.roundRect) {
                ctx.beginPath();
                ctx.roundRect(x, y, barWidth, barHeight, [3, 3, 1, 1]);
                ctx.fill();
            } else {
                ctx.fillRect(x, y, barWidth, barHeight);
            }
        }
    }

    renderFrame();
}

function stopVisualizer() {
    if (visualizerAnimFrame) {
        cancelAnimationFrame(visualizerAnimFrame);
        visualizerAnimFrame = null;
    }
    const container = document.getElementById('visualizer-container');
    if (container) {
        container.classList.add('hidden');
    }
}

// =========================================================================
// Atlas Fonético y Articulatorio Interactivo (IPA Vowel Chart & Vocal Tract)
// =========================================================================

const VOWELS_INFO = {
    'iː': { name: 'Vocal anterior cerrada no redondeada', desc: 'Labios en sonrisa tensa, lengua muy alta hacia los dientes frontales.', de: 'bieten, wir', en: 'sheep, feel' },
    'yː': { name: 'Umlaut Ü largo cerrado redondeado', desc: 'Labios en beso/silbato de [u], pero impulsando sonido de [i].', de: 'fühlen, über', en: '-' },
    'ɪ': { name: 'Vocal casi cerrada casi anterior corta', desc: 'Vocal corta y relajada; boca semiabierta sin tensión.', de: 'bitten, ich', en: 'ship, fill' },
    'ʏ': { name: 'Umlaut Ü corto relajado', desc: 'Umlaut Ü breve y suave con labios ligeramente redondeados.', de: 'füllen, fünf', en: '-' },
    'eː': { name: 'Vocal anterior cerrada-media tensa', desc: 'E larga y clara con las comisuras de los labios estiradas.', de: 'Beet, See', en: '-' },
    'øː': { name: 'Umlaut Ö largo cerrado-medio', desc: 'Labios redondeados en posición de "o", pero intentando emitir "e".', de: 'schön, Öl', en: '-' },
    'ɛ': { name: 'Vocal anterior abierta-media corta', desc: 'E corta y seca, la mandíbula baja moderadamente.', de: 'Bett, sechs', en: 'bed, red' },
    'œ': { name: 'Umlaut Ö corto abierto-medio', desc: 'Ö breve con boca más abierta y labios en óvalo.', de: 'möchte, zwölf', en: '-' },
    'ɛː': { name: 'Umlaut Ä largo abierto-medio', desc: 'E abierta y alargada, mandíbula baja manteniendo lengua frontal.', de: 'Mädchen, wählen', en: '-' },
    'æ': { name: 'Vocal casi abierta anterior (Short A inglesa)', desc: 'Mandíbula muy abierta hacia abajo con lengua extendida.', de: '-', en: 'cat, black, trap' },
    'a': { name: 'Vocal abierta anterior', desc: 'A frontal abierta y brillante.', de: 'Tag, klares', en: '-' },
    'ə': { name: 'Vocal media central (Schwa)', desc: 'Vocal totalmente neutra en sílabas sin acento.', de: 'bitte, habe', en: 'about, father' },
    'ɐ': { name: 'Vocal cuasi-abierta central (R vocalizada)', desc: 'R alemana final (-er), suena como una "a" suave y relajada.', de: 'Lehrer, Wasser', en: '-' },
    'ʌ': { name: 'Vocal central/posterior semiabierta (Wedge)', desc: 'Vocal corta y gutural en el centro de la boca.', de: '-', en: 'cut, cup, love' },
    'uː': { name: 'Vocal posterior cerrada redondeada', desc: 'U tensa y profunda con labios en círculo estrecho.', de: 'Buch, gut', en: 'pool, boot' },
    'ʊ': { name: 'Vocal posterior casi cerrada corta', desc: 'U corta y relajada sin tanta tensión labial.', de: 'Mutter, und', en: 'pull, book' },
    'oː': { name: 'Vocal posterior cerrada-media', desc: 'O larga y pura, labios proyectados en círculo.', de: 'schon, Ofen', en: '-' },
    'ɔ': { name: 'Vocal posterior abierta-media corta', desc: 'O corta y abierta, boca amplia.', de: 'offen, kochen', en: 'thought, dog' },
    'ɑː': { name: 'Vocal posterior abierta no redondeada', desc: 'A profunda que resuena en la parte trasera de la garganta.', de: '-', en: 'father, palm, calm' }
};

const ARTICULATION_ZONES = [
    { id: 'bilabial', label: 'Bilabial', icon: '👄', title: 'Labios (Bilabial)', desc: 'Contacto de ambos labios juntos (/b/, /p/, /m/). Expulsión explosiva o resonancia nasal.', phonemes: ['b', 'p', 'm'] },
    { id: 'labiodental', label: 'Labiodental', icon: '🦷', title: 'Dientes + Labio (/v/, /f/)', desc: 'Los incisivos superiores rozan el labio inferior provocando una fricción continua acústica (/v/ vibrante sonora, /f/ sorda).', phonemes: ['v', 'f'] },
    { id: 'dental', label: 'Interdental', icon: '👅', title: 'Lengua en Dientes (/θ/ y /ð/)', desc: 'La punta de la lengua asoma suavemente entre los dientes frontales: soplido suave (/θ/ en think) o vibración con voz (/ð/ en this).', phonemes: ['θ', 'ð'] },
    { id: 'alveolar', label: 'Alveolar', icon: '📍', title: 'Alvéolos Dentales', desc: 'La punta de la lengua toca la cresta tras los dientes superiores (/t/, /d/, /s/, /z/, /n/, /l/). Oposición sonora y sorda clave.', phonemes: ['t', 'd', 's', 'z', 'n', 'l'] },
    { id: 'postalveolar', label: 'Postalveolar', icon: '👂', title: 'Región Postalveolar (/ʃ/, /tʃ/)', desc: 'La lengua retrocede hacia el paladar con labios redondeados hacia afuera (/ʃ/ como en Deutsch o sheep).', phonemes: ['ʃ', 'ʒ', 'tʃ', 'dʒ'] },
    { id: 'palatal', label: 'Palatal', icon: '🏔️', title: 'Paladar Medio (Ich-Laut /ç/)', desc: 'El dorso de la lengua sube plano contra el paladar duro medio, susurrando el aire suavemente sin aspereza.', phonemes: ['ç', 'j'] },
    { id: 'velar', label: 'Velar', icon: '🚪', title: 'Paladar Blando (Ach-Laut /x/)', desc: 'El dorso posterior de la lengua contacta o fricciona contra el velo del paladar (/k/, /ɡ/, /x/ en Buch o kochen).', phonemes: ['k', 'ɡ', 'x', 'ŋ'] },
    { id: 'uvular', label: 'Uvular', icon: '🌊', title: 'Campanilla / Úvula (R alemana /ʁ/)', desc: 'La campanilla vibra con suavidad o genera fricción gutural en la garganta profunda al inicio de palabra.', phonemes: ['ʁ'] },
    { id: 'glottal', label: 'Glotal', icon: '🗣️', title: 'Cuerdas Vocales / Glotis (/h/, /ʔ/)', desc: 'Aspiración suave (/h/) o golpe de glotis (/ʔ/) antes de vocales iniciales en alemán.', phonemes: ['h', 'ʔ'] },
    { id: 'vowel', label: 'Vocálico', icon: '🎯', title: 'Resonancia Vocálica (Cuadrilátero)', desc: 'Tracto vocal totalmente abierto sin obstrucción física; el tono se modula por la altura lingual y la forma labial.', phonemes: ['iː', 'yː', 'øː', 'æ', 'uː', 'ʊ', 'eː', 'oː'] }
];

// Alternar entre Cuadrilátero Vocálico y Puntos de Articulación
function switchVisualMap(mode) {
    const vowelCont = document.getElementById('vowel-map-container');
    const consCont = document.getElementById('consonants-map-container');
    const tabVowels = document.getElementById('tab-vowels-map');
    const tabCons = document.getElementById('tab-consonants-map');

    if (mode === 'vowels') {
        vowelCont.classList.remove('hidden');
        consCont.classList.add('hidden');
        tabVowels.className = "px-3 py-1.5 rounded-lg bg-white text-slate-900 shadow-xs transition-all";
        tabCons.className = "px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 transition-all";
    } else {
        consCont.classList.remove('hidden');
        vowelCont.classList.add('hidden');
        tabCons.className = "px-3 py-1.5 rounded-lg bg-white text-slate-900 shadow-xs transition-all";
        tabVowels.className = "px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 transition-all";
    }
}

// Inicializar eventos de clic y hover en los nodos del cuadrilátero vocálico
function initInteractiveVowelChart() {
    const nodes = document.querySelectorAll('.vowel-node');
    const infoDesc = document.getElementById('vowel-info-desc');

    nodes.forEach(node => {
        const v = node.getAttribute('data-vowel');
        const info = VOWELS_INFO[v];

        node.addEventListener('mouseenter', () => {
            if (info && infoDesc) {
                const exStr = currentLanguage === 'de-DE' ? `Ejemplo alemán: "${info.de}"` : `Ejemplo inglés: "${info.en}"`;
                infoDesc.innerHTML = `<strong>[${v}] ${info.name}:</strong> ${info.desc} <span class="text-indigo-600 font-semibold font-mono">(${exStr})</span>`;
            }
        });

        node.addEventListener('click', () => {
            if (info && infoDesc) {
                const exStr = currentLanguage === 'de-DE' ? `"${info.de}"` : `"${info.en}"`;
                infoDesc.innerHTML = `<strong>[${v}] Seleccionado:</strong> ${info.name}. ${info.desc} <em>Ejemplo: ${exStr}</em>`;
            }
        });
    });
}

// Actualizar Atlas según el ejercicio seleccionado
function updateVisualAtlas(ex) {
    if (!ex) return;

    const focusPhonemes = ex.focus_phonemes || [];
    const activeIndicator = document.getElementById('active-vowel-indicator');
    const infoDesc = document.getElementById('vowel-info-desc');

    // 1. Actualizar cuadrilátero vocálico
    const allNodes = document.querySelectorAll('.vowel-node');
    allNodes.forEach(node => node.classList.remove('active-vowel'));

    const activeVowels = [];
    allNodes.forEach(node => {
        const v = node.getAttribute('data-vowel');
        if (focusPhonemes.includes(v)) {
            node.classList.add('active-vowel');
            activeVowels.push(v);
        }
    });

    if (activeVowels.length > 0) {
        if (activeIndicator) {
            activeIndicator.textContent = `Fonema vocálico activo: /${activeVowels.join('/ /')}/`;
            activeIndicator.classList.remove('hidden');
        }
        const firstV = activeVowels[0];
        const info = VOWELS_INFO[firstV];
        if (info && infoDesc) {
            const exStr = currentLanguage === 'de-DE' ? `Ejemplo: "${info.de}"` : `Ejemplo: "${info.en}"`;
            infoDesc.innerHTML = `<strong>🎯 Fonema objetivo [${firstV}]:</strong> ${info.name}. ${info.desc} <span class="text-indigo-600 font-bold font-mono">(${exStr})</span>`;
        }
    } else {
        if (activeIndicator) {
            activeIndicator.textContent = "Sin vocales prioritarias en este ejercicio";
        }
    }

    // 2. Renderizar y actualizar Puntos de Articulación Consonántica
    renderArticulationZones(ex);

    // 3. Selección inteligente de pestaña visual según el tipo de ejercicio
    const artType = (ex.articulation_type || '').toLowerCase();
    const isVowelExercise = artType === 'vowel' || ex.category.toLowerCase().includes('umlaut') || ex.category.toLowerCase().includes('vocálic');

    if (isVowelExercise) {
        switchVisualMap('vowels');
    } else {
        switchVisualMap('consonants');
    }
}

// Renderizar badges y detalle de las zonas de articulación
function renderArticulationZones(ex) {
    const grid = document.getElementById('articulation-zones-grid');
    if (!grid) return;
    grid.innerHTML = '';

    const artType = (ex.articulation_type || '').toLowerCase();
    const focusPhonemes = ex.focus_phonemes || [];

    let matchedZone = null;

    ARTICULATION_ZONES.forEach(zone => {
        const isTypeMatch = artType === zone.id;
        const hasPhonemeMatch = zone.phonemes.some(p => focusPhonemes.includes(p));
        const isActive = isTypeMatch || hasPhonemeMatch;

        if (isActive && !matchedZone) {
            matchedZone = zone;
        }

        const card = document.createElement('div');
        card.className = `art-zone-card p-3 rounded-2xl border text-center transition-all ${
            isActive ? 'active-zone bg-indigo-50 border-indigo-400 font-bold shadow-xs' : 'bg-slate-50 border-slate-200 text-slate-600'
        }`;
        card.innerHTML = `
            <div class="text-2xl mb-1">${zone.icon}</div>
            <div class="text-xs font-extrabold ${isActive ? 'text-indigo-900' : 'text-slate-800'}">${zone.label}</div>
            <div class="text-[10px] text-slate-500 font-mono mt-0.5">${zone.phonemes.slice(0, 3).map(p => `/${p}/`).join(' ')}</div>
        `;

        card.onclick = () => selectArticulationZone(zone);
        grid.appendChild(card);
    });

    if (matchedZone) {
        selectArticulationZone(matchedZone, ex);
    } else {
        selectArticulationZone(ARTICULATION_ZONES[0], ex);
    }
}

// Seleccionar y mostrar explicación anatómica detallada
function selectArticulationZone(zone, ex) {
    const badge = document.getElementById('cz-badge');
    const title = document.getElementById('cz-title');
    const desc = document.getElementById('cz-desc');

    if (badge) badge.textContent = zone.label;
    if (title) title.textContent = `${zone.icon} ${zone.title}`;
    if (desc) {
        let text = zone.desc;
        if (ex && ex.tip && (ex.articulation_type === zone.id || zone.phonemes.some(p => (ex.focus_phonemes || []).includes(p)))) {
            text += ` <br><strong class="text-indigo-900">Consejo anatómico para este ejercicio:</strong> ${ex.tip}`;
        }
        desc.innerHTML = text;
    }
}

