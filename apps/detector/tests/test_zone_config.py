import pytest

from minieyes_detector.zones import Zone, ZoneConfigError, load_zones

TWO_CAMERAS = """
cameras:
  cam1:
    zones:
      - name: forklift-lane
        polygon: [[100, 100], [300, 100], [300, 300], [100, 300]]
      - name: loading-bay
        polygon: [[0, 0], [50, 0], [50, 50]]
  cam2:
    zones:
      - name: press
        polygon: [[10, 10], [20, 10], [20, 20], [10, 20]]
"""


def test_valid_config_groups_zones_by_camera():
    zones = load_zones(TWO_CAMERAS)

    assert zones == {
        "cam1": [
            Zone("forklift-lane", "cam1", ((100, 100), (300, 100), (300, 300), (100, 300))),
            Zone("loading-bay", "cam1", ((0, 0), (50, 0), (50, 50))),
        ],
        "cam2": [Zone("press", "cam2", ((10, 10), (20, 10), (20, 20), (10, 20)))],
    }


def test_polygon_with_fewer_than_three_points_is_rejected_by_name():
    bad = """
cameras:
  cam1:
    zones:
      - name: thin-line
        polygon: [[0, 0], [10, 10]]
"""
    with pytest.raises(ZoneConfigError, match="thin-line"):
        load_zones(bad)


def test_duplicate_zone_names_on_a_camera_are_rejected():
    dup = """
cameras:
  cam1:
    zones:
      - name: press
        polygon: [[0, 0], [10, 0], [10, 10]]
      - name: press
        polygon: [[20, 20], [30, 20], [30, 30]]
"""
    with pytest.raises(ZoneConfigError, match="press"):
        load_zones(dup)


def test_shipped_example_config_is_valid():
    from pathlib import Path

    example = Path(__file__).parents[1] / "config" / "zones.example.yaml"

    zones = load_zones(example.read_text(encoding="utf-8"))

    assert [z.name for z in zones["cam1"]] == ["forklift-lane", "press-area"]
