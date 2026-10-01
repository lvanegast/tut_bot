from typing import List, Optional

from tut_bot.models.schemas import Exercise

EXERCISES_DATABASE: List[Exercise] = [
    # =========================================================================
    # ALEMÁN (de-DE)
    # =========================================================================
    # 1. Ich-Laut (/ç/) vs Ach-Laut (/x/)
    Exercise(
        id="de-phon-01",
        language="de-DE",
        category="ich-Laut vs ach-Laut",
        level="A1",
        title="El sonido de 'Ich' (Ich-Laut /ç/)",
        target_text="Ich spreche kein Deutsch.",
        ipa="ɪç ˈʃpʁɛçə kaɪn dɔɪtʃ",
        translation_es="No hablo alemán.",
        focus_phonemes=["ç", "ʃ"],
        tip="El sonido de 'ch' tras 'i/e' (/ç/) es palatal, como un siseo suave con la lengua pegada al paladar medio, nunca una 'k' ni una 'j' áspera española.",
    ),
    Exercise(
        id="de-phon-02",
        language="de-DE",
        category="ich-Laut vs ach-Laut",
        level="A1",
        title="El sonido de 'Buch' (Ach-Laut /x/)",
        target_text="Das Buch liegt auf dem Tisch.",
        ipa="das buːx liːkt aʊf deːm tɪʃ",
        translation_es="El libro está sobre la mesa.",
        focus_phonemes=["x", "ʃ"],
        tip="Tras vocales posteriores (a, o, u), la 'ch' se pronuncia en la parte posterior (velar /x/), similar a la 'j' española suave.",
    ),
    Exercise(
        id="de-phon-03",
        language="de-DE",
        category="ich-Laut vs ach-Laut",
        level="A2",
        title="Contraste directo Ich vs Ach",
        target_text="Ich suche ein einfaches Buch.",
        ipa="ɪç ˈzuːxə aɪn ˈaɪnfaχəs buːx",
        translation_es="Busco un libro sencillo.",
        focus_phonemes=["ç", "x"],
        tip="Observa cómo cambia de /ç/ en 'Ich' a /x/ en 'suche' y 'Buch'.",
    ),
    # 2. Vocales con diéresis (Umlauts: ä, ö, ü)
    Exercise(
        id="de-umlaut-01",
        language="de-DE",
        category="Umlauts (ä, ö, ü)",
        level="A1",
        title="Umlaut Ö (/øː/, /œ/)",
        target_text="Ich möchte ein Brötchen möchten.",
        ipa="ɪç ˈmœçtə aɪn ˈbʁøːtçən",
        translation_es="Quisiera un pancitoecillo.",
        focus_phonemes=["øː", "œ", "ç"],
        tip="Para pronunciar 'ö', coloca la boca en posición de decir 'o' (labios redondeados), pero intenta emitir una 'e'. ¡No abras los labios!",
    ),
    Exercise(
        id="de-umlaut-02",
        language="de-DE",
        category="Umlauts (ä, ö, ü)",
        level="A1",
        title="Umlaut Ü (/yː/, /ʏ/)",
        target_text="Für fünf Schüler gibt es Übungen.",
        ipa="fyːɐ̯ fʏnf ˈʃyːlɐ ɡɪpt ɛs ˈyːbʊŋən",
        translation_es="Para cinco alumnos hay ejercicios.",
        focus_phonemes=["yː", "ʏ"],
        tip="Para 'ü', pon los labios como si fueras a silbar o dar un beso (posición de 'u'), pero intenta pronunciar 'i'.",
    ),
    Exercise(
        id="de-umlaut-03",
        language="de-DE",
        category="Umlauts (ä, ö, ü)",
        level="A2",
        title="Umlaut Ä (/ɛː/)",
        target_text="Die Mädchen wählen schöne Äpfel.",
        ipa="diː ˈmɛːtçən ˈvɛːlən ˈʃøːnə ˈɛpfəl",
        translation_es="Las chicas eligen manzanas hermosas.",
        focus_phonemes=["ɛː", "ç", "øː"],
        tip="La 'ä' es una 'e' más abierta que la española. Abre la mandíbula un poco más hacia abajo.",
    ),
    # 3. Auslautverhärtung (Ensordecimiento final de consonantes)
    Exercise(
        id="de-auslaut-01",
        language="de-DE",
        category="Auslautverhärtung (Finales)",
        level="A2",
        title="Consonantes finales duras (d->t, b->p, g->k)",
        target_text="Guten Tag, das ist ein schönes Bild!",
        ipa="ˈɡuːtn taːk das ɪst aɪn ˈʃøːnəs bɪlt",
        translation_es="¡Buen día, esta es una hermosa imagen!",
        focus_phonemes=["k", "t"],
        tip="Al final de palabra o sílaba, 'Tag' termina en sonido /k/, y 'Bild' termina en sonido /t/.",
    ),
    # 4. R Alemana (Uvular /ʁ/ vs Vocalizada /ɐ/)
    Exercise(
        id="de-r-01",
        language="de-DE",
        category="La 'R' Alemana",
        level="A2",
        title="R uvular inicial vs R vocalizada final",
        target_text="Der Lehrer trinkt klares Wasser.",
        ipa="deːɐ̯ ˈleːʁɐ tʁɪŋkt ˈklaːʁəs ˈvasɐ",
        translation_es="El profesor bebe agua clara.",
        focus_phonemes=["ʁ", "ɐ"],
        tip="Al final de palabra (-er, der), la 'r' se vocaliza en /ɐ/ (suena como una 'a' corta y relajada). Al inicio, vibra en la campanilla.",
    ),
    # 5. Frases cotidianas A1-B1
    Exercise(
        id="de-daily-01",
        language="de-DE",
        category="Vida Cotidiana",
        level="A1",
        title="Pedir en una cafetería",
        target_text="Entschuldigung, kann ich bitte einen Kaffee haben?",
        ipa="ɛntˈʃʊldɪɡʊŋ kan ɪç ˈbɪtə ˈaɪnən ˈkafeː ˈhaːbn̩",
        translation_es="Disculpe, ¿puedo pedir un café por favor?",
        focus_phonemes=["ç", "ʃ"],
        tip="Presta atención a la fluidez y a la unión de palabras en preguntas de cortesía.",
    ),
    Exercise(
        id="de-daily-02",
        language="de-DE",
        category="Vida Cotidiana",
        level="B1",
        title="Expresar opinión con oraciones subordinadas",
        target_text="Ich glaube, dass wir heute noch pünktlich ankommen.",
        ipa="ɪç ˈɡlaʊbə das viːɐ̯ ˈhɔɪtə nɔx ˈpʏŋktlɪç ˈankɔmən",
        translation_es="Creo que hoy todavía llegaremos puntuales.",
        focus_phonemes=["ç", "x", "ʏ"],
        tip="Cuida la entonación que desciende al final de la cláusula subordinada.",
    ),
    # =========================================================================
    # INGLÉS (en-US)
    # =========================================================================
    # 1. Sonidos TH (/θ/ sordo vs /ð/ sonoro)
    Exercise(
        id="en-th-01",
        language="en-US",
        category="TH Sounds (/θ/ vs /ð/)",
        level="A1",
        title="Unvoiced TH (/θ/ como en 'think')",
        target_text="I think thirty three things are thrilling.",
        ipa="aɪ θɪŋk ˈθɜːti θriː θɪŋz ɑːr ˈθrɪlɪŋ",
        translation_es="Creo que treinta y tres cosas son emocionantes.",
        focus_phonemes=["θ"],
        tip="Coloca la punta de la lengua suavemente entre los dientes frontales y sopla aire sin vibrar las cuerdas vocales.",
    ),
    Exercise(
        id="en-th-02",
        language="en-US",
        category="TH Sounds (/θ/ vs /ð/)",
        level="A1",
        title="Voiced TH (/ð/ como en 'this')",
        target_text="This is their father and mother.",
        ipa="ðɪs ɪz ðɛr ˈfɑːðər ænd ˈmʌðər",
        translation_es="Este es el padre y la madre de ellos.",
        focus_phonemes=["ð"],
        tip="Misma posición de la lengua que el TH sordo, pero haciendo vibrar activamente la garganta (cuerdas vocales).",
    ),
    # 2. Contraste de vocales cortas vs largas (/iː/ vs /ɪ/)
    Exercise(
        id="en-vowels-01",
        language="en-US",
        category="Pares Mínimos Vocálicos",
        level="A2",
        title="Sheep /iː/ vs Ship /ɪ/",
        target_text="The big sheep sleeps on the green hill.",
        ipa="ðə bɪɡ ʃiːp sliːps ɑːn ðə ɡriːn hɪl",
        translation_es="La gran oveja duerme sobre la colina verde.",
        focus_phonemes=["iː", "ɪ"],
        tip="En 'sleeps' la vocal es tensa y sonriente (/iː/). En 'big' e 'hill', la vocal es relajada, corta y central (/ɪ/).",
    ),
    Exercise(
        id="en-vowels-02",
        language="en-US",
        category="Pares Mínimos Vocálicos",
        level="A2",
        title="Cat /æ/ vs Cut /ʌ/",
        target_text="The black cat jumped over the cup.",
        ipa="ðə blæk kæt dʒʌmpt ˈoʊvər ðə kʌp",
        translation_es="El gato negro saltó sobre la taza.",
        focus_phonemes=["æ", "ʌ"],
        tip="/æ/ requiere abrir la boca ampliamente hacia abajo. /ʌ/ es una vocal corta y neutral en el centro de la boca.",
    ),
    # 3. Labiodental V (/v/) vs Bilabial B (/b/)
    Exercise(
        id="en-b-v-01",
        language="en-US",
        category="V vs B",
        level="A1",
        title="Distinguiendo V (/v/) de B (/b/)",
        target_text="Very best friends travel by van and boat.",
        ipa="ˈvɛri bɛst frɛndz ˈtrævəl baɪ væn ænd boʊt",
        translation_es="Los mejores amigos viajan en furgoneta y barco.",
        focus_phonemes=["v", "b"],
        tip="En español no diferenciamos B de V. En inglés, para la 'V' tus dientes superiores DEBEN tocar el labio inferior con fricción.",
    ),
    # 4. Conversación Fluida
    Exercise(
        id="en-daily-01",
        language="en-US",
        category="Conversación Cotidiana",
        level="B1",
        title="Presentación profesional y proyectos",
        target_text="I would really appreciate your feedback on this project.",
        ipa="aɪ wʊd ˈrɪəli əˈpriːʃieɪt jʊər ˈfiːdbæk ɑːn ðɪs ˈprɑːdʒɛkt",
        translation_es="Realmente agradecería tus comentarios sobre este proyecto.",
        focus_phonemes=["ʃ", "ð", "æ"],
        tip="Enfócate en la fluidez del ritmo y la reducción de sonidos no acentuados ('would', 'your').",
    ),
]


def get_exercises(
    language: Optional[str] = None, category: Optional[str] = None, level: Optional[str] = None
) -> List[Exercise]:
    results = EXERCISES_DATABASE
    if language:
        results = [e for e in results if e.language.lower() == language.lower()]
    if category:
        results = [e for e in results if e.category.lower() == category.lower()]
    if level:
        results = [e for e in results if e.level.lower() == level.lower()]
    return results


def get_categories(language: str) -> List[str]:
    seen = set()
    categories = []
    for e in EXERCISES_DATABASE:
        if e.language.lower() == language.lower() and e.category not in seen:
            seen.add(e.category)
            categories.append(e.category)
    return categories
