import json
import logging

from minieyes_detector.logs import JsonFormatter, configure


def record(msg, *args, level=logging.INFO, **extra):
    return logging.makeLogRecord(
        {
            "name": "minieyes",
            "levelname": logging.getLevelName(level),
            "levelno": level,
            "msg": msg,
            "args": args,
            **extra,
        }
    )


def test_a_record_is_one_json_line_with_context_fields():
    line = JsonFormatter().format(
        record(
            "intrusion in %s", "forklift-lane", camera="cam1", zone="forklift-lane", event_id="0001"
        )
    )

    assert "\n" not in line
    assert json.loads(line) == {
        "level": "INFO",
        "msg": "intrusion in forklift-lane",
        "logger": "minieyes",
        "camera": "cam1",
        "zone": "forklift-lane",
        "event_id": "0001",
    }


def test_context_fields_are_omitted_when_absent_and_tracebacks_stay_on_one_line():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        rec = record("publish failed", level=logging.ERROR, exc_info=sys.exc_info())

    line = JsonFormatter().format(rec)
    parsed = json.loads(line)

    assert "\n" not in line
    assert set(parsed) == {"level", "msg", "logger", "exc"}
    assert "ValueError: boom" in parsed["exc"]


def test_configure_installs_the_json_formatter_on_the_root_logger():
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    try:
        configure("WARNING")

        assert root.level == logging.WARNING
        assert [type(h.formatter) for h in root.handlers] == [JsonFormatter]
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
