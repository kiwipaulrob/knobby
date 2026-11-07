# Zigbee knob technical guide (HOBEIAN ZG-101ZD + Music Assistant)

Everything learned making this knob drive volume, seeking, favourites
and voice confirmations reliably. Device behaviour first, then the
traps, then how the automation is built around them.

## 1. The device

- **HOBEIAN ZG-101ZD**, a Tuya TS0601-class smart knob, paired via
  **Zigbee2MQTT**. A sibling device (Candeo ERS-10TZBVK-AA) shares the
  same action set and is the better-documented reference.
- Gestures arrive as **plain-string payloads** on one MQTT topic, e.g.
  `zigbee2mqtt/knob 2/action` with payload `brightness_step_up`.
  The topic carries no JSON envelope — automations can match
  `trigger.payload` directly.
- Each gesture also updates `sensor.knob_2_last_action` and, for steps,
  numeric sensors (`action_step_size`, `action_rate`,
  `action_color_temperature_delta`, …).
- **ZHA can't drive this setup.** Both the retired relay and the native
  blueprint consume MQTT topics, which the built-in ZHA integration
  doesn't publish. The knob must be paired through Zigbee2MQTT.
- Known upstream quirk: Z2M has misdetected this model (wrong
  identification as "Tuya Smart knob ZG-101Z/D", herdsman issue
  #28149). If exposes/actions look wrong after pairing, re-interview
  the device before blaming the automation.

## 2. Operation modes and the action truth table

The knob has two operation modes (Z2M `operation_mode` select:
`event` / `command`). The vocabulary changes completely between them:

| Gesture | Event mode action | Command mode action |
|---|---|---|
| Rotate right / left | `rotate_right` / `rotate_left` | `brightness_step_up` / `brightness_step_down` |
| Press-and-rotate right / left | *(same as rotate)* | `color_temperature_step_up` / `color_temperature_step_down` |
| Press | `single` | `toggle` |
| Double-press | `double` | `double` |
| Hold (release after long press) | `hold` | — |
| Push and hold > ~3 s | — | `hue_move` |

Notes:

- In **command mode** the knob tells you whether it was pressed: plain
  rotation sends brightness steps, pressed rotation sends colour-
  temperature steps. That distinction is free intent information —
  the automation seeks on colour-temperature steps unconditionally
  and never needs a latch for them.
- In **event mode** press-and-rotate is indistinguishable from a plain
  turn (`rotate_right`/`rotate_left`), so held-turn seeking there does
  need a latch (see §5).
- `hue_move` fires only after ~3 s of continuous pressing. There is
  **no press-down event** — a short press is only visible on release
  (`toggle`/`single`).
- **Triple-press sends no action at all.** It only flips the device's
  operation mode. The automation detects previous-track from the
  mode-select entity flipping in *either* direction (dual-edge proxy),
  so triple works whichever mode you start in.

## 3. Event ordering and timing — the traps

These were found the hard way, in live traces. Design around them.

1. **Turns arrive before the hold, never after.** Press-and-rotate
   sends its steps during the first ~3 s; `hue_move` (the hold) fires
   at the end. Any "wait to see if a turn follows the hold" logic
   watches a window in which nothing can arrive, so every long seek
   ends in a favourite. The fix: every rotation stamps
   `input_datetime.knob_2_last_turn`, and the hold step checks
   *backwards* as well as forwards — a turn within the seek window
   just *before* the hold cancels the favourite.
2. **The 3-second threshold shapes every gesture.** Press + rotate +
   release inside ~3 s produces steps with no hold event at all.
   Cross the threshold and a hold event lands on top of finished
   steps. Favourite-on-hold must therefore tolerate trailing holds,
   not just leading ones.
3. **The mode select can lie.** Observed live: the Z2M select read
   `event` for 12+ hours while every action arriving was
   command-vocabulary. Setting it back via `select.select_option`
   was accepted and then silently reverted. Consequences: anything
   keyed off the select (triple/previous-track detection) can go
   stale. If triple dies, suspect the select before the automation.
4. **Steps can alternate direction.** A press-and-rotate-forward
   session was once observed as `…_down, …_up, …_down, …_up…`
   alternating ~1/s with no hold event. Possibly frustrated wiggling,
   possibly a device quirk — if seeks ever jitter back and forth,
   capture `sensor.knob_2_last_action` history and compare.
5. **Recorder may not show helper history.** The seek latch armed and
   disarmed for hours while its history query returned zero rows
   (`last_changed` moved; the recorder simply had nothing). Check
   `last_changed` on the entity state before concluding a helper
   never fired.
6. **Template footguns.** HA's `as_timestamp()` rejects a never-fired
   `last_triggered` (`None`) — guard with `is none`, never
   `as_timestamp(x or 0)`. Blueprint `variables:` evaluate top-down:
   a variable must be defined *below* anything it references is fine,
   but *above* its users — referencing a variable declared later
   renders empty (this once broke `tts.speak` with "expected 'all'
   or 'none'").
   - Template variables always render to strings: a `from_json`-parsed
   mapping stringifies to its repr on output, so `is mapping`/`.get()`
   on a downstream variable never matches. Validate once, keep the raw
   string, and re-parse from source at each use site behind the guard
   (this silently disabled the first version of the position clock —
   caught by the offline render sim, §5).
   - Never branch `{% if %}` on a rendered boolean: `"False"` is a
   non-empty (truthy) string. Render `1`/`0` and compare numerically.
   - A missing attribute renders the string `"None"` — truthy, and fatal
   to `as_timestamp`. Prove it looks like a timestamp (`is string and
   '-' in x`) before parsing.

## 4. Volume control

- Steps are **logarithmic** (×/÷ ~1.122 per detent) so they feel even
  from quiet to loud, with a small **silence kick** so level 1 from
  silence is never dead.
- The knob **follows the music**: on every gesture the automation
  resolves the active speaker — quality endpoint while playing/paused,
  else whichever speaker is playing, else the last-used speaker (a
  paused client is indistinguishable from idle, so it is remembered),
  else any paused speaker. **TVs are always excluded** by entity id.
- Group players are first-class: volume, seeking and announcements
  target the group; the speaker picker can address the room the knob
  is in instead.

## 5. Seek and hold/seek arbitration

- Seek step is **±10 s per detent**, clamped to the track duration;
  seeks are skipped entirely for duration-less streams.
- The player's position feed cannot be trusted mid-track: Music
  Assistant only refreshes `media_position` in the first seconds of
  each song, so after the first minute the sample is frozen and any
  forward projection catapults the seek to the track end. The
  automation therefore keeps its **own position clock** in an
  optional `input_text` helper (`input_text.knob_2_position_clock`)
  holding `{title, position, wall-clock, state}` JSON. Each seek
  extrapolates from the clock while it names the playing track, else
  from a fresh (< 60 s) feed sample, else from the raw sample — then
  clamps to the duration. The clock is anchored on every seek,
  frozen on pause, re-anchored on play, and blanked on track change
  and after voice announcements (which restart the audio flow). With
  no helper picked, behaviour is the old feed-only fallback.
  Live-verified on hardware: hold-turn seeks land ±10 s per detent
  mid-track, and the helper cycled anchor→blank exactly as designed.
- Pressed-turns (`color_temperature_*`) seek unconditionally (§2).
  Unpressed turns seek only while the **seek latch**
  (`input_boolean.knob_2_seek_latch`) is freshly armed by a hold —
  otherwise they are volume.
- Hold-to-favourite is **committed ~2 s after the hold** (tunable
  `seek_window`): a turn arriving after the hold, *or stamped just
  before it* (§3.1), converts the gesture into a seek and the
  favourite never fires. Favouriting is MA add-only, so a stray
  favourite is harmless — but the announcement would talk over the
  music, which is why suppression matters more than the favourite
  itself.

## 6. Voice confirmations

- Favourite confirmations speak ("Added {song} by {artist} to
  favourites") and are **proportional**: the retired relay spoke at
  50% of the music's current level (floor 1/100) so quiet late-night
  listening was never shouted over; the native blueprint speaks at
  current level via Music Assistant.
- Confirmations are **group-aware**: they play on the speaker's sync
  group when it has 2+ live members, direct otherwise. Never announce
  into a group the speaker isn't a member of — MA accepts it and
  plays it to nobody (common after restarts leave ghost members;
  regrouping is normal maintenance).
- **Chime:** `music_assistant.play_announcement` with
  `use_pre_announce: false` speaks with no bell. The HA voice path
  (`tts.speak`) always plays MA's pre-announce chime, and custom
  speeds only exist there.
- **Cloud vs Piper:** custom speed is passed as Piper/Wyoming
  `length_scale`. The Cloud TTS engine **rejects** that option and
  hard-errors the whole announce call (observed live), so the
  automation only takes the custom-speed branch for Piper/Wyoming
  voices — Cloud always uses the chime-free MA call at natural pace.
  Speeds other than 1.0 on Cloud are silently ignored, not errors.
- **Voice problems must never abort the gesture.** The announce step
  runs `continue_on_error: true` with a silent-fallback chain
  (room speaker → remember → group → MA default), because the
  favourite has already landed by then.

## 7. Wiring reference (native blueprint)

One automation from
`blueprints/automation/kiwipaulrob/zg101zd_knob_ma_native.yaml`:

| Input | Purpose |
|---|---|
| `knob_action_topic` | MQTT action topic (`zigbee2mqtt/knob 2/action`) |
| `mode_select` | Z2M operation-mode select (triple/previous-track dual-edge) |
| `speaker_source` | `knob_room` (default) / `pick_players` / `pick_group` |
| `exclude_players` | Entity ids never targeted (TVs) |
| `seek_latch` | `input_boolean` arming held-turn seek |
| `last_turn_helper` | `input_datetime` stamped per rotation (hold look-back) |
| `memory_helper` / `remember_speaker` | Last-used-speaker recall |
| `position_clock` | Optional `input_text` holding the knob's own `{title, position, wall-clock, state}` JSON (seek anchor — §5) |
| `announce_message/voice/speaker/speed` | Confirmation text, `tts.*` engine, target, pace |

Helpers are plain HA entities (`input_boolean`, `input_datetime`,
`input_text`) — create them in the UI, pick them in the blueprint,
Automations → Reload. No restarts, no hosted code.

## 8. Troubleshooting quick index

| Symptom | Likely cause |
|---|---|
| Nothing happens on any gesture | MQTT topic mismatch; automation off; check `sensor.knob_2_last_action` updates |
| Press-and-rotate seeks but favourites too | `last_turn_helper` empty/unset, or seek window shorter than the hold threshold |
| Press-and-rotate changes volume | Event-mode turns with latch off — or device actually in event mode |
| `Invalid options found: ['length_scale']` | Custom speed + non-Piper voice (fixed: speed branch is Piper/Wyoming-only) |
| Announce plays silence | Target group the speaker isn't a member of (ghost members after restart) |
| Triple-press does nothing | `operation_mode` select stale — it can read `event` while the device speaks command |
| Seeks land at/near the track end after the first minute | Dead position feed (MA refreshes only at track start) — pick the `position_clock` helper so seeks extrapolate from the knob's own anchor (§5) |
| Seeks land a fixed step past zero | `None` position base — same dead-feed family; clock or fresh sample required, never a stale projection |
| Volume jumps on first detent from silence | Silence-kick constant — intentional |
| A run dies in a template | `as_timestamp()` on `None`, or a variable referenced above its definition |

## 9. Lineage

The retired Python relay (`ma-fav-button-relay.py`, `examples/`,
`tests/test_relay_*.py`) did all of this behind a `rest_command`
with the brains in hosted code: dumb-pipe HA automations, per-gesture
`event_type` slots, dry-run testing (`/health`, `"dry_run": true`),
and the gesture blueprint `zg101zd_knob_gestures.yaml`. It still
works, but the native blueprint replaces it with one import, no
hosted code, and the same gestures plus triple-press previous and
press-and-turn seek. The relay's proportional-voice and dry-run
ideas are preserved above so they survive the relay docs' removal.
