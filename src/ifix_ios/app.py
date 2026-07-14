import sys

import click

from ifix_ios.core.detector import DeviceDetector, DeviceMode, format_device_info, MODE_COLORS, MODE_ICONS
from ifix_ios.core.firmware import get_device_guide, device_name, latest_signed
from ifix_ios.core.guide_agent import GuideAgent, StepType
from ifix_ios.core.installer import ensure_deps, are_deps_installed, install_deps
from ifix_ios.core.restore import (
    RestoreAction,
    RestoreRunner,
    check_dependencies,
)


@click.group(invoke_without_command=True)
@click.version_option(
    version="0.1.0",
    prog_name="ifix-ios",
    message="%(prog)s v%(version)s — iOS Device Recovery Tool\nCopyright (c) 2026 anthra123x — MIT License",
)
@click.pass_context
def cli(ctx):
    if ctx.invoked_subcommand is None:
        launch_tui()


@cli.command()
def detect():
    """Detect current iOS device state (works without idevicerestore)."""
    detector = DeviceDetector()
    dev = detector.detect()

    from rich.console import Console
    console = Console()

    if dev.mode == DeviceMode.ABSENT:
        console.print("[yellow]○ No hay dispositivo iOS conectado.[/]")
        console.print("  Conecta un iPhone/iPad por USB y ejecuta de nuevo.")
        return

    console.print(format_device_info(dev))

    # Show quick diagnosis
    agent = GuideAgent()
    diagnosis = agent.diagnose(dev)
    color = MODE_COLORS.get(dev.mode, "white")
    icon = MODE_ICONS.get(dev.mode, "?")
    console.print(f"\n[{color}]{icon} {diagnosis.title}[/]")
    console.print(f"  {diagnosis.description}")

    if dev.mode in (DeviceMode.BOOTLOOP, DeviceMode.RECOVERY, DeviceMode.DFU):
        console.print(f"\n[bold cyan]Recomendación:[/] [green]ifix-ios fix[/] [dim]o presiona F en la TUI[/]")


@cli.command()
@click.option("--yes", "-y", is_flag=True, help="Auto-confirm all prompts")
@click.option("--sudo-password", "-p", help="sudo password (omit for automatic detection)")
def fix(yes, sudo_password):
    """Auto-detect issue and apply best fix with fallback."""
    if not ensure_deps(sudo_password):
        return

    agent = GuideAgent(sudo_password=sudo_password)
    diagnosis = agent.diagnose()
    dev = diagnosis.device

    from rich.console import Console
    from rich.panel import Panel
    from rich.markup import escape
    console = Console()

    if dev.mode == DeviceMode.ABSENT:
        console.print("[yellow]○ No hay dispositivo conectado.[/]")
        console.print("  Conecta un iPhone/iPad por USB y ejecuta de nuevo.")
        return

    color = MODE_COLORS.get(dev.mode, "white")
    icon = MODE_ICONS.get(dev.mode, "?")
    console.print()
    console.print(Panel(
        f"[{color}]{icon} {diagnosis.title}[/]\n"
        f"  {diagnosis.description}\n"
        + "\n".join(f"  {d}" for d in diagnosis.details) if diagnosis.details else "",
        title="[bold]Diagnóstico[/]",
        border_style=color,
    ))

    if dev.mode == DeviceMode.NORMAL:
        console.print("[green]✓ Dispositivo saludable. No se necesita reparación.[/]")
        return

    plan = agent.build_plan(diagnosis)
    console.print(f"\n[dim]Plan: {plan.label}[/]")

    if not yes and dev.mode == DeviceMode.DFU:
        if not click.confirm("\n⚠ DFU requiere erase restore (borra TODOS los datos). ¿Continuar?", default=False):
            console.print("[yellow]Cancelado por el usuario.[/]")
            return

    console.print()
    with console.status("[bold cyan]Ejecutando plan de reparación...[/]") as status:
        for event in agent.run_plan(plan):
            if event.message and event.step != StepType.ENTER_RECOVERY:
                status.update(f"[bold cyan]{event.message[:60]}[/]")
            if event.done:
                if event.success:
                    console.print(f"  [green]✓ {event.message}[/]")
                elif event.error == "absent":
                    console.print(f"  [yellow]⚠ {event.message}[/]")
                else:
                    console.print(f"  [red]✗ {event.message}[/]")
                    if plan.current_step < len(plan.steps) - 1:
                        console.print("  [yellow]→ Probando siguiente paso...[/]")


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
def guide():
    """Diagnóstico y guía paso a paso según el estado del dispositivo."""
    from rich.console import Console
    console = Console()

    agent = GuideAgent()
    diagnosis = agent.diagnose()
    dev = diagnosis.device

    if dev.mode == DeviceMode.ABSENT:
        console.print("[yellow]🔌 No hay dispositivo conectado.[/]")
        console.print("   Conecta un iPhone/iPad por USB y ejecuta de nuevo.")
        return

    console.print()
    nice = device_name(dev.product_type or "?")
    console.print(f"[bold]{diagnosis.title}[/]")
    console.print(f"  {diagnosis.description}")

    if dev.product_type:
        console.print(f"\n📱 [bold]{nice}[/] [dim]({dev.product_type})[/]")
    if dev.device_name:
        console.print(f"   Nombre: {dev.device_name}")
    if dev.product_version:
        console.print(f"📦 iOS: {dev.product_version}")

    console.print()
    for line in get_device_guide(dev):
        console.print(line)

    console.print()
    console.print("[bold cyan]Presiona una tecla:[/]")
    console.print("  [cyan]U[/] = Update (preserva datos)")
    console.print("  [cyan]E[/] = Erase restore (borra todo)")
    console.print("  [cyan]F[/] = Auto Fix (recomendado)")
    if dev.mode in ("bootloop", "recovery"):
        console.print("  [cyan]R[/] = Forzar entrada a Recovery Mode")
    console.print("  [cyan]Q[/] = Salir")


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


def launch_tui():
    try:
        from ifix_ios.tui_app import main as tui_main
        tui_main()
    except ImportError as e:
        click.secho(f"Error al abrir TUI: {e}", fg="red")
        click.echo("Asegúrate de tener textual: pip install 'ifix-ios[tui]'")
        click.echo("  o: pip install textual")


@cli.command()
def tui():
    """Launch interactive TUI (default si no se da subcomando)."""
    launch_tui()


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
