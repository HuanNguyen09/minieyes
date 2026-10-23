from fakes import FakeClock

from minieyes_detector.debounce import Debouncer
from minieyes_detector.zones import Detection, Hit, Zone

LANE = Zone("forklift-lane", "cam1", ((0, 0), (10, 0), (10, 10)))
WALKER = Detection((1, 1, 3, 5), 0.9, "person")


def hit(zone=LANE):
    return Hit(zone, WALKER)


def test_intrusion_fires_only_after_two_consecutive_frames():
    clock = FakeClock()
    debouncer = Debouncer(frames=2, cooldown=10.0, clock=clock)

    first = debouncer.update("cam1", [hit()])
    clock.advance(0.2)
    second = debouncer.update("cam1", [hit()])

    assert first == []
    assert [(i.zone.name, i.detection) for i in second] == [("forklift-lane", WALKER)]


def test_a_frame_without_the_hit_resets_the_streak():
    clock = FakeClock()
    debouncer = Debouncer(frames=2, cooldown=10.0, clock=clock)

    results = []
    for frame_hits in ([hit()], [], [hit()]):
        results.append(debouncer.update("cam1", frame_hits))
        clock.advance(0.2)

    assert results == [[], [], []]


def test_repeats_are_suppressed_until_the_cooldown_has_elapsed():
    clock = FakeClock()
    debouncer = Debouncer(frames=2, cooldown=10.0, clock=clock)

    fired_at = []
    for _ in range(30):  # person stays in the zone for 15 s, one frame every 0.5 s
        if debouncer.update("cam1", [hit()]):
            fired_at.append(clock())
        clock.advance(0.5)

    assert fired_at == [0.5, 10.5]


def test_several_people_in_one_zone_count_as_one_streak_and_one_intrusion():
    clock = FakeClock()
    debouncer = Debouncer(frames=2, cooldown=10.0, clock=clock)
    other = Detection((5, 1, 7, 5), 0.8, "person")
    crowd = [Hit(LANE, WALKER), Hit(LANE, other)]

    first = debouncer.update("cam1", crowd)
    clock.advance(0.5)
    second = debouncer.update("cam1", crowd)

    assert first == []
    assert len(second) == 1


def test_cameras_and_zones_are_tracked_independently():
    clock = FakeClock()
    debouncer = Debouncer(frames=2, cooldown=10.0, clock=clock)
    bay = Zone("loading-bay", "cam1", ((20, 20), (30, 20), (30, 30)))
    press = Zone("press", "cam2", ((0, 0), (10, 0), (10, 10)))

    assert debouncer.update("cam1", [hit(LANE)]) == []
    assert debouncer.update("cam2", [hit(press)]) == []  # other camera does not reset cam1
    clock.advance(0.5)
    fired_cam1 = debouncer.update("cam1", [hit(LANE), hit(bay)])  # bay is only on its 1st frame
    fired_cam2 = debouncer.update("cam2", [hit(press)])

    assert [i.zone.name for i in fired_cam1] == ["forklift-lane"]
    assert [i.zone.name for i in fired_cam2] == ["press"]
