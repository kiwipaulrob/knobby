# Volume knob for Music Assistant (no relay, no code)

Turn a Zigbee knob into a volume knob for Music Assistant: **turn** for
volume, **press** for play/pause, **double-press** for next track,
**triple-press** for previous, **hold** to favourite the song,
**turn while holding** to seek through the track.

One blueprint import inside Home Assistant does it all — no Python, no
extra service, no YAML editing. Built for the HOBEIAN ZG-101ZD and any
Zigbee2MQTT knob that sends the same actions.

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fkiwipaulrob%2Fma-fav-button%2Fmain%2Fblueprints%2Fautomation%2Fkiwipaulrob%2Fzg101zd_knob_ma_native.yaml)

## How the volume works

Each rotation detent moves the volume about **1 dB** up or down —
logarithmic steps (×/÷ 1.122), so it feels even from whisper-quiet to
loud, the way hearing works. The knob controls one speaker at a time,
resolved fresh on every gesture:

1. whichever of your speakers is **playing** right now,
2. else the **last-used** speaker (optional memory keeper — see setup),
3. else your **first-listed** speaker as fallback.

You choose the candidate set at import: the **knob's room** (default —
whatever Music Assistant players live in the same HA room as the knob,
no picking needed), **hand-picked players** (most-used first, since the
order is the fallback order), or a **speaker group**. Players you never
want touched (TVs, displays — Music Assistant exposes some as players)
go on the never-pick list, which applies in every mode.

Turn the knob **while holding it** and rotations seek through the track
instead (±10 seconds per detent, clamped to the track) — the favourite
waits to make sure you weren't turning.

## Gestures

| Gesture | What happens |
|---|---|
| Turn right / left | Volume up / down (~1 dB per detent) — or seek while held |
| Press | Play / pause |
| Double-press | Next track |
| Triple-press | Previous track |
| Hold | Favourite the current song (committed ~2 s after the hold, so a turn can cancel it) |
| Hold + turn | Seek ±10 s per detent |

## Setup (~2 minutes)

**1. Put the knob in its room.** In HA: Settings → Devices → your knob,
assign it to the room it lives in. Room mode reads this, so skip it and
the knob finds no speakers.

**2. Note the knob's action topic.** It looks like
`zigbee2mqtt/<name>/action` using the name on the knob's Zigbee2MQTT
device page (spaces become underscores — a knob called "knob" gives
`zigbee2mqtt/knob/action`). Confirm it: open the knob in the
Zigbee2MQTT UI, press/turn it, and watch the Action field under Exposes
update. (If you changed Z2M's base topic under Settings → MQTT, use
that instead of `zigbee2mqtt`.) This comes prefilled at import —
correct it if yours differs. Zigbee2MQTT is required — the blueprint
listens on MQTT topics, which the built-in Zigbee integration (ZHA)
doesn't publish, so a ZHA-paired knob stays invisible to it. (Native
ZHA support would need different triggers and isn't built yet.)

**3. Create the seek latch.** Settings → Devices & services → Helpers →
\+ Create helper → Toggle, named e.g. "Knob seek" (one per knob — a
second knob gets its own). Leave it off; the blueprint switches it on
and off by itself to tell seeking apart from volume.

**4. Import the blueprint** (badge above) and fill the form: action
topic, the knob's `operation_mode` select (Settings → Devices → knob →
entities — the entry ending in `operation_mode`; triple-press is the
only thing that flips it, which is how the blueprint detects
triple-presses), speaker source, and the latch helper from step 3 — plus the memory
field and remember switch if several speakers share the knob (see below).

**5. Turn it.** Volume should move on the playing speaker immediately —
no restart needed (Automations → Reload only if you edit later).

**More than one speaker on this knob?** Create an `input_text` helper
(Settings → Devices & services → Helpers → + Create helper → Text),
pick it in the memory field, and switch on "Knob remembers last
speaker" (off by default). From then on every turn, press and hold
writes the speaker just used into the memory, so the knob finds it
next time everything is idle. One speaker? Skip all of this — the
fallback already lands correctly.

**6. (Optional) voice confirmation.** The announce message ships
prefilled (`Added {song} by {artist} to favourites`); pick a voice and
it speaks after each favourite — on the picked speaker, or the knob's
current speaker if that box is empty. A speed slider (0.5×–1.5×,
natural pace by default) slows or quickens Piper voices — other
engines ignore it. Clear the message, or leave the voice empty, for silence.

## Technique and quirks

- **Press, beat, turn.** Hold the knob, pause a beat, then turn to seek.
  Spinning the instant you press still nudges volume for the first
  detent(s) — physics beats intent at that speed.
- **Triple-press flips the knob's mode** (event ↔ command) instead of
  sending an action — the blueprint watches the flip in both directions
  and fires previous-track twice (restart-current, then step back). A
  very fast triple parses as a double (next track) instead; slow down a
  touch if previous-track misfires.
- **Tuning** lives in a collapsed section at the bottom of the form:
  volume step (default 1 dB), seek step (default 10 s), hold-to-seek
  window (default 2 s — longer is more forgiving, but the favourite
  lands that much later).

## Troubleshooting

- **Nothing happens:** the action topic is wrong (step 2) — the single
  most common cause. Re-check it against the Z2M device page.
- **Wrong speaker moves:** the knob is in the wrong HA room, or a TV /
  display needs adding to never-pick.
- **Holding favourites when you meant to seek:** you turned too fast
  after pressing — press, beat, turn.
- **Announce stays silent:** no voice picked, or the message box was
  cleared. Both are valid "off switches".
- **Needs HA 2024.6.0+** (input sections on the form).

## Files

- `blueprints/automation/kiwipaulrob/zg101zd_knob_ma_native.yaml` — the blueprint
- `examples/ma-active-player-memory.yaml` — optional memory keeper
  (tracks the playing speaker across restarts; needs an `input_text` helper)

## License

MIT — do what you like, no warranty. Not affiliated with Music
Assistant, Nabu Casa, or HOBEIAN.
