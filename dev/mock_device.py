#!/usr/bin/env python3
"""
Mock iOS Device Simulator for ifix-ios development.

Creates a simulated device environment to test ifix-ios without
a physical iPhone/iPad connected. Intercepts lsusb and
libimobiledevice calls by modifying PATH.

Usage:
  # Normal mode
  python dev/mock_device.py normal

  # Recovery mode
  python dev/mock_device.py recovery

  # DFU mode
  python dev/mock_device.py dfu

  # Boot-loop (device visible but lockdownd not responding)
  python dev/mock_device.py bootloop

  # Clear mock and return to normal
  python dev/mock_device.py clear

Use while running ifix-ios commands in another terminal.
"""

import argparse
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

MOCK_BIN_DIR = Path("/tmp/ifix-ios-mock-bin")

DEVICE_INFO_TEMPLATES = {
    "normal": {
        "usb_line": "Bus 001 Device 042: ID 05ac:12a8 Apple, Inc. iPhone 5/5C/5S/6/SE/7/8/X/XR",
        "device_id": "0000MOCK-1234567890123456",
        "device_info": """ActivationState: Unactivated
ActivationStateAcknowledged: true
BasebandActivationTicketVersion: V2
BasebandCertId: 1652214800
BasebandChipID: 2814177
BasebandStatus: BBInfoAvailable
BasebandVersion: 2.60.00
BluetoothAddress: 00:11:22:33:44:55
BuildVersion: 23F84
DeviceClass: iPhone
DeviceColor: 1
DeviceName: Mock iPhone
EthernetAddress: 00:11:22:33:44:66
HardwareModel: D94AP
ModelNumber: MOCK16PRO
ProductType: iPhone17,2
ProductVersion: 26.5.2
SerialNumber: MOCKMOCKMOCK
UniqueChipID: 2643364300816412
UniqueDeviceID: 0000MOCK-1234567890123456
WiFiAddress: 00:11:22:33:44:77
BatteryCurrentCapacity: 85
""",
    },
    "recovery": {
        "usb_line": "Bus 001 Device 042: ID 05ac:1281 Apple, Inc. Apple Mobile Device [Recovery Mode]",
        "device_id": "",
        "device_info": "",
    },
    "dfu": {
        "usb_line": "Bus 001 Device 042: ID 05ac:1227 Apple, Inc. Apple Mobile Device [DFU Mode]",
        "device_id": "",
        "device_info": "",
    },
    "bootloop": {
        "usb_line": "Bus 001 Device 042: ID 05ac:12a8 Apple, Inc. iPhone 5/5C/5S/6/SE/7/8/X/XR",
        "device_id": "0000MOCK-1234567890123456",
        "device_info": "",
        "ideviceinfo_fail": True,
    },
}


def create_mock_lsusb(usb_line: str) -> str:
    return f"""#!/bin/bash
echo "{usb_line}"
"""
IDEVRESTORE_OUTPUT = """idevicerestore 1.0.0 (mock)
Found device in Recovery mode
ECID: 2643364300816412
Identified device as d94ap, iPhone17,2
device serial number is M9KXNV6M2V
Selected firmware 26.5.2 (build 23F84)
Checksum matches.
Variant: Customer Upgrade Install (IPSW)
This restore will update the device without erasing user data.
"""


def create_mock_idevice_id(device_id: str) -> str:
    return f"""#!/bin/bash
echo "{device_id}"
"""


def create_mock_ideviceinfo(info_text: str, fail: bool = False) -> str:
    if fail:
        return """#!/bin/bash
if [ "$1" = "--version" ]; then
    echo "ideviceinfo 1.4.0 (mock)"
    exit 0
fi
echo "ERROR: Could not connect to lockdownd (-12)" >&2
exit 1
"""
    return f"""#!/bin/bash
if [ "$1" = "--version" ]; then
    echo "ideviceinfo 1.4.0 (mock)"
    exit 0
fi
echo "{info_text}"
"""


def create_mock_idevicerestore() -> str:
    return "#!/bin/bash\n" + 'cat << "EOF"\n' + IDEVRESTORE_OUTPUT + "EOF\n"


def install_mocks(mode_data: dict):
    MOCK_BIN_DIR.mkdir(parents=True, exist_ok=True)

    bins = {
        "lsusb": create_mock_lsusb(mode_data["usb_line"]),
        "idevice_id": create_mock_idevice_id(mode_data["device_id"]),
        "ideviceinfo": create_mock_ideviceinfo(
            mode_data["device_info"],
            fail=mode_data.get("ideviceinfo_fail", False),
        ),
        "idevicerestore": create_mock_idevicerestore(),
    }

    for name, content in bins.items():
        path = MOCK_BIN_DIR / name
        path.write_text(content)
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    old_path = os.environ.get("PATH", "")
    if str(MOCK_BIN_DIR) not in old_path:
        new_path = f"{MOCK_BIN_DIR}:{old_path}"
        os.environ["PATH"] = new_path

    shell = os.environ.get("SHELL", "/bin/bash")
    rc_file = Path.home() / (".bashrc" if "bash" in shell else ".zshrc")
    export_line = f'\nexport PATH="{MOCK_BIN_DIR}:$PATH"\n'

    if rc_file.exists():
        current = rc_file.read_text()
        if str(MOCK_BIN_DIR) not in current:
            with open(rc_file, "a") as f:
                f.write(export_line)

    print(f"Mock device installed in {MOCK_BIN_DIR}")
    print(f"PATH updated. Mock mode: {mode_data.get('usb_line', '')}")
    print()
    print("Run in another terminal:")
    print("  ifix-ios detect")
    print("  ifix-ios monitor")
    print()
    print("To restore real device access:")
    print(f"  rm -rf {MOCK_BIN_DIR}")
    print("  # and restart your shell or remove the PATH line from ~/.bashrc")


def clear_mocks():
    if MOCK_BIN_DIR.exists():
        shutil.rmtree(MOCK_BIN_DIR)
        print(f"Removed {MOCK_BIN_DIR}")

    shell = os.environ.get("SHELL", "/bin/bash")
    rc_file = Path.home() / (".bashrc" if "bash" in shell else ".zshrc")
    if rc_file.exists():
        content = rc_file.read_text()
        lines = content.splitlines()
        cleaned = [
            l for l in lines if str(MOCK_BIN_DIR) not in l
        ]
        rc_file.write_text("\n".join(cleaned))
        print(f"Cleaned PATH from {rc_file}")

    print("Mock environment cleared. Restart your shell or run: source ~/.bashrc")


def main():
    parser = argparse.ArgumentParser(description="Mock iOS device for ifix-ios testing")
    parser.add_argument(
        "mode",
        nargs="?",
        default="normal",
        choices=["normal", "recovery", "dfu", "bootloop", "clear"],
        help="Device mode to simulate",
    )
    args = parser.parse_args()

    if args.mode == "clear":
        clear_mocks()
        return

    if args.mode not in DEVICE_INFO_TEMPLATES:
        print(f"Unknown mode: {args.mode}")
        sys.exit(1)

    install_mocks(DEVICE_INFO_TEMPLATES[args.mode])


if __name__ == "__main__":
    main()
