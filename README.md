# ifix-ios

> **Terminal-based iOS device recovery tool** — Detect, diagnose, and fix iPhone/iPad problems directly from your terminal.

`ifix-ios` is an open-source command-line tool that helps you recover iOS devices that are stuck in boot-loops, frozen on the Apple logo, or unresponsive after a failed update. It wraps industry-standard tools like `idevicerestore` and `libimobiledevice` into a user-friendly interface with both a **CLI** (command-line) and **TUI** (interactive terminal UI) mode.

---

## ✨ Features

- **Device detection** — Automatically detects the state of any connected iOS device:
  - `NORMAL` — Working normally
  - `RECOVERY` — In recovery mode (cable + laptop icon)
  - `DFU` — In DFU mode (black screen)
  - `BOOTLOOP` — Stuck at Apple logo, keeps restarting
  - `ABSENT` — Not connected
- **Smart auto-fix** — `ifix-ios fix` analyzes the problem and recommends the best action
- **Update mode** — Reinstalls iOS **preserving all your data** (same as Finder/iTunes update)
- **Erase restore** — Full wipe and clean install (solves almost all software issues)
- **Real-time progress** — Live progress bars for download, verification, and restore phases
- **Interactive TUI** — Full terminal UI with keyboard navigation for guided recovery
- **Live monitoring** — Watch device state changes in real time
- **Mock simulator** — Built-in mock device mode for testing without a real iPhone
- **Cross-platform** — Works on Linux and Windows (WSL2)

---

## 📋 Prerequisites

### Linux (Fedora / RHEL / Debian / Ubuntu / Arch)

The tool relies on these system packages that interface with iOS devices over USB:

| Package | Purpose |
|---------|---------|
| `idevicerestore` | Firmware restore engine |
| `libimobiledevice-utils` | Device detection and info (`idevice_id`, `ideviceinfo`) |
| `usbmuxd` | USB multiplexing daemon for iOS devices |
| `libusb` | Low-level USB communication |

**Fedora / RHEL:**
```bash
sudo dnf install idevicerestore libimobiledevice-utils usbmuxd
```

**Debian / Ubuntu:**
```bash
sudo apt install idevicerestore libimobiledevice-utils usbmuxd
```

**Arch Linux:**
```bash
sudo pacman -S idevicerestore libimobiledevice usbmuxd
```

### Windows (WSL2)

> `ifix-ios` runs inside **WSL2 (Windows Subsystem for Linux)** with USB passthrough.

1. Install [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) with an Ubuntu or Fedora distro
2. Install [usbipd-win](https://github.com/dorssel/usbipd-win) for USB device sharing:
   ```powershell
   winget install usbipd
   ```
3. Attach your iPhone via USB to WSL2:
   ```powershell
   # In Windows PowerShell (Admin)
   usbipd list                       # Find your iPhone's bus ID
   usbipd bind --busid <BUSID>       # Share the device
   usbipd attach --wsl --busid <BUSID>  # Attach to WSL2
   ```
4. Inside WSL2, install the Linux prerequisites (see above) and `ifix-ios`

---

## 🚀 Installation

```bash
pip install ifix-ios
```

**Or install from source:**
```bash
git clone https://github.com/anthra123x/ifix-ios.git
cd ifix-ios
pip install -e .
```

---

## 🎮 Usage

### Quick start

```bash
# 1. Connect your iPhone via USB
# 2. Detect device state
ifix-ios detect

# 3. If stuck on Apple logo or boot-loop, run auto-fix
ifix-ios fix

# 4. Or launch the interactive TUI
ifix-ios tui
```

### Commands

#### `ifix-ios detect`

Detects the connected iOS device and shows its current state, model, iOS version, and more.

```
$ ifix-ios detect
  Mode       NORMAL
  UDID       00008140-000964203629801C
  ECID       2643364300816412
  Model      iPhone17,2 (D94AP)
  iOS        26.5.2 (23F84)
  Name       My iPhone
  Serial     M9KXNV6M2V
  Activation Unactivated
  Battery    85%
  USB PID    0x12a8
```

#### `ifix-ios update`

Downloads and installs the latest signed iOS firmware **without erasing user data**. Use this when your device is stuck on the Apple logo after an update.

```bash
ifix-ios update
```

If sudo is required on your system:
```bash
ifix-ios update -p "your_sudo_password"
```

#### `ifix-ios restore`

Performs a **full erase restore** — wipes everything and installs a clean copy of iOS. This is the most reliable fix for software-related boot failures.

```bash
ifix-ios restore
```

You will be prompted for confirmation before proceeding.

#### `ifix-ios fix`

The **smart auto-fix** mode. It automatically:
1. Detects the device state
2. Analyzes the problem
3. Recommends and executes the best action

```bash
ifix-ios fix
```

| Detected State | Recommended Action |
|----------------|-------------------|
| `NORMAL` | Nothing (device is healthy) |
| `BOOTLOOP` | Update (preserves data) |
| `RECOVERY` | Update or erase restore |
| `DFU` | Erase restore (required) |

#### `ifix-ios monitor`

Continuously watches the device state and refreshes every second. Press `Ctrl+C` to stop.

```bash
ifix-ios monitor
```

#### `ifix-ios tui`

Launches the **Textual-based Terminal User Interface** — a full interactive screen with:
- Live device status panel
- Action buttons (Detect, Update, Erase, Fix)
- Real-time log output
- Progress bar for restore operations

```bash
ifix-ios tui
```

**TUI Keyboard Shortcuts:**
| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Refresh device detection |
| `d` | Detect device |
| `u` | Start update |
| `e` | Start erase restore |

---

## 🧪 Development & Testing

### Mock device simulator

Test `ifix-ios` without a real iPhone by using the built-in mock device simulator:

```bash
# Simulate a healthy iPhone in normal mode
python dev/mock_device.py normal

# Simulate a device stuck on the Apple logo
python dev/mock_device.py bootloop

# Simulate recovery mode
python dev/mock_device.py recovery

# Simulate DFU mode
python dev/mock_device.py dfu

# Clear mock and restore real device access
python dev/mock_device.py clear
```

After activating a mock mode, run `ifix-ios detect` in another terminal to verify.

### Running tests

```bash
pytest tests/ -v
```

### Development setup

```bash
git clone https://github.com/anthra123x/ifix-ios.git
cd ifix-ios
python3 -m venv dev/venv
source dev/venv/bin/activate
pip install -e ".[dev]"
```

---

## 🏗 Project Structure

```
ifix-ios/
├── README.md                  # This file
├── LICENSE                    # MIT License
├── pyproject.toml             # Python packaging
├── Makefile                   # Common commands
├── src/ifix_ios/
│   ├── __main__.py            # python -m ifix_ios
│   ├── app.py                 # CLI mode (click)
│   ├── tui_app.py             # TUI mode (textual)
│   └── core/
│       ├── detector.py        # Device state detection engine
│       └── restore.py         # idevicerestore wrapper with progress
├── dev/
│   └── mock_device.py         # Device simulator for testing
└── tests/
    ├── test_detector.py       # Unit tests for device detection
    └── test_restore.py        # Unit tests for restore engine
```

---

## ⚙️ How It Works

1. **Detection** — `detector.py` scans USB devices using `lsusb` to find Apple devices (vendor ID `0x05ac`). It identifies the mode by the USB product ID:
   - `0x12a8` → Normal mode
   - `0x1281` → Recovery mode
   - `0x1227` → DFU mode
   
   For normal mode, it also checks if `lockdownd` (the iOS lockdown service) is reachable. If USB is visible but lockdownd isn't responding, the device is in a boot-loop.

2. **Restore** — `restore.py` wraps `idevicerestore` and parses its real-time output to provide progress bars and status updates. It supports two operations:
   - **Update** (`-l -y`): Reinstalls iOS without touching user data
   - **Erase** (`-l -y -e`): Full wipe and clean install

3. **CLI** — Built with `click` for robust command-line argument parsing and help messages.

4. **TUI** — Built with `textual` for a full terminal UI experience with reactive widgets.

---

## 🛠 Troubleshooting

**"idevicerestore not found"**
```bash
# Fedora
sudo dnf install idevicerestore

# Ubuntu/Debian
sudo apt install idevicerestore
```

**"Device not detected"**
- Make sure your iPhone is connected via USB
- Try a different cable (USB-C to USB-C or USB-A)
- On WSL2, ensure USB passthrough is configured with `usbipd`
- Restart `usbmuxd`: `sudo systemctl restart usbmuxd`

**"Permission denied" when accessing USB**
```bash
# Add yourself to the plugdev group
sudo usermod -aG plugdev $USER
# Log out and back in
```

**"Could not connect to lockdownd"**
The device is either in recovery/DFU mode or stuck in a boot-loop. Run `ifix-ios fix` to auto-detect and resolve.

---

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Open [issues](https://github.com/anthra123x/ifix-ios/issues) for bugs or feature requests
- Submit [pull requests](https://github.com/anthra123x/ifix-ios/pulls) with improvements
- Improve documentation and tests

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

This tool builds on the excellent work of:
- [libimobiledevice](https://libimobiledevice.org/) — Cross-platform library for iOS device communication
- [idevicerestore](https://github.com/libimobiledevice/idevicerestore) — Firmware restore tool
- [Textual](https://textual.textualize.io/) — Python TUI framework
- [Rich](https://rich.readthedocs.io/) — Terminal formatting library
- [Click](https://click.palletsprojects.com/) — CLI toolkit
