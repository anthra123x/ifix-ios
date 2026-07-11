import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import urlopen, Request


CACHE_DIR = Path.home() / ".cache" / "ifix-ios"
CACHE_TTL = timedelta(hours=6)

KNOWN_DEVICES: dict[str, str] = {
    "iPhone17,2": "iPhone 16 Pro Max",
    "iPhone17,1": "iPhone 16 Pro",
    "iPhone17,3": "iPhone 16",
    "iPhone17,4": "iPhone 16 Plus",
    "iPhone17,5": "iPhone 16e",
    "iPhone16,1": "iPhone 15 Pro",
    "iPhone16,2": "iPhone 15 Pro Max",
    "iPhone15,3": "iPhone 15",
    "iPhone15,4": "iPhone 15 Plus",
    "iPhone15,2": "iPhone 14 Pro",
    "iPhone15,3": "iPhone 14 Pro Max",
    "iPhone14,7": "iPhone 14",
    "iPhone14,8": "iPhone 14 Plus",
    "iPhone14,2": "iPhone 13 Pro",
    "iPhone14,3": "iPhone 13 Pro Max",
    "iPhone14,5": "iPhone 13",
    "iPhone14,6": "iPhone 13 mini",
    "iPhone13,1": "iPhone 12 mini",
    "iPhone13,2": "iPhone 12",
    "iPhone13,3": "iPhone 12 Pro",
    "iPhone13,4": "iPhone 12 Pro Max",
    "iPad14,3": "iPad Air M2",
    "iPad14,4": "iPad Air M2",
    "iPad13,16": "iPad Pro 12.9 M1",
    "iPad13,11": "iPad Pro 11 M1",
    "iPad14,1": "iPad mini 6",
    "iPad13,1": "iPad 10th gen",
}


class FirmwareInfo:
    def __init__(self, version: str, build: str, released: str, signed: bool):
        self.version = version
        self.build = build
        self.released = released
        self.signed = signed

    def __repr__(self):
        return f"{self.version} ({self.build}){' ✓' if self.signed else ''}"


def device_name(product_type: str) -> str:
    return KNOWN_DEVICES.get(product_type, f"Unknown ({product_type})")


def load_cache(device_id: str) -> list[FirmwareInfo] | None:
    cache_file = CACHE_DIR / f"firmware_{device_id}.json"
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text())
        cached_at = datetime.fromisoformat(data["cached_at"])
        if datetime.now() - cached_at > CACHE_TTL:
            return None
        return [
            FirmwareInfo(f["version"], f["build"], f.get("released", ""), f.get("signed", False))
            for f in data["firmwares"]
        ]
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def save_cache(device_id: str, firmwares: list[FirmwareInfo]):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "cached_at": datetime.now().isoformat(),
        "firmwares": [
            {"version": f.version, "build": f.build, "released": f.released, "signed": f.signed}
            for f in firmwares
        ],
    }
    (CACHE_DIR / f"firmware_{device_id}.json").write_text(json.dumps(data, indent=2))


def fetch_firmwares(device_id: str) -> list[FirmwareInfo]:
    cached = load_cache(device_id)
    if cached:
        return cached

    url = f"https://api.ipsw.me/v4/device/{device_id}?type=ipsw"
    try:
        req = Request(url, headers={"User-Agent": "ifix-ios/0.1.0"})
        resp = urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())

        firmwares = []
        for fw in data.get("firmwares", []):
            firmwares.append(FirmwareInfo(
                version=fw.get("version", "?"),
                build=fw.get("buildid", "?"),
                released=fw.get("released", ""),
                signed=fw.get("signed", False),
            ))

        if firmwares:
            save_cache(device_id, firmwares)
        return firmwares
    except Exception:
        return []


def latest_signed(device_id: str) -> FirmwareInfo | None:
    firmwares = fetch_firmwares(device_id)
    signed = [f for f in firmwares if f.signed]
    if signed:
        return sorted(signed, key=lambda f: f.version, reverse=True)[0]
    if firmwares:
        return sorted(firmwares, key=lambda f: f.version, reverse=True)[0]
    return None


def get_device_guide(dev) -> list[str]:
    from ifix_ios.core.detector import DeviceMode

    lines = []
    mode = dev.mode
    model = dev.product_type or "?"

    if mode == DeviceMode.ABSENT:
        lines.append("🔌 No hay dispositivo conectado.")
        lines.append("   Conecta un iPhone/iPad por USB y espera a que se detecte.")
        return lines

    nice_name = device_name(model)
    lines.append(f"📱 [bold]{nice_name}[/] ({model})")

    if dev.product_version:
        lines.append(f"📦 Versión actual: iOS {dev.product_version}")
    else:
        lines.append("📦 Versión actual: desconocida (modo recovery/DFU)")

    if mode == DeviceMode.NORMAL:
        lines.append("")
        lines.append("[green]✓ Dispositivo funcionando correctamente.[/]")
        lines.append("   No requiere reparación.")
        return lines

    if mode == DeviceMode.RECOVERY:
        lines.append("")
        lines.append("[yellow]⚠ MODO RECUPERACIÓN[/]")
        lines.append("   El dispositivo muestra el icono de cable + laptop.")
        lines.append("   Causas posibles: actualización fallida, jailbreak, corrupción de sistema.")
        lines.append("")
        lines.append("[b]📋 Plan de acción:[/b]")
        lines.append("   [1] [cyan]U[/] Update — Reinstala iOS sin borrar datos (recomendado)")
        lines.append("   [2] [cyan]E[/] Erase Restore — Borra todo e instala iOS limpio")
        lines.append("")
        lines.append("   Recomendación: Prueba Update primero. Si falla, haz Erase.")

    elif mode == DeviceMode.DFU:
        lines.append("")
        lines.append("[red]!! MODO DFU[/]")
        lines.append("   La pantalla está completamente negra.")
        lines.append("   El dispositivo no inicia el sistema operativo.")
        lines.append("")
        lines.append("[b]📋 Plan de acción:[/b]")
        lines.append("   [1] [cyan]E[/] Erase Restore — Única opción disponible")
        lines.append("   [2) Update NO es posible en DFU")
        lines.append("")
        lines.append("   ⚠ Se borrarán TODOS los datos del dispositivo.")

    elif mode == DeviceMode.BOOTLOOP:
        lines.append("")
        lines.append("[red]✗ BOOT-LOOP[/]")
        lines.append("   El dispositivo se reinicia constantemente en el logo de Apple.")
        lines.append("   Causas posibles: actualización fallida, batería baja, corrupción de datos.")
        lines.append("")
        lines.append("[b]📋 Plan de acción:[/b]")
        lines.append("   [1] [cyan]U[/] Update — Reinstala iOS sin borrar datos (recomendado)")
        lines.append("   [2] [cyan]E[/] Erase Restore — Si el update no funciona")
        lines.append("   [3] [cyan]D[/] Force Recovery — Forzar modo recovery manualmente")
        lines.append("")
        lines.append("   Recomendación: Conecta el cable, pon el dispositivo en Recovery")
        lines.append("   (subir/bajar volumen rápido, luego hold botón lateral)")
        lines.append("   y ejecuta Update.")

    # Latest signed firmware info
    latest = latest_signed(model)
    if latest:
        lines.append("")
        lines.append(f"[dim]Última versión firmada por Apple:[/] [green]{latest.version}[/] ({latest.build})")
        if dev.product_version and latest.version != dev.product_version:
            lines.append(f"[dim]  Diferencia:[/] {dev.product_version} → {latest.version}")
    else:
        lines.append("")
        lines.append("[dim]No se pudo consultar la última versión de iOS (sin internet).[/]")

    return lines
