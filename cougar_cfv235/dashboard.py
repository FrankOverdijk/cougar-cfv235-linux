"""Collect Linux sensor readings and render a dashboard PNG."""

import io
import json
import math
import subprocess
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .device import HEIGHT, WIDTH

BG = "#101418"
PANEL = "#171D22"
LINE = "#344047"
SILVER = "#C7C8CA"
PRIMARY = "#F0F1F1"
MUTED = "#84949C"
BAR = "#A8BABD"

FONT_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
]
FONT_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
]


def font(size, bold=False):
    for name in FONT_BOLD if bold else FONT_REGULAR:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size=size)


FONT_TITLE = font(43, True)
FONT_LABEL = font(23, True)
FONT_BIG = font(65, True)
FONT_MID = font(37, True)
FONT_SUB = font(22)
FONT_SMALL = font(19)


def run(*cmd, timeout=3):
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return r.stdout if r.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired, PermissionError):
        return ""


def sensors_data():
    try:
        result = json.loads(run("sensors", "-j", timeout=4))
        return result if isinstance(result, dict) else {}
    except (ValueError, TypeError):
        return {}


def sensor_value(data, prefix, label):
    for chip_name, chip in data.items():
        if not chip_name.lower().startswith(prefix.lower()) or not isinstance(
            chip, dict
        ):
            continue
        for title, values in chip.items():
            if title.lower() == label.lower() and isinstance(values, dict):
                for field, v in values.items():
                    if (
                        field.endswith("_input")
                        and isinstance(v, (int, float))
                        and math.isfinite(v)
                    ):
                        return float(v)
    return None


def cpu_counter():
    try:
        raw = Path("/proc/stat").read_text().splitlines()[0].split()
        vals = list(map(int, raw[1:9]))
        idle = vals[3] + vals[4]
        total = sum(vals)
        return total, idle
    except (OSError, IndexError, ValueError):
        return None


def cpu_load(old, new):
    if not old or not new:
        return None
    total = new[0] - old[0]
    idle = new[1] - old[1]
    return max(0.0, min(100.0, 100.0 * (1 - idle / total))) if total > 0 else None


def memory_data():
    try:
        kv = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            if k in ("MemTotal", "MemAvailable"):
                kv[k] = int(v.strip().split()[0])
        total = kv["MemTotal"] / 1048576
        used = (kv["MemTotal"] - kv["MemAvailable"]) / 1048576
        return used, total, 100 * used / total
    except (OSError, KeyError, ValueError, ZeroDivisionError):
        return None, None, None


def gpu_data():
    csv = run(
        "nvidia-smi",
        "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total",
        "--format=csv,noheader,nounits",
        timeout=4,
    )
    try:
        vals = [float(s.strip()) for s in csv.strip().splitlines()[0].split(",")]
        if not all(map(math.isfinite, vals)):
            return {}
        return {
            "temp": vals[0],
            "load": vals[1],
            "used_mb": vals[2],
            "total_mb": vals[3],
        }
    except (IndexError, ValueError):
        return {}


def cpu_temperature(data):
    for driver, label in (
        ("k10temp", "Tctl"),
        ("coretemp", "Package id 0"),
        ("zenpower", "Tdie"),
    ):
        value = sensor_value(data, driver, label)
        if value is not None:
            return value
    return None


def measure(old_cpu=None):
    sd = sensors_data()
    m_used, m_total, m_pct = memory_data()
    cp = cpu_counter()
    return {
        "cpu_temp": cpu_temperature(sd),
        "cpu_usage": cpu_load(old_cpu, cp),
        "gpu": gpu_data(),
        "mem_used": m_used,
        "mem_total": m_total,
        "mem_pct": m_pct,
        "pump": sensor_value(sd, "kraken2", "Pump"),
        "coolant": sensor_value(sd, "kraken2", "Coolant"),
        "sample_time": datetime.now().strftime("%H:%M:%S"),
        "_counter": cp,
    }


def fmt(value, unit="", digits=0):
    if value is None:
        return "--"
    return f"{value:.{digits}f}{unit}"


def draw_bar(d, x, y, width, value):
    d.rounded_rectangle((x, y, x + width, y + 11), radius=5, fill=LINE)
    if value is not None:
        fill = max(0, min(width, int(width * max(0, min(100, value)) / 100)))
        if fill:
            d.rounded_rectangle((x, y, x + max(7, fill), y + 11), radius=5, fill=BAR)


def dashboard_png(data):
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(img)
    d.text((56, 31), "SYSTEM MONITOR", font=FONT_TITLE, fill=PRIMARY)
    d.line((56, 104, 1864, 104), fill=LINE, width=2)
    d.text((1675, 37), data["sample_time"], font=FONT_MID, fill=SILVER)
    boxes = [(56, "CPU"), (522, "GPU"), (988, "MEMORY"), (1454, "COOLING")]
    for x, label in boxes:
        d.rounded_rectangle(
            (x, 126, x + 410, 394), radius=13, fill=PANEL, outline=LINE, width=2
        )
        d.text((x + 27, 153), label, font=FONT_LABEL, fill=MUTED)
    # CPU
    x = 56
    d.text((x + 24, 193), fmt(data["cpu_temp"], "°C", 1), font=FONT_BIG, fill=PRIMARY)
    d.text(
        (x + 27, 298),
        f"Load  {fmt(data['cpu_usage'], '%', 0)}",
        font=FONT_SUB,
        fill=SILVER,
    )
    draw_bar(d, x + 27, 350, 351, data["cpu_usage"])
    # GPU
    x = 522
    gpu = data["gpu"]
    d.text((x + 24, 193), fmt(gpu.get("temp"), "°C", 0), font=FONT_BIG, fill=PRIMARY)
    d.text(
        (x + 27, 298),
        f"Load  {fmt(gpu.get('load'), '%', 0)}",
        font=FONT_SUB,
        fill=SILVER,
    )
    draw_bar(d, x + 27, 350, 351, gpu.get("load"))
    # Memory
    x = 988
    d.text((x + 24, 193), fmt(data["mem_pct"], "%", 0), font=FONT_BIG, fill=PRIMARY)
    if data["mem_used"] is not None:
        desc = f"{data['mem_used']:.1f} / {data['mem_total']:.1f} GiB"
    else:
        desc = "Memory data unavailable"
    d.text((x + 27, 298), desc, font=FONT_SUB, fill=SILVER)
    draw_bar(d, x + 27, 350, 351, data["mem_pct"])
    # Pump and coolant
    x = 1454
    d.text((x + 27, 204), fmt(data["pump"], " RPM", 0), font=FONT_MID, fill=PRIMARY)
    d.text((x + 27, 279), "Coolant", font=FONT_SUB, fill=MUTED)
    d.text((x + 27, 311), fmt(data["coolant"], "°C", 1), font=FONT_MID, fill=SILVER)
    d.text((56, 422), "LOCAL SENSORS", font=FONT_SMALL, fill=MUTED)
    d.text((1685, 422), "LINUX", font=FONT_SMALL, fill=SILVER)
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def demo_data():
    return {
        "sample_time": "14:27:06",
        "cpu_temp": 52.6,
        "cpu_usage": 31.0,
        "gpu": {"temp": 59.0, "load": 74.0},
        "mem_pct": 39.0,
        "mem_used": 12.5,
        "mem_total": 32.0,
        "pump": 2150.0,
        "coolant": 32.8,
    }
