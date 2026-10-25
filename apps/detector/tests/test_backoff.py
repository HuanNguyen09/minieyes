import random

from minieyes_detector.backoff import Backoff


def test_delays_double_from_one_second_and_cap_at_thirty():
    backoff = Backoff(base=1.0, cap=30.0, jitter=0.0)

    delays = [backoff.next_delay() for _ in range(7)]

    assert delays == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0]


def test_jitter_keeps_each_delay_within_twenty_percent_of_nominal():
    nominal = [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0]
    backoff = Backoff(base=1.0, cap=30.0, jitter=0.2, rng=random.Random(42))

    delays = [backoff.next_delay() for _ in nominal]

    for delay, expected in zip(delays, nominal, strict=True):
        assert 0.8 * expected <= delay <= 1.2 * expected
    assert delays != nominal  # jitter was actually applied


def test_reset_after_a_success_starts_again_from_the_base_delay():
    backoff = Backoff(base=1.0, cap=30.0, jitter=0.0)
    for _ in range(4):
        backoff.next_delay()

    backoff.reset()

    assert backoff.next_delay() == 1.0
