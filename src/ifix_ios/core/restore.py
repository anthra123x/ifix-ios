import re
import subprocess
import sys
from enum import Enum
from pathlib import Path


class RestoreAction(Enum):
    UPDATE = "update"
    ERASE = "erase"


class RestorePhase(Enum):
    CHECKING = "Checking device..."
    VERIFYING = "Verifying firmware..."
    DOWNLOADING = "Downloading firmware..."
    EXTRACTING = "Extracting firmware..."
    SENDING_IBEC = "Sending iBEC..."
    UPLOADING = "Uploading components..."
    INSTALLING = "Installing RecoveryOS..."
    SEALING = "Sealing system volume..."
    FINISHING = "Finishing..."
    DONE = "Done"
    FAILED = "Failed"


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
        if "Done sending" in line or "DONE" in line:
            self.done = True
            self.success = True
            self.phase = RestorePhase.DONE
            self.percent = 100
            return

        if "Status: Restore Finished" in line:
            self.done = True
            self.success = True
            self.phase = RestorePhase.DONE
            self.percent = 100
            return

        if "Found device in Recovery mode" in line:
            self.phase = RestorePhase.CHECKING
            self.percent = 0
            return

        if "Verifying" in line:
            self.phase = RestorePhase.VERIFYING
            self._parse_percent(line)
            return

        if "Downloading" in line:
            self.phase = RestorePhase.DOWNLOADING
            self._parse_percent(line)
            return

        if "Uploading" in line:
            self.phase = RestorePhase.UPLOADING
            self._parse_percent(line)
            self.component = self._extract_component(line)
            return

        if "Sending" in line and "(" in line:
            self.phase = RestorePhase.UPLOADING
            self.message = line.strip()[:60]
            return

        if "Error" in line or "error" in line:
            self.error = line.strip()
            self.phase = RestorePhase.FAILED
            self.success = False
            self.done = True
            return

        if "Unmounting filesystems" in line:
            self.phase = RestorePhase.SEALING
            return

        if "Sealing System Volume" in line or "sealing" in line.lower():
            self.phase = RestorePhase.SEALING
            self._parse_percent(line)
            return

        if "Restore Finished" in line:
            self.done = True
            self.success = True
            self.phase = RestorePhase.DONE
            self.percent = 100

    def _parse_percent(self, line: str) -> None:
        m = re.search(r"(\d+)\.\d%", line)
        if m:
            self.percent = int(m.group(1))

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
    def __init__(self, sudo_password: str | None = None):
        self.sudo_password = sudo_password

    def run(self, action: RestoreAction) -> RestoreProgress:
        progress = RestoreProgress()
        cmd = ["idevicerestore", "-l", "-y"]
        if action == RestoreAction.ERASE:
            cmd.append("-e")

        try:
            if self.sudo_password:
                full_cmd = ["sudo", "-S"] + cmd
                proc = subprocess.Popen(
                    full_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                assert proc.stdin is not None
                proc.stdin.write(self.sudo_password + "\n")
                proc.stdin.flush()
            else:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.strip()
                if line:
                    progress.update(line)
                    yield progress

            proc.wait()
            if proc.returncode != 0 and not progress.success:
                progress.done = True
                progress.success = False
                progress.error = f"Process exited with code {proc.returncode}"
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
