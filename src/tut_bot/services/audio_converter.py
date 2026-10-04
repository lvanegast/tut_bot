import logging
import os
import shutil
import subprocess
import tempfile
from typing import Optional

import imageio_ffmpeg

logger = logging.getLogger(__name__)


class AudioConverter:
    """
    Servicio de conversión y remuestreo de audio para tut_bot.
    Convierte notas de voz OGG/Opus (Telegram) a WAV PCM 16kHz 16-bit mono (Azure Speech SDK),
    y WAV a OGG Opus para reproducir como notas de voz en Telegram.
    """

    def __init__(self):
        # En Linux/Docker (Jetson Nano), preferir el binario nativo del sistema (/usr/bin/ffmpeg)
        sys_ffmpeg = shutil.which("ffmpeg")
        if sys_ffmpeg:
            self._ffmpeg_exe = sys_ffmpeg
            logger.info(f"FFmpeg del sistema detectado: {self._ffmpeg_exe}")
        else:
            try:
                self._ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                logger.info(f"FFmpeg detectado mediante imageio_ffmpeg: {self._ffmpeg_exe}")
            except Exception as e:
                self._ffmpeg_exe = "ffmpeg"
                logger.warning(
                    f"No se pudo resolver ffmpeg mediante imageio_ffmpeg: {e}. Usando 'ffmpeg' por defecto."
                )

    @property
    def ffmpeg_bin(self) -> str:
        return self._ffmpeg_exe

    def ogg_to_wav(self, ogg_bytes: bytes) -> Optional[bytes]:
        """Convierte bytes de audio OGG/Opus a WAV PCM 16kHz mono de 16 bits."""
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f_in:
            f_in.write(ogg_bytes)
            in_path = f_in.name

        out_path = in_path.replace(".ogg", "_converted.wav")
        try:
            cmd = [
                self.ffmpeg_bin,
                "-y",
                "-i",
                in_path,
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                out_path,
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                logger.error(
                    f"Fallo al convertir OGG a WAV: {result.stderr.decode('utf-8', errors='ignore')}"
                )
                return None

            with open(out_path, "rb") as f_out:
                return f_out.read()
        except Exception as e:
            logger.error(f"Excepción convirtiendo OGG a WAV: {e}")
            return None
        finally:
            for p in (in_path, out_path):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

    def wav_to_ogg_opus(self, wav_bytes: bytes) -> Optional[bytes]:
        """Convierte bytes WAV a OGG Opus para enviar como nota de voz en Telegram."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f_in:
            f_in.write(wav_bytes)
            in_path = f_in.name

        out_path = in_path.replace(".wav", "_voice.ogg")
        try:
            cmd = [
                self.ffmpeg_bin,
                "-y",
                "-i",
                in_path,
                "-c:a",
                "libopus",
                "-b:a",
                "32k",
                "-ar",
                "48000",
                out_path,
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                # Si libopus no está disponible, intentar OGG genérico
                cmd_fallback = [
                    self.ffmpeg_bin,
                    "-y",
                    "-i",
                    in_path,
                    "-c:a",
                    "libvorbis",
                    "-q:a",
                    "4",
                    out_path,
                ]
                result_fb = subprocess.run(
                    cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                if result_fb.returncode != 0:
                    logger.error(
                        f"Fallo al convertir WAV a OGG: {result.stderr.decode('utf-8', errors='ignore')}"
                    )
                    return None

            with open(out_path, "rb") as f_out:
                return f_out.read()
        except Exception as e:
            logger.error(f"Excepción convirtiendo WAV a OGG: {e}")
            return None
        finally:
            for p in (in_path, out_path):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass


audio_converter = AudioConverter()
