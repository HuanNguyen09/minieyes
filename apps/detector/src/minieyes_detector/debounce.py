"""Turn per-frame zone hits into intrusions: require a streak of frames, then hold a cooldown."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from minieyes_detector.zones import Detection, Hit, Zone

Clock = Callable[[], float]


@dataclass(frozen=True)
class Intrusion:
    zone: Zone
    detection: Detection


class Debouncer:
    def __init__(self, frames: int, cooldown: float, clock: Clock):
        self._frames = frames
        self._cooldown = cooldown
        self._clock = clock
        self._streaks: dict[tuple[str, str], int] = {}
        self._last_fired: dict[tuple[str, str], float] = {}

    def update(self, camera: str, hits: Iterable[Hit]) -> list[Intrusion]:
        # one entry per zone this frame, keeping the most confident detection
        best: dict[str, Hit] = {}
        for h in hits:
            current = best.get(h.zone.name)
            if current is None or h.detection.confidence > current.detection.confidence:
                best[h.zone.name] = h

        seen = {(camera, name) for name in best}
        for key in [k for k in self._streaks if k[0] == camera and k not in seen]:
            del self._streaks[key]

        intrusions = []
        for h in best.values():
            key = (camera, h.zone.name)
            self._streaks[key] = self._streaks.get(key, 0) + 1
            if self._streaks[key] < self._frames:
                continue
            now = self._clock()
            last = self._last_fired.get(key)
            if last is None or now - last >= self._cooldown:
                self._last_fired[key] = now
                intrusions.append(Intrusion(h.zone, h.detection))
        return intrusions
