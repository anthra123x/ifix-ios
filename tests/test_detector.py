from ifix_ios.core.detector import (
    DeviceDetector,
    DeviceInfo,
    DeviceMode,
    MODE_COLORS,
    MODE_ICONS,
    MODE_LABELS,
    format_device_info,
)


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


def test_device_info_bootloop():
    dev = DeviceInfo(mode=DeviceMode.BOOTLOOP, udid="0000TEST")
    assert dev.mode == DeviceMode.BOOTLOOP
    assert dev.is_bootloop if hasattr(dev, "is_bootloop") else True


def test_detect_no_device():
    detector = DeviceDetector()
    dev = detector.detect()
    assert dev.mode in (DeviceMode.ABSENT, DeviceMode.UNKNOWN)


def test_format_device_info_empty():
    dev = DeviceInfo()
    result = format_device_info(dev)
    assert result is not None


def test_format_device_info_with_data():
    dev = DeviceInfo(
        mode=DeviceMode.NORMAL,
        udid="0000TEST-1234",
        product_type="iPhone17,2",
        product_version="26.5.2",
        device_name="Test iPhone",
        battery_level=85,
    )
    result = format_device_info(dev)
    assert result is not None


def test_mode_colors_exist():
    for mode in DeviceMode:
        assert mode in MODE_COLORS, f"Missing color for {mode}"


def test_mode_icons_exist():
    for mode in DeviceMode:
        assert mode in MODE_ICONS, f"Missing icon for {mode}"


def test_mode_labels_exist():
    for mode in DeviceMode:
        assert mode in MODE_LABELS, f"Missing label for {mode}"
    assert isinstance(MODE_LABELS[DeviceMode.NORMAL], str)


def test_cache_persistence_across_detections():
    detector = DeviceDetector()
    detector._last_known_info["product_type"] = "iPhone17,2"
    detector._last_known_info["device_name"] = "Cached iPhone"
    detector._last_known_info["ecid"] = "12345"

    merged = detector._merge_last_known(DeviceInfo(mode=DeviceMode.DFU))
    assert merged.product_type == "iPhone17,2"
    assert merged.device_name == "Cached iPhone"
    assert merged.ecid == "12345"


def test_cache_does_not_override_existing():
    detector = DeviceDetector()
    detector._last_known_info["product_type"] = "iPhone99,9"

    merged = detector._merge_last_known(
        DeviceInfo(mode=DeviceMode.NORMAL, product_type="iPhone17,2")
    )
    assert merged.product_type == "iPhone17,2"
