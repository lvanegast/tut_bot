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

