# ifix-ios — Project Protocol for AI Agents

## Workflow: implement → verify

After ANY code change, run the full test protocol:

```bash
make test-protocol
```

This runs:
1. **Import check** — all modules load correctly
2. **Unit tests** (36 tests) — detector, guide agent, restore parser
3. **Stress tests** (41 tests) — all modes, transitions, edge cases, concurrency
4. **Cleanup** — removes mock environment

## For quick iteration

```bash
make test-quick      # unit tests only (~0.2s)
make test-stress     # stress tests only (~0.2s)
make test            # everything
make test-coverage   # with coverage report (HTML in /tmp/ifix-ios-coverage)
```

## Architecture

```
src/ifix_ios/
├── app.py              CLI commands (Click)
├── tui_app.py          TUI (Textual)
├── core/
│   ├── detector.py     USB + idevice detection, DeviceInfo
│   ├── guide_agent.py  Diagnosis, repair plan, fallback execution
│   ├── restore.py      idevicerestore wrapper, progress parser
│   ├── firmware.py     ipsw.me API, cache
│   └── installer.py    System dep installer
```

## Key classes

| Class | File | Responsibility |
|-------|------|----------------|
| `DeviceDetector` | `detector.py` | USB scan → DeviceInfo |
| `GuideAgent` | `guide_agent.py` | Diagnose → build_plan → run_plan(fallback) |
| `RestoreRunner` | `restore.py` | Execute idevicerestore, yield progress |
| `RestoreProgress` | `restore.py` | Parse output lines into phase/percent |
| `IDeviceTUI` | `tui_app.py` | Textual app with auto-refresh 2s |

## When adding new features

1. Write tests FIRST (TDD)
2. Mark stress tests with `@pytest.mark.stress`
3. Run `make test-protocol` before committing
4. Update `KNOWN_DEVICES` in `firmware.py` for new models

## Mock device testing

```bash
python dev/mock_device.py normal    # simulate normal iPhone
python dev/mock_device.py recovery  # simulate recovery mode
python dev/mock_device.py dfu       # simulate DFU mode
python dev/mock_device.py bootloop  # simulate boot-loop
python dev/mock_device.py clear     # restore real device access
```
