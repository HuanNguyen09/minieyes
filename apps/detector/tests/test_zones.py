from minieyes_detector.zones import Detection, Zone, evaluate

SQUARE = Zone(
    name="forklift-lane", camera="cam1", polygon=((100, 100), (300, 100), (300, 300), (100, 300))
)


def person(x1, y1, x2, y2, confidence=0.9):
    return Detection(bbox=(x1, y1, x2, y2), confidence=confidence, label="person")


def test_person_standing_inside_zone_is_a_hit():
    walker = person(180, 50, 220, 200)  # feet at (200, 200)

    hits = evaluate([walker], [SQUARE])

    assert [(h.zone.name, h.detection) for h in hits] == [("forklift-lane", walker)]


def test_feet_exactly_on_zone_boundary_count_as_inside():
    on_bottom_edge = person(180, 150, 220, 300)  # feet at (200, 300)
    on_left_edge = person(80, 150, 120, 250)  # feet at (100, 250)

    hits = evaluate([on_bottom_edge, on_left_edge], [SQUARE])

    assert [h.detection for h in hits] == [on_bottom_edge, on_left_edge]


def test_only_people_trigger_zones():
    forklift = Detection(bbox=(150, 150, 250, 250), confidence=0.95, label="truck")

    assert evaluate([forklift], [SQUARE]) == []


def test_zone_is_judged_by_the_feet_not_the_body():
    leaning_over = person(150, 150, 250, 350)  # body overlaps zone, feet at (200, 350)

    assert evaluate([leaning_over], [SQUARE]) == []


def test_point_in_the_notch_of_a_concave_zone_is_outside():
    # U-shaped zone: notch is the gap between x=150..250 above y=200
    u_shape = Zone(
        name="u",
        camera="cam1",
        polygon=(
            (100, 100),
            (150, 100),
            (150, 200),
            (250, 200),
            (250, 100),
            (300, 100),
            (300, 300),
            (100, 300),
        ),
    )
    in_notch = person(190, 50, 210, 150)  # feet at (200, 150)
    in_left_arm = person(115, 50, 135, 150)  # feet at (125, 150)

    hits = evaluate([in_notch, in_left_arm], [u_shape])

    assert [h.detection for h in hits] == [in_left_arm]


def test_person_in_overlapping_zones_hits_each_zone():
    inner = Zone(
        name="loading-bay", camera="cam1", polygon=((150, 150), (250, 150), (250, 250), (150, 250))
    )
    walker = person(180, 100, 220, 200)  # feet at (200, 200)

    hits = evaluate([walker], [SQUARE, inner])

    assert sorted(h.zone.name for h in hits) == ["forklift-lane", "loading-bay"]
