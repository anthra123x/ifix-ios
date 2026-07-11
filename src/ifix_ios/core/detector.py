import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class DeviceMode(Enum):
    NORMAL = "normal"
    RECOVERY = "recovery"
    DFU = "dfu"
    BOOTLOOP = "bootloop"
    ABSENT = "absent"
    UNKNOWN = "unknown"


USB_PRODUCT_IDS = {
    0x12a8: DeviceMode.NORMAL,
    0x1281: DeviceMode.RECOVERY,
    0x1227: DeviceMode.DFU,
}

USB_VENDOR_APPLE = 0x05ac


@dataclass
class DeviceInfo:
    mode: DeviceMode = DeviceMode.ABSENT
    udid: str | None = None
    ecid: str | None = None
    product_type: str | None = None
    product_version: str | None = None
    build: str | None = None
    device_name: str | None = None
    serial: str | None = None
    model: str | None = None
    activation_state: str | None = None
    usb_id: str | None = None
    battery_level: int | None = None
    raw: dict[str, str] = field(default_factory=dict)


class DeviceDetector:
    def scan_usb(self) -> tuple[DeviceMode, str | None]:
        mode, pid_str = self._scan_usb_pyusb()
        if mode not in (DeviceMode.UNKNOWN, DeviceMode.ABSENT):
            return mode, pid_str
        return self._scan_usb_lsusb()

    def _scan_usb_pyusb(self) -> tuple[DeviceMode, str | None]:
        try:
            import usb.core
            import usb.backend.libusb1
            device = usb.core.find(idVendor=USB_VENDOR_APPLE)
            if device is None:
                return DeviceMode.ABSENT, None
            pid = device.idProduct
            mode = USB_PRODUCT_IDS.get(pid, DeviceMode.UNKNOWN)
            return mode, f"{pid:04x}"
        except (ImportError, usb.core.USBError, ValueError):
            return DeviceMode.UNKNOWN, None

    def _scan_usb_lsusb(self) -> tuple[DeviceMode, str | None]:
        try:
            result = subprocess.run(
                ["lsusb"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if "Apple" not in line and "05ac" not in line:
                    continue
                m = re.search(r"ID\s+05ac:([0-9a-fA-F]+)", line)
                if m:
                    pid = int(m.group(1), 16)
                    mode = USB_PRODUCT_IDS.get(pid, DeviceMode.UNKNOWN)
                    return mode, m.group(1)
            return DeviceMode.ABSENT, None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return DeviceMode.UNKNOWN, None

    def get_idevice_id(self) -> str | None:
        try:
            result = subprocess.run(
                ["idevice_id", "-l"],
                capture_output=True, text=True, timeout=5
            )
            udid = result.stdout.strip()
            return udid if udid else None
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

    def get_idevice_info(self) -> dict[str, str]:
        info: dict[str, str] = {}
        try:
            result = subprocess.run(
                ["ideviceinfo"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    info[key.strip()] = val.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return info

    def check_lockdownd(self) -> bool:
        try:
            result = subprocess.run(
                ["ideviceinfo"],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def has_idevice_tools(self) -> bool:
        return self.get_idevice_id() is not None

    def detect(self) -> DeviceInfo:
        dev = DeviceInfo()
        usb_mode, usb_id = self.scan_usb()
        dev.usb_id = usb_id
        dev.mode = usb_mode

        if usb_mode == DeviceMode.ABSENT:
            return dev

        has_tools = self.has_idevice_tools()

        if usb_mode == DeviceMode.DFU:
            if has_tools:
                dev.udid = self.get_idevice_id()
            return dev

        if usb_mode in (DeviceMode.RECOVERY, DeviceMode.UNKNOWN):
            if has_tools:
                try:
                    result = subprocess.run(
                        ["idevicerestore", "-l", "-n", "-y"],
                        capture_output=True, text=True, timeout=10
                    )
                    for line in result.stdout.splitlines():
                        if "ECID:" in line:
                            dev.ecid = line.split(":")[-1].strip()
                        elif "Identified device as" in line:
                            dev.product_type = line.split("as")[-1].strip().split(",")[0]
                        elif "device serial number is" in line:
                            dev.serial = line.split("is")[-1].strip()
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
            return dev

        if not has_tools:
            return dev

        device_id = self.get_idevice_id()
        dev.udid = device_id

        if device_id:
            lockdown_ok = self.check_lockdownd()
            if not lockdown_ok and usb_mode == DeviceMode.NORMAL:
                dev.mode = DeviceMode.BOOTLOOP
                return dev
            info = self.get_idevice_info()
            dev.raw = info
            dev.product_version = info.get("ProductVersion")
            dev.product_type = info.get("ProductType")
            dev.build = info.get("BuildVersion")
            dev.device_name = info.get("DeviceName")
            dev.model = info.get("HardwareModel")
            dev.activation_state = info.get("ActivationState")
            dev.serial = info.get("SerialNumber")
            dev.ecid = info.get("UniqueChipID")
            if "BatteryCurrentCapacity" in info:
                try:
                    dev.battery_level = int(info["BatteryCurrentCapacity"])
                except ValueError:
                    pass
        else:
            if usb_mode == DeviceMode.NORMAL:
                dev.mode = DeviceMode.BOOTLOOP

        return dev


def format_device_info(dev: DeviceInfo) -> str:
    from rich.table import Table
    from rich.text import Text

    mode_colors = {
        DeviceMode.NORMAL: "green",
        DeviceMode.RECOVERY: "yellow",
        DeviceMode.DFU: "red",
        DeviceMode.BOOTLOOP: "red",
        DeviceMode.ABSENT: "dim",
        DeviceMode.UNKNOWN: "yellow",
    }

    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column("Key", style="bold cyan", no_wrap=True)
    table.add_column("Value", style="white")

    mode_text = Text(dev.mode.value.upper(), style=mode_colors.get(dev.mode, "white"))
    table.add_row("Mode", mode_text)

    if dev.udid:
        table.add_row("UDID", dev.udid)
    if dev.ecid:
        table.add_row("ECID", dev.ecid)
    if dev.product_type:
        table.add_row("Model", f"{dev.product_type} ({dev.model or '?'})")
    if dev.product_version:
        table.add_row("iOS", f"{dev.product_version} ({dev.build or '?'})")
    if dev.device_name:
        table.add_row("Name", dev.device_name)
    if dev.serial:
        table.add_row("Serial", dev.serial)
    if dev.activation_state:
        table.add_row("Activation", dev.activation_state)
    if dev.battery_level is not None:
        table.add_row("Battery", f"{dev.battery_level}%")
    if dev.usb_id:
        table.add_row("USB PID", f"0x{dev.usb_id}")

    return table
