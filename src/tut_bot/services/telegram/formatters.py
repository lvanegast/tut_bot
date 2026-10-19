import re
from typing import Optional

EXPLANATIONS = {
    # Alemán
    "ç": "ch suave palatal (siseo suave con lengua en el medio paladar, no es 'j' áspera)",
    "x": "ch velar (similar a la 'j' española suave)",
    "ʃ": "sonido 'sh' (como mandar a callar)",
    "ʁ": "r uvular alemana (vibra en la campanilla)",
    "ɐ": "r final vocalizada (suena como una 'a' corta relajada, ej. 'Lehrer' -> 'Lee-ra')",
    "øː": "ö larga (labios en 'o', diciendo 'e')",
    "œ": "ö corta (labios redondeados)",
    "yː": "ü larga (labios en beso de 'u', diciendo 'i')",
    "ʏ": "ü corta y relajada",
    "ɛː": "ä (e abierta, baja un poco la mandíbula)",
    "ts": "sonido 'ts' (como tsunami o pizza)",
    "z": "s sonora (vibra como zumbido de abeja)",
    "s": "s sorda estándar",
    # Inglés
    "θ": "th sorda (como la 'z' española en 'zapato', sin vibrar)",
    "ð": "th sonora (lengua entre dientes con vibración, ej. 'this', 'father')",
    "iː": "i larga tensa y sonriente (ej. 'sheep')",
    "ɪ": "i corta relajada (ej. 'ship')",
    "æ": "a abierta amplia (entre a y e, mandíbula baja, ej. 'cat')",
    "ʌ": "u corta central neutra (ej. 'cup')",
    "w": "w inglesa redondeada sin tocar dientes (ej. 'we')",
    "v": "v labiodental (dientes superiores sobre labio inferior con vibración)",
}

LABELS = {
    # Alemán
    "ʁ": "r gutural",
    "ɐ": "-er final",
    "ç": "ch suave",
    "x": "ch velar",
    "ʃ": "sh",
    "øː": "ö larga",
    "œ": "ö corta",
    "yː": "ü larga",
    "ʏ": "ü corta",
    "ɛː": "ä abierta",
    "ɛ": "e abierta",
    "eː": "e larga",
    "iː": "i larga",
    "ɪ": "i corta",
    "oː": "o larga",
    "ɔ": "o corta",
    "uː": "u larga",
    "ʊ": "u corta",
    "ə": "e relajada",
    "ts": "z / ts",
    "z": "s sonora",
    "s": "s sorda",
    "aɪ": "ei / ai",
    "aʊ": "au",
    "ɔʏ": "eu / äu",
    # Inglés
    "θ": "th sorda",
    "ð": "th sonora",
    "æ": "a abierta",
    "ʌ": "u central",
    "w": "w inglesa",
    "v": "v labiodental",
    "dʒ": "j suave",
    "tʃ": "ch",
    "ŋ": "ng",
}


def _make_progress_bar(score: Optional[float], length: int = 10) -> str:
    """Genera una barra de progreso visual con caracteres Unicode."""
    val = float(score) if score is not None else 0.0
    filled = int(round((val / 100.0) * length))
    filled = max(0, min(length, filled))
    return "█" * filled + "░" * (length - filled)


def _format_markdown_for_telegram(text: str) -> str:
    """Convierte markdown (encabezados, **negrita**, *cursiva*) a formato HTML válido para Telegram sin dejar marcas como ##."""
    if not text:
        return ""
    # 1. Escapar entidades HTML especiales
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 2. Convertir encabezados Markdown (#, ##, ###) a negrita limpia
    lines = []
    for line in text.split("\n"):
        header_match = re.match(r"^\s*#{1,6}\s*(.+)$", line)
        if header_match:
            header_content = header_match.group(1).strip()
            lines.append(f"<b>{header_content}</b>")
        else:
            lines.append(line)
    text = "\n".join(lines)

    # 3. Limpiar cualquier ## o # suelto al inicio o entre texto
    text = re.sub(r"#{2,}", "", text)

    # 4. Convertir **negrita**
    parts = text.split("**")
    if len(parts) > 1:
        res = []
        for i, part in enumerate(parts):
            if i % 2 == 1:
                res.append(f"<b>{part}</b>")
            else:
                res.append(part)
        text = "".join(res)

    # 5. Convertir *cursiva* si queda
    parts = text.split("*")
    if len(parts) > 1:
        res = []
        for i, part in enumerate(parts):
            if i % 2 == 1:
                res.append(f"<i>{part}</i>")
            else:
                res.append(part)
        text = "".join(res)

    return text.strip()


def get_phoneme_explanation(phoneme: str, language: str = "de-DE") -> str:
    """Traduce símbolos fonéticos IPA a explicaciones comprensibles en español."""
    clean_p = phoneme.replace("/", "").replace("[", "").replace("]", "").strip()
    return EXPLANATIONS.get(clean_p, "")


def get_phoneme_friendly_label(phoneme: str, language: str = "de-DE") -> str:
    """Devuelve la representación legible con letra común para que el usuario siempre identifique el sonido."""
    clean_p = phoneme.replace("/", "").replace("[", "").replace("]", "").strip()
    label = LABELS.get(clean_p)
    if label:
        return f"'{label}' (/{clean_p}/)"
    return f"/{clean_p}/"
