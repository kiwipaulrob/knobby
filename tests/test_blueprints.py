"""Blueprint validation: both knob blueprints parse, carry the expected
inputs/gestures, and the native variant uses only stock HA/MA actions
(no relay, no rest_command, no http)."""
import os
import yaml

BP_DIR = os.path.join(os.path.dirname(__file__), "..", "blueprints",
                      "automation", "kiwipaulrob")
GENERIC = os.path.join(BP_DIR, "zg101zd_knob_gestures.yaml")
NATIVE = os.path.join(BP_DIR, "zg101zd_knob_ma_native.yaml")

GENERIC_GESTURES = {"rotate_right", "rotate_left", "press", "double_press",
                    "hold", "hold_rotate_right", "hold_rotate_left"}
NATIVE_GESTURES = {"volume_right", "volume_left", "press", "double_press",
                   "hold", "seek_right", "seek_left"}


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
    assert inputs == {"knob_action_topic"} | {g + "_action" for g in GENERIC_GESTURES}
    assert bp.get("mode") == "queued" and bp.get("max") == 10


def _all_inputs(bp):
    """Yield (name, spec) for every input, descending into sections."""
    for name, spec in bp["blueprint"]["input"].items():
        if isinstance(spec, dict) and "input" in spec:
            yield from _all_inputs({"blueprint": {"input": spec["input"]}})
        else:
            yield name, spec


def test_native_blueprint_inputs():
    bp = load(NATIVE)
    assert bp["blueprint"]["domain"] == "automation"
    assert bp["blueprint"].get("author")
    assert bp["blueprint"]["homeassistant"]["min_version"] == "2024.6.0"
    top = bp["blueprint"]["input"]
    for key in ("knob_action_topic", "mode_select", "speaker_source",
                "speaker_pick", "speaker_group", "exclude_players",
                "memory_helper", "remember_speaker", "seek_latch", "announce_message",
                "announce_voice", "announce_speaker", "announce_speed", "tuning"):
        assert key in top, key
    assert top["knob_action_topic"]["default"] == "zigbee2mqtt/knob/action"
    assert top["speaker_source"]["default"] == "knob_room"
    assert top["speaker_pick"]["default"] == []
    # No `visible` conditions: HA 2026.10's blueprint input schema rejects
    # the key (import fails "not a valid option"), so mode scoping lives in
    # the descriptions instead.
    assert "visible" not in top["speaker_pick"]
    assert "visible" not in top["speaker_group"]
    assert top["exclude_players"]["default"] == []
    assert top["announce_message"]["default"] == "Added {song} by {artist} to favourites"
    assert top["announce_voice"]["selector"] == {"entity": {"domain": "tts"}}
    assert top["announce_speaker"]["selector"] == {"entity": {"domain": "media_player"}}
    assert top["remember_speaker"]["default"] is False
    assert "boolean" in top["remember_speaker"]["selector"]
    assert top["announce_speed"]["default"] == 1
    # Every optional input must carry a default (possibly null): HA refuses
    # to generate an automation from the blueprint when a default-less
    # input is not provided ("Missing input ..."). Only the two mandatory
    # inputs (mode_select, seek_latch) may lack one.
    for key, inp in top.items():
        if inp is None or "input" in inp:
            continue
        if key in ("mode_select", "seek_latch"):
            continue
        assert "default" in inp, key
    assert top["announce_speed"]["selector"] == {"number": {"min": 0.5,
                                                           "max": 1.5,
                                                           "step": 0.1}}
    tuning = top["tuning"]
    assert tuning.get("collapsed") is True
    for key in ("volume_db_per_detent", "seek_seconds", "seek_window"):
        assert key in tuning["input"], key
    assert tuning["input"]["volume_db_per_detent"]["default"] == 1
    assert tuning["input"]["seek_seconds"]["default"] == 10
    assert tuning["input"]["seek_window"]["default"] == {"hours": 0,
                                                        "minutes": 0,
                                                        "seconds": 2}
    # Parallel: rotation runs stay instant while a hold run waits out
    # the seek window; the latch (not run ordering) decides seek vs
    # volume.
    assert bp.get("mode") == "parallel" and bp.get("max") == 10
    assert bp.get("max_exceeded") == "silent"


def test_native_inputs_all_have_selectors():
    bp = load(NATIVE)
    for name, spec in _all_inputs(bp):
        assert spec.get("name"), name
        assert spec.get("description"), name
        assert "selector" in spec, name


def test_native_blueprint_no_relay():
    raw = open(NATIVE).read()
    for banned in ("rest_command", "http://", "8699", "ma_dimmer"):
        assert banned not in raw, banned
    for required in ("media_player.volume_set", "media_player.media_toggle",
                     "media_player.media_next_track",
                     "media_player.media_previous_track",
                     "button.press", "media_player.media_seek",
                     "input_boolean", "wait_for_trigger", "wait.completed",
                     "last_changed",
                     "device_entities(device_id(target))",
                     "media_position_updated_at",
                     "integration_entities('music_assistant')",
                     "room_cands", "group_cands", "picked_cands",
                     "exclude", "win_secs",
                     "announce_msg", "tts.speak", "{song}", "{artist}",
                     "ann_speaker", "remember_speaker",
                     "input_text.set_value", "length_scale"):
        assert required in raw, required


def test_native_event_map_covers_gestures():
    bp = load(NATIVE)
    assert set(bp["variables"]["event_map"].values()) == NATIVE_GESTURES


def test_native_triple_proxy_dual_edge():
    bp = load(NATIVE)
    triples = [t for t in bp["triggers"]
               if isinstance(t, dict) and t.get("id") in ("triple", "triple_rev")]
    assert len(triples) == 2
    edges = {(t.get("from"), t.get("to")) for t in triples}
    assert edges == {("event", "command"), ("command", "event")}
    raw = open(NATIVE).read()
    # No remote mode-set: the blueprint watches the select, never writes it.
    assert "select.select_option" not in raw


def test_memory_example_parses():
    path = os.path.join(os.path.dirname(__file__), "..", "examples",
                        "ma-active-player-memory.yaml")
    with open(path) as f:
        doc = yaml.safe_load(f)
    assert doc["alias"] == "MA active player memory"
    assert "input_text.ma_active_player" in yaml.safe_dump(doc)
    assert "group.ma_speakers" in yaml.safe_dump(doc)
