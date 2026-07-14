from ifix_ios.core.guide_agent import (
    GuideAgent,
    GuideEvent,
    Diagnosis,
    RepairPlan,
    StepType,
    PROBLEM_DESCRIPTIONS,
)
from ifix_ios.core.detector import DeviceInfo, DeviceMode


def test_diagnosis_absent():
    agent = GuideAgent()
    dev = DeviceInfo(mode=DeviceMode.ABSENT)
    d = agent.diagnose(dev)
    assert d.problem_id == "absent"
    assert d.severity == "warning"


def test_diagnosis_normal():
    agent = GuideAgent()
    dev = DeviceInfo(
        mode=DeviceMode.NORMAL,
        product_type="iPhone17,2",
        product_version="26.5.2",
        device_name="Test iPhone",
    )
    d = agent.diagnose(dev)
    assert d.problem_id == "normal"
    assert d.severity == "info"
    assert len(d.details) > 0


def test_diagnosis_bootloop():
    agent = GuideAgent()
    dev = DeviceInfo(mode=DeviceMode.BOOTLOOP, udid="0000TEST")
    d = agent.diagnose(dev)
    assert d.problem_id == "bootloop"
    assert d.severity == "critical"


def test_diagnosis_recovery():
    agent = GuideAgent()
    dev = DeviceInfo(mode=DeviceMode.RECOVERY, ecid="12345", product_type="iPhone17,2")
    d = agent.diagnose(dev)
    assert d.problem_id == "recovery"
    assert d.severity == "critical"


def test_diagnosis_dfu():
    agent = GuideAgent()
    dev = DeviceInfo(mode=DeviceMode.DFU)
    d = agent.diagnose(dev)
    assert d.problem_id == "dfu"
    assert d.severity == "critical"


def test_plan_for_normal():
    agent = GuideAgent()
    dev = DeviceInfo(mode=DeviceMode.NORMAL)
    d = agent.diagnose(dev)
    plan = agent.build_plan(d)
    assert StepType.DIAGNOSE in plan.steps


def test_plan_for_bootloop():
    agent = GuideAgent()
    dev = DeviceInfo(mode=DeviceMode.BOOTLOOP, udid="0000TEST")
    d = agent.diagnose(dev)
    plan = agent.build_plan(d)
    assert StepType.UPDATE_RESTORE in plan.steps
    assert StepType.ERASE_RESTORE in plan.steps
    assert StepType.ENTER_RECOVERY in plan.steps


def test_plan_for_dfu():
    agent = GuideAgent()
    dev = DeviceInfo(mode=DeviceMode.DFU)
    d = agent.diagnose(dev)
    plan = agent.build_plan(d)
    assert StepType.ERASE_RESTORE in plan.steps
    assert StepType.UPDATE_RESTORE not in plan.steps


def test_plan_for_absent():
    agent = GuideAgent()
    dev = DeviceInfo(mode=DeviceMode.ABSENT)
    d = agent.diagnose(dev)
    plan = agent.build_plan(d)
    assert StepType.DIAGNOSE in plan.steps


def test_guide_event_defaults():
    e = GuideEvent(step=StepType.DIAGNOSE, message="testing")
    assert e.step == StepType.DIAGNOSE
    assert e.message == "testing"
    assert e.level == "info"
    assert not e.done
    assert not e.success
    assert e.error is None


def test_guide_event_done():
    e = GuideEvent(step=StepType.DONE, message="done", done=True, success=True)
    assert e.done
    assert e.success


def test_problem_descriptions_all_modes():
    for mode in DeviceMode:
        assert mode.value in PROBLEM_DESCRIPTIONS, f"Missing description for {mode}"


def test_step_labels_all_steps():
    for step in StepType:
        assert step in {
            StepType.CHECK_DEPS,
            StepType.DIAGNOSE,
            StepType.UPDATE_RESTORE,
            StepType.ERASE_RESTORE,
            StepType.ENTER_RECOVERY,
            StepType.VERIFY_REPAIR,
            StepType.DONE,
        }


def test_run_plan_absent_device():
    agent = GuideAgent()
    dev = DeviceInfo(mode=DeviceMode.ABSENT)
    d = agent.diagnose(dev)
    plan = agent.build_plan(d)

    events = list(agent.run_plan(plan))
    assert len(events) > 0
    final = events[-1]
    assert final.done
