---
name: language-curriculum-coach
description: Expert methodology for designing language learning curricula, generating CEFR-aligned exercises (speaking, writing, listening), articulatory phonetic coaching, and engineering conversational roleplay scenarios for tut_bot.
---

# Skill: Language Curriculum Coach (Tutor de Idiomas)

Esta skill proporciona los flujos de trabajo, plantillas pedagógicas y mejores prácticas para expandir y operar el tutor inteligente `tut_bot`, inspirada en plataformas abiertas de referencia como **FreeLingo**, **Language-Loop**, **LibreLingo** y el algoritmo **FSRS** (Spaced Repetition).

---

## 1. Arquitectura de un Ejercicio de Aprendizaje

Cada ejercicio dentro del sistema debe satisfacer la siguiente estructura de datos en Python (`tut_bot.models.schemas.Exercise`):

```python
Exercise(
    id="<lang>-<skill>-<num>",  # ej: de-write-15, en-listen-12, de-speak-18
    language="de-DE",  # o en-US
    category="Tema Gramatical o Situacional",
    level="A1",  # A1, A2, B1
    skill_type="writing",  # "speaking" | "writing" | "listening"
    title="Título descriptivo del objetivo",
    prompt="Instrucción pedagógica directa para el alumno",
    target_text="Frase nativa esperada o transcripción del audio",
    translation_es="Traducción fidedigna al español",
    tip="Consejo metodológico o nemotécnico",
    options=["Opción A", "Opción B", "Opción C"],  # Para comprensión auditiva
    correct_option_index=1,  # Índice 0-based de la opción correcta
    vocabulary_breakdown={  # Desglose de términos para popup inmediato
        "palabra_meta": "significado, género gramatical y notas"
    },
    grammar_note="Regla gramatical fundamental explicada sin jerga excesiva",
    focus_phonemes=["ç", "yː"],  # Solo para speaking: fonemas evaluados
    articulation_type="palatal",  # palatal, alveolar, dental, vowel, etc.
)
```

---

## 2. Flujo de Trabajo para Generación Dinámica de Ejercicios con IA

Cuando un usuario agota los ejercicios estáticos de un nivel o solicita práctica infinita, utiliza el siguiente prompt estructurado con Gemini (`gemini-flash-lite-latest` o `gemini-flash-latest`):

```text
Eres un diseñador curricular experto en {idioma} para hispanohablantes (Nivel {nivel}, Modalidad {modalidad}).
Genera 1 ejercicio pedagógico novedoso adaptado a las dificultades de un hispanohablante.
Responde ÚNICAMENTE en JSON con los campos:
{
  "category": "...",
  "title": "...",
  "prompt": "...",
  "target_text": "...",
  "translation_es": "...",
  "tip": "...",
  "vocabulary_breakdown": {"término": "significado y género"},
  "grammar_note": "...",
  "options": ["A", "B", "C"],
  "correct_option_index": 0
}
```

---

## 3. Matriz de Fonética Contrastiva (Español ➔ Alemán / Inglés)

| Sonido Meta | Dificultad para el Hispanohablante | Cómo Explicar la Articulación Bucal |
| :--- | :--- | :--- |
| **Alemán: /ç/ (*ich-Laut*)** | Se tiende a pronunciar como /x/ (*jota* española fuerte) | "Sonríe, pega la lengua contra los lados de las muelas superiores y susurra aire frío hacia afuera como un gato enojado." |
| **Alemán: /yː/ (*ü* larga)** | Se suele sustituir por /i/ o por /u/ | "Coloca los labios redondos y tensos como si fueras a dar un beso (posición de 'u'), pero sin mover los labios, intenta pronunciar la vocal 'i'." |
| **Inglés: /θ/ (*think*)** | Se sustituye habitualmente por /s/ o por /t/ | "Asoma levemente la punta de la lengua entre tus dientes incisivos superiores e inferiores. Sopla aire suavemente sin vibrar la garganta." |
| **Inglés: /v/ (*van*)** | El español neutraliza B y V en un sonido bilabial | "Apoya firmemente los dientes superiores sobre tu labio inferior. Haz vibrar la garganta y deja escapar un zumbido continuo." |
| **Inglés: /ɪ/ vs /iː/** | El español solo tiene una 'i' | "En *ship*, la mandíbula baja un milímetro y la boca se relaja. En *sheep*, la boca sonríe ampliamente con tensión muscular." |

---

## 4. Modo Conversación con Rol (Roleplay Inmersivo y Amigable)

Inspirado en la síntesis de **FreeLingo**, **Large-Language-Tutor**, **SpeakGenie** y **Conversationally**, el modo conversación se estructura bajo los siguientes pilares de diseño:

1. **Escenarios Situacionales A1/A2:**
   - ☕ *En la panadería/cafetería:* Pedir café y panecillos, pagar en efectivo o con tarjeta.
   - 🚆 *En la estación de tren:* Consultar andenes, direcciones y horarios de salida.
   - 🏨 *En la recepción del curso / hotel:* Presentarse, indicar origen y deletrear nombre.
   - 🩺 *En la farmacia / consulta:* Describir un malestar cotidiano y pedir recomendación.
2. **Ciclo de Turno con *Recasting* y Baja Presión (`team-langbot/conversationally` + `artcc/freelingo`):**
   - El bot responde como un compañero de charla entusiasta y empático.
   - Si el alumno comete un error, el personaje modela la forma correcta dentro de su réplica sin interrumpir ni regañar.
   - Envío de audio nativo (TTS normal y 0.8x lento) + texto con traducción oculta en `<tg-spoiler>`.
3. **Andamiaje Dinámico (*Smart Scaffolding*, `CipherCraze/SpeakGenie-AI-Tutor`):**
   - Cada turno provee `suggested_replies` (2-3 ideas de respuesta rápida).
   - El alumno puede pulsar `💡 ¿Qué puedo responder?` para recibir un diálogo emergente inmediato que disipa bloqueos.
4. **Desacoplamiento de Roles (`vertexais/large-language-tutor`):**
   - El personaje nunca abandona su papel para calificar o regañar. La evaluación formal queda diferida al debriefing final (`/finalizar` o cumplimiento de objetivo) con fortalezas y consejos constructivos.
