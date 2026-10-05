# Reglas Pedagógicas y Técnicas del Tutor de Idiomas (tut_bot)

Este conjunto de reglas rige el desarrollo pedagógico, la calibración curricular y la arquitectura del tutor inteligente para el aprendizaje de Alemán e Inglés en hispanohablantes.

## 1. Alineación Curricular y Calibración Estricta CEFR (MCER)
Todo ejercicio, drill o diálogo debe respetar los estándares oficiales de examen (**Goethe-Zertifikat A1: Start Deutsch 1** para alemán y **Cambridge A1 Key / Oxford 3000** para inglés):

- **A1 (Acceso / Supervivencia Real):**
  - **Límite Léxico:** Máximo ~650 palabras de altísima frecuencia (saludos, comidas/bebidas cotidianas, números del 1 al 10, horas en punto con *Uhr*, días de la semana, familia directa).
  - **Sintaxis:** Oraciones directas cortas (Sujeto + Verbo + Objeto). Prohibido introducir oraciones complejas con declinaciones dativas adjetivales mixtas (ej. *in einem großen Krankenhaus*) o vocabulario técnico/compuesto (*Wörterbuch*, *Baustelle*) en A1; esas pertenecen a A2.
  - **Tiempos:** Presente simple indicativo y modales básicos de cortesía inmediata (*möchte*, *would like*).
- **A2 (Plataforma / Vida Social y Servicios):**
  - Tiempos de pasado: *Perfekt* / *Präteritum* modal en alemán; *Past Simple* regular/irregular en inglés.
  - Horarios con cuartos y medias (*Viertel vor/nach*, *half past*), precios de dos cifras y direcciones en la ciudad.
  - Conectores y subordinación: *weil*, *dass*, *because*, *when*, *if* (First Conditional).
  - Declinaciones clave: Acusativo vs Dativo en alemán; comparativos y superlativos en inglés.
- **B1 (Umbral / Independencia Profesional):**
  - Hipotéticos y cortesía avanzada: *Konjunktiv II* en alemán (*hätte, wäre, würde + Infinitiv*); *Second Conditional* en inglés.
  - Voz pasiva: *Passiv Präsens* (*wird gebaut*) y *Passive Voice* (*was sent*).
  - Oraciones de relativo y estilo indirecto (*Reported Speech*).

## 2. Principio de Krashen ($i + 1$) y Andamiaje Cognitivo (Scaffolding)
- **Carga Cognitiva:** Un alumno A1 se frustra y bloquea si escucha un audio con 3 o más palabras desconocidas ($i + 3$). El 90% de la oración debe actuar como ancla conocida, introduciendo únicamente 1 concepto meta ($i + 1$).
- **Andamiaje Previo Obligatorio en Comprensión Auditiva (👂):**
  - Toda tarjeta de ejercicio auditivo debe mostrar antes del audio un bloque `🔑 Vocabulario de apoyo` con las 2-3 palabras clave y su traducción para reducir la carga de memoria de trabajo.
- **Velocidad de Reproducción Dual:**
  - Los principiantes hispanohablantes no pueden segmentar fonéticamente el habla nativa rápida. El sistema debe ofrecer siempre:
    1. `🔊 Escuchar (1.0x)`: Velocidad nativa estándar.
    2. `🐢 Escuchar Lento (0.8x)`: Velocidad pausada mediante SSML (`prosody rate='-20%'`) para captar terminaciones y fonemas sin distorsión tonal.

## 3. Lingüística Contrastiva (Español L1 ➔ Alemán / Inglés L2)
- Nunca asumir que un sonido es "obvio". Los hispanohablantes no diferencian de forma nativa:
  - Consonante bilabial /b/ de labiodental /v/.
  - Vocales tensas largas (/iː/, /uː/) de relajadas cortas (/ɪ/, /ʊ/).
  - Fricativa palatal sorda /ç/ (*ich*) vs velar /x/ (*ach*).
  - Ensordecimiento de consonantes finales en alemán (*Auslautverhärtung*).
- Todo feedback fonético debe incluir:
  1. La transcripción fonética figurada amigable en español.
  2. La colocación exacta de los órganos articuladores (lengua, dientes, labios, cuerda vocal).
  3. Un *drill* mínimo contrastivo de 2-3 palabras.

## 4. Restricciones de Recursos en el Edge (NVIDIA Jetson Nano)
- **Almacenamiento Flash:** Todos los archivos de audio convertidos (.ogg, .wav) deben ser estrictamente temporales y purgados automáticamente.
- **Consumo de Memoria:** Mantener el proceso principal bajo 512 MB de RAM. No cargar modelos pesados locales si se pueden delegar a APIs en la nube (Azure Speech / Google Gemini).
