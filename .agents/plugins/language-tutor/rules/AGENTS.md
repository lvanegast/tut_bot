# Reglas Pedagógicas y Técnicas del Tutor de Idiomas (tut_bot)

Este conjunto de reglas rige el desarrollo pedagógico, la expansión curricular y la arquitectura del tutor inteligente para el aprendizaje de Alemán e Inglés en hispanohablantes.

## 1. Alineación Curricular CEFR (MCER)
Todo ejercicio, drill o diálogo debe respetar la progresión formal del Marco Común Europeo de Referencia:
- **A1 (Acceso / Supervivencia):**
  - Oraciones simples (Sujeto + Verbo + Objeto).
  - Tiempos: Presente indicativo y modales básicos de cortesía (möchte, would like).
  - Vocabulario de alta frecuencia: Saludos, familia, compras, números, días de la semana, direcciones inmediatas.
- **A2 (Plataforma):**
  - Tiempos de pasado: Perfekt / Präteritum modal en alemán; Past Simple regular/irregular en inglés.
  - Conectores y subordinación básica: *weil*, *dass*, *because*, *when*, *if* (First Conditional).
  - Declinaciones clave: Acusativo vs Dativo en alemán; Comparativos y superlativos en inglés.
- **B1 (Umbral / Independencia):**
  - Hipotéticos y cortesía avanzada: Konjunktiv II en alemán (*hätte, wäre, würde + Infinitiv*); Second Conditional en inglés.
  - Voz pasiva: *Passiv Präsens* (*wird gebaut*) y Passive Voice (*was sent*).
  - Oraciones de relativo y estilo indirecto (*Reported Speech*).

## 2. Lingüística Contrastiva (Español L1 ➔ Alemán / Inglés L2)
- Nunca asumir que un sonido es "obvio". Los hispanohablantes no diferencian de forma nativa:
  - Consonante bilabial /b/ de labiodental /v/.
  - Vocales tensas largas (/iː/, /uː/) de relajadas cortas (/ɪ/, /ʊ/).
  - Fricativa palatal sorda /ç/ (*ich*) vs velar /x/ (*ach*).
  - Ensordecimiento de consonantes finales en alemán (*Auslautverhärtung*).
- Todo feedback fonético debe incluir:
  1. La transcripción fonética figurada amigable en español.
  2. La colocación exacta de los órganos articuladores (lengua, dientes, labios, cuerda vocal).
  3. Un *drill* mínimo contrastivo de 2-3 palabras.

## 3. Principios de Interacción Multimodal
- **Escritura (✍️):** Evaluar concordancia de género (der/die/das), mayúsculas obligatorias en sustantivos alemanes, y posición del verbo (V2 en cláusulas principales, verbo al final en subordinadas con *weil*).
- **Comprensión Auditiva (👂):** Plantear situaciones auditivas realistas (anuncios en aeropuertos/estaciones, llamadas de consulta médica, diálogo en restaurantes). Generar audio con Azure Speech TTS nativo.
- **Pronunciación (🗣️):** Usar Azure Pronunciation Assessment y desglose fonémico.

## 4. Restricciones de Recursos en el Edge (NVIDIA Jetson Nano)
- **Almacenamiento Flash:** Todos los archivos de audio convertidos (.ogg, .wav) deben ser estrictamente temporales y purgados automáticamente.
- **Consumo de Memoria:** Mantener el proceso principal bajo 512 MB de RAM. No cargar modelos pesados locales si se pueden delegar a APIs en la nube (Azure Speech / Google Gemini).
