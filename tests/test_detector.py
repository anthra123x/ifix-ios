from ifix_ios.core.detector import DeviceDetector, DeviceInfo, DeviceMode


def test_device_info_defaults():
    dev = DeviceInfo()
    assert dev.mode == DeviceMode.ABSENT
    assert dev.udid is None
    assert dev.ecid is None


def test_device_info_with_values():
    dev = DeviceInfo(
        mode=DeviceMode.NORMAL,
        udid="0000TEST-1234",
        product_version="26.5.2",
        product_type="iPhone17,2",
    )
    assert dev.mode == DeviceMode.NORMAL
    assert dev.udid == "0000TEST-1234"
    assert dev.product_version == "26.5.2"
    assert dev.product_type == "iPhone17,2"


def test_detect_no_device():
    detector = DeviceDetector()
    dev = detector.detect()
    assert dev.mode in (DeviceMode.ABSENT, DeviceMode.UNKNOWN)
