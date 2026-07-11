import asyncio
import time
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    ProgressBar,
    RichLog,
    Static,
)

from ifix_ios.core.detector import DeviceDetector, DeviceMode, DeviceInfo
from ifix_ios.core.installer import ensure_deps
from ifix_ios.core.restore import (
    RestoreAction,
    RestoreRunner,
)


class DeviceStatusWidget(Static):
    device = reactive(DeviceInfo)

    def __init__(self):
        super().__init__("")
        self.device = DeviceInfo()

    def watch_device(self, dev: DeviceInfo):
        mode_colors = {
            DeviceMode.NORMAL: "green",
            DeviceMode.RECOVERY: "yellow",
            DeviceMode.DFU: "red",
            DeviceMode.BOOTLOOP: "red",
            DeviceMode.ABSENT: "gray",
            DeviceMode.UNKNOWN: "yellow",
        }
        color = mode_colors.get(dev.mode, "white")
        lines = [
            f"[bold]Device Status[/bold]",
            f"  Mode: [{color}]{dev.mode.value.upper()}[/{color}]",
        ]
        if dev.udid:
            lines.append(f"  UDID: {dev.udid}")
        if dev.ecid:
            lines.append(f"  ECID: {dev.ecid}")
        if dev.product_type:
            lines.append(f"  Model: {dev.product_type}")
        if dev.product_version:
            lines.append(f"  iOS: {dev.product_version}")
        if dev.device_name:
            lines.append(f"  Name: {dev.device_name}")
        if dev.activation_state:
            lines.append(f"  Activation: {dev.activation_state}")
        if dev.battery_level is not None:
            lines.append(f"  Battery: {dev.battery_level}%")
        self.update("\n".join(lines))


class LogWidget(RichLog):
    def __init__(self):
        super().__init__(highlight=True, markup=True, max_lines=100)


class MainScreen(Screen):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("d", "detect", "Detect"),
        Binding("u", "update", "Update"),
        Binding("e", "erase", "Erase"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Horizontal(
                Vertical(
                    DeviceStatusWidget(),
                    Button("🔄 Detect", variant="primary", id="detect"),
                    Button("📥 Update (preserve data)", variant="default", id="update"),
                    Button("⚠ Erase Restore", variant="error", id="erase"),
                    Button("🛠 Auto Fix", variant="warning", id="fix"),
                    classes="sidebar",
                ),
                Vertical(
                    LogWidget(),
                    ProgressBar(total=100, show_eta=False, id="progress"),
                    classes="main",
                ),
            )
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(LogWidget).write("[bold green]ifix-ios TUI ready[/bold green]")
        self.query_one(LogWidget).write("Connect your iOS device or use the buttons above.")
        self.refresh_device()

    def refresh_device(self):
        self._detect_device()

    @work(thread=True)
    def _detect_device(self) -> None:
        detector = DeviceDetector()
        dev = detector.detect()
        status = self.query_one(DeviceStatusWidget)
        status.device = dev
        self.app.call_from_thread(self._on_detect, dev)

    def _on_detect(self, dev: DeviceInfo):
        log = self.query_one(LogWidget)
        mode_colors = {
            DeviceMode.NORMAL: "green",
            DeviceMode.RECOVERY: "yellow",
            DeviceMode.DFU: "red",
            DeviceMode.BOOTLOOP: "red",
            DeviceMode.ABSENT: "gray",
        }
        color = mode_colors.get(dev.mode, "white")
        log.write(f"[{color}]Device: {dev.mode.value.upper()}[/{color}]")
        if dev.udid:
            log.write(f"  UDID: {dev.udid}")
        if dev.product_version:
            log.write(f"  iOS: {dev.product_version}")
        if dev.battery_level is not None:
            log.write(f"  Battery: {dev.battery_level}%")

    def action_detect(self) -> None:
        self._detect_device()

    def action_refresh(self) -> None:
        self._detect_device()

    @work(thread=True)
    def action_update(self) -> None:
        self._run_restore_workflow(RestoreAction.UPDATE)

    @work(thread=True)
    def action_erase(self) -> None:
        self._run_restore_workflow(RestoreAction.ERASE)

    def _run_restore_workflow(self, action: RestoreAction) -> None:
        log = self.query_one(LogWidget)
        progress = self.query_one(ProgressBar)
        action_name = "update" if action == RestoreAction.UPDATE else "erase restore"
        log.write(f"[bold yellow]Starting {action_name}...[/bold yellow]")

        if not ensure_deps():
            log.write("[red]Dependencies missing. Run: ifix-ios setup[/red]")
            return

        log.write("[dim]Requesting sudo password (check terminal)...[/dim]")
        runner = RestoreRunner()
        progress.update(total=100, advance=0)
        last_phase = ""

        for state in runner.run(action):
            if state.error:
                log.write(f"[red]Error: {state.error}[/red]")
                return
            if state.done:
                progress.progress = 100
                if state.success:
                    log.write("[green]✓ Restore complete! Device should reboot now.[/green]")
                else:
                    log.write(f"[red]Failed: {state.error or 'Unknown'}[/red]")
                return
            new_phase = state.phase.value.capitalize()
            if new_phase != last_phase:
                log.write(f"[cyan]{new_phase}...[/cyan]")
                last_phase = new_phase
            progress.update(total=100, advance=state.percent - progress.progress)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id
        if action == "detect":
            self._detect_device()
        elif action == "update":
            self.action_update()
        elif action == "erase":
            self.action_erase()
        elif action == "fix":
            self.action_fix()

    @work(thread=True)
    def action_fix(self) -> None:
        log = self.query_one(LogWidget)
        log.write("[bold yellow]Running auto-fix...[/bold yellow]")

        detector = DeviceDetector()
        dev = detector.detect()
        mode = dev.mode

        log.write(f"Detected mode: [bold]{mode.value.upper()}[/bold]")

        if mode == DeviceMode.ABSENT:
            log.write("[red]No device connected.[/red]")
            return

        if mode == DeviceMode.NORMAL:
            log.write("[green]Device appears healthy. No fix needed.[/green]")
            return

        if mode in (DeviceMode.BOOTLOOP, DeviceMode.RECOVERY):
            log.write("[yellow]Attempting update (preserves data)...[/yellow]")
            self._run_restore_workflow(RestoreAction.UPDATE)
        elif mode == DeviceMode.DFU:
            log.write("[yellow]Device in DFU. Erase restore required.[/yellow]")
            self._run_restore_workflow(RestoreAction.ERASE)


class IDeviceTUI(App):
    TITLE = "ifix-ios"
    SUB_TITLE = "iOS Device Recovery Tool"
    SCREENS = {"main": MainScreen}
    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        self.push_screen("main")


if __name__ == "__main__":
    app = IDeviceTUI()
    app.run()
