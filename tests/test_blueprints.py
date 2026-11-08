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
                "memory_helper", "remember_speaker", "seek_latch",
                "last_turn_helper", "position_clock", "announce_message",
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
    # input is not provided ("Missing input ..."). Only the mandatory
    # inputs (mode_select, seek_latch, position_clock) may lack one.
    for key, inp in top.items():
        if inp is None or "input" in inp:
            continue
        if key in ("mode_select", "seek_latch", "position_clock"):
            continue
        assert "default" in inp, key
    assert top["announce_speed"]["selector"] == {"number": {"min": 0.5,
                                                           "max": 1.5,
                                                           "step": 0.1}}
    tuning = top["tuning"]
    assert tuning.get("collapsed") is True
    for key in ("volume_db_per_detent", "seek_seconds", "seek_window"):
        assert key in tuning["input"], key
    # The helper inputs live in the main body, not under Tuning.
    assert top["last_turn_helper"]["selector"] == {"entity": {"domain": "input_datetime"}}
    assert "default" not in top["position_clock"]
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
    for required in ("media_player.volume_set", "media_player.media_play",
                     "media_player.media_pause", "media_player.media_next_track",
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
                     "music_assistant.play_announcement", "use_pre_announce",
                     "tts_entity_id", "last_turn_helper", "turn_stamp",
                     "turn_ts", "input_datetime.set_datetime",
                     "input_text.set_value", "length_scale"):
        assert required in raw, required
    # The stamp is read via the timestamp attribute, never string-parsed
    # (a time-only helper's "HH:MM:SS" state breaks as_timestamp()).
    assert "as_timestamp(states(turn_stamp))" not in raw


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


def test_hold_skips_continued_hold_echo():
    # Live bug: hue_move repeats ~2/s while held, and the first hold run
    # disarms the latch when its wait expires — so a continued hold
    # started a fresh run that favourited and announced AGAIN, each
    # announcement later than the last. A hold arriving just after a
    # favourite landed must disarm and stop, not re-favourite.
    raw = open(NATIVE).read()
    assert "Skip when a favourite just landed" in raw
    assert "Stop, the favourite already landed" in raw
    assert "states[fav].last_changed" in raw


def test_seek_base_freshness_guard():
    # Live bug (Nov 2026): MA only refreshes position in the first seconds
    # of each track, so projecting from a stale sample catapulted every
    # seek to the track end. The seek base must prefer the knob's own
    # clock while it names the playing track (clock_ok), then a fresh
    # feed sample (feed_ok), then the raw sample — never a stale
    # projection. Booleans render 1/0 because a bare "False" string is
    # truthy in {% if %}.
    raw = open(NATIVE).read()
    for token in ("feed_ok", "clock_ok", "base_pos", "position_clock",
                  "tracks it itself", "Anchor the position clock",
                  "Invalidate the position clock"):
        assert token in raw, token
    assert "live_pos" not in raw


def test_triple_previous_consults_position_clock():
    # Triple-press used to fire previous twice unconditionally, so the
    # current track audibly restarted before stepping back. Near the
    # track start (position clock, else fresh feed) it now fires once.
    raw = open(NATIVE).read()
    for token in ("triple_single", "Previous again when further in"):
        assert token in raw, token


def test_turn_lookback_compares_timestamp_numerically():
    # Live bug: the hold look-back compared the rendered turn_ts STRING
    # to int 0, which raises in Jinja — the condition could never pass,
    # so press-and-turn fell through to the forward watch alone.
    raw = open(NATIVE).read()
    assert "turn_ts > 0" not in raw
    assert "turn_ts | float(0) > 0" in raw


def test_position_math_lives_at_top_level():
    # Seek, triple-press, and pause used to re-derive the same
    # clock/feed/raw priority locally; the shared base_pos is now the
    # single definition, so the per-gesture copies must be gone.
    raw = open(NATIVE).read()
    for gone in ("t_base", "t_clock_ok", "t_pos", "p_est"):
        assert gone not in raw, gone
    assert "triple_single" in raw


def test_stamp_guard_is_boolean():
    # Live bug: the turn-stamp guards read `{{ turn_stamp }}`, which renders
    # the helper's entity-id STRING. HA template conditions only pass on the
    # string "true", so the guard was always false and no turn ever stamped
    # (helper frozen since provisioning). Guards must be boolean expressions;
    # the Jinja truthiness inside turn_ts was always fine and stays as is.
    raw = open(NATIVE).read()
    assert 'conditions: "{{ turn_stamp }}"' not in raw
    assert raw.count("(turn_stamp | default('')) != ''") == 2


def test_keeper_folded_into_native():
    bp = load(NATIVE)
    trig_ids = [t.get("id") for t in bp["triggers"]]
    assert "keeper" in trig_ids
    keeper = next(t for t in bp["triggers"] if t.get("id") == "keeper")
    assert "playing" in keeper["value_template"]
    assert "keeper" in bp["conditions"][0]["value_template"]
    dumped = yaml.safe_dump(bp)
    assert "now_playing[0]" in dumped
    assert "ma-active-player-memory" not in dumped


def _walk_templates(node, out):
    if isinstance(node, str):
        if "{{" in node or "{%" in node:
            out.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            _walk_templates(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_templates(v, out)


def _find_volume_vars(node):
    # The plain-turn step is "- variables: {cur, factor, base, raw, level}".
    if isinstance(node, dict):
        if isinstance(node.get("variables"), dict) and set(
                ("cur", "raw", "level")) <= set(node["variables"]):
            return node["variables"]
        for v in node.values():
            hit = _find_volume_vars(v)
            if hit is not None:
                return hit
    elif isinstance(node, list):
        for v in node:
            hit = _find_volume_vars(v)
            if hit is not None:
                return hit
    return None


def test_volume_climbs_from_whisper_levels():
    # Live bug: MA holds whole percent, so 2% x1.122 = 2.24% read back 2%
    # and the knob could never climb past 2%. Render the SHIPPED raw/level
    # templates and demand real progress from 0% and 2% upward, plus a
    # full taper to 0 going down.
    import jinja2
    bp = load(NATIVE)
    tpls = _find_volume_vars(bp)
    assert tpls is not None, "volume variables block not found"
    env = jinja2.Environment()
    raw_t, level_t = (env.from_string(tpls["raw"]),
                      env.from_string(tpls["level"]))

    def step(vol, fwd, factor=10 ** (1 / 20)):
        ctx = {"cur": vol, "fwd": fwd, "factor": factor, "db_step": 1,
               "base": vol if vol > 0 else 0.02}
        raw = float(raw_t.render(ctx))
        return float(level_t.render({**ctx, "raw": raw}))

    for start in (0.0, 0.02):
        v = start
        for _ in range(10):
            v = step(v, True)
        assert v > start + 0.05, (start, v)
    v = 0.5
    for _ in range(200):
        v = step(v, False)
    assert v == 0.0, v


def test_native_templates_parse():
    """Every Jinja template in the native blueprint must compile.

    pytest checks YAML structure, but only HA compiles the templates:
    a paren typo ships green tests and an unavailable automation.
    A bad action name (media_toggle) ships green tests and a run that
    dies at that step, so check the media_player actions too.
    """
    import jinja2
    bp = load(NATIVE)
    found = []
    _walk_templates(bp, found)
    assert len(found) > 20, found
    env = jinja2.Environment()
    for tpl in found:
        env.parse(tpl)
    raw = open(NATIVE).read()
    assert "media_toggle" not in raw
    valid_mp = {"turn_on", "turn_off", "toggle", "volume_up", "volume_down",
                "volume_set", "volume_mute", "media_play", "media_pause",
                "media_play_pause", "media_stop", "media_previous_track",
                "media_next_track", "play_media", "media_seek",
                "select_source", "select_sound_mode", "shuffle_set",
                "repeat_set", "clear_playlist"}
    import re
    for m in re.finditer(r"action:\s*media_player\.(\w+)", raw):
        assert m.group(1) in valid_mp, m.group(0)


def test_variables_defined_before_use():
    # Live bug: ann_speaker referenced target from ABOVE it; HA
    # evaluates variables top-down, so it rendered empty and
    # tts.speak died with "expected 'all' or 'none'".
    bp = load(NATIVE)
    keys = list(bp["variables"].keys())
    assert keys.index("ann_speaker") > keys.index("target"), keys
    assert keys.index("base_pos") > keys.index("clk_s"), keys


def _find_seek_vars(node):
    # The seek step is "- variables: {pos, upd, dur, ..., seek_to}".
    if isinstance(node, dict):
        if isinstance(node.get("variables"), dict) and "seek_to" in node[
                "variables"]:
            return node["variables"]
        for v in node.values():
            hit = _find_seek_vars(v)
            if hit is not None:
                return hit
    elif isinstance(node, list):
        for v in node:
            hit = _find_seek_vars(v)
            if hit is not None:
                return hit
    return None


def _find_vars_with(node, key):
    # Find a "- variables:" mapping that defines <key>.
    if isinstance(node, dict):
        if isinstance(node.get("variables"), dict) and key in node[
                "variables"]:
            return node["variables"]
        for v in node.values():
            hit = _find_vars_with(v, key)
            if hit is not None:
                return hit
    elif isinstance(node, list):
        for v in node:
            hit = _find_vars_with(v, key)
            if hit is not None:
                return hit
    return None


def _find_step(node, alias):
    # Find a "- alias: <alias>" step dict anywhere in the blueprint.
    if isinstance(node, dict):
        if node.get("alias") == alias:
            return node
        for v in node.values():
            hit = _find_step(v, alias)
            if hit is not None:
                return hit
    elif isinstance(node, list):
        for v in node:
            hit = _find_step(v, alias)
            if hit is not None:
                return hit
    return None


def test_position_clock_math():
    # The knob's own clock must beat the dead feed: with a minutes-stale
    # media_position_updated_at, the seek base extrapolates from the
    # clock anchor, not the frozen sample. Render the SHIPPED templates
    # (top-level parse + seek block) under stubbed HA functions.
    import jinja2
    import json
    from datetime import datetime, timezone
    bp = load(NATIVE)
    seek_tpls = _find_seek_vars(bp)
    assert seek_tpls is not None, "seek variables block not found"
    anchor_step = _find_step(bp, "Anchor the position clock on this seek")
    assert anchor_step is not None, "anchor step not found"
    anchor_tpl = anchor_step["choose"][0]["sequence"][0]["data"]["value"]
    triple_vars = _find_vars_with(bp, "triple_single")
    assert triple_vars is not None, "triple variables block not found"

    NOW = 1794000000.0

    def iso(dt_epoch):
        return datetime.fromtimestamp(dt_epoch,
                                      tz=timezone.utc).isoformat()

    env = jinja2.Environment()

    # Mirror HA 2026.10.4: from_json(value) raises on bad input, but
    # from_json(value, default) returns the default instead.
    _missing = object()

    def _from_json(v, default=_missing):
        try:
            return json.loads(v)
        except ValueError:
            if default is _missing:
                raise
            return default

    env.filters["from_json"] = _from_json
    env.filters["to_json"] = lambda v: json.dumps(v)

    def run(feed_pos, feed_age_s, clock_val, title, playing, dur,
            fwd=True, step=10.0, now_epoch=NOW):
        now_d = datetime.fromtimestamp(now_epoch, tz=timezone.utc)
        attrs = {"media_position": feed_pos,
                 "media_position_updated_at": (iso(now_epoch - feed_age_s)
                                               if feed_age_s is not None
                                               else None),
                 "media_duration": dur, "media_title": title}

        def states(eid):
            if eid == "input_text.clock":
                return clock_val
            return "unknown"

        def state_attr(eid, attr):
            if eid == "media_player.test":
                return attrs.get(attr)
            return None

        def is_state(eid, want):
            return (eid == "media_player.test"
                    and ("playing" if playing else "paused") == want)

        def now():
            return now_d

        def as_timestamp(v):
            if isinstance(v, datetime):
                return v.timestamp()
            if isinstance(v, (int, float)):
                return float(v)
            return datetime.fromisoformat(v).timestamp()

        glb = {"states": states, "state_attr": state_attr,
               "is_state": is_state, "now": now,
               "as_timestamp": as_timestamp}
        ctx = {"target": "media_player.test",
               "clock": "input_text.clock" if clock_val is not None else "",
               "fwd": fwd, "seek_step": step}
        for name in ("cur_title", "clock_raw", "clk_valid", "clk_t",
                     "clk_p", "clk_w", "clk_s", "pos", "upd", "dur",
                     "now_ts", "feed_ts", "feed_ok", "clock_ok",
                     "base_pos"):
            ctx[name] = env.from_string(
                bp["variables"][name]).render(**glb, **ctx)
        for name in ("stepped", "seek_to"):
            ctx[name] = env.from_string(seek_tpls[name]).render(**glb, **ctx)
        ctx["triple_single"] = env.from_string(
            triple_vars["triple_single"]).render(**glb, **ctx)
        return ctx, glb

    def clock_json(p, age_s, title="Song", s=1):
        return json.dumps({"t": title, "p": p, "w": NOW - age_s, "s": s})

    # 1. Dead feed (5 min stale) + live clock: extrapolate from anchor.
    ctx, _ = run(feed_pos=0, feed_age_s=300,
                 clock_val=clock_json(100, 120),
                 title="Song", playing=True, dur=300)
    assert abs(float(ctx["base_pos"]) - 220) < 2, ctx["base_pos"]
    assert abs(float(ctx["seek_to"]) - 230) < 2, ctx["seek_to"]

    # 2. Dead feed, no clock helper: raw sample fallback (old behaviour).
    ctx, _ = run(feed_pos=0, feed_age_s=300, clock_val=None,
                 title="Song", playing=True, dur=300)
    assert float(ctx["base_pos"]) == 0, ctx["base_pos"]
    assert float(ctx["seek_to"]) == 10, ctx["seek_to"]

    # 3. Fresh feed + garbage clock: project from the feed.
    ctx, _ = run(feed_pos=50, feed_age_s=10, clock_val="hello",
                 title="Song", playing=True, dur=300)
    assert abs(float(ctx["base_pos"]) - 60) < 2, ctx["base_pos"]

    # 4. Title mismatch (track changed elsewhere): clock ignored.
    ctx, _ = run(feed_pos=5, feed_age_s=300,
                 clock_val=clock_json(100, 120, title="Old Song"),
                 title="New Song", playing=True, dur=300)
    assert float(ctx["base_pos"]) == 5, ctx["base_pos"]

    # 5. Paused now: frozen clock, no projection from anything.
    ctx, _ = run(feed_pos=0, feed_age_s=300,
                 clock_val=clock_json(100, 120),
                 title="Song", playing=False, dur=300)
    assert float(ctx["base_pos"]) == 0, ctx["base_pos"]

    # 6. Anchor write round-trips through from_json, then extrapolates.
    ctx, glb = run(feed_pos=0, feed_age_s=300,
                   clock_val=clock_json(100, 120),
                   title="Song", playing=True, dur=300)
    ctx["seek_to"] = "230.0"
    written = env.from_string(anchor_tpl).render(**glb, **ctx)
    parsed = json.loads(written)
    assert parsed["t"] == "Song" and parsed["s"] == 1, written
    assert abs(parsed["p"] - 230) < 0.01 and parsed["w"] == NOW, written
    ctx2, _ = run(feed_pos=0, feed_age_s=330, clock_val=written,
                  title="Song", playing=True, dur=300, now_epoch=NOW + 30)
    assert abs(float(ctx2["base_pos"]) - 260) < 2, ctx2["base_pos"]

    # 7. Runaway extrapolation clamps at duration, never past the end.
    ctx, _ = run(feed_pos=0, feed_age_s=300,
                 clock_val=clock_json(290, 60),
                 title="Song", playing=True, dur=300)
    assert float(ctx["seek_to"]) == 300, ctx["seek_to"]

    # 8. Backward detent from the clock.
    ctx, _ = run(feed_pos=0, feed_age_s=300,
                 clock_val=clock_json(100, 120),
                 title="Song", playing=True, dur=300, fwd=False)
    assert abs(float(ctx["seek_to"]) - 210) < 2, ctx["seek_to"]

    # 9. Playing but the feed has no timestamp at all: no crash, raw
    # sample fallback (a missing updated_at renders "None", which must
    # never reach as_timestamp).
    ctx, _ = run(feed_pos=7, feed_age_s=None, clock_val=None,
                 title="Song", playing=True, dur=300)
    assert float(ctx["base_pos"]) == 7, ctx["base_pos"]

    # 10. Triple near the start fires once; far in fires twice.
    ctx, _ = run(feed_pos=1, feed_age_s=300,
                 clock_val=clock_json(1, 2),
                 title="Song", playing=True, dur=300)
    assert abs(float(ctx["base_pos"]) - 3) < 2, ctx["base_pos"]
    assert ctx["triple_single"] == "1", ctx["triple_single"]
    ctx, _ = run(feed_pos=100, feed_age_s=300,
                 clock_val=clock_json(100, 120),
                 title="Song", playing=True, dur=300)
    assert ctx["triple_single"] == "0", ctx["triple_single"]

    # 11. Stale sample past a shorter track's duration (auto-advance
    # with a frozen feed) fires once; genuinely near the end with a
    # live clock still fires twice.
    ctx, _ = run(feed_pos=290, feed_age_s=300, clock_val=None,
                 title="Song", playing=True, dur=180)
    assert ctx["triple_single"] == "1", ctx["triple_single"]
    ctx, _ = run(feed_pos=0, feed_age_s=300,
                 clock_val=clock_json(290, 5),
                 title="Song", playing=True, dur=300)
    assert ctx["triple_single"] == "0", ctx["triple_single"]

    # 12. Paused mid-track takes the safe double-fire.
    ctx, _ = run(feed_pos=0, feed_age_s=300,
                 clock_val=clock_json(100, 120),
                 title="Song", playing=False, dur=300)
    assert ctx["triple_single"] == "0", ctx["triple_single"]

