import pytest

from minieyes_detector.settings import Settings, SettingsError

REQUIRED = {
    "MINIEYES_SITE": "site-01",
    "MINIEYES_CAMERAS": "cam1=rtsp://camera-sim:8554/cam1, cam2=rtsp://10.0.0.7/stream",
    "MINIEYES_EVENT_API_URL": "https://events.example.test",
    "MINIEYES_API_KEY": "site-01-key",
}


def test_required_values_are_parsed_and_the_rest_default():
    s = Settings.from_env(REQUIRED)

    assert s.site == "site-01"
    assert s.cameras == {
        "cam1": "rtsp://camera-sim:8554/cam1",
        "cam2": "rtsp://10.0.0.7/stream",
    }
    assert (s.event_api_url, s.api_key) == ("https://events.example.test", "site-01-key")
    assert (s.triton_url, s.model) == ("triton:8001", "yolov8n")
    assert s.zones_file == "/config/zones.yaml"
    assert (s.http_port, s.debounce_frames, s.cooldown_seconds) == (8080, 2, 30.0)
    assert s.log_level == "INFO"


def test_overrides_are_converted_to_the_right_types():
    s = Settings.from_env(
        REQUIRED
        | {
            "MINIEYES_HTTP_PORT": "9100",
            "MINIEYES_COOLDOWN_SECONDS": "12.5",
            "MINIEYES_DEBOUNCE_FRAMES": "3",
        }
    )

    assert (s.http_port, s.cooldown_seconds, s.debounce_frames) == (9100, 12.5, 3)


def test_missing_required_values_fail_fast_and_name_every_one():
    with pytest.raises(SettingsError) as raised:
        Settings.from_env({"MINIEYES_SITE": "site-01"})

    message = str(raised.value)
    for name in ("MINIEYES_CAMERAS", "MINIEYES_EVENT_API_URL", "MINIEYES_API_KEY"):
        assert name in message


def test_a_camera_entry_without_a_url_is_rejected():
    with pytest.raises(SettingsError, match="cam2"):
        Settings.from_env(REQUIRED | {"MINIEYES_CAMERAS": "cam1=rtsp://a/1,cam2"})


def test_the_api_key_can_come_from_a_mounted_secret_file(tmp_path):
    key_file = tmp_path / "api-key"
    key_file.write_text("from-secret\n")
    env = {k: v for k, v in REQUIRED.items() if k != "MINIEYES_API_KEY"}

    s = Settings.from_env(env | {"MINIEYES_API_KEY_FILE": str(key_file)})

    assert s.api_key == "from-secret"
