import logging

import uvicorn

from tut_bot.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tut_bot.runner")

if __name__ == "__main__":
    logger.info(f"Iniciando tut_bot en http://localhost:{settings.PORT}")
    logger.info(
        f"Modo Mock / Simulación: {'ACTIVADO' if settings.is_mock_mode else 'DESACTIVADO (Azure + Gemini reales)'}"
    )
    uvicorn.run("tut_bot.main:app", host=settings.HOST, port=settings.PORT, reload=True)
