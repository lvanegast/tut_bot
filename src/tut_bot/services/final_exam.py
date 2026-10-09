import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExamQuestion:
    id: str
    section: str  # "hoeren" (listening), "lesen" (reading), "grammatik" (grammar), "schreiben" (writing), "sprechen" (speaking)
    section_name_es: str
    prompt_es: str
    context_text: Optional[str] = None  # Texto de lectura o transcripción del audio
    audio_text: Optional[str] = None  # Texto a sintetizar en audio para comprensión auditiva
    question_text: str = ""
    options: List[str] = field(default_factory=list)  # Para preguntas de opción múltiple
    correct_option_index: Optional[int] = None
    target_answer: Optional[str] = None  # Para preguntas abiertas de escritura o pronunciación
    explanation_es: str = ""
    points: int = 1


@dataclass
class LevelExam:
    level: str  # "A1", "A2", "B1"
    language: str  # "de-DE", "en-US"
    title_es: str
    description_es: str
    passing_score_percentage: float  # ej: 75.0
    questions: List[ExamQuestion] = field(default_factory=list)


# =========================================================================
# BANCO DE EXÁMENES OFICIALES DE CERTIFICACIÓN POR NIVEL
# =========================================================================

GERMAN_A1_EXAM = LevelExam(
    level="A1",
    language="de-DE",
    title_es="🇩🇪 Examen Final de Nivel A1 (Start Deutsch 1)",
    description_es="Evaluación integral de las 6 unidades temáticas de A1: Comprensión Auditiva, Lectura, Gramática, Escritura y Expresión Oral.",
    passing_score_percentage=75.0,
    questions=[
        # 1. Hören (Comprensión Auditiva - Restaurante / Precios)
        ExamQuestion(
            id="de_a1_q1_hoeren",
            section="hoeren",
            section_name_es="Comprensión Auditiva (Hören)",
            prompt_es="Escucha el audio del camarero y responde cuánto cuesta la cuenta en total.",
            audio_text="Guten Tag! Ein Kaffee und ein Stück Apfelkuchen. Das macht zusammen fünf Euro fünfzig bitte.",
            question_text="¿Cuánto debe pagar el cliente?",
            options=[
                "4,50 Euro",
                "5,50 Euro",
                "6,00 Euro",
            ],
            correct_option_index=1,
            explanation_es="'Fünf Euro fünfzig' corresponde a 5,50 €.",
            points=1,
        ),
        # 2. Lesen (Comprensión de Lectura - Rutina y Citas)
        ExamQuestion(
            id="de_a1_q2_lesen",
            section="lesen",
            section_name_es="Comprensión de Lectura (Lesen)",
            prompt_es="Lee el siguiente mensaje de texto y responde la pregunta.",
            context_text="Hallo Lucas! Am Samstag habe ich keine Zeit, aber am Sonntag um 15:00 Uhr können wir uns im Café Schmidt treffen. Passt das dir? Liebe Grüße, Anna.",
            question_text="¿Cuándo y a qué hora propone Anna encontrarse?",
            options=[
                "El sábado a las 15:00 en casa de Lucas",
                "El domingo a las 15:00 en el Café Schmidt",
                "El domingo a las 14:00 en la estación",
            ],
            correct_option_index=1,
            explanation_es="Anna dice claramente: 'am Sonntag um 15:00 Uhr können wir uns im Café Schmidt treffen'.",
            points=1,
        ),
        # 3. Grammatik (Estructura y Verbos Modales)
        ExamQuestion(
            id="de_a1_q3_grammatik",
            section="grammatik",
            section_name_es="Gramática y Estructura (Grammatik)",
            prompt_es="Selecciona la forma verbal correcta para completar la oración.",
            question_text="Entschuldigung, _____ Sie mir bitte helfen? Wo ist der Bahnhof?",
            options=[
                "kannst",
                "können",
                "könnt",
            ],
            correct_option_index=1,
            explanation_es="Con el pronombre formal de cortesía 'Sie' se utiliza la forma plural/formal 'können'.",
            points=1,
        ),
        # 4. Wortschatz (Vocabulario Situacional - Ciudad y Transporte)
        ExamQuestion(
            id="de_a1_q4_wortschatz",
            section="wortschatz",
            section_name_es="Vocabulario Situacional (Wortschatz)",
            prompt_es="¿Qué palabra completa mejor la indicación de dirección?",
            question_text="Gehen Sie an der Ampel nach _____ und dann geradeaus.",
            options=[
                "rechts",
                "brot",
                "morgen",
            ],
            correct_option_index=0,
            explanation_es="'nach rechts' (a la derecha) o 'nach links' son las direcciones estándar en la ciudad.",
            points=1,
        ),
        # 5. Schreiben (Expresión Escrita - Presentación Personal)
        ExamQuestion(
            id="de_a1_q5_schreiben",
            section="schreiben",
            section_name_es="Expresión Escrita (Schreiben)",
            prompt_es="Escribe en alemán la siguiente frase completa de cortesía: 'Quisiera un vaso de agua, por favor.'",
            target_answer="Ich möchte ein Glas Wasser, bitte.",
            explanation_es="Se usa la estructura de cortesía 'Ich möchte ein Glas Wasser, bitte.'",
            points=1,
        ),
        # 6. Sprechen (Expresión Oral - Fonética y Fluidez)
        ExamQuestion(
            id="de_a1_q6_sprechen",
            section="sprechen",
            section_name_es="Expresión Oral (Sprechen)",
            prompt_es="Graba una nota de voz pronunciando con claridad esta frase habitual:",
            target_answer="Ich heiße Lucas und ich lerne Deutsch.",
            audio_text="Ich heiße Lucas und ich lerne Deutsch.",
            explanation_es="Enfócate en articular /ç/ suave en 'Ich' y las vocales claras en 'Deutsch'.",
            points=1,
        ),
    ],
)

ENGLISH_A1_EXAM = LevelExam(
    level="A1",
    language="en-US",
    title_es="🇺🇸 Examen Final de Nivel A1 (Cambridge A1 Key)",
    description_es="Evaluación integral de las 6 unidades temáticas de A1: Listening, Reading, Grammar, Writing y Speaking.",
    passing_score_percentage=75.0,
    questions=[
        # 1. Listening (Comprensión Auditiva)
        ExamQuestion(
            id="en_a1_q1_hoeren",
            section="hoeren",
            section_name_es="Listening Comprehension",
            prompt_es="Listen to the announcement and select what time the train departs.",
            audio_text="Attention passengers: The train to Oxford will depart from platform four at three fifteen PM.",
            question_text="At what time does the train to Oxford leave?",
            options=[
                "At 3:15 PM from platform 4",
                "At 3:50 PM from platform 2",
                "At 4:15 PM from platform 3",
            ],
            correct_option_index=0,
            explanation_es="'three fifteen PM' is 3:15 PM from platform 4.",
            points=1,
        ),
        # 2. Reading (Comprensión de Lectura)
        ExamQuestion(
            id="en_a1_q2_lesen",
            section="lesen",
            section_name_es="Reading Comprehension",
            prompt_es="Read the short message and answer the question.",
            context_text="Hi Sarah! I am at the supermarket right now. We have bread and milk, but we need some cheese and apples. See you at home! Oliver.",
            question_text="What does Oliver need to buy?",
            options=[
                "Bread and milk",
                "Cheese and apples",
                "Coffee and tea",
            ],
            correct_option_index=1,
            explanation_es="Oliver says: 'we need some cheese and apples'.",
            points=1,
        ),
        # 3. Grammar (Gramática)
        ExamQuestion(
            id="en_a1_q3_grammatik",
            section="grammatik",
            section_name_es="Grammar & Structure",
            prompt_es="Choose the correct verb form to complete the sentence.",
            question_text="My brother _____ in London and works as an engineer.",
            options=[
                "live",
                "lives",
                "living",
            ],
            correct_option_index=1,
            explanation_es="Third-person singular in present simple takes '-s': 'My brother lives'.",
            points=1,
        ),
        # 4. Vocabulary (Vocabulario)
        ExamQuestion(
            id="en_a1_q4_wortschatz",
            section="wortschatz",
            section_name_es="Situational Vocabulary",
            prompt_es="Complete the sentence with the correct polite request phrase.",
            question_text="Excuse me, _____ I have the bill, please?",
            options=[
                "could",
                "must",
                "am",
            ],
            correct_option_index=0,
            explanation_es="'Could I have the bill, please?' is the standard polite request in restaurants.",
            points=1,
        ),
        # 5. Writing (Escritura)
        ExamQuestion(
            id="en_a1_q5_schreiben",
            section="schreiben",
            section_name_es="Written Expression",
            prompt_es="Write in English: 'Me gustaría una taza de café, por favor.'",
            target_answer="I would like a cup of coffee, please.",
            explanation_es="Standard polite structure: 'I would like a cup of coffee, please.'",
            points=1,
        ),
        # 6. Speaking (Expresión Oral)
        ExamQuestion(
            id="en_a1_q6_sprechen",
            section="sprechen",
            section_name_es="Speaking Expression",
            prompt_es="Record a voice note pronouncing this common sentence:",
            target_answer="Nice to meet you, I am from Spain.",
            audio_text="Nice to meet you, I am from Spain.",
            explanation_es="Focus on clear vowels and smooth intonation.",
            points=1,
        ),
    ],
)

# Exámenes de nivel A2 y B1 preparados para continuidad curricular
GERMAN_A2_EXAM = LevelExam(
    level="A2",
    language="de-DE",
    title_es="🇩🇪 Examen Final de Nivel A2 (Goethe-Zertifikat A2)",
    description_es="Evaluación de pasado (Perfekt), subordinadas con 'weil' y declinación dativa.",
    passing_score_percentage=75.0,
    questions=[
        ExamQuestion(
            id="de_a2_q1_grammatik",
            section="grammatik",
            section_name_es="Gramática - Pasado Perfekt",
            prompt_es="Selecciona la forma correcta del participio pasado.",
            question_text="Gestern habe ich einen interessanten Film _____.",
            options=["gesehen", "sehen", "geseht"],
            correct_option_index=0,
            explanation_es="El participio de 'sehen' es irregular: 'gesehen'.",
            points=1,
        ),
        ExamQuestion(
            id="de_a2_q2_grammatik",
            section="grammatik",
            section_name_es="Conectores Subordinados",
            prompt_es="Elige la oración con el orden correcto usando 'weil':",
            question_text="Ich lerne Deutsch, weil _____.",
            options=[
                "ich in Deutschland arbeiten möchte",
                "ich möchte in Deutschland arbeiten",
                "möchte ich in Deutschland arbeiten",
            ],
            correct_option_index=0,
            explanation_es="La conjunción 'weil' envía el verbo conjugado al final de la oración.",
            points=1,
        ),
        ExamQuestion(
            id="de_a2_q3_schreiben",
            section="schreiben",
            section_name_es="Escritura - Preposiciones de Dativo",
            prompt_es="Escribe en alemán: 'Voy a la estación en autobús.'",
            target_answer="Ich fahre mit dem Bus zum Bahnhof.",
            explanation_es="'mit' rige dativo ('mit dem Bus').",
            points=1,
        ),
        ExamQuestion(
            id="de_a2_q4_sprechen",
            section="sprechen",
            section_name_es="Expresión Oral - Relato en Pasado",
            prompt_es="Pronuncia con entonación natural:",
            target_answer="Letzte Woche bin ich nach Berlin gefahren.",
            audio_text="Letzte Woche bin ich nach Berlin gefahren.",
            explanation_es="Observa el auxiliar 'sein' ('bin gefahren') para verbos de movimiento.",
            points=1,
        ),
    ],
)

ENGLISH_A2_EXAM = LevelExam(
    level="A2",
    language="en-US",
    title_es="🇺🇸 Examen Final de Nivel A2 (Cambridge A2 Key)",
    description_es="Evaluación de Past Simple, comparativos y conectores causales.",
    passing_score_percentage=75.0,
    questions=[
        ExamQuestion(
            id="en_a2_q1_grammatik",
            section="grammatik",
            section_name_es="Grammar - Past Simple",
            prompt_es="Choose the correct past form of the irregular verb:",
            question_text="Yesterday, we _____ to a wonderful restaurant in London.",
            options=["went", "goed", "gone"],
            correct_option_index=0,
            explanation_es="The past simple of 'go' is 'went'.",
            points=1,
        ),
        ExamQuestion(
            id="en_a2_q2_grammatik",
            section="grammatik",
            section_name_es="Comparatives",
            prompt_es="Select the correct comparative adjective:",
            question_text="The train is usually _____ than the bus.",
            options=["faster", "more fast", "fastest"],
            correct_option_index=0,
            explanation_es="Short adjectives form comparatives with '-er': 'faster than'.",
            points=1,
        ),
        ExamQuestion(
            id="en_a2_q3_schreiben",
            section="schreiben",
            section_name_es="Writing - Future Plans",
            prompt_es="Write in English: 'Voy a visitar a mis amigos mañana.'",
            target_answer="I am going to visit my friends tomorrow.",
            explanation_es="Use 'going to' for intended future plans.",
            points=1,
        ),
        ExamQuestion(
            id="en_a2_q4_sprechen",
            section="sprechen",
            section_name_es="Speaking - Past Experience",
            prompt_es="Say clearly:",
            target_answer="I had a great time with my family yesterday.",
            audio_text="I had a great time with my family yesterday.",
            explanation_es="Practice smooth connected speech and clear past endings.",
            points=1,
        ),
    ],
)


def get_level_exam(language: str, level: str) -> Optional[LevelExam]:
    """Recupera el examen oficial de certificación para el idioma y nivel solicitados."""
    norm_lang = "de-DE" if language.startswith("de") else "en-US"
    norm_level = level.upper()

    if norm_lang == "de-DE":
        if norm_level == "A1":
            return GERMAN_A1_EXAM
        elif norm_level == "A2":
            return GERMAN_A2_EXAM
    else:
        if norm_level == "A1":
            return ENGLISH_A1_EXAM
        elif norm_level == "A2":
            return ENGLISH_A2_EXAM

    return None
