from ifix_ios.core.restore import RestoreProgress, RestorePhase, RestoreAction


def test_restore_progress_initial():
    p = RestoreProgress()
    assert p.phase == RestorePhase.CHECKING
    assert p.percent == 0
    assert not p.done
    assert not p.success


def test_restore_progress_done():
    p = RestoreProgress()
    p.update("Status: Restore Finished")
    assert p.done
    assert p.success
    assert p.phase == RestorePhase.DONE


def test_restore_progress_done_alt():
    p = RestoreProgress()
    p.update("DONE")
    assert p.done
    assert p.success


def test_restore_progress_verifying():
    p = RestoreProgress()
    p.update("Verifying 'iPhone.ipsw'...")
    p.update("Verifying [===========] 50.0%")
    assert p.phase == RestorePhase.VERIFYING
    assert p.percent == 50


def test_restore_progress_downloading():
    p = RestoreProgress()
    p.update("Downloading firmware...")
    p.update("Downloading [=] 1.2%")
    assert p.phase == RestorePhase.DOWNLOADING
    assert p.percent == 1


def test_restore_progress_error():
    p = RestoreProgress()
    p.update("Error: Could not connect to lockdownd (-12)")
    assert p.phase == RestorePhase.FAILED
    assert p.done
    assert not p.success
    assert "lockdownd" in (p.error or "")
