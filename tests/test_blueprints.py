"""Blueprint validation: both knob blueprints parse, carry the expected
inputs/gestures, and the native variant uses only stock HA/MA actions
(no relay, no rest_command, no http)."""
import os
import yaml

BP_DIR = os.path.join(os.path.dirname(__file__), "..", "blueprints",
                      "automation", "kiwipaulrob")
GENERIC = os.path.join(BP_DIR, "zg101zd_knob_gestures.yaml")
NATIVE = os.path.join(BP_DIR, "zg101zd_knob_ma_native.yaml")

GESTURES = {"rotate_right", "rotate_left", "press", "double_press", "hold",
            "hold_rotate_right", "hold_rotate_left"}


class BlueprintLoader(yaml.SafeLoader):
    pass


def _input_tag(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {"!input": loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {"!input": loader.construct_sequence(node)}
    return {"!input": loader.construct_mapping(node)}


BlueprintLoader.add_multi_constructor("!", _input_tag)


def load(path):
    with open(path) as f:
        return yaml.load(f, Loader=BlueprintLoader)


def test_generic_blueprint_gestures():
    bp = load(GENERIC)
    assert bp["blueprint"]["domain"] == "automation"
    inputs = set(bp["blueprint"]["input"])
    assert inputs == {"knob_action_topic"} | {g + "_action" for g in GESTURES}
    assert bp.get("mode") == "queued" and bp.get("max") == 10


def test_native_blueprint_inputs():
    bp = load(NATIVE)
    assert bp["blueprint"]["domain"] == "automation"
    inputs = bp["blueprint"]["input"]
    for key in ("knob_action_topic", "speakers", "memory_helper",
                "volume_db_per_detent", "seek_seconds"):
        assert key in inputs, key
    assert inputs["volume_db_per_detent"]["default"] == 1
    assert inputs["seek_seconds"]["default"] == 10
    assert bp.get("mode") == "queued" and bp.get("max") == 10


def test_native_blueprint_no_relay():
    raw = open(NATIVE).read()
    for banned in ("rest_command", "http://", "8699", "ma_dimmer"):
        assert banned not in raw, banned
    for required in ("media_player.volume_set", "media_player.media_toggle",
                     "media_player.media_next_track", "button.press",
                     "media_player.media_seek", "last_triggered",
                     "device_entities(device_id(target))",
                     "media_position_updated_at"):
        assert required in raw, required


def test_native_event_map_covers_gestures():
    bp = load(NATIVE)
    assert set(bp["variables"]["event_map"].values()) == GESTURES


def test_memory_example_parses():
    path = os.path.join(os.path.dirname(__file__), "..", "examples",
                        "ma-active-player-memory.yaml")
    with open(path) as f:
        doc = yaml.safe_load(f)
    assert doc["alias"] == "MA active player memory"
    assert "input_text.ma_active_player" in yaml.safe_dump(doc)
    assert "group.ma_speakers" in yaml.safe_dump(doc)
