# ifix-ios

<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0-blue" alt="Version 0.1.0">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License MIT">
  <img src="https://img.shields.io/badge/python-3.12%2B-brightgreen" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/platform-linux%20%7C%20windows%20(wsl2)-lightgrey" alt="Platform: Linux | Windows (WSL2)">
</p>

**ifix-ios** es una herramienta de terminal diseñada para diagnosticar y reparar dispositivos iOS (iPhone / iPad) que presentan fallos de software: pantalla negra con el logo de Apple, boot-loop tras una actualización, modo recuperación o DFU.

Ofrece una interfaz **CLI** (línea de comandos) y una **TUI** (interfaz interactiva de terminal) construida con [Textual](https://textual.textualize.io/), permitiendo tanto a usuarios avanzados como principiantes recuperar sus dispositivos sin depender de Finder, iTunes ni una Mac.

---

## 📦 Características

- **Detección inteligente** del estado del dispositivo en 5 modos posibles:
  - `NORMAL` — Funcionamiento correcto
  - `RECOVERY` — Modo recuperación (icono de cable + laptop)
  - `DFU` — Modo DFU (pantalla completamente negra)
  - `BOOTLOOP` — Atascado en el logo de Apple con reinicios constantes
  - `ABSENT` — No se detecta ningún dispositivo
- **Actualización (update)** — Reinstala iOS sin eliminar datos del usuario
- **Restauración completa (erase)** — Borra todo el dispositivo e instala iOS limpio
- **Auto-reparación** — `ifix-ios fix` analiza el problema y ejecuta la mejor solución automáticamente
- **Barras de progreso en tiempo real** durante descarga, verificación y restauración del firmware
- **Monitor en vivo** — Observa los cambios de estado del dispositivo segundo a segundo
- **Modo simulador** — Entorno de pruebas integrado sin necesidad de un iPhone real
- **Multiplataforma** — Funciona en Linux nativo y Windows a través de WSL2

---

## 🔧 Requisitos del sistema

### Linux (Fedora / RHEL / Debian / Ubuntu / Arch)

| Paquete | Propósito |
|---------|-----------|
| `idevicerestore` | Motor de restauración de firmware iOS |
| `libimobiledevice-utils` | Detección e información del dispositivo |
| `usbmuxd` | Multiplexor USB para comunicación con iOS |
| `libusb` | Comunicación USB de bajo nivel |

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

> ifix-ios se ejecuta dentro de **WSL2** con paso de dispositivos USB.

1. Instala [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) con una distribución Ubuntu o Fedora
2. Instala [usbipd-win](https://github.com/dorssel/usbipd-win) para compartir dispositivos USB:
   ```powershell
   winget install usbipd
   ```
3. Conecta tu iPhone y compártelo con WSL2:
   ```powershell
   # En Windows PowerShell (como administrador)
   usbipd list                         # Identifica el bus ID del iPhone
   usbipd bind --busid <BUSID>         # Comparte el dispositivo
   usbipd attach --wsl --busid <BUSID> # Conecta a WSL2
   ```

---

## 🚀 Instalación

```bash
pip install ifix-ios
```

**O desde el código fuente:**
```bash
git clone https://github.com/anthra123x/ifix-ios.git
cd ifix-ios
pip install -e .
```

---

## 🎮 Uso

### Inicio rápido

```bash
# 1. Conecta tu iPhone por USB
# 2. Detecta el estado del dispositivo
ifix-ios detect

# 3. Si está atascado en el logo o en boot-loop, ejecuta auto-reparación
ifix-ios fix

# 4. O lanza la interfaz interactiva
ifix-ios tui
```

### Comandos

---

#### `ifix-ios detect`

Detecta el dispositivo iOS conectado y muestra su estado, modelo, versión de iOS e información relevante.

```
$ ifix-ios detect
  Modo       NORMAL
  UDID       00008140-000964203629801C
  ECID       2643364300816412
  Modelo     iPhone17,2 (D94AP)
  iOS        26.5.2 (23F84)
  Nombre     Mi iPhone
  Serial     M9KXNV6M2V
  Activación Sin activar
  Batería    85%
  USB PID    0x12a8
```

**Estados detectables:**

| Indicador | Significado |
|-----------|-------------|
| `NORMAL` | Dispositivo funcionando correctamente |
| `RECOVERY` | Modo recuperación — icono de cable y laptop en pantalla |
| `DFU` | Modo DFU — pantalla negra, no hay comunicación con lockdown |
| `BOOTLOOP` | USB visible pero lockdownd no responde — atascado en el logo |
| `ABSENT` | No hay ningún dispositivo Apple conectado |

---

#### `ifix-ios update`

Descarga e instala la última versión de iOS firmada por Apple **sin eliminar los datos del usuario**. Es la opción recomendada cuando el dispositivo se queda con el logo de Apple tras una actualización fallida.

```bash
ifix-ios update
```

Si el sistema requiere sudo:
```bash
ifix-ios update -p "tu_contraseña_sudo"
```

---

#### `ifix-ios restore`

Realiza una **restauración completa del dispositivo** — elimina todos los datos y aplicaciones e instala una copia limpia de iOS. Esta es la opción más efectiva para resolver problemas de software graves.

```bash
ifix-ios restore
```

El sistema solicitará confirmación antes de proceder.

---

#### `ifix-ios fix`

**Modo de auto-reparación inteligente.** Analiza automáticamente el estado del dispositivo y ejecuta la mejor acción disponible sin intervención manual.

```bash
ifix-ios fix
```

| Estado detectado | Acción recomendada |
|------------------|-------------------|
| `NORMAL` | No requiere acción (dispositivo sano) |
| `BOOTLOOP` | Actualización (conserva datos) |
| `RECOVERY` | Actualización o restauración completa |
| `DFU` | Restauración completa (obligatorio) |

---

#### `ifix-ios monitor`

Monitorea el estado del dispositivo en tiempo real, actualizando la información cada segundo. Presiona `Ctrl+C` para detener.

```bash
ifix-ios monitor
```

---

#### `ifix-ios tui`

Inicia la **interfaz de usuario de terminal** construida con Textual. Proporciona una experiencia visual completa con:

- Panel de estado del dispositivo en vivo
- Botones de acción (Detectar, Actualizar, Restaurar, Reparar)
- Registro de eventos en tiempo real
- Barra de progreso para operaciones de restauración

```bash
ifix-ios tui
```

**Atajos de teclado en la TUI:**

| Tecla | Acción |
|-------|--------|
| `q` | Salir |
| `r` | Refrescar detección |
| `d` | Detectar dispositivo |
| `u` | Iniciar actualización |
| `e` | Iniciar restauración completa |

---

## 🧪 Desarrollo y pruebas

### Simulador de dispositivo

El proyecto incluye un simulador integrado que permite probar todas las funcionalidades sin necesidad de un iPhone real.

```bash
# Simular un iPhone en modo normal
python dev/mock_device.py normal

# Simular un dispositivo atascado en el logo de Apple
python dev/mock_device.py bootloop

# Simular modo recuperación
python dev/mock_device.py recovery

# Simular modo DFU
python dev/mock_device.py dfu

# Limpiar el entorno simulado
python dev/mock_device.py clear
```

Después de activar un modo simulado, ejecuta `ifix-ios detect` en otra terminal para verificar.

### Ejecutar pruebas

```bash
pytest tests/ -v
```

### Entorno de desarrollo

```bash
git clone https://github.com/anthra123x/ifix-ios.git
cd ifix-ios
python3 -m venv dev/venv
source dev/venv/bin/activate
pip install -e ".[dev]"
```

---

## 🏗 Arquitectura del proyecto

```
ifix-ios/
├── README.md                      # Documentación principal
├── LICENSE                        # Licencia MIT
├── pyproject.toml                 # Configuración del paquete Python
├── Makefile                       # Comandos de utilidad
├── src/ifix_ios/
│   ├── __main__.py                # Punto de entrada (python -m ifix_ios)
│   ├── app.py                     # Modo CLI con Click
│   ├── tui_app.py                 # Modo TUI con Textual
│   └── core/
│       ├── detector.py            # Motor de detección de estados
│       └── restore.py             # Wrapper de idevicerestore con progreso
├── dev/
│   └── mock_device.py             # Simulador de dispositivos para pruebas
└── tests/
    ├── test_detector.py           # Pruebas unitarias de detección
    └── test_restore.py            # Pruebas unitarias de restauración
```

---

## ⚙️ Funcionamiento interno

1. **Detección** — `detector.py` escanea el bus USB con `lsusb` en busca de dispositivos Apple (vendor ID `0x05ac`). Identifica el modo mediante el ID de producto USB:
   - `0x12a8` → Modo normal
   - `0x1281` → Modo recuperación
   - `0x1227` → Modo DFU
   
   En modo normal, verifica adicionalmente si el servicio `lockdownd` de iOS responde. Si el USB es visible pero lockdownd no responde, el dispositivo está en boot-loop.

2. **Restauración** — `restore.py` ejecuta `idevicerestore` como subproceso y analiza su salida en tiempo real para proporcionar barras de progreso y mensajes de estado. Soporta dos operaciones:
   - **Update** (`-l -y`): Reinstala iOS sin tocar los datos del usuario
   - **Erase** (`-l -y -e`): Borrado completo e instalación limpia

3. **CLI** — Implementada con [Click](https://click.palletsprojects.com/) para manejo robusto de argumentos, opciones y mensajes de ayuda.

4. **TUI** — Implementada con [Textual](https://textual.textualize.io/) para una experiencia de terminal interactiva con widgets reactivos.

---

## 🛠 Solución de problemas

**"idevicerestore no encontrado"**
```bash
# Fedora
sudo dnf install idevicerestore

# Ubuntu/Debian
sudo apt install idevicerestore
```

**"El dispositivo no se detecta"**
- Verifica que el iPhone esté conectado por USB
- Prueba con otro cable (USB-C a USB-C o USB-A)
- En WSL2, asegúrate de haber configurado el paso USB con `usbipd`
- Reinicia `usbmuxd`: `sudo systemctl restart usbmuxd`

**"Permiso denegado" al acceder al USB**
```bash
# Agrega tu usuario al grupo plugdev
sudo usermod -aG plugdev $USER
# Cierra sesión y vuelve a iniciarla
```

**"Could not connect to lockdownd"**
El dispositivo está en modo recuperación, DFU o atascado en boot-loop. Ejecuta `ifix-ios fix` para detectar y resolver automáticamente.

---

## 🤝 Cómo contribuir

Las contribuciones son bienvenidas. Puedes:
- Reportar errores o solicitar funciones en [issues](https://github.com/anthra123x/ifix-ios/issues)
- Enviar mejoras mediante [pull requests](https://github.com/anthra123x/ifix-ios/pulls)
- Mejorar la documentación y las pruebas

---

## 📄 Licencia

**MIT License** — Copyright © 2026 [anthra123x](https://github.com/anthra123x)

Consulta el archivo [LICENSE](LICENSE) para más detalles.

---

## 🙏 Agradecimientos

Esta herramienta se basa en el excelente trabajo de:
- [libimobiledevice](https://libimobiledevice.org/) — Biblioteca multiplataforma para comunicación con dispositivos iOS
- [idevicerestore](https://github.com/libimobiledevice/idevicerestore) — Herramienta de restauración de firmware
- [Textual](https://textual.textualize.io/) — Framework TUI para Python
- [Rich](https://rich.readthedocs.io/) — Biblioteca de formato para terminal
- [Click](https://click.palletsprojects.com/) — Toolkit para interfaces de línea de comandos
