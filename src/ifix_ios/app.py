import sys

import click

from ifix_ios.core.detector import DeviceDetector, format_device_info
from ifix_ios.core.installer import ensure_deps, are_deps_installed, install_deps
from ifix_ios.core.restore import (
    RestoreAction,
    RestoreRunner,
    check_dependencies,
)


@click.group()
@click.version_option(
    version="0.1.0",
    prog_name="ifix-ios",
    message="%(prog)s v%(version)s — iOS Device Recovery Tool\nCopyright (c) 2026 anthra123x — MIT License",
)
def cli():
    pass


@cli.command()
def detect():
    """Detect current iOS device state (works without idevicerestore)."""
    detector = DeviceDetector()
    dev = detector.detect()

    table = format_device_info(dev)
    from rich.console import Console
    Console().print(table)

    if dev.mode.value == "bootloop":
        click.echo("\n" + click.style("⚠ Device in boot-loop. Try: ifix-ios fix", fg="yellow"))
    elif dev.mode.value == "absent":
        click.echo("\n" + click.style("No Apple device detected. Connect via USB.", fg="yellow"))


@cli.command()
@click.option("--sudo-password", "-p", help="sudo password (omit for automatic detection)")
def update(sudo_password):
    """Update iOS preserving user data."""
    if not ensure_deps(sudo_password):
        return
    _run_restore(RestoreAction.UPDATE, sudo_password)


@cli.command()
@click.option("--sudo-password", "-p", help="sudo password (omit if not needed)")
@click.confirmation_option(prompt="This will ERASE ALL DATA. Continue?")
def restore(sudo_password):
    """Full erase restore."""
    if not ensure_deps(sudo_password):
        return
    _run_restore(RestoreAction.ERASE, sudo_password)


@cli.command()
@click.option("--sudo-password", "-p", default=None)
def fix(sudo_password):
    """Auto-detect issue and apply best fix."""
    if not ensure_deps(sudo_password):
        return

    detector = DeviceDetector()
    dev = detector.detect()
    mode = dev.mode

    if mode.value == "absent":
        click.secho("No Apple device detected.", fg="yellow")
        return

    click.secho(f"Device mode: {mode.value.upper()}", bold=True)
    table = format_device_info(dev)
    from rich.console import Console
    Console().print(table)

    if mode.value == "normal":
        click.secho("✅ Device appears healthy. No fix needed.", fg="green")
        return

    if mode.value == "bootloop":
        click.secho("\nBoot-loop detected.", fg="yellow", bold=True)
        click.echo("Recommendation: Try update first (preserves data).")
        if click.confirm("Run update (preserve data)?"):
            _run_restore(RestoreAction.UPDATE, sudo_password)
        elif click.confirm("Run full erase restore?"):
            _run_restore(RestoreAction.ERASE, sudo_password)
        return

    if mode.value == "recovery":
        click.secho("\nDevice in Recovery Mode.", fg="yellow", bold=True)
        if click.confirm("Attempt update (preserve data)?"):
            _run_restore(RestoreAction.UPDATE, sudo_password)
        elif click.confirm("Run full erase restore?"):
            _run_restore(RestoreAction.ERASE, sudo_password)
        return

    if mode.value == "dfu":
        click.secho("\nDevice in DFU Mode.", fg="red", bold=True)
        click.echo("DFU requires a full erase restore.")
        if click.confirm("Proceed with erase restore?"):
            _run_restore(RestoreAction.ERASE, sudo_password)
        return


@cli.command()
@click.option("--sudo-password", "-p", default=None)
def setup(sudo_password):
    """Install system dependencies (idevicerestore + libimobiledevice)."""
    if are_deps_installed():
        click.secho("All dependencies already installed.", fg="green")
        return
    if install_deps(sudo_password):
        click.secho("Setup complete!", fg="green")
    else:
        click.secho("Setup failed. See above for details.", fg="red")
        raise SystemExit(1)


@cli.command()
def monitor():
    """Continuously monitor device state."""
    import time
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table

    detector = DeviceDetector()

    def make_table():
        dev = detector.detect()
        return format_device_info(dev)

    console = Console()
    with Live(make_table(), refresh_per_second=2, console=console) as live:
        try:
            while True:
                live.update(make_table())
                time.sleep(1)
        except KeyboardInterrupt:
            pass


@cli.command()
def tui():
    """Launch interactive TUI."""
    try:
        from ifix_ios.tui_app import IDeviceTUI
        from textual.app import App
        app = IDeviceTUI()
        app.run()
    except ImportError as e:
        click.secho(f"Failed to launch TUI: {e}", fg="red")
        click.echo("Make sure textual is installed: pip install textual")


def _run_restore(action: RestoreAction, sudo_password: str | None):
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )

    console = Console()
    action_name = "update" if action == RestoreAction.UPDATE else "erase restore"
    console.print(f"[bold]Starting {action_name}...[/bold]")

    runner = RestoreRunner(sudo_password=sudo_password)

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )

    with progress:
        task = progress.add_task(f"[cyan]{action_name.title()}...", total=100)
        last_phase = ""
        for state in runner.run(action):
            if state.error:
                progress.update(task, description=f"[red]Error: {state.error}")
                return
            if state.done:
                if state.success:
                    progress.update(task, completed=100, description="[green]Done!")
                else:
                    progress.update(
                        task,
                        description=f"[red]Failed: {state.error or 'Unknown'}",
                    )
                return
            new_phase = state.phase.value.capitalize()
            if new_phase != last_phase:
                progress.update(
                    task, description=f"[cyan]{new_phase}", completed=state.percent
                )
                last_phase = new_phase
            else:
                progress.update(task, completed=state.percent)

    console.print("[green]✓ Restore completed successfully.[/green]")
    console.print("The device should reboot. Disconnect cable when you see the setup screen.")


def main():
    cli()
