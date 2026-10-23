"""Red-zone geometry: decide which configured zones a detected person is standing in."""

from collections.abc import Iterable
from dataclasses import dataclass

import yaml

Point = tuple[float, float]


@dataclass(frozen=True)
class Detection:
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 in frame pixels
    confidence: float
    label: str


@dataclass(frozen=True)
class Zone:
    name: str
    camera: str
    polygon: tuple[Point, ...]


class ZoneConfigError(ValueError):
    """Raised when the zones YAML is invalid; the message names the offending zone."""


@dataclass(frozen=True)
class Hit:
    zone: Zone
    detection: Detection


def evaluate(detections: Iterable[Detection], zones: Iterable[Zone]) -> list[Hit]:
    zones = list(zones)
    hits = []
    for detection in detections:
        if detection.label != "person":
            continue
        feet = _anchor(detection.bbox)
        hits.extend(Hit(zone, detection) for zone in zones if _inside(feet, zone.polygon))
    return hits


def _anchor(bbox: tuple[float, float, float, float]) -> Point:
    x1, _, x2, y2 = bbox
    return ((x1 + x2) / 2, y2)


def _on_segment(point: Point, a: Point, b: Point, eps: float = 1e-9) -> bool:
    (x, y), (ax, ay), (bx, by) = point, a, b
    cross = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
    if abs(cross) > eps:
        return False
    return (
        min(ax, bx) - eps <= x <= max(ax, bx) + eps and min(ay, by) - eps <= y <= max(ay, by) + eps
    )


def _inside(point: Point, polygon: tuple[Point, ...]) -> bool:
    """Ray casting; points on the boundary count as inside."""
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        (xi, yi), (xj, yj) = polygon[i], polygon[(i + 1) % n]
        if _on_segment(point, (xi, yi), (xj, yj)):
            return True
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
    return inside


def load_zones(text: str) -> dict[str, list[Zone]]:
    """Parse zones YAML (``cameras.<camera>.zones[].{name, polygon}``) into zones per camera."""
    doc = yaml.safe_load(text) or {}
    result: dict[str, list[Zone]] = {}
    for camera, spec in (doc.get("cameras") or {}).items():
        zones = []
        for z in spec.get("zones", []):
            points = tuple((p[0], p[1]) for p in z["polygon"])
            if len(points) < 3:
                raise ZoneConfigError(
                    f"zone {z['name']!r} on {camera!r} needs at least 3 points, got {len(points)}"
                )
            if any(existing.name == z["name"] for existing in zones):
                raise ZoneConfigError(f"zone {z['name']!r} is defined twice on {camera!r}")
            zones.append(Zone(z["name"], camera, points))
        result[camera] = zones
    return result
