import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)


class Settings:
    AZURE_SPEECH_KEY: str = os.getenv("AZURE_SPEECH_KEY", "").strip()
    AZURE_SPEECH_REGION: str = os.getenv("AZURE_SPEECH_REGION", "eastus").strip()
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    WEB_BASE_URL: str = os.getenv("WEB_BASE_URL", "").strip()

    _mock_env = os.getenv("MOCK_MODE", "auto").strip().lower()

    @property
    def is_azure_ready(self) -> bool:
        return bool(self.AZURE_SPEECH_KEY and not self.AZURE_SPEECH_KEY.startswith("tu_"))

    @property
    def is_gemini_ready(self) -> bool:
        return bool(self.GEMINI_API_KEY and not self.GEMINI_API_KEY.startswith("tu_"))

    @property
    def is_telegram_ready(self) -> bool:
        return bool(self.TELEGRAM_BOT_TOKEN and not self.TELEGRAM_BOT_TOKEN.startswith("tu_"))

    @property
    def is_mock_mode(self) -> bool:
        if self._mock_env in ("true", "1", "yes"):
            return True
        if self._mock_env in ("false", "0", "no"):
            return False
        # If 'auto', enable mock mode if either key is missing
        return not (self.is_azure_ready and self.is_gemini_ready)


settings = Settings()
