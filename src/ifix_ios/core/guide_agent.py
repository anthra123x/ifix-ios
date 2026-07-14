from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generator

from ifix_ios.core.detector import (
    DeviceDetector,
    DeviceInfo,
    DeviceMode,
    MODE_COLORS,
    MODE_ICONS,
)
from ifix_ios.core.firmware import get_device_guide, device_name
from ifix_ios.core.installer import ensure_deps
from ifix_ios.core.restore import RestoreAction, RestoreRunner


class StepType(Enum):
    CHECK_DEPS = "check_deps"
    DIAGNOSE = "diagnose"
    UPDATE_RESTORE = "update_restore"
    ERASE_RESTORE = "erase_restore"
    ENTER_RECOVERY = "enter_recovery"
    VERIFY_REPAIR = "verify_repair"
    DONE = "done"


STEP_LABELS = {
    StepType.CHECK_DEPS: "Verificar dependencias",
    StepType.DIAGNOSE: "Diagnosticar dispositivo",
    StepType.UPDATE_RESTORE: "Update (preservar datos)",
    StepType.ERASE_RESTORE: "Erase Restore (borrar todo)",
    StepType.ENTER_RECOVERY: "Forzar modo Recovery",
    StepType.VERIFY_REPAIR: "Verificar reparación",
    StepType.DONE: "Completado",
}


@dataclass
class Diagnosis:
    device: DeviceInfo
    problem_id: str
    title: str
    description: str
    severity: str
    details: list[str] = field(default_factory=list)


@dataclass
class RepairPlan:
    steps: list[StepType]
    label: str = ""


@dataclass
class GuideEvent:
    step: StepType
    message: str
    level: str = "info"
    done: bool = False
    success: bool = False
    error: str | None = None
    progress: int = 0
    total: int = 100


STEP_MESSAGES = {
    StepType.CHECK_DEPS: "🔧 Verificando que las herramientas necesarias estén instaladas...",
    StepType.DIAGNOSE: "🔍 Analizando el estado del dispositivo...",
    StepType.UPDATE_RESTORE: "📦 Reinstalando iOS sin borrar datos...",
    StepType.ERASE_RESTORE: "⚠️  Restaurando iOS — se borrarán TODOS los datos...",
    StepType.ENTER_RECOVERY: "📋 Forzando entrada a modo Recovery...",
    StepType.VERIFY_REPAIR: "✅ Verificando que la reparación funcionó...",
    StepType.DONE: "🏁 Proceso completado.",
}


PROBLEM_DESCRIPTIONS: dict[str, tuple[str, str, str]] = {
    "absent": (
        "No hay dispositivo conectado",
        "Conecta un iPhone o iPad por USB para comenzar.",
        "warning",
    ),
    "unknown": (
        "Dispositivo en modo desconocido",
        "Se detectó un dispositivo Apple pero no se pudo determinar su estado.",
        "warning",
    ),
    "normal": (
        "Dispositivo funcionando correctamente",
        "El dispositivo está en estado normal y no requiere reparación.",
        "info",
    ),
    "bootloop": (
        "Boot-loop detectado",
        "El dispositivo se reinicia constantemente en el logo de Apple. "
        "Causas posibles: actualización fallida, batería baja, corrupción de datos.",
        "critical",
    ),
    "recovery": (
        "Modo Recovery",
        "El dispositivo muestra el icono de cable + laptop. "
        "Causas posibles: actualización fallida, jailbreak, corrupción de sistema.",
        "critical",
    ),
    "dfu": (
        "Modo DFU",
        "La pantalla está completamente negra. "
        "El dispositivo no inicia el sistema operativo.",
        "critical",
    ),
}


class GuideAgent:
    def __init__(self, sudo_password: str | None = None, use_sudo: bool = False):
        self.detector = DeviceDetector()
        self.sudo_password = sudo_password
        self.use_sudo = use_sudo
        self._runner: RestoreRunner | None = None

    def diagnose(self, dev: DeviceInfo | None = None) -> Diagnosis:
        if dev is None:
            dev = self.detector.detect()

        mode = dev.mode
        problem_id = mode.value
        title, description, severity = PROBLEM_DESCRIPTIONS.get(
            problem_id, ("Estado desconocido", "No se pudo determinar.", "warning")
        )

        details = []
        if dev.product_type:
            nice = device_name(dev.product_type)
            details.append(f"Modelo: {nice} ({dev.product_type})")
        if dev.product_version:
            details.append(f"iOS: {dev.product_version}")
        if dev.device_name:
            details.append(f"Nombre: {dev.device_name}")

        return Diagnosis(dev, problem_id, title, description, severity, details)

    def build_plan(self, diagnosis: Diagnosis) -> RepairPlan:
        mode = diagnosis.device.mode
        if mode == DeviceMode.ABSENT:
            return RepairPlan([StepType.DIAGNOSE], "Esperando dispositivo...")
        if mode == DeviceMode.NORMAL:
            return RepairPlan([StepType.DIAGNOSE], "Sin reparación necesaria")
        if mode in (DeviceMode.BOOTLOOP, DeviceMode.RECOVERY):
            return RepairPlan(
                [StepType.UPDATE_RESTORE, StepType.VERIFY_REPAIR,
                 StepType.ENTER_RECOVERY, StepType.UPDATE_RESTORE,
                 StepType.VERIFY_REPAIR, StepType.ERASE_RESTORE,
                 StepType.VERIFY_REPAIR],
                "Plan de reparación: Update → Recovery+Update → Erase",
            )
        if mode == DeviceMode.DFU:
            return RepairPlan(
                [StepType.ERASE_RESTORE, StepType.VERIFY_REPAIR],
                "Plan de reparación: Erase Restore (única opción)",
            )
        return RepairPlan(
            [StepType.DIAGNOSE],
            "No hay plan disponible para este estado",
        )

    def run_plan(
        self,
        plan: RepairPlan,
        on_event: Callable[[GuideEvent], None] | None = None,
        confirm_callback: Callable[[str], bool] | None = None,
    ) -> Generator[GuideEvent, None, None]:
        total_steps = len(plan.steps)

        for i, step in enumerate(plan.steps):
            step_num = i + 1
            base_msg = STEP_MESSAGES.get(step, f"Paso {step_num}/{total_steps}")
            yield GuideEvent(
                step=step,
                message=f"[{step_num}/{total_steps}] {base_msg}",
                progress=0,
            )

            if step == StepType.DIAGNOSE:
                yield from self._do_diagnose()
            elif step == StepType.CHECK_DEPS:
                yield from self._do_check_deps()
            elif step == StepType.UPDATE_RESTORE:
                yield from self._do_restore(RestoreAction.UPDATE, step, step_num, total_steps)
            elif step == StepType.ERASE_RESTORE:
                if confirm_callback and not confirm_callback(
                    "⚠️ Esta operación borrará TODOS los datos del dispositivo. ¿Continuar?"
                ):
                    yield GuideEvent(
                        step=step,
                        message="Erase cancelado por el usuario.",
                        level="warning",
                        done=True,
                        success=False,
                        error="cancelado",
                    )
                    continue
                yield from self._do_restore(RestoreAction.ERASE, step, step_num, total_steps)
            elif step == StepType.ENTER_RECOVERY:
                yield from self._do_enter_recovery()
            elif step == StepType.VERIFY_REPAIR:
                yield from self._do_verify_repair()
            elif step == StepType.DONE:
                yield GuideEvent(
                    step=step,
                    message="Plan de reparación completado.",
                    level="success",
                    done=True,
                    success=True,
                    progress=100,
                )

        yield GuideEvent(
            step=StepType.DONE,
            message="Proceso finalizado.",
            level="success",
            done=True,
            success=True,
            progress=100,
        )

    def _do_diagnose(self) -> Generator[GuideEvent, None, None]:
        yield GuideEvent(StepType.DIAGNOSE, "Detectando dispositivo...", progress=30)
        dev = self.detector.detect()
        diagnosis = self.diagnose(dev)

        if diagnosis.device.mode == DeviceMode.ABSENT:
            yield GuideEvent(
                StepType.DIAGNOSE,
                "🔌 No hay dispositivo conectado. Conecta un iPhone/iPad por USB.",
                level="warning",
                done=True,
                success=False,
                error="absent",
            )
            return

        icon = MODE_ICONS.get(diagnosis.device.mode, "?")
        color = MODE_COLORS.get(diagnosis.device.mode, "white")
        yield GuideEvent(
            StepType.DIAGNOSE,
            f"[{color}]{icon} {diagnosis.title}[/]",
            progress=60,
        )
        yield GuideEvent(
            StepType.DIAGNOSE,
            f"  {diagnosis.description}",
            progress=80,
        )
        if diagnosis.details:
            for d in diagnosis.details:
                yield GuideEvent(StepType.DIAGNOSE, f"  {d}", progress=90)
        yield GuideEvent(
            StepType.DIAGNOSE,
            "Diagnóstico completado.",
            level="success",
            done=True,
            success=True,
            progress=100,
        )

    def _do_restore(
        self, action: RestoreAction, step: StepType, step_num: int, total: int
    ) -> Generator[GuideEvent, None, None]:
        action_label = "update" if action == RestoreAction.UPDATE else "erase restore"
        yield GuideEvent(step, f"Iniciando {action_label}...", progress=5)

        if not ensure_deps():
            yield GuideEvent(
                step,
                "Faltan dependencias del sistema. Presiona S para instalar.",
                level="error",
                done=True,
                success=False,
                error="missing_deps",
            )
            return

        self._runner = RestoreRunner(
            sudo_password=self.sudo_password, use_sudo=self.use_sudo
        )
        last_phase = ""
        for state in self._runner.run(action):
            if state.error:
                yield GuideEvent(
                    step,
                    f"Error: {state.error}",
                    level="error",
                    done=True,
                    success=False,
                    error=state.error,
                    progress=state.percent,
                )
                return
            if state.done:
                if state.success:
                    yield GuideEvent(
                        step,
                        f"✓ {action_label.title()} completado.",
                        level="success",
                        done=True,
                        success=True,
                        progress=100,
                    )
                else:
                    yield GuideEvent(
                        step,
                        f"✗ Falló el {action_label}.",
                        level="error",
                        done=True,
                        success=False,
                        error=state.error or "unknown",
                    )
                return
            phase = state.phase.value
            if phase != last_phase:
                yield GuideEvent(step, f"[cyan]{phase}[/]", progress=state.percent)
                last_phase = phase
            else:
                yield GuideEvent(step, "", progress=state.percent)

    def _do_enter_recovery(self) -> Generator[GuideEvent, None, None]:
        yield GuideEvent(
            StepType.ENTER_RECOVERY,
            "Para forzar modo Recovery en el dispositivo:",
            progress=20,
        )
        yield GuideEvent(
            StepType.ENTER_RECOVERY,
            "  1. Conecta el dispositivo al ordenador",
            progress=40,
        )
        yield GuideEvent(
            StepType.ENTER_RECOVERY,
            "  2. Presiona y suelta rápido Subir Volumen",
            progress=60,
        )
        yield GuideEvent(
            StepType.ENTER_RECOVERY,
            "  3. Presiona y suelta rápido Bajar Volumen",
            progress=80,
        )
        yield GuideEvent(
            StepType.ENTER_RECOVERY,
            "  4. Mantén presionado el botón Lateral hasta que veas el cable + laptop",
            progress=95,
        )
        yield GuideEvent(
            StepType.ENTER_RECOVERY,
            "Esperando a que el dispositivo entre en Recovery...",
            done=True,
            success=True,
            progress=100,
        )

    def _do_verify_repair(self) -> Generator[GuideEvent, None, None]:
        yield GuideEvent(StepType.VERIFY_REPAIR, "Verificando estado...", progress=30)
        dev = self.detector.detect()

        if dev.mode == DeviceMode.NORMAL:
            yield GuideEvent(
                StepType.VERIFY_REPAIR,
                "✓ Dispositivo funcionando correctamente.",
                level="success",
                done=True,
                success=True,
                progress=100,
            )
        elif dev.mode == DeviceMode.ABSENT:
            yield GuideEvent(
                StepType.VERIFY_REPAIR,
                "El dispositivo se desconectó. Puede que esté reiniciándose.",
                level="warning",
                done=True,
                success=False,
                error="absent",
            )
        else:
            yield GuideEvent(
                StepType.VERIFY_REPAIR,
                f"El dispositivo aún está en modo {dev.mode.value}.",
                level="warning",
                done=True,
                success=False,
                error=dev.mode.value,
            )

    def cancel(self):
        if self._runner:
            self._runner.cancel()
