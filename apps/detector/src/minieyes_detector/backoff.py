"""Exponential backoff with a cap and proportional jitter."""

import random


class Backoff:
    def __init__(
        self,
        base: float = 1.0,
        cap: float = 30.0,
        jitter: float = 0.2,
        rng: random.Random | None = None,
    ):
        self._base = base
        self._cap = cap
        self._jitter = jitter
        self._rng = rng or random.Random()
        self._attempt = 0

    def next_delay(self) -> float:
        delay = min(self._base * 2**self._attempt, self._cap)
        self._attempt += 1
        return delay * self._rng.uniform(1 - self._jitter, 1 + self._jitter)

    def reset(self) -> None:
        self._attempt = 0
