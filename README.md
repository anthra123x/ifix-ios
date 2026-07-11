# ifix-ios

<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0-blue" alt="Version 0.1.0">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License MIT">
  <img src="https://img.shields.io/badge/python-3.12%2B-brightgreen" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/platform-linux%20%7C%20windows%20(wsl2)-lightgrey" alt="Platform: Linux | Windows (WSL2)">
</p>

**ifix-ios** es una herramienta de terminal todo-en-uno para diagnosticar y reparar dispositivos iOS (iPhone/iPad) con problemas de software — logo de Apple congelado, boot-loop, modo recovery, modo DFU, pantalla negra tras actualización.

Solo escribes `ifix-ios` y se abre una **interfaz interactiva** tipo `htop`/`btop`. Detecta el dispositivo, te dice qué versión de iOS necesita y te guía paso a paso para repararlo.

---

## 🚀 Flujo de trabajo típico

### 1. Instalar (una sola vez)

```bash
pip install ifix-ios
```

### 2. Conectar el iPhone por USB y ejecutar

```bash
ifix-ios
```

Esto abre la **TUI interactiva**. El tool detecta automáticamente el estado del dispositivo cada 2 segundos y te muestra en pantalla:

### 3. La TUI te guía

```
┌── DISPOSITIVO ──   │ 10:58:18 ⚠ RECOVERY                  ┐
│  Estado:   ⚠ RECOVERY│ 10:58:18 iPhone 16 Pro Max          │
│  Nombre:   iPhone...  │ 10:58:18 ── Guía paso a paso ──     │
│  Modelo:   iPhone17,2 │ 10:58:18 📱 iPhone 16 Pro Max       │
│  iOS:      26.5.2     │ 10:58:18 ⚠ MODO RECUPERACIÓN       │
│  UDID:     0000..     │ 10:58:18 📋 Plan de acción:        │
│  ECID:     2644..     │ 10:58:18 [1] Update (preserva datos)│
│ ── ACCIONES ──        │ 10:58:18 [2] Erase Restore          │
│  D  Detectar          │ 10:58:18 ─────────────────────────   │
│  U  Update (datos)    │                                     │
│  E  Erase (borra todo)│ Versión firmada: 26.5.2 (23F84)     │
│  G  Guía paso a paso  │                                     │
│  F  Auto Fix          │━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 0%  │
│  Q  Salir             │                                     │
├─────────────────────────────────────────────────────────────┤
│ ⚠ RECOVERY — iPhone 16 Pro Max │ q d u e f g               │
└─────────────────────────────────────────────────────────────┘
```

### 4. Elegir acción

| Tecla | Acción | Qué hace |
|-------|--------|----------|
| `U` | Update | Reinstala iOS **sin borrar datos** |
| `E` | Erase Restore | Borra todo e instala iOS limpio |
| `F` | Auto Fix | Detecta el problema y aplica la mejor solución |
| `G` | Guide | Muestra diagnóstico y guía paso a paso |
| `D` | Detect | Refresca detección manualmente |
| `S` | Setup | Instala dependencias del sistema |
| `Q` | Quit | Salir |

> El tool **busca automáticamente** la última versión de iOS firmada por Apple
> para tu modelo desde [ipsw.me](https://ipsw.me) y la muestra en pantalla.

---

## 📋 Guía por estado del dispositivo

### 🔴 Boot-loop (logo de Apple reiniciándose)

```
📱 iPhone 16 Pro Max (iPhone17,2)
📦 Versión actual: 26.5.2

✗ BOOT-LOOP
  El dispositivo se reinicia constantemente en el logo de Apple.

📋 Plan de acción:
  [1] U  Update — Reinstala iOS sin borrar datos (RECOMENDADO)
  [2] E  Erase Restore — Si el update no funciona
  [3] D  Force Recovery — Forzar modo recovery manualmente

  Recomendación: Conecta el cable, pon el dispositivo en Recovery
  (subir/bajar volumen rápido, luego hold botón lateral)
  y ejecuta Update.

Última versión firmada por Apple: 26.5.2 (23F84)
```

### 🟡 Recovery Mode (icono de cable + laptop)

```
📱 iPhone 16 Pro Max (iPhone17,2)

⚠ MODO RECUPERACIÓN
  Causas posibles: actualización fallida, jailbreak, corrupción.

📋 Plan de acción:
  [1] U  Update — Reinstala iOS sin borrar datos (RECOMENDADO)
  [2] E  Erase Restore — Borra todo e instala iOS limpio
```

### 🔴 DFU Mode (pantalla negra)

```
📱 iPhone 16 Pro Max (iPhone17,2)

!! MODO DFU
  La pantalla está completamente negra.

📋 Plan de acción:
  [1] E  Erase Restore — Única opción disponible
  ⚠ Se borrarán TODOS los datos del dispositivo.
```

### 🟢 Normal (funciona correctamente)

```
📱 iPhone 16 Pro Max (iPhone17,2)

✓ Dispositivo funcionando correctamente.
  No requiere reparación.
```

---

## 🧪 Modo simulado (pruebas sin iPhone real)

```bash
# Simular cada modo en terminales separadas
python dev/mock_device.py normal
python dev/mock_device.py bootloop
python dev/mock_device.py recovery
python dev/mock_device.py dfu
```

---

## 🔧 Instalación manual de dependencias

Si el auto-setup falla, instala manualmente:

```bash
# Fedora
sudo dnf install idevicerestore libimobiledevice-utils usbmuxd

# Ubuntu/Debian
sudo apt install idevicerestore libimobiledevice-utils usbmuxd

# Arch
sudo pacman -S idevicerestore libimobiledevice usbmuxd
```

---

## 📦 Características

- **TUI profesional** tipo htop/btop — `ifix-ios` abre la interfaz directamente
- **Detección automática** cada 2 segundos (conecta/desconecta sin reiniciar)
- **Guía paso a paso** según el modo detectado
- **Consulta de firmware** vía ipsw.me API — muestra la última versión firmada
- **Update** — Reinstala iOS sin eliminar datos
- **Erase Restore** — Borrado completo + instalación limpia
- **Auto Fix** — Diagnóstico inteligente + mejor acción automática
- **Setup automático** de dependencias del sistema
- **Cache de firmware** (6 horas) para respuestas rápidas sin internet
- **Multiplataforma**: Linux nativo + Windows WSL2

---

## 🏗 Arquitectura

```
ifix-ios/
├── src/ifix_ios/
│   ├── app.py              # CLI con Click (ifix-ios detect/update/...)
│   ├── tui_app.py           # TUI interactiva con Textual
│   ├── ifix_ios.tcss        # Estilos CSS para la TUI
│   └── core/
│       ├── detector.py      # Detección USB (pyusb + lsusb)
│       ├── restore.py       # Wrapper de idevicerestore
│       ├── firmware.py      # Consulta de versiones iOS (ipsw.me)
│       └── installer.py     # Instalador automático de deps
├── dev/mock_device.py       # Simulador para pruebas
└── tests/
    ├── test_detector.py
    └── test_restore.py
```

---

## 📄 Licencia

**MIT License** — Copyright © 2026 [anthra123x](https://github.com/anthra123x)
