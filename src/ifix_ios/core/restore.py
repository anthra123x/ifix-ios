import re
import signal
import subprocess
from enum import Enum
from typing import Generator


class RestoreAction(Enum):
    UPDATE = "update"
    ERASE = "erase"


class RestorePhase(Enum):
    CHECKING = "Verificando dispositivo..."
    VERIFYING = "Verificando firmware..."
    DOWNLOADING = "Descargando firmware..."
    EXTRACTING = "Extrayendo firmware..."
    SENDING_IBEC = "Enviando iBEC..."
    UPLOADING = "Subiendo componentes..."
    INSTALLING = "Instalando RecoveryOS..."
    SEALING = "Sellando volumen del sistema..."
    FINISHING = "Finalizando..."
    DONE = "Completado"
    FAILED = "Falló"


class RestoreProgress:
    def __init__(self):
        self.phase: RestorePhase = RestorePhase.CHECKING
        self.percent: int = 0
        self.component: str = ""
        self.message: str = ""
        self.done: bool = False
        self.success: bool = False
        self.error: str | None = None

    def update(self, line: str):
        line_lower = line.lower()

        if "error" in line_lower:
            self.error = line.strip()
            self.phase = RestorePhase.FAILED
            self.success = False
            self.done = True
            return

        if ("done" in line_lower and "sending" in line_lower) or line.strip() == "DONE":
            self._finish_success()
            return

        if "status:" in line_lower and "restore finished" in line_lower:
            self._finish_success()
            return

        if "restore finished" in line_lower:
            self._finish_success()
            return

        if "found device in recovery mode" in line_lower:
            self.phase = RestorePhase.CHECKING
            self.percent = 0
            self.component = ""
            self.message = ""
            return

        if "verifying" in line_lower:
            self.phase = RestorePhase.VERIFYING
            self._parse_percent(line)
            return

        if "downloading" in line_lower:
            self.phase = RestorePhase.DOWNLOADING
            self._parse_percent(line)
            return

        if "uploading" in line_lower:
            self.phase = RestorePhase.UPLOADING
            self._parse_percent(line)
            self.component = self._extract_component(line)
            return

        if "sending" in line_lower and "(" in line:
            self.phase = RestorePhase.UPLOADING
            self.message = line.strip()[:60]
            self.component = ""
            return

        if "unmounting" in line_lower:
            self.phase = RestorePhase.SEALING
            return

        if "sealing" in line_lower:
            self.phase = RestorePhase.SEALING
            self._parse_percent(line)
            return

    def _finish_success(self):
        self.done = True
        self.success = True
        self.phase = RestorePhase.DONE
        self.percent = 100

    def _parse_percent(self, line: str) -> None:
        m = re.search(r"(\d+)\.?\d*\s*%", line)
        if m:
            try:
                self.percent = int(m.group(1))
            except ValueError:
                pass

    def _extract_component(self, line: str) -> str:
        m = re.search(r"\((.*?)\)", line)
        if m:
            name = m.group(1)
            parts = name.split("/")
            return parts[-1] if parts else name
        m2 = re.search(r"Sending\s+(\S+)", line)
        if m2:
            return m2.group(1)
        return ""


class RestoreRunner:
    def __init__(self, sudo_password: str | None = None, use_sudo: bool = False):
        self.sudo_password = sudo_password
        self.use_sudo = use_sudo
        self._proc: subprocess.Popen | None = None

    def run(self, action: RestoreAction) -> Generator[RestoreProgress, None, None]:
        progress = RestoreProgress()
        cmd = ["idevicerestore", "-l", "-y"]
        if action == RestoreAction.ERASE:
            cmd.append("-e")

        try:
            if self.sudo_password:
                full_cmd = ["sudo", "-S"] + cmd
                self._proc = subprocess.Popen(
                    full_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                assert self._proc.stdin is not None
                self._proc.stdin.write(self.sudo_password + "\n")
                self._proc.stdin.flush()
            elif self.use_sudo:
                full_cmd = ["sudo", "-n"] + cmd
                self._proc = subprocess.Popen(
                    full_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
            else:
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

            assert self._proc.stdout is not None
            for line in iter(self._proc.stdout.readline, ""):
                line = line.strip()
                if line:
                    progress.update(line)
                    yield progress

            self._proc.wait()
            if self._proc.returncode != 0 and not progress.success:
                progress.done = True
                progress.success = False
                progress.error = f"Process exited with code {self._proc.returncode}"
                yield progress

        except FileNotFoundError:
            progress.done = True
            progress.success = False
            progress.error = "idevicerestore not found. Install it first."
            yield progress
        except Exception as e:
            progress.done = True
            progress.success = False
            progress.error = str(e)
            yield progress
        finally:
            self._proc = None

    def cancel(self):
        if self._proc and self._proc.poll() is None:
            self._proc.send_signal(signal.SIGINT)
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()


def check_dependencies() -> list[str]:
    missing: list[str] = []
    for cmd in ["idevicerestore"]:
        try:
            subprocess.run(
                [cmd, "--version"],
                capture_output=True, timeout=3
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            missing.append(cmd)
    return missing
