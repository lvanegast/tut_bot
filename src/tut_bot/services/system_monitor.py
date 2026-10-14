import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("tut_bot.system_monitor")


def get_system_metrics() -> Dict[str, Any]:
    """
    Obtiene métricas operativas y de hardware del host (NVIDIA Jetson Nano / Linux / Windows)
    sin requerir bibliotecas pesadas de terceros.
    """
    metrics: Dict[str, Any] = {}

    # 1. Temperatura de la CPU / Tegra SoC (en Linux / Jetson Nano)
    thermal_paths = [
        Path("/sys/devices/virtual/thermal/thermal_zone0/temp"),  # CPU-therm en Jetson
        Path("/sys/class/thermal/thermal_zone0/temp"),
    ]
    for tp in thermal_paths:
        if tp.exists():
            try:
                raw_temp = tp.read_text().strip()
                val = float(raw_temp)
                # En Linux suele reportarse en miligrados Celsius (ej: 42000 = 42.0 C)
                celsius = val / 1000.0 if val > 100 else val
                metrics["cpu_temp_c"] = round(celsius, 1)
                break
            except Exception as e:
                logger.debug(f"No se pudo leer temperatura térmica: {e}")

    # 2. Memoria RAM y SWAP (Linux /proc/meminfo)
    meminfo_path = Path("/proc/meminfo")
    if meminfo_path.exists():
        try:
            mem_data: Dict[str, int] = {}
            for line in meminfo_path.read_text().splitlines():
                parts = line.split(":")
                if len(parts) == 2:
                    k = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    if val.isdigit():
                        mem_data[k] = int(val) // 1024  # Convertir a MB

            total_ram = mem_data.get("MemTotal", 0)
            avail_ram = mem_data.get("MemAvailable", mem_data.get("MemFree", 0))
            if total_ram > 0:
                used_ram = total_ram - avail_ram
                metrics["ram_total_mb"] = total_ram
                metrics["ram_used_mb"] = used_ram
                metrics["ram_available_mb"] = avail_ram
                metrics["ram_used_pct"] = round((used_ram / total_ram) * 100, 1)

            total_swap = mem_data.get("SwapTotal", 0)
            free_swap = mem_data.get("SwapFree", 0)
            if total_swap > 0:
                used_swap = total_swap - free_swap
                metrics["swap_total_mb"] = total_swap
                metrics["swap_used_mb"] = used_swap
                metrics["swap_used_pct"] = round((used_swap / total_swap) * 100, 1)
        except Exception as e:
            logger.debug(f"No se pudo parsear /proc/meminfo: {e}")

    # 3. Modo de Energía en Jetson Nano (nvpmodel)
    nvpmodel_conf = Path("/var/lib/nvpmodel/status")
    if nvpmodel_conf.exists():
        try:
            content = nvpmodel_conf.read_text().strip()
            # En Jetson Nano: '0' = MAXN (10W), '1' = 5W
            if "0" in content:
                metrics["power_mode"] = "Mode 0: MAXN (10W)"
            elif "1" in content:
                metrics["power_mode"] = "Mode 1: 5W"
            else:
                metrics["power_mode"] = content
        except Exception:
            pass

    # 4. Almacenamiento libre en disco
    try:
        data_dir = os.environ.get("DATA_DIR", ".")
        total, used, free = shutil.disk_usage(data_dir)
        metrics["disk_free_gb"] = round(free / (1024**3), 2)
        metrics["disk_total_gb"] = round(total / (1024**3), 2)
    except Exception as e:
        logger.debug(f"Error calculando espacio en disco: {e}")

    return metrics


def format_system_status(
    azure_ok: bool,
    gemini_ok: bool,
    telegram_ok: bool,
    mock_mode: bool,
    metrics: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Genera un informe con formato HTML amigable para Telegram y panel operativo.
    """
    if metrics is None:
        metrics = get_system_metrics()

    az_badge = "✅ Conectado" if azure_ok else ("⚠️ Simulado (Mock)" if mock_mode else "❌ Desconectado")
    gem_badge = "✅ Conectado" if gemini_ok else ("⚠️ Simulado (Mock)" if mock_mode else "❌ Desconectado")
    tg_badge = "✅ Activo" if telegram_ok else "❌ Desconectado"

    lines = [
        "🖥️ <b>Estado del Sistema tut_bot</b>\n",
        "⚙️ <b>Servicios y Conexiones:</b>",
        f"  • Azure Speech SDK: {az_badge}",
        f"  • Google Gemini: {gem_badge}",
        f"  • Telegram Bot: {tg_badge}",
        "  • Base de datos SQLite: ✅ Operativa\n",
    ]

    has_metrics = bool(metrics.get("ram_total_mb") or metrics.get("cpu_temp_c") or metrics.get("disk_free_gb"))
    if has_metrics:
        lines.append("🌡️ <b>Métricas de Hardware (Host / Jetson):</b>")

        # Temperatura CPU
        if "cpu_temp_c" in metrics:
            temp = metrics["cpu_temp_c"]
            if temp < 70:
                temp_badge = f"{temp:.1f} °C (Óptima 🟢)"
            elif temp < 85:
                temp_badge = f"{temp:.1f} °C (Moderada 🟡)"
            else:
                temp_badge = f"{temp:.1f} °C (¡ALTA! Riesgo térmico 🔴)"
            lines.append(f"  • Temperatura CPU: {temp_badge}")

        # Modo de energía Jetson
        if "power_mode" in metrics:
            lines.append(f"  • Perfil de Energía: <code>{metrics['power_mode']}</code>")

        # RAM
        if "ram_total_mb" in metrics:
            used_mb = metrics.get("ram_used_mb", 0)
            tot_mb = metrics.get("ram_total_mb", 1)
            pct = metrics.get("ram_used_pct", 0)
            status_ram = "🟢" if pct < 75 else ("🟡" if pct < 88 else "🔴")
            lines.append(f"  • Memoria RAM: {used_mb} MB / {tot_mb} MB ({pct:.1f}% {status_ram})")

        # SWAP
        if "swap_total_mb" in metrics and metrics["swap_total_mb"] > 0:
            s_used = metrics.get("swap_used_mb", 0)
            s_tot = metrics.get("swap_total_mb", 1)
            s_pct = metrics.get("swap_used_pct", 0)
            lines.append(f"  • Memoria SWAP: {s_used} MB / {s_tot} MB ({s_pct:.1f}%)")

        # Disco
        if "disk_free_gb" in metrics:
            free_gb = metrics["disk_free_gb"]
            tot_gb = metrics.get("disk_total_gb", 0)
            lines.append(f"  • Disco Libre: {free_gb} GB / {tot_gb} GB")

        lines.append("")

        # Alertas preventivas
        alerts = []
        if metrics.get("cpu_temp_c", 0) >= 85:
            alerts.append("⚠️ <b>Atención:</b> Temperatura de CPU muy elevada (>85°C). Activa ventilación para evitar corte térmico.")
        if metrics.get("ram_used_pct", 0) >= 88:
            alerts.append("⚠️ <b>Atención:</b> Uso de RAM > 88%. Vigilar posibles fugas de memoria o límite de contenedores.")

        if alerts:
            lines.extend(alerts)
            lines.append("")
        else:
            lines.append("✨ <i>Hardware operando en parámetros seguros para servicio 24/7.</i>")
    else:
        lines.append("✨ <i>Servidor FastAPI activo en puerto 8000.</i>")

    return "\n".join(lines)
