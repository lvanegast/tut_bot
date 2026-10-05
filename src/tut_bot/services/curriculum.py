import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class UnitInfo:
    id: str
    number: int
    level: str
    language: str
    icon: str
    title: str
    title_es: str
    description_es: str
    target_words: List[str] = field(default_factory=list)


# =========================================================================
# 1. CURRÍCULO OFICIAL ALEMÁN A1 (GOETHE-ZERTIFIKAT A1: START DEUTSCH 1)
# 6 Unidades Temáticas con el inventario oficial de ~650 palabras clave
# =========================================================================

GERMAN_A1_UNITS: List[UnitInfo] = [
    UnitInfo(
        id="unit_1",
        number=1,
        level="A1",
        language="de-DE",
        icon="👋",
        title="Begrüßung, Alphabet & Herkunft",
        title_es="Saludos, Presentaciones y Alfabeto",
        description_es="Saludar formal e informalmente, deletrear el nombre, países de origen, idiomas y números del 0 al 20.",
        target_words=[
            "hallo", "guten", "morgen", "tag", "abend", "nacht", "tschüss", "auf wiedersehen",
            "bitte", "danke", "sehr", "vielen", "entschuldigung", "tut mir leid", "ja", "nein",
            "wie", "wer", "was", "woher", "wo", "wohin", "heißen", "sein", "kommen", "wohnen",
            "sprechen", "lernen", "verstehen", "buchstabieren", "name", "vorname", "nachname",
            "herr", "frau", "kollege", "deutsch", "spanisch", "englisch", "frankreich", "deutschland",
            "spanien", "österreich", "schweiz", "sprache", "land", "stadt", "alphabet", "buchstabe",
            "wort", "satz", "frage", "antwort", "null", "eins", "zwei", "drei", "vier", "fünf",
            "sechs", "sieben", "acht", "neun", "zehn", "elf", "zwölf", "dreizehn", "vierzehn",
            "fünfzehn", "sechzehn", "siebzehn", "achtzehn", "neunzehn", "zwanzig", "telefonnummer",
            "adresse", "e-mail", "formular", "ausfüllen", "unterschreiben", "pass", "ausweis",
            "visitenkarte", "neu", "alt", "gut", "schlecht", "richtig", "falsch", "noch einmal",
            "langsam", "laut", "leise", "hier", "da", "dort", "auch", "nicht", "nur", "ein bisschen",
        ],
    ),
    UnitInfo(
        id="unit_2",
        number=2,
        level="A1",
        language="de-DE",
        icon="☕",
        title="Essen, Trinken & Einkaufen",
        title_es="Comidas, Bebidas, Precios y Restaurante",
        description_es="Pedir en el restaurante, comprar comida en el supermercado, preguntar precios y cantidades.",
        target_words=[
            "essen", "trinken", "kaufen", "verkaufen", "bestellen", "bezahlen", "kosten", "schmecken",
            "möchten", "nehmen", "brauchen", "kochen", "frühstücken", "hunger", "durst", "kaffee",
            "tee", "wasser", "mineralwasser", "saft", "apfelsaft", "orangensaft", "milch", "bier",
            "wein", "cola", "brot", "brötchen", "käse", "wurst", "schinken", "fleisch", "fisch",
            "hähnchen", "ei", "butter", "zucker", "salz", "pfeffer", "öl", "essig", "reis",
            "nudeln", "kartoffel", "pommes", "salat", "gemüse", "obst", "apfel", "banane", "orange",
            "zitrone", "tomate", "gurke", "zwiebel", "suppe", "kuchen", "schokolade", "eis",
            "speisekarte", "rechnung", "kellner", "gast", "restaurante", "café", "bäckerei",
            "supermarkt", "markt", "geschäft", "laden", "euro", "cent", "preis", "angebot", "prospekt",
            "teuer", "billig", "günstig", "frisch", "lecker", "süß", "sauer", "heiß", "kalt",
            "flasche", "glas", "tasse", "dose", "packung", "stück", "kilo", "gramm", "liter",
            "bar", "karte", "zusammen", "getrennt", "stimmt so", "guten appetit", "prost", "zum wohl",
        ],
    ),
    UnitInfo(
        id="unit_3",
        number=3,
        level="A1",
        language="de-DE",
        icon="👨‍👩‍👧",
        title="Familie, Freunde & Beziehungen",
        title_es="Familia, Amigos, Edad y Personas",
        description_es="Describir a los miembros de la familia, decir la edad, estado civil y profesiones cotidianas.",
        target_words=[
            "familie", "eltern", "mutter", "vater", "mama", "papa", "sohn", "tochter", "kind",
            "kinder", "bruder", "schwester", "geschwister", "großeltern", "großmutter", "großvater",
            "oma", "opa", "enkel", "enkelin", "onkel", "tante", "cousin", "cousine", "mann",
            "ehemann", "frau", "ehefrau", "freund", "freundin", "partner", "partnerin", "baby",
            "jugendliche", "erwachsene", "mensch", "leute", "person", "alter", "geburtstag", "jahr",
            "monat", "leben", "lieben", "heiraten", "haben", "ledig", "verheiratet", "geschieden",
            "zusammen", "allein", "beruf", "arbeit", "arbeiten", "arbeitsplatz", "student", "studentin",
            "schüler", "schülerin", "lehrer", "lehrerin", "arzt", "ärztin", "krankenschwester",
            "polizist", "verkäufer", "kellner", "koch", "ingenieur", "informatiker", "sekretär",
            "arbeitslos", "in rente", "klein", "groß", "dick", "dünn", "schön", "hübsch", "jung",
            "alt", "sympathisch", "nett", "freundlich", "lustig", "ruhig", "glücklich", "traurig",
        ],
    ),
    UnitInfo(
        id="unit_4",
        number=4,
        level="A1",
        language="de-DE",
        icon="⏰",
        title="Alltag, Uhrzeit & Wohnen",
        title_es="Rutina Diaria, Horas, Citas y Vivienda",
        description_es="Preguntar y decir la hora, partes del día, días de la semana, agendar citas y describir la casa.",
        target_words=[
            "uhr", "uhrzeit", "stunde", "minute", "sekunde", "halb", "viertel", "vor", "nach",
            "spät", "früh", "pünktlich", "zeit", "keine zeit", "termin", "vereinbaren", "verschieben",
            "absagen", "kalender", "heute", "gestern", "morgen", "übermorgen", "tag", "woche",
            "wochenende", "montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag",
            "vormittag", "mittag", "nachmittag", "abend", "nacht", "aufstehen", "aufwachen", "duschen",
            "waschen", "anziehen", "ausziehen", "frühstücken", "zur arbeit gehen", "nach hause gehen",
            "fernsehen", "schlafen", "anrufen", "einkaufen", "kochen", "wohnung", "haus", "zimmer",
            "wohnzimmer", "schlafzimmer", "kinderzimmer", "küche", "bad", "badezimmer", "flur",
            "balkon", "garten", "keller", "garage", "tür", "fenster", "wand", "boden", "möbel",
            "tisch", "stuhl", "sofa", "bett", "schrank", "regal", "lampe", "teppich", "fernseher",
            "kühlschrank", "herd", "waschmaschine", "miete", "kaution", "nebenkosten", "hell",
            "dunkel", "groß", "klein", "gemütlich", "modern", "bequem", "sauber", "schmutzig",
        ],
    ),
    UnitInfo(
        id="unit_5",
        number=5,
        level="A1",
        language="de-DE",
        icon="🚆",
        title="Stadt, Verkehr & Orientierung",
        title_es="Ciudad, Transporte, Direcciones y Viajes",
        description_es="Orientarse en la ciudad, pedir indicaciones, usar medios de transporte y comprar billetes de viaje.",
        target_words=[
            "stadt", "zentrum", "stadtmitte", "dorf", "straße", "platz", "weg", "kreuzung", "ampel",
            "ecke", "brücke", "park", "post", "bank", "apotheke", "krankenhaus", "polizei", "kirche",
            "museum", "kino", "theater", "schule", "universität", "rathaus", "hotel", "restaurant",
            "bahnhof", "hauptbahnhof", "flughafen", "haltestelle", "gleis", "bahnsteig", "zug",
            "s-bahn", "u-bahn", "straßenbahn", "bus", "taxi", "auto", "fahrrad", "flugzeug", "schiff",
            "fahren", "abfahren", "ankommen", "umsteigen", "einsteigen", "aussteigen", "fliegen",
            "gehen", "zu fuß", "abfahrt", "ankunft", "verspätung", "fahrplan", "fahrkarte", "ticket",
            "einfach", "hin und zurück", "automat", "schalter", "information", "koffer", "tasche",
            "gepäck", "reisen", "urlaub", "ausflug", "wo", "wohin", "woher", "links", "rechts",
            "geradeaus", "in der nähe", "weit", "neben", "vor", "hinter", "zwischen", "an", "auf",
            "in", "unter", "über", "suchen", "finden", "zeigen", "entschuldigung", "wie komme ich zu",
        ],
    ),
    UnitInfo(
        id="unit_6",
        number=6,
        level="A1",
        language="de-DE",
        icon="🩺",
        title="Gesundheit, Wetter & Freizeit",
        title_es="Salud Básica, Clima, Actividades y Ocio",
        description_es="Explicar síntomas simples al médico, hablar del clima, estaciones del año y pasatiempos favoritos.",
        target_words=[
            "gesundheit", "krank", "gesund", "schmerz", "kopfschmerzen", "bauchschmerzen", "halsschmerzen",
            "fieber", "husten", "schnupfen", "grippe", "erkältung", "arzt", "ärztin", "praxis",
            "termin", "apotheke", "medikament", "tablette", "tropfen", "rezept", "pflaster", "bett",
            "ausruhen", "fehlen", "weh tun", "kopf", "auge", "ohr", "nase", "mund", "zahn", "hals",
            "arm", "hand", "finger", "bauch", "rücken", "bein", "fuß", "knie", "wetter", "sonne",
            "regen", "schnee", "wind", "wolke", "nebel", "grad", "temperatur", "warm", "heiß",
            "kalt", "kühles", "sonnig", "regnerisch", "windig", "bewölkt", "frühling", "sommer",
            "herbst", "winter", "freizeit", "hobby", "sport", "fußball", "tennis", "schwimmen",
            "laufen", "joggen", "wandern", "fahrrad fahren", "lesen", "buch", "zeitung", "musik",
            "hören", "singen", "tanzen", "spielen", "computerspiel", "kino", "film", "freunde treffen",
            "fotografieren", "reisen", "kochen", "spaß", "gern", "lieber", "am liebsten", "toll",
            "super", "langweilig", "interessant", "anfangen", "aufhören", "mitmachen", "einladen",
        ],
    ),
]


# =========================================================================
# 2. CURRÍCULO OFICIAL INGLÉS A1 (CAMBRIDGE A1 KEY / OXFORD 3000 A1)
# 6 Unidades Temáticas con el inventario oficial de ~650 palabras clave
# =========================================================================

ENGLISH_A1_UNITS: List[UnitInfo] = [
    UnitInfo(
        id="unit_1",
        number=1,
        level="A1",
        language="en-US",
        icon="👋",
        title="Greetings, Alphabet & Introductions",
        title_es="Saludos, Presentaciones y Alfabeto",
        description_es="Saludar, despedirse, deletrear nombres, países de origen, nacionalidades y números del 0 al 20.",
        target_words=[
            "hello", "hi", "good", "morning", "afternoon", "evening", "night", "goodbye", "bye",
            "please", "thank you", "thanks", "welcome", "sorry", "excuse me", "yes", "no", "how",
            "who", "what", "where", "from", "be", "am", "is", "are", "call", "live", "speak",
            "learn", "understand", "spell", "name", "first name", "surname", "mr", "mrs", "miss",
            "english", "spanish", "american", "britain", "spain", "mexico", "country", "city",
            "language", "alphabet", "letter", "word", "sentence", "question", "answer", "zero",
            "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
            "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
            "nineteen", "twenty", "phone", "number", "address", "email", "passport", "id", "card",
            "new", "old", "good", "bad", "right", "wrong", "again", "slowly", "loud", "quiet",
            "here", "there", "also", "too", "not", "only", "a little",
        ],
    ),
    UnitInfo(
        id="unit_2",
        number=2,
        level="A1",
        language="en-US",
        icon="☕",
        title="Food, Drinks & Shopping",
        title_es="Comidas, Bebidas, Precios y Restaurante",
        description_es="Pedir en cafeterías y restaurantes, comprar comida en el supermercado y preguntar precios.",
        target_words=[
            "eat", "drink", "buy", "sell", "order", "pay", "cost", "taste", "would like", "want",
            "need", "cook", "breakfast", "lunch", "dinner", "hungry", "thirsty", "coffee", "tea",
            "water", "mineral water", "juice", "orange juice", "apple juice", "milk", "beer", "wine",
            "coke", "bread", "toast", "cheese", "ham", "meat", "fish", "chicken", "egg", "butter",
            "sugar", "salt", "pepper", "oil", "rice", "pasta", "potato", "chips", "fries", "salad",
            "vegetable", "fruit", "apple", "banana", "orange", "lemon", "tomato", "soup", "cake",
            "chocolate", "ice cream", "menu", "bill", "waiter", "waitress", "guest", "restaurant",
            "cafe", "bakery", "supermarket", "market", "shop", "store", "dollar", "cent", "price",
            "cheap", "expensive", "fresh", "delicious", "sweet", "hot", "cold", "bottle", "glass",
            "cup", "box", "can", "piece", "kilo", "liter", "cash", "credit card", "together",
            "separate", "keep the change", "enjoy your meal", "cheers",
        ],
    ),
    UnitInfo(
        id="unit_3",
        number=3,
        level="A1",
        language="en-US",
        icon="👨‍👩‍👧",
        title="Family, Friends & People",
        title_es="Familia, Amigos, Edad y Personas",
        description_es="Describir a la familia, edad, estado civil y profesiones cotidianas.",
        target_words=[
            "family", "parents", "mother", "father", "mom", "dad", "son", "daughter", "child",
            "children", "brother", "sister", "grandparents", "grandmother", "grandfather", "grandma",
            "grandpa", "uncle", "aunt", "cousin", "husband", "wife", "friend", "boyfriend",
            "girlfriend", "partner", "baby", "teenager", "adult", "person", "people", "age",
            "birthday", "year", "month", "live", "love", "marry", "have", "single", "married",
            "divorced", "together", "alone", "job", "work", "workplace", "student", "pupil",
            "teacher", "doctor", "nurse", "police", "clerk", "waiter", "chef", "cook", "engineer",
            "programmer", "secretary", "unemployed", "retired", "small", "tall", "short", "fat",
            "thin", "pretty", "handsome", "young", "old", "nice", "friendly", "funny", "quiet",
            "happy", "sad",
        ],
    ),
    UnitInfo(
        id="unit_4",
        number=4,
        level="A1",
        language="en-US",
        icon="⏰",
        title="Daily Routine, Time & Home",
        title_es="Rutina Diaria, Horas, Citas y Casa",
        description_es="Preguntar y decir la hora, partes del día, días de la semana y partes de la casa.",
        target_words=[
            "time", "o'clock", "hour", "minute", "second", "half", "quarter", "past", "to", "early",
            "late", "on time", "appointment", "schedule", "calendar", "today", "yesterday", "tomorrow",
            "day", "week", "weekend", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
            "sunday", "morning", "noon", "afternoon", "evening", "night", "wake up", "get up", "shower",
            "wash", "dress", "eat breakfast", "go to work", "go home", "watch tv", "sleep", "call",
            "shop", "cook", "flat", "apartment", "house", "room", "living room", "bedroom", "kitchen",
            "bathroom", "hall", "balcony", "garden", "garage", "door", "window", "wall", "floor",
            "furniture", "table", "chair", "sofa", "bed", "wardrobe", "shelf", "lamp", "carpet",
            "tv", "fridge", "stove", "washing machine", "rent", "bright", "dark", "big", "small",
            "comfortable", "clean", "dirty",
        ],
    ),
    UnitInfo(
        id="unit_5",
        number=5,
        level="A1",
        language="en-US",
        icon="🚆",
        title="City, Transport & Directions",
        title_es="Ciudad, Transporte, Direcciones y Viajes",
        description_es="Pedir direcciones en la ciudad, usar transporte público y comprar billetes de viaje.",
        target_words=[
            "city", "town", "center", "downtown", "street", "road", "square", "way", "corner",
            "bridge", "park", "post office", "bank", "pharmacy", "hospital", "police station",
            "church", "museum", "cinema", "theatre", "school", "university", "hotel", "station",
            "airport", "bus stop", "platform", "train", "underground", "subway", "tram", "bus",
            "taxi", "car", "bicycle", "bike", "plane", "airplane", "ship", "boat", "drive", "ride",
            "leave", "arrive", "change", "get on", "get off", "fly", "walk", "on foot", "departure",
            "arrival", "delay", "timetable", "ticket", "single", "return", "round trip", "machine",
            "luggage", "suitcase", "bag", "travel", "holiday", "vacation", "trip", "where", "left",
            "right", "straight on", "near", "far", "next to", "in front of", "behind", "between",
            "under", "over", "look for", "find", "show", "how do i get to",
        ],
    ),
    UnitInfo(
        id="unit_6",
        number=6,
        level="A1",
        language="en-US",
        icon="🩺",
        title="Health, Weather & Free Time",
        title_es="Salud Básica, Clima y Ocio",
        description_es="Explicar malestares simples al doctor, hablar del tiempo, estaciones y actividades de ocio.",
        target_words=[
            "health", "sick", "ill", "healthy", "pain", "headache", "stomachache", "fever", "cough",
            "cold", "flu", "doctor", "hospital", "pharmacy", "medicine", "pill", "rest", "head",
            "eye", "ear", "nose", "mouth", "tooth", "teeth", "throat", "arm", "hand", "finger",
            "stomach", "back", "leg", "foot", "feet", "knee", "weather", "sun", "rain", "snow",
            "wind", "cloud", "fog", "degree", "temperature", "warm", "hot", "cold", "sunny", "rainy",
            "windy", "cloudy", "spring", "summer", "autumn", "fall", "winter", "free time", "hobby",
            "sport", "football", "soccer", "tennis", "swim", "run", "read", "book", "newspaper",
            "music", "listen", "sing", "dance", "play", "game", "movie", "meet friends", "photo",
            "travel", "cook", "fun", "like", "prefer", "favorite", "great", "boring", "interesting",
        ],
    ),
]


TOTAL_A1_LEXICON_COUNT = 650


def get_curriculum_units(language: str, level: str = "A1") -> List[UnitInfo]:
    """Retorna las unidades temáticas para el idioma y nivel solicitados."""
    if language.startswith("de"):
        return GERMAN_A1_UNITS
    return ENGLISH_A1_UNITS


def get_unit_by_id(unit_id: str, language: str, level: str = "A1") -> Optional[UnitInfo]:
    """Busca una unidad específica por su identificador (ej: 'unit_1')."""
    units = get_curriculum_units(language, level)
    for u in units:
        if u.id == unit_id:
            return u
    return None


def get_all_target_lemmas(language: str, level: str = "A1") -> List[str]:
    """Retorna la lista completa agregada de palabras objetivo de todas las unidades."""
    units = get_curriculum_units(language, level)
    all_words: List[str] = []
    seen = set()
    for u in units:
        for w in u.target_words:
            w_norm = w.strip().lower()
            if w_norm and w_norm not in seen:
                seen.add(w_norm)
                all_words.append(w_norm)
    return all_words


def extract_words_from_text(text: str) -> List[str]:
    """Extrae palabras/lemas normalizados de un texto o frase."""
    if not text:
        return []
    # Remover puntuación y caracteres especiales, manteniendo letras alemanas (ä, ö, ü, ß)
    clean_text = re.sub(r"[^\w\säöüÄÖÜßáéíóúÁÉÍÓÚñÑ]", " ", text.lower())
    tokens = clean_text.split()
    # Filtrar números o tokens de 1 letra (excepto vocales/artículos)
    result = []
    for t in tokens:
        if not t.isdigit() and len(t) >= 2:
            result.append(t)
    return result


def match_known_words(candidate_words: List[str], language: str, level: str = "A1") -> List[str]:
    """Filtra y devuelve aquellas palabras del candidato que coinciden con el inventario oficial."""
    target_set = set(get_all_target_lemmas(language, level))
    matched = []
    for w in candidate_words:
        w_clean = w.strip().lower()
        if w_clean in target_set:
            matched.append(w_clean)
    return matched


# =========================================================================
# 3. ESCENARIOS OFICIALES DE CONVERSACIÓN (ROLEPLAY CON IA)
# =========================================================================

@dataclass
class ScenarioInfo:
    id: str
    unit_id: str
    level: str
    language: str
    title: str
    character_name: str
    character_role: str
    mission_brief: str
    initial_greeting: str
    initial_greeting_es: str
    target_phrases: List[str] = field(default_factory=list)


GERMAN_A1_SCENARIOS: List[ScenarioInfo] = [
    ScenarioInfo(
        id="scen_de_u1",
        unit_id="unit_1",
        level="A1",
        language="de-DE",
        title="👋 Primer día en el curso de alemán",
        character_name="Frau Müller",
        character_role="Profesora de alemán en el Sprachinstitut en Berlín",
        mission_brief="Saluda formalmente a la profesora, dile tu nombre, de qué país vienes y deletrea tu apellido.",
        initial_greeting="Guten Tag! Herzlich willkommen im Sprachkurs. Wie heißen Sie?",
        initial_greeting_es="¡Buenas tardes! Bienvenido/a al curso de idiomas. ¿Cómo se llama usted?",
        target_phrases=["Ich heiße...", "Ich komme aus...", "Mein Vorname ist...", "Auf Wiedersehen"],
    ),
    ScenarioInfo(
        id="scen_de_u2",
        unit_id="unit_2",
        level="A1",
        language="de-DE",
        title="☕ En la Panadería y Cafetería",
        character_name="Herr Schmidt",
        character_role="Panadero tradicional en 'Bäckerei Schmidt' en Múnich",
        mission_brief="Pide dos panecillos ('zwei Brötchen') y un café solo, pregunta el precio ('Wie viel kostet das?') y paga.",
        initial_greeting="Guten Morgen! Was darf es denn sein?",
        initial_greeting_es="¡Buenos días! ¿Qué va a ser para usted?",
        target_phrases=["Ich möchte...", "Ein Kaffee bitte", "Wie viel kostet das?", "Danke schön"],
    ),
    ScenarioInfo(
        id="scen_de_u3",
        unit_id="unit_3",
        level="A1",
        language="de-DE",
        title="👨‍👩‍👧 Conociendo a un nuevo compañero",
        character_name="Lukas",
        character_role="Estudiante universitario alemán en una cafetería",
        mission_brief="Conversa con Lukas. Cuéntale si tienes hermanos o si tus padres viven contigo y pregúntale su edad.",
        initial_greeting="Hallo! Bist du auch neu hier? Erzähl mal, hast du Geschwister?",
        initial_greeting_es="¡Hola! ¿Tú también eres nuevo aquí? Cuéntame, ¿tienes hermanos?",
        target_phrases=["Ich habe einen Bruder", "Meine Eltern wohnen in...", "Wie alt bist du?"],
    ),
    ScenarioInfo(
        id="scen_de_u4",
        unit_id="unit_4",
        level="A1",
        language="de-DE",
        title="⏰ Agendando una cita con un amigo",
        character_name="Anna",
        character_role="Tu amiga alemana organizando planes de fin de semana",
        mission_brief="Acuerda con Anna el día y la hora exacta para encontrarse (ej: el sábado a las 15:00 horas).",
        initial_greeting="Hallo! Hast du am Wochenende Zeit? Wann wollen wir uns treffen?",
        initial_greeting_es="¡Hola! ¿Tienes tiempo el fin de semana? ¿A qué hora queremos encontrarnos?",
        target_phrases=["Am Samstag um...", "Um wie viel Uhr?", "Ja, das passt mir gut!"],
    ),
    ScenarioInfo(
        id="scen_de_u5",
        unit_id="unit_5",
        level="A1",
        language="de-DE",
        title="🚆 Pidiendo indicaciones en la estación",
        character_name="Herr Weber",
        character_role="Empleado del mostrador de información en la estación central (Hauptbahnhof)",
        mission_brief="Pregunta con educación cómo llegar a la parada de autobús o a qué andén llega el tren.",
        initial_greeting="Guten Tag! Informationsschalter Hauptbahnhof. Wie kann ich Ihnen helfen?",
        initial_greeting_es="¡Buenas tardes! Mostrador de información de la estación central. ¿Cómo le puedo ayudar?",
        target_phrases=["Entschuldigung, wo ist...?", "Auf welchem Gleis?", "Vielen Dank für die Hilfe"],
    ),
    ScenarioInfo(
        id="scen_de_u6",
        unit_id="unit_6",
        level="A1",
        language="de-DE",
        title="🩺 En la Farmacia (Apotheke)",
        character_name="Frau Wagner",
        character_role="Farmacéutica en una botica céntrica",
        mission_brief="Dile a la farmacéutica que tienes dolor de cabeza ('Kopfschmerzen') y pide algo para tomar.",
        initial_greeting="Guten Tag! Was fehlt Ihnen denn? Wie kann ich helfen?",
        initial_greeting_es="¡Buenas tardes! ¿Qué le ocurre? ¿Cómo le puedo ayudar?",
        target_phrases=["Ich habe Kopfschmerzen", "Haben Sie Tabletten?", "Gute Besserung"],
    ),
]


ENGLISH_A1_SCENARIOS: List[ScenarioInfo] = [
    ScenarioInfo(
        id="scen_en_u1",
        unit_id="unit_1",
        level="A1",
        language="en-US",
        title="👋 First Day at the Language School",
        character_name="Ms. Miller",
        character_role="English teacher at the language institute in London",
        mission_brief="Greet the teacher politely, introduce yourself, say where you are from, and spell your name.",
        initial_greeting="Good morning! Welcome to our English class. What is your name?",
        initial_greeting_es="¡Buenos días! Bienvenido/a a nuestra clase de inglés. ¿Cuál es tu nombre?",
        target_phrases=["My name is...", "I am from...", "Nice to meet you", "Goodbye"],
    ),
    ScenarioInfo(
        id="scen_en_u2",
        unit_id="unit_2",
        level="A1",
        language="en-US",
        title="☕ At the London Coffee Shop",
        character_name="Tom (Barista)",
        character_role="Barista at a busy central cafe in London",
        mission_brief="Order a black coffee and a croissant, ask how much it costs ('How much is it?') and pay.",
        initial_greeting="Hello there! What can I get for you today?",
        initial_greeting_es="¡Hola! ¿Qué te puedo servir hoy?",
        target_phrases=["I would like a coffee", "How much is it?", "Keep the change", "Thank you"],
    ),
    ScenarioInfo(
        id="scen_en_u3",
        unit_id="unit_3",
        level="A1",
        language="en-US",
        title="👨‍👩‍👧 Meeting a New Roommate",
        character_name="Oliver",
        character_role="Your new university flatmate",
        mission_brief="Chat with Oliver. Tell him about your family (brothers, sisters, parents) and where they live.",
        initial_greeting="Hi! Great to meet you. Do you have any brothers or sisters back home?",
        initial_greeting_es="¡Hola! Un gusto conocerte. ¿Tienes hermanos o hermanas en tu ciudad?",
        target_phrases=["I have one brother", "My parents live in...", "How old are you?"],
    ),
    ScenarioInfo(
        id="scen_en_u4",
        unit_id="unit_4",
        level="A1",
        language="en-US",
        title="⏰ Making Weekend Plans",
        character_name="Sarah",
        character_role="Your classmate arranging weekend study plans",
        mission_brief="Agree on a meeting day and exact time with Sarah (e.g., Saturday at 3:00 PM).",
        initial_greeting="Hey! Are you free this weekend? What time should we meet up?",
        initial_greeting_es="¡Hola! ¿Estás libre este fin de semana? ¿A qué hora deberíamos encontrarnos?",
        target_phrases=["On Saturday at...", "What time?", "That sounds great!"],
    ),
    ScenarioInfo(
        id="scen_en_u5",
        unit_id="unit_5",
        level="A1",
        language="en-US",
        title="🚆 Asking for Directions to the Station",
        character_name="Officer Davis",
        character_role="Friendly police officer on a street corner",
        mission_brief="Politely ask the officer how to get to the nearest underground station or bus stop.",
        initial_greeting="Hello! Can I help you with directions?",
        initial_greeting_es="¡Hola! ¿Puedo ayudarte con direcciones?",
        target_phrases=["Excuse me, where is...?", "Turn left", "Thank you very much"],
    ),
    ScenarioInfo(
        id="scen_en_u6",
        unit_id="unit_6",
        level="A1",
        language="en-US",
        title="🩺 At the Chemist / Pharmacy",
        character_name="Dr. Jenkins",
        character_role="Pharmacist at a local drugstore",
        mission_brief="Tell the pharmacist that you have a headache and need something mild to take.",
        initial_greeting="Hello. What seems to be the problem today?",
        initial_greeting_es="Hola. ¿Cuál parece ser el problema hoy?",
        target_phrases=["I have a headache", "Do you have medicine?", "Thank you, doctor"],
    ),
]


def get_curriculum_scenarios(language: str, level: str = "A1") -> List[ScenarioInfo]:
    """Retorna los escenarios conversacionales según el idioma."""
    if language.startswith("de"):
        return GERMAN_A1_SCENARIOS
    return ENGLISH_A1_SCENARIOS


def get_scenario_by_id(scenario_id: str, language: str, level: str = "A1") -> Optional[ScenarioInfo]:
    """Busca un escenario específico por su identificador."""
    for s in get_curriculum_scenarios(language, level):
        if s.id == scenario_id:
            return s
    return None


def get_scenarios_for_unit(unit_id: str, language: str, level: str = "A1") -> List[ScenarioInfo]:
    """Retorna los escenarios vinculados a una unidad temática."""
    scenarios = get_curriculum_scenarios(language, level)
    if unit_id == "all":
        return scenarios
    filtered = [s for s in scenarios if s.unit_id == unit_id]
    return filtered or scenarios

