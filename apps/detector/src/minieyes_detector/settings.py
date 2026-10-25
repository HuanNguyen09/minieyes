"""Detector settings from MINIEYES_* environment variables, validated at startup."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class SettingsError(ValueError):
    """Configuration is missing or malformed; the process should exit."""


@dataclass(frozen=True)
class Settings:
    site: str
    cameras: dict[str, str]
    event_api_url: str
    api_key: str
    triton_url: str = "triton:8001"
    model: str = "yolov8n"
    zones_file: str = "/config/zones.yaml"
    http_port: int = 8080
    debounce_frames: int = 2
    cooldown_seconds: float = 30.0
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        def get(name: str) -> str | None:
            value = env.get(f"MINIEYES_{name}", "").strip()
            return value or None

        api_key = get("API_KEY")
        if api_key is None and (key_file := get("API_KEY_FILE")):
            api_key = Path(key_file).read_text().strip() or None

        required = {
            "MINIEYES_SITE": get("SITE"),
            "MINIEYES_CAMERAS": get("CAMERAS"),
            "MINIEYES_EVENT_API_URL": get("EVENT_API_URL"),
            "MINIEYES_API_KEY": api_key,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise SettingsError(f"missing required settings: {', '.join(missing)}")

        optional: dict[str, object] = {}
        for name, field, convert in (
            ("TRITON_URL", "triton_url", str),
            ("MODEL", "model", str),
            ("ZONES_FILE", "zones_file", str),
            ("HTTP_PORT", "http_port", int),
            ("DEBOUNCE_FRAMES", "debounce_frames", int),
            ("COOLDOWN_SECONDS", "cooldown_seconds", float),
            ("LOG_LEVEL", "log_level", str.upper),
        ):
            if (raw := get(name)) is not None:
                try:
                    optional[field] = convert(raw)
                except ValueError as e:
                    raise SettingsError(f"MINIEYES_{name}={raw!r}: {e}") from e

        return cls(
            site=required["MINIEYES_SITE"],
            cameras=_parse_cameras(required["MINIEYES_CAMERAS"]),
            event_api_url=required["MINIEYES_EVENT_API_URL"],
            api_key=api_key,
            **optional,
        )


def _parse_cameras(raw: str) -> dict[str, str]:
    """`cam1=rtsp://...,cam2=rtsp://...` -> {"cam1": "rtsp://...", ...}"""
    cameras = {}
    for entry in raw.split(","):
        name, _, url = entry.strip().partition("=")
        if not name or not url:
            raise SettingsError(f"MINIEYES_CAMERAS entry {entry.strip()!r} must be name=url")
        cameras[name.strip()] = url.strip()
    return cameras
