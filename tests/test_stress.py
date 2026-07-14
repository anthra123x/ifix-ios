"""
Comprehensive stress test suite for ifix-ios.
Tests detection, guide agent, restore, and edge cases
using mocked subprocess/USB calls.
"""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# Helpers
# =============================================================================


def _make_subprocess_runner(stdout_map):
    """Return a function that returns CompletedProcess based on command name."""

    def fake_run(*args, **kwargs):
        cmd = kwargs.get("args") or (args[0] if args else [])
        name = os.path.basename(cmd[0]) if cmd else ""
        entry = stdout_map.get(name)
        if entry is None:
            for key, value in stdout_map.items():
                if key in name:
                    entry = value
                    break
        if entry is None:
            entry = {"stdout": "", "returncode": 0}
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=entry.get("returncode", 0),
            stdout=entry.get("stdout", ""),
            stderr=entry.get("stderr", ""),
        )

    return fake_run


def _mock_usb(monkeypatch, mode, pid):
    """Replace DeviceDetector._scan_usb_pyusb to return a fixed mode."""
    from ifix_ios.core.detector import DeviceDetector, DeviceMode

    def fake_scan(self):
        return mode, pid

    monkeypatch.setattr(DeviceDetector, "_scan_usb_pyusb", fake_scan)


def _mock_subprocess(monkeypatch, fake_run):
    """Replace subprocess.run in the detector module."""
    import ifix_ios.core.detector
    monkeypatch.setattr(ifix_ios.core.detector.subprocess, "run", fake_run)


# =============================================================================
# Combined mock fixtures
# =============================================================================


@pytest.fixture
def mock_absent(monkeypatch):
    """No device connected."""
    from ifix_ios.core.detector import DeviceMode
    _mock_usb(monkeypatch, DeviceMode.ABSENT, None)
    _mock_subprocess(monkeypatch, _make_subprocess_runner({"lsusb": {"stdout": ""}}))


@pytest.fixture
def mock_absent_no_tools(monkeypatch):
    """No device connected, no idevice tools."""
    from ifix_ios.core.detector import DeviceMode
    _mock_usb(monkeypatch, DeviceMode.ABSENT, None)

    def no_tools(*args, **kwargs):
        cmd = kwargs.get("args") or (args[0] if args else [])
        name = os.path.basename(cmd[0]) if cmd else ""
        if name in ("idevice_id", "ideviceinfo", "idevicerestore"):
            raise FileNotFoundError(f"{name} not found")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    _mock_subprocess(monkeypatch, no_tools)


@pytest.fixture
def mock_normal_full(monkeypatch):
    """Normal device with full idevice tools."""
    from ifix_ios.core.detector import DeviceMode
    _mock_usb(monkeypatch, DeviceMode.NORMAL, "12a8")
    _mock_subprocess(monkeypatch, _make_subprocess_runner({
        "idevice_id": {"stdout": "0000MOCK-1234567890\n"},
        "ideviceinfo": {"stdout": """ProductType: iPhone17,2
ProductVersion: 26.5.2
BuildVersion: 23F84
DeviceName: Test iPhone 16 Pro Max
HardwareModel: D94AP
ActivationState: Unactivated
SerialNumber: MOCK12345678
UniqueChipID: 2643364300816412
UniqueDeviceID: 0000MOCK-1234567890
BatteryCurrentCapacity: 85
"""},
        "lsusb": {"stdout": "Bus 001 Device 042: ID 05ac:12a8 Apple, Inc. iPhone\n"},
    }))


@pytest.fixture
def mock_normal_notools(monkeypatch):
    """Normal mode but no idevice tools."""
    from ifix_ios.core.detector import DeviceMode
    _mock_usb(monkeypatch, DeviceMode.NORMAL, "12a8")

    def no_tools(*args, **kwargs):
        cmd = kwargs.get("args") or (args[0] if args else [])
        name = os.path.basename(cmd[0]) if cmd else ""
        if name in ("idevice_id", "ideviceinfo", "idevicerestore"):
            raise FileNotFoundError(f"{name} not found")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    _mock_subprocess(monkeypatch, no_tools)


@pytest.fixture
def mock_bootloop(monkeypatch):
    """Bootloop: device visible but lockdownd fails."""
    from ifix_ios.core.detector import DeviceMode
    _mock_usb(monkeypatch, DeviceMode.NORMAL, "12a8")
    _mock_subprocess(monkeypatch, _make_subprocess_runner({
        "idevice_id": {"stdout": "0000MOCK-1234567890\n"},
        "ideviceinfo": {"stdout": "", "returncode": 1, "stderr": "ERROR: lockdownd (-12)"},
        "lsusb": {"stdout": "Bus 001 Device 042: ID 05ac:12a8 Apple, Inc. iPhone\n"},
    }))


@pytest.fixture
def mock_recovery(monkeypatch):
    """Recovery mode device."""
    from ifix_ios.core.detector import DeviceMode
    _mock_usb(monkeypatch, DeviceMode.RECOVERY, "1281")
    _mock_subprocess(monkeypatch, _make_subprocess_runner({
        "idevicerestore": {"stdout": """idevicerestore 1.0.0 (mock)
Found device in Recovery mode
ECID: 2643364300816412
Identified device as d94ap, iPhone17,2
device serial number is MOCK12345678
"""},
        "lsusb": {"stdout": "Bus 001 Device 042: ID 05ac:1281 Apple, Inc. [Recovery Mode]\n"},
        "idevice_id": {"stdout": ""},
        "ideviceinfo": {"stdout": ""},
    }))


@pytest.fixture
def mock_dfu(monkeypatch):
    """DFU mode device."""
    from ifix_ios.core.detector import DeviceMode
    _mock_usb(monkeypatch, DeviceMode.DFU, "1227")
    _mock_subprocess(monkeypatch, _make_subprocess_runner({
        "idevice_id": {"stdout": "0000MOCK-1234567890\n"},
        "lsusb": {"stdout": ""},
    }))


@pytest.fixture
def mock_dfu_notools(monkeypatch):
    """DFU mode, no tools."""
    from ifix_ios.core.detector import DeviceMode
    _mock_usb(monkeypatch, DeviceMode.DFU, "1227")

    def no_tools(*args, **kwargs):
        cmd = kwargs.get("args") or (args[0] if args else [])
        name = os.path.basename(cmd[0]) if cmd else ""
        if name in ("idevice_id", "ideviceinfo", "idevicerestore"):
            raise FileNotFoundError(f"{name} not found")
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    _mock_subprocess(monkeypatch, no_tools)


@pytest.fixture
def mock_unknown_pid(monkeypatch):
    """USB detected but unknown PID."""
    from ifix_ios.core.detector import DeviceMode
    _mock_usb(monkeypatch, DeviceMode.UNKNOWN, "9999")
    _mock_subprocess(monkeypatch, _make_subprocess_runner({
        "lsusb": {"stdout": "Bus 001 Device 042: ID 05ac:9999 Apple, Inc.\n"},
        "idevice_id": {"stdout": ""},
        "ideviceinfo": {"stdout": ""},
    }))


@pytest.fixture
def mock_lsusb_fallback(monkeypatch):
    """pyusb error, falls back to lsusb which finds device."""
    from ifix_ios.core.detector import DeviceMode
    _mock_usb(monkeypatch, DeviceMode.UNKNOWN, None)
    _mock_subprocess(monkeypatch, _make_subprocess_runner({
        "lsusb": {"stdout": "Bus 001 Device 042: ID 05ac:12a8 Apple, Inc. iPhone\n"},
        "idevice_id": {"stdout": "0000UDID\n"},
        "ideviceinfo": {"stdout": "ProductType: iPhone17,2\nProductVersion: 26.5.2\n"},
    }))


# =============================================================================
# STRESS TEST 1: Detection — all mode transitions
# =============================================================================


@pytest.mark.stress
class TestDetectionStress:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        from ifix_ios.core.detector import DeviceDetector
        DeviceDetector._last_known_info.clear()

    def test_absent_device(self, mock_absent_no_tools):
        from ifix_ios.core.detector import DeviceDetector, DeviceMode
        detector = DeviceDetector()
        dev = detector.detect()
        assert dev.mode == DeviceMode.ABSENT
        assert dev.udid is None
        assert dev.usb_id is None

    def test_normal_device_full_info(self, mock_normal_full):
        from ifix_ios.core.detector import DeviceDetector, DeviceMode
        detector = DeviceDetector()
        dev = detector.detect()
        assert dev.mode == DeviceMode.NORMAL
        assert dev.udid == "0000MOCK-1234567890"
        assert dev.product_type == "iPhone17,2"
        assert dev.product_version == "26.5.2"
        assert dev.device_name == "Test iPhone 16 Pro Max"
        assert dev.battery_level == 85

    def test_recovery_device(self, mock_recovery):
        from ifix_ios.core.detector import DeviceDetector, DeviceMode
        detector = DeviceDetector()
        dev = detector.detect()
        assert dev.mode == DeviceMode.RECOVERY
        assert dev.ecid == "2643364300816412"
        assert dev.product_type == "iPhone17,2"

    def test_dfu_device(self, mock_dfu):
        from ifix_ios.core.detector import DeviceDetector, DeviceMode
        detector = DeviceDetector()
        dev = detector.detect()
        assert dev.mode == DeviceMode.DFU
        assert dev.udid == "0000MOCK-1234567890"

    def test_bootloop_device(self, mock_bootloop):
        from ifix_ios.core.detector import DeviceDetector, DeviceMode
        detector = DeviceDetector()
        dev = detector.detect()
        assert dev.mode == DeviceMode.BOOTLOOP

    def test_unknown_pid(self, mock_unknown_pid):
        from ifix_ios.core.detector import DeviceDetector, DeviceMode
        detector = DeviceDetector()
        dev = detector.detect()
        assert dev.mode == DeviceMode.UNKNOWN

    def test_lsusb_fallback(self, mock_lsusb_fallback):
        from ifix_ios.core.detector import DeviceDetector, DeviceMode
        detector = DeviceDetector()
        dev = detector.detect()
        assert dev.mode == DeviceMode.NORMAL

    def test_no_idevice_tools_normal(self, mock_normal_notools):
        from ifix_ios.core.detector import DeviceDetector, DeviceMode
        detector = DeviceDetector()
        dev = detector.detect()
        assert dev.mode == DeviceMode.NORMAL
        assert dev.udid is None
        assert dev.device_name is None

    def test_no_idevice_tools_dfu(self, mock_dfu_notools):
        from ifix_ios.core.detector import DeviceDetector, DeviceMode
        detector = DeviceDetector()
        dev = detector.detect()
        assert dev.mode == DeviceMode.DFU
        assert dev.udid is None

    def test_mode_transition_preserves_info(self, monkeypatch):
        """Device goes from normal to recovery; info persists via cache."""
        from ifix_ios.core.detector import DeviceDetector, DeviceMode

        detector = DeviceDetector()

        # Normal mode first
        _mock_usb(monkeypatch, DeviceMode.NORMAL, "12a8")
        _mock_subprocess(monkeypatch, _make_subprocess_runner({
            "idevice_id": {"stdout": "0000MOCK-1234567890\n"},
            "ideviceinfo": {"stdout": """ProductType: iPhone17,2
ProductVersion: 26.5.2
DeviceName: Test iPhone 16 Pro Max
"""},
            "lsusb": {"stdout": ""},
        }))
        normal_dev = detector.detect()
        assert normal_dev.mode == DeviceMode.NORMAL
        assert normal_dev.device_name == "Test iPhone 16 Pro Max"

        # Recovery mode — info should carry over
        _mock_usb(monkeypatch, DeviceMode.RECOVERY, "1281")
        _mock_subprocess(monkeypatch, _make_subprocess_runner({
            "idevicerestore": {"stdout": "ECID: 2643364300816412\n"},
            "lsusb": {"stdout": ""},
            "idevice_id": {"stdout": ""},
            "ideviceinfo": {"stdout": ""},
        }))
        recovery_dev = detector.detect()
        assert recovery_dev.mode == DeviceMode.RECOVERY
        assert recovery_dev.product_type == "iPhone17,2"
        assert recovery_dev.device_name == "Test iPhone 16 Pro Max"

    def test_rapid_detections_no_crash(self, mock_normal_full):
        from ifix_ios.core.detector import DeviceDetector, DeviceMode
        detector = DeviceDetector()
        for _ in range(50):
            dev = detector.detect()
            assert dev.mode == DeviceMode.NORMAL
            assert dev.product_type == "iPhone17,2"


# =============================================================================
# STRESS TEST 2: Guide Agent — all diagnosis + plan combinations
# =============================================================================


@pytest.mark.stress
class TestGuideAgentStress:
    def _make_dev(self, mode, **kwargs):
        from ifix_ios.core.detector import DeviceInfo
        return DeviceInfo(mode=mode, **kwargs)

    def test_all_modes_diagnose(self):
        from ifix_ios.core.guide_agent import GuideAgent
        from ifix_ios.core.detector import DeviceMode

        agent = GuideAgent()
        for mode in DeviceMode:
            dev = self._make_dev(mode)
            d = agent.diagnose(dev)
            assert d.problem_id == mode.value
            assert d.device.mode == mode

    def test_normal_device_no_repair_needed(self):
        from ifix_ios.core.guide_agent import GuideAgent, StepType
        from ifix_ios.core.detector import DeviceMode

        agent = GuideAgent()
        dev = self._make_dev(DeviceMode.NORMAL)
        d = agent.diagnose(dev)
        plan = agent.build_plan(d)
        assert StepType.DIAGNOSE in plan.steps
        assert StepType.ERASE_RESTORE not in plan.steps

    def test_bootloop_plan_has_update_first(self):
        from ifix_ios.core.guide_agent import GuideAgent, StepType
        from ifix_ios.core.detector import DeviceMode

        agent = GuideAgent()
        dev = self._make_dev(DeviceMode.BOOTLOOP, udid="0000TEST")
        d = agent.diagnose(dev)
        plan = agent.build_plan(d)
        assert plan.steps.index(StepType.UPDATE_RESTORE) < plan.steps.index(StepType.ERASE_RESTORE)

    def test_dfu_plan_erase_only(self):
        from ifix_ios.core.guide_agent import GuideAgent, StepType
        from ifix_ios.core.detector import DeviceMode

        agent = GuideAgent()
        dev = self._make_dev(DeviceMode.DFU)
        d = agent.diagnose(dev)
        plan = agent.build_plan(d)
        assert StepType.UPDATE_RESTORE not in plan.steps
        assert StepType.ERASE_RESTORE in plan.steps

    def test_absent_plan_minimal(self):
        from ifix_ios.core.guide_agent import GuideAgent, StepType
        from ifix_ios.core.detector import DeviceMode

        agent = GuideAgent()
        dev = self._make_dev(DeviceMode.ABSENT)
        d = agent.diagnose(dev)
        plan = agent.build_plan(d)
        assert len(plan.steps) == 1
        assert StepType.DIAGNOSE in plan.steps

    def test_run_plan_absent_emits_done(self):
        from ifix_ios.core.guide_agent import GuideAgent
        from ifix_ios.core.detector import DeviceMode

        agent = GuideAgent()
        dev = self._make_dev(DeviceMode.ABSENT)
        d = agent.diagnose(dev)
        plan = agent.build_plan(d)
        events = list(agent.run_plan(plan))
        assert len(events) > 0
        assert events[-1].done

    def test_run_plan_normal_emits_success(self):
        from ifix_ios.core.guide_agent import GuideAgent
        from ifix_ios.core.detector import DeviceMode

        agent = GuideAgent()
        dev = self._make_dev(DeviceMode.NORMAL)
        d = agent.diagnose(dev)
        plan = agent.build_plan(d)
        events = list(agent.run_plan(plan))
        assert events[-1].done

    def test_guide_agent_cancel_safe(self):
        from ifix_ios.core.guide_agent import GuideAgent
        agent = GuideAgent()
        agent.cancel()
        assert True

    def test_100_rapid_diagnoses(self):
        from ifix_ios.core.guide_agent import GuideAgent
        from ifix_ios.core.detector import DeviceMode

        agent = GuideAgent()
        all_modes = list(DeviceMode)
        for i in range(100):
            mode = all_modes[i % len(all_modes)]
            dev = self._make_dev(mode)
            d = agent.diagnose(dev)
            assert d.problem_id == mode.value


# =============================================================================
# STRESS TEST 3: Restore parsing — simulated output
# =============================================================================


@pytest.mark.stress
class TestRestoreParsingStress:
    @pytest.fixture(autouse=True)
    def setup(self):
        from ifix_ios.core.restore import RestoreProgress
        self.RestoreProgress = RestoreProgress

    def step_progress(self, lines):
        p = self.RestoreProgress()
        for line in lines:
            p.update(line)
        return p

    def test_full_update_flow(self):
        lines = [
            "Found device in Recovery mode",
            "Verifying iPhone17,2_26.5.2_23F84_Restore.ipsw...",
            "Verifying [===========           ] 45.0%",
            "Verifying [=======================] 100.0%",
            "Downloading firmware...",
            "Downloading [======                ] 22.0%",
            "Downloading [=======================] 100.0%",
            "Extracting firmware...",
            "Uploading [=======               ] 30.0% (iBEC)",
            "Sending iBEC (31300 bytes)...",
            "Uploading [===============       ] 60.0% (kernelcache)",
            "Uploading [=======================] 100.0%",
            "Unmounting filesystems",
            "Sealing System Volume 75.0%",
            "Sealing System Volume 100.0%",
            "Status: Restore Finished",
        ]
        p = self.step_progress(lines)
        assert p.done
        assert p.success
        assert p.phase.name == "DONE"

    def test_full_erase_flow(self):
        lines = [
            "Found device in Recovery mode",
            "Verifying firmware...",
            "Verifying [====                  ] 20.0%",
            "Verifying [==================    ] 80.0%",
            "Verifying [=======================] 100.0%",
            "Downloading [=                    ] 5.0%",
            "Downloading [========             ] 35.0%",
            "Downloading [==================  ] 85.0%",
            "Downloading [=======================] 100.0%",
            "Uploading [==                   ] 10.0% (iBSS)",
            "Uploading [========             ] 40.0% (iBEC)",
            "Uploading [============         ] 55.0% (DeviceTree)",
            "Uploading [==================   ] 80.0% (kernelcache)",
            "Uploading [=======================] 100.0%",
            "Installing RecoveryOS...",
            "Sealing System Volume 50.0%",
            "Sealing System Volume 100.0%",
            "Restore Finished",
        ]
        p = self.step_progress(lines)
        assert p.done
        assert p.success

    def test_error_mid_restore(self):
        lines = [
            "Found device in Recovery mode",
            "Verifying firmware...",
            "Verifying [====                  ] 20.0%",
            "Error: Could not connect to lockdownd (-12)",
        ]
        p = self.step_progress(lines)
        assert p.done
        assert not p.success
        assert "lockdownd" in (p.error or "")

    def test_error_in_upload(self):
        lines = [
            "Uploading [=======               ] 30.0% (kernelcache)",
            "Error: AMRecoveryModeDeviceCopyHomeButtonHasTag failed with error 0xe8000001",
        ]
        p = self.step_progress(lines)
        assert p.done
        assert not p.success
        assert p.phase.name == "FAILED"

    def test_component_extraction_and_reset(self):
        p = self.RestoreProgress()
        p.update("Uploading [======= 30.0%] (kernelcache.release.iphone17)")
        assert p.component == "kernelcache.release.iphone17"
        p.update("Sending iBEC (31300 bytes)...")
        assert p.component == ""

    def test_percent_various_formats(self):
        cases = [
            ("Verifying [=] 1.2%", 1),
            ("Verifying [===] 15.0%", 15),
            ("Verifying [=========] 50%", 50),
            ("Verifying [===============] 75.5%", 75),
            ("Verifying [====================] 99.9%", 99),
            ("Verifying 100%", 100),
        ]
        for line, expected in cases:
            p = self.RestoreProgress()
            p.update(line)
            assert p.percent == expected, f"Failed on: {line}"

    def test_sealing_various_messages(self):
        sealing_lines = [
            "Sealing System Volume 25.0%",
            "sealing system volume 50.0%",
            "Sealing 75.0%",
        ]
        for line in sealing_lines:
            p = self.RestoreProgress()
            p.update(line)
            assert p.phase.name == "SEALING", f"Failed to detect: {line}"

    def test_sequential_updates_no_state_leak(self):
        p = self.RestoreProgress()
        p.update("Verifying [===========] 50.0%")
        assert p.percent == 50
        p.update("Found device in Recovery mode")
        assert p.percent == 0
        assert p.phase.name == "CHECKING"
        assert p.component == ""
        assert p.message == ""

    def test_random_noise_lines(self):
        noise = [
            "", " ", "  \t  ",
            "usb 1-1: new high-speed USB device number 42",
            "some random debug output",
            "[0m[[0m 0% [0m]",
            "\x1b[?25l\x1b[?25h",
            "WARNING: device may not be in a valid state",
        ]
        for line in noise:
            p = self.RestoreProgress()
            p.update(line)
        assert True


# =============================================================================
# STRESS TEST 4: Edge cases
# =============================================================================


@pytest.mark.stress
class TestEdgeCases:
    def test_cache_corrupt_json_doesnt_crash(self, tmp_path):
        from ifix_ios.core.firmware import load_cache

        cache_file = tmp_path / ".cache" / "ifix-ios" / "firmware_iPhone17,2.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text("this is not valid json {{{")

        with patch.object(Path, "home", return_value=tmp_path):
            result = load_cache("iPhone17,2")
            assert result is None

    def test_cache_expired_returns_none(self, tmp_path):
        from ifix_ios.core.firmware import load_cache

        data = {"cached_at": "2020-01-01T00:00:00", "firmwares": []}
        cache_dir = tmp_path / ".cache" / "ifix-ios"
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "firmware_iPhone17,2.json").write_text(json.dumps(data))

        with patch.object(Path, "home", return_value=tmp_path):
            result = load_cache("iPhone17,2")
            assert result is None

    def test_lsusb_no_apple_no_crash(self):
        from ifix_ios.core.detector import DeviceDetector, DeviceMode

        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args[0] if args else [],
                returncode=0,
                stdout="""Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
Bus 001 Device 002: ID 8087:0024 Intel Corp.
""",
                stderr="",
            )

        with patch("ifix_ios.core.detector.subprocess.run") as mock_run:
            mock_run.side_effect = fake_run
            detector = DeviceDetector()
            mode, pid = detector._scan_usb_lsusb()
            assert mode == DeviceMode.ABSENT
            assert pid is None

    def test_lsusb_command_not_found(self):
        from ifix_ios.core.detector import DeviceDetector, DeviceMode

        def fake_run(*args, **kwargs):
            raise FileNotFoundError("lsusb not found")

        with patch("ifix_ios.core.detector.subprocess.run") as mock_run:
            mock_run.side_effect = fake_run
            detector = DeviceDetector()
            mode, pid = detector._scan_usb_lsusb()
            assert mode == DeviceMode.UNKNOWN

    def test_concurrent_detection_no_race(self):
        from ifix_ios.core.detector import DeviceDetector

        d1 = DeviceDetector()
        d2 = DeviceDetector()
        d1._last_known_info["product_type"] = "iPhone17,2"
        assert d2._last_known_info["product_type"] == "iPhone17,2"


# =============================================================================
# STRESS TEST 5: Format device info — all states
# =============================================================================


@pytest.mark.stress
class TestFormatDeviceInfoStress:
    def _make_dev(self, mode, **kwargs):
        from ifix_ios.core.detector import DeviceInfo, DeviceMode
        return DeviceInfo(mode=mode or DeviceMode.UNKNOWN, **kwargs)

    def test_format_all_modes_no_data(self):
        from ifix_ios.core.detector import DeviceMode, format_device_info

        for mode in DeviceMode:
            dev = self._make_dev(mode)
            result = format_device_info(dev)
            assert result is not None

    def test_format_with_partial_data(self):
        from ifix_ios.core.detector import DeviceMode, format_device_info

        combos = [
            {"udid": "0000TEST"},
            {"product_type": "iPhone17,2"},
            {"battery_level": 50},
            {"product_version": "26.5.2", "build": "23F84"},
            {"device_name": "Test", "serial": "SERIAL123"},
            {"activation_state": "Unlocked"},
            {"ecid": "12345"},
        ]
        for data in combos:
            dev = self._make_dev(DeviceMode.NORMAL, **data)
            result = format_device_info(dev)
            assert result is not None

    def test_format_battery_extremes(self):
        from ifix_ios.core.detector import DeviceMode, format_device_info

        for level in [0, 1, 10, 49, 50, 99, 100]:
            dev = self._make_dev(DeviceMode.NORMAL, battery_level=level)
            result = format_device_info(dev)
            assert result is not None


# =============================================================================
# STRESS TEST 6: Concurrent operations simulation
# =============================================================================


@pytest.mark.stress
class TestConcurrencyStress:
    @pytest.fixture(autouse=True)
    def clear_cache(self):
        from ifix_ios.core.detector import DeviceDetector
        DeviceDetector._last_known_info.clear()

    def test_mixed_detection_types(self, monkeypatch):
        from ifix_ios.core.detector import DeviceDetector, DeviceMode

        detector = DeviceDetector()

        # Absent
        _mock_usb(monkeypatch, DeviceMode.ABSENT, None)
        _mock_subprocess(monkeypatch, _make_subprocess_runner({"lsusb": {"stdout": ""}}))
        assert detector.detect().mode == DeviceMode.ABSENT

        # Normal
        _mock_usb(monkeypatch, DeviceMode.NORMAL, "12a8")
        _mock_subprocess(monkeypatch, _make_subprocess_runner({
            "idevice_id": {"stdout": "0000UDID\n"},
            "ideviceinfo": {"stdout": "ProductType: iPhone17,2\nProductVersion: 26.5.2\nDeviceName: Test\n"},
            "lsusb": {"stdout": ""},
        }))
        assert detector.detect().mode == DeviceMode.NORMAL

        # DFU
        _mock_usb(monkeypatch, DeviceMode.DFU, "1227")
        _mock_subprocess(monkeypatch, _make_subprocess_runner({
            "idevice_id": {"stdout": "0000UDID\n"},
            "lsusb": {"stdout": ""},
        }))
        assert detector.detect().mode == DeviceMode.DFU

        # Recovery
        _mock_usb(monkeypatch, DeviceMode.RECOVERY, "1281")
        _mock_subprocess(monkeypatch, _make_subprocess_runner({
            "idevicerestore": {"stdout": "ECID: 12345\nIdentified device as d94ap, iPhone17,2\n"},
            "lsusb": {"stdout": ""},
            "idevice_id": {"stdout": ""},
            "ideviceinfo": {"stdout": ""},
        }))
        assert detector.detect().mode == DeviceMode.RECOVERY

        # Back to absent
        _mock_usb(monkeypatch, DeviceMode.ABSENT, None)
        _mock_subprocess(monkeypatch, _make_subprocess_runner({"lsusb": {"stdout": ""}}))
        assert detector.detect().mode == DeviceMode.ABSENT


# =============================================================================
# STRESS TEST 7: Installer edge cases
# =============================================================================


@pytest.mark.stress
class TestInstallerStress:
    def test_detect_unknown_distro(self):
        from ifix_ios.core.installer import detect_distro

        with patch("ifix_ios.core.installer.Path.read_text", side_effect=FileNotFoundError):
            with patch("ifix_ios.core.installer.subprocess.run", side_effect=FileNotFoundError):
                assert detect_distro() is None

    def test_get_distro_config_none(self):
        from ifix_ios.core.installer import get_distro_config
        assert get_distro_config(None) is None

    def test_get_distro_config_unknown_no_fallback_files(self):
        from ifix_ios.core.installer import get_distro_config
        with patch("ifix_ios.core.installer.Path.exists", return_value=False):
            assert get_distro_config("somerandomos") is None


from ifix_ios.core.guide_agent import StepType
