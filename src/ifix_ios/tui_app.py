import threading
from datetime import datetime
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Footer,
    Header,
    Label,
    ProgressBar,
    RichLog,
    Static,
)

from ifix_ios.core.detector import DeviceDetector, DeviceMode, DeviceInfo
from ifix_ios.core.firmware import get_device_guide, device_name, latest_signed
from ifix_ios.core.installer import ensure_deps
from ifix_ios.core.restore import (
    RestoreAction,
    RestoreRunner,
)


MODE_COLORS = {
    DeviceMode.NORMAL: "green",
    DeviceMode.RECOVERY: "yellow",
    DeviceMode.DFU: "red",
    DeviceMode.BOOTLOOP: "red",
    DeviceMode.ABSENT: "gray",
    DeviceMode.UNKNOWN: "yellow",
}

MODE_ICONS = {
    DeviceMode.NORMAL: "✓",
    DeviceMode.RECOVERY: "⚠",
    DeviceMode.DFU: "!!",
    DeviceMode.BOOTLOOP: "✗",
    DeviceMode.ABSENT: "○",
    DeviceMode.UNKNOWN: "?",
}


class DevicePanel(Static):
    device = reactive(DeviceInfo)

    def __init__(self):
        super().__init__("")
        self.device = DeviceInfo()
        self.styles.height = "100%"

    def watch_device(self, dev: DeviceInfo):
        if dev.mode == DeviceMode.ABSENT:
            self.update("")
            return

        color = MODE_COLORS.get(dev.mode, "white")
        icon = MODE_ICONS.get(dev.mode, "?")
        mode_display = f"[{color}]{icon} {dev.mode.value.upper()}[/]"
        lines = [
            "[b]── DISPOSITIVO ──[/b]",
            f"  Estado:   {mode_display}",
        ]
        if dev.device_name:
            lines.append(f"  Nombre:   {dev.device_name}")
        if dev.product_type:
            lines.append(f"  Modelo:   {dev.product_type}")
        if dev.product_version:
            ver = f"{dev.product_version} ({dev.build or '?'})" if dev.build else dev.product_version
            lines.append(f"  iOS:      {ver}")
        if dev.udid:
            lines.append(f"  UDID:     {dev.udid[:24]}...")
        if dev.ecid:
            lines.append(f"  ECID:     {dev.ecid}")
        if dev.serial:
            lines.append(f"  Serial:   {dev.serial}")
        if dev.activation_state:
            lines.append(f"  Activ:    {dev.activation_state}")
        if dev.battery_level is not None:
            bars = "█" * (dev.battery_level // 10) + "░" * (10 - dev.battery_level // 10)
            lines.append(f"  Batería:  {bars} {dev.battery_level}%")
        if dev.usb_id:
            lines.append(f"  USB PID:  0x{dev.usb_id}")
        lines.extend([
            "",
            "[b]── ACCIONES ──[/b]",
            "",
            "  [b cyan]D[/]  Detectar ahora",
            "  [b cyan]U[/]  Update (preserva datos)",
            "  [b cyan]E[/]  Erase restore (borra todo)",
            "  [b cyan]F[/]  Auto Fix",
            "  [b cyan]G[/]  Guía paso a paso",
            "  [b cyan]S[/]  Setup (instalar deps)",
            "  [b cyan]Q[/]  Salir",
            "",
            f"  [green]✓[/]  Normal",
            f"  [yellow]⚠[/]  Recovery / Boot-loop",
            f"  [red]!![/]   DFU",
            f"  [gray]○[/]   No conectado",
        ])
        self.update("\n".join(lines))


class LogPanel(RichLog):
    def __init__(self):
        super().__init__(highlight=True, markup=True, max_lines=500, wrap=True)


class FooterBar(Static):
    def __init__(self):
        super().__init__("")
        self.styles.height = 1


class MainScreen(Screen):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "detect", "Detect"),
        Binding("u", "update", "Update"),
        Binding("e", "erase", "Erase"),
        Binding("f", "fix", "Auto Fix"),
        Binding("g", "guide", "Guide"),
        Binding("s", "setup", "Setup"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Horizontal(
            DevicePanel(),
            Vertical(
                Label("╔═══════════════════════════════════════╗", id="log-header"),
                LogPanel(),
                ProgressBar(total=100, show_eta=False, id="progress"),
                id="right-panel",
            ),
            id="main-content",
        )
        yield FooterBar()
        yield Footer()

    def __init__(self):
        super().__init__()
        self._last_mode: DeviceMode | None = None

    def on_mount(self) -> None:
        self._auto_refresh_interval = self.set_interval(2, self._auto_refresh)
        self.refresh_device()

    def app_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        formatted = f"[dim]{ts}[/] {msg}"
        if threading.get_ident() == self.app._thread_id:
            self._write_log(formatted)
        else:
            self.app.call_from_thread(self._write_log, formatted)

    def _write_log(self, msg: str):
        self.query_one(LogPanel).write(msg)

    def _clear_log(self):
        self.query_one(LogPanel).clear()

    def refresh_device(self):
        self._detect_device()

    def _auto_refresh(self) -> None:
        self._detect_device(quiet=True)

    @work(thread=True)
    def _detect_device(self, quiet: bool = False) -> None:
        detector = DeviceDetector()
        dev = detector.detect()
        self.app.call_from_thread(self._on_detection_complete, dev, quiet)

    def _on_detection_complete(self, dev: DeviceInfo, quiet: bool):
        panel = self.query_one(DevicePanel)
        panel.device = dev

        mode_changed = dev.mode != self._last_mode
        self._last_mode = dev.mode

        if mode_changed:
            self._clear_log()

        if dev.mode == DeviceMode.ABSENT:
            if mode_changed:
                self._write_log("[dim]○ No hay dispositivo conectado[/]")
            self._update_footer(dev)
            return

        color = MODE_COLORS.get(dev.mode, "white")
        icon = MODE_ICONS.get(dev.mode, "?")
        self._write_log(f"[{color}]{icon} [{color}]{dev.mode.value.upper()}[/]")
        if dev.device_name and dev.product_version:
            self._write_log(f"   {dev.device_name} — iOS {dev.product_version}")
        elif not dev.device_name and not dev.product_version:
            self._write_log("[yellow]Info limitada — presiona [cyan]S[/] Setup para batería, nombre e iOS[/]")
        elif dev.device_name:
            self._write_log(f"   {dev.device_name}")

        if mode_changed:
            self.show_guide(dev)

        self._update_footer(dev)

    def show_guide(self, dev: DeviceInfo | None = None):
        if dev is None:
            detector = DeviceDetector()
            dev = detector.detect()
        self._write_log("[bold]── Guía paso a paso ──[/]")
        for line in get_device_guide(dev):
            self._write_log(line)
        self._write_log("[bold]─────────────────────[/]")

    def action_guide(self) -> None:
        logger = self.query_one(LogPanel)
        logger.clear()
        detector = DeviceDetector()
        dev = detector.detect()
        if dev.mode == DeviceMode.ABSENT:
            self._write_log("[dim]○ No hay dispositivo conectado[/]")
            return
        self.show_guide(dev)

    def _update_footer(self, dev: DeviceInfo):
        if dev.mode == DeviceMode.ABSENT:
            self.query_one(FooterBar).update("[gray]○ No conectado[/]")
            return
        color = MODE_COLORS.get(dev.mode, "white")
        icon = MODE_ICONS.get(dev.mode, "?")
        left = f"[{color}]{icon} {dev.mode.value.upper()}[/]"
        if dev.device_name:
            left += f" — {dev.device_name}"
        right = "[dim]Q[/]uit [dim]D[/]etect [dim]U[/]pdate [dim]E[/]rase [dim]F[/]ix [dim]G[/]uide [dim]S[/]etup"
        self.query_one(FooterBar).update(f"{left}  │  {right}")

    def action_detect(self) -> None:
        self._detect_device(quiet=False)

    @work(thread=True)
    def action_update(self) -> None:
        self._run_restore_workflow(RestoreAction.UPDATE)

    @work(thread=True)
    def action_erase(self) -> None:
        self._run_restore_workflow(RestoreAction.ERASE)

    @work(thread=True)
    def action_setup(self) -> None:
        self.app_log("[yellow]▶ Instalando dependencias...[/]")
        try:
            ok = ensure_deps()
        except Exception as e:
            self.app_log(f"[red]✗ Error: {e}[/]")
            return
        if ok:
            self.app_log("[green]✓ Dependencias instaladas[/]")
            detector = DeviceDetector()
            dev = detector.detect()
            self.app.call_from_thread(self._on_detection_complete, dev, False)
        else:
            self.app_log("[red]✗ Falló instalación[/]")
            self.app_log("[yellow]Ejecutá [bold cyan]sudo dnf install libimobiledevice-utils[/] manualmente[/]")

    def _run_restore_workflow(self, action: RestoreAction) -> None:
        action_name = "update" if action == RestoreAction.UPDATE else "erase restore"
        self.app_log(f"[bold yellow]▶ Iniciando {action_name}...[/]")

        if not ensure_deps():
            self.app_log("[red]Faltan dependencias. Presiona [bold]S[/] para setup[/]")
            return

        runner = RestoreRunner()
        self._update_progress(0, 0)
        last_phase = ""

        for state in runner.run(action):
            if state.error:
                self.app_log(f"[red]✗ Error: {state.error}[/]")
                return
            if state.done:
                self._set_progress_done(state.success)
                return
            phase = state.phase.value
            if phase != last_phase:
                self.app_log(f"[cyan]{phase}[/]")
                last_phase = phase
            self._update_progress(state.percent, 100)

    def _update_progress(self, value: int, total: int):
        self.app.call_from_thread(self._do_update_progress, value, total)

    def _do_update_progress(self, value: int, total: int):
        progress = self.query_one(ProgressBar)
        if progress.total != total:
            progress.update(total=total)
        progress.update(advance=value - progress.progress)

    def _set_progress_done(self, success: bool):
        self.app.call_from_thread(self._do_progress_done, success)

    def _do_progress_done(self, success: bool):
        progress = self.query_one(ProgressBar)
        progress.progress = 100
        if success:
            self._write_log("[green]✓ Restore completado. El dispositivo debería reiniciarse.[/]")
            self._write_log("[dim]Desconecta el cable cuando veas la pantalla de configuración.[/]")
        else:
            self._write_log("[red]✗ Falló el restore[/]")

    @work(thread=True)
    def action_fix(self) -> None:
        self.app_log("[bold yellow]▶ Auto Fix...[/]")

        if not ensure_deps():
            self.app_log("[red]Faltan dependencias. Presiona [bold]S[/] para setup[/]")
            return

        detector = DeviceDetector()
        dev = detector.detect()
        mode = dev.mode

        self.app_log(f"Estado detectado: [bold]{mode.value.upper()}[/]")

        if mode == DeviceMode.ABSENT:
            self.app_log("[red]No hay dispositivo conectado.[/]")
            return

        if mode == DeviceMode.NORMAL:
            self.app_log("[green]✓ Dispositivo saludable. No se necesita reparación.[/]")
            return

        if mode in (DeviceMode.BOOTLOOP, DeviceMode.RECOVERY):
            self.app_log("[yellow]→ Intentando update (preserva datos)...[/]")
            self._run_restore_workflow(RestoreAction.UPDATE)
        elif mode == DeviceMode.DFU:
            self.app_log("[yellow]→ DFU requiere erase restore completo[/]")
            self._run_restore_workflow(RestoreAction.ERASE)


CSS_PATH = Path(__file__).parent / "ifix_ios.tcss"


class IDeviceTUI(App):
    TITLE = "ifix-ios"
    SUB_TITLE = "iOS Device Recovery Tool"
    CSS_PATH = str(CSS_PATH)
    SCREENS = {"main": MainScreen}
    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        self.push_screen("main")


def main():
    app = IDeviceTUI()
    app.run()


if __name__ == "__main__":
    main()
