import os
import re
import subprocess
import sys
from pathlib import Path


DISTRO_PACKAGES = {
    "fedora": {
        "packages": ["idevicerestore", "libimobiledevice-utils", "usbmuxd"],
        "cmd": ["dnf", "install", "-y"],
    },
    "rhel": {
        "packages": ["idevicerestore", "libimobiledevice-utils", "usbmuxd"],
        "cmd": ["dnf", "install", "-y"],
    },
    "centos": {
        "packages": ["idevicerestore", "libimobiledevice-utils", "usbmuxd"],
        "cmd": ["dnf", "install", "-y"],
    },
    "ubuntu": {
        "packages": ["idevicerestore", "libimobiledevice-utils", "usbmuxd"],
        "cmd": ["apt", "install", "-y"],
    },
    "debian": {
        "packages": ["idevicerestore", "libimobiledevice-utils", "usbmuxd"],
        "cmd": ["apt", "install", "-y"],
    },
    "arch": {
        "packages": ["idevicerestore", "libimobiledevice", "usbmuxd"],
        "cmd": ["pacman", "-S", "--noconfirm"],
    },
    "manjaro": {
        "packages": ["idevicerestore", "libimobiledevice", "usbmuxd"],
        "cmd": ["pacman", "-S", "--noconfirm"],
    },
    "opensuse": {
        "packages": ["idevicerestore", "libimobiledevice-utils", "usbmuxd"],
        "cmd": ["zypper", "install", "-y"],
    },
}


CACHE_FILE = Path.home() / ".cache" / "ifix-ios" / "deps_installed"


def detect_distro() -> str | None:
    try:
        result = subprocess.run(
            ["cat", "/etc/os-release"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            m = re.match(r'^ID=(\w+)', line)
            if m:
                return m.group(1).lower()
            m = re.match(r'^ID="(\w+)"', line)
            if m:
                return m.group(1).lower()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    try:
        result = subprocess.run(
            ["lsb_release", "-i", "-s"],
            capture_output=True, text=True, timeout=5
        )
        name = result.stdout.strip().lower()
        if name:
            return name
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


def get_distro_config(distro: str | None) -> dict | None:
    if not distro:
        return None
    for key, config in DISTRO_PACKAGES.items():
        if key in distro:
            return config

    fedora_like = Path("/etc/fedora-release")
    debian_like = Path("/etc/debian_version")
    arch_like = Path("/etc/arch-release")

    if fedora_like.exists():
        return DISTRO_PACKAGES["fedora"]
    if debian_like.exists():
        return DISTRO_PACKAGES["debian"]
    if arch_like.exists():
        return DISTRO_PACKAGES["arch"]

    return None


def check_command(cmd: str) -> bool:
    try:
        args = [cmd, "--version"] if cmd != "lsusb" else [cmd]
        subprocess.run(args, capture_output=True, timeout=3)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def are_deps_installed() -> bool:
    if CACHE_FILE.exists():
        return True
    needed = ["idevicerestore", "idevice_id", "ideviceinfo"]
    installed = all(check_command(c) for c in needed)
    if installed:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text("1")
        return True
    return False


def clear_cache():
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()


def install_deps(sudo_password: str | None = None) -> bool:
    distro = detect_distro()
    config = get_distro_config(distro)

    if not config:
        print("Could not detect your Linux distribution.")
        print("Please install manually:")
        print("  Fedora:  sudo dnf install idevicerestore libimobiledevice-utils usbmuxd")
        print("  Ubuntu:  sudo apt install idevicerestore libimobiledevice-utils usbmuxd")
        print("  Arch:    sudo pacman -S idevicerestore libimobiledevice usbmuxd")
        return False

    cmd = ["sudo"] + config["cmd"] + config["packages"]

    print(f"Detected: {distro}")
    print(f"Installing: {' '.join(config['packages'])}")
    print("This requires sudo access.")

    try:
        if sudo_password:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            assert proc.stdin is not None
            proc.stdin.write(sudo_password + "\n")
            proc.stdin.flush()
            proc.stdin.close()
        else:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

        assert proc.stdout is not None
        for line in proc.stdout:
            print(f"  {line.strip()}")
        proc.wait()

        if proc.returncode == 0:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            CACHE_FILE.write_text("1")
            print("\n✓ Dependencies installed successfully!")
            return True
        else:
            print(f"\n✗ Installation failed (exit code {proc.returncode})")
            return False

    except FileNotFoundError:
        print("Error: sudo not found. Are you on Linux?")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def ensure_deps(sudo_password: str | None = None) -> bool:
    if are_deps_installed():
        return True

    print("\n" + "=" * 50)
    print("  ifix-ios needs system dependencies to work.")
    print("  These will be installed via your package manager.")
    print("=" * 50 + "\n")

    if install_deps(sudo_password):
        return True

    print("\nYou can also install manually and then run:")
    print("  ifix-ios setup")
    return False
