# Volume-knob setup playbook (for a local model guiding the user)

You are helping the user set up a Zigbee smart knob (Tuya ZG-101ZD or
compatible) so that turning it changes the volume of whatever is playing,
pressing/holding adds the current song to Music Assistant favourites, and
triple-pressing switches the knob between volume and next/previous-track
mode. The automation doing all of this is the **native blueprint** in this
repo: `blueprints/automation/kiwipaulrob/zg101zd_knob_ma_native.yaml`.

## Ground rules

- The user is doing the clicking in Home Assistant; you are talking them
  through it. One step at a time, confirm each step before moving on.
- **Read every setup option back verbatim** — field names, menu paths and
  default values exactly as written here. Never paraphrase an entity name,
  topic or option the user must type or pick.
- Never invent entity IDs, topics or room names. If the user doesn't know
  one, tell them exactly where in Home Assistant to look it up (paths are
  given below) and wait for their answer.
- If something doesn't match what you describe, stop and ask — don't push
  ahead on a guess.

## Prerequisites (check all four before starting)

1. Home Assistant with the **Music Assistant** integration playing to at
   least one speaker.
2. **Zigbee2MQTT** with the knob already paired. (The built-in Zigbee
   integration, ZHA, does **not** work with this blueprint — it listens on
   MQTT topics, which ZHA never publishes.)
3. The knob shows an **Action** value changing in the Zigbee2MQTT UI when
   pressed/turned (proves gestures are reaching MQTT).
4. The user can install blueprints (a HA user with automation rights).

## Information to collect first

Ask for these; each has a fallback the user can accept:

- **Knob's MQTT action topic.** Default: `zigbee2mqtt/knob/action`. If they
  renamed the device in Z2M or changed the base topic (Z2M Settings → MQTT),
  the topic differs — have them open the knob in the Zigbee2MQTT UI and read
  you the exact topic.
- **Speaker setup.** Which is true?
  a) The speakers are grouped by **room** in Music Assistant (knob controls
     whichever speaker is playing in its room) — you need the room name.
  b) There is effectively **one speaker** for this knob — you need its
     `media_player` entity.
  c) **Several specific speakers** — you need each `media_player` entity.
  d) A fixed **group** of speakers — you need the group `media_player`.
- **Room name** (only for option a): the Music Assistant room the knob lives
  in. It should match the HA area name.

## Import the blueprint

Give the user one of these two paths:

- **Import link** (easiest): open
  `https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https://github.com/kiwipaulrob/ma-fav-button/blob/main/blueprints/automation/kiwipaulrob/zg101zd_knob_ma_native.yaml`
  in a browser and click Import / Preview.
- **Manual**: copy the file into HA at
  `config/blueprints/automation/kiwipaulrob/zg101zd_knob_ma_native.yaml`,
  then Settings → Automations & scenes → Blueprints → Reload (⋮ menu).

Then: Settings → Automations & scenes → Create automation → Start with a
blueprint → pick the knob blueprint.

## Fill in the form (field by field)

1. **Knob action topic** — the topic from above. Prefilled with
   `zigbee2mqtt/knob/action`; correct it only if theirs differs.
2. **Knob operation_mode select** — required. Path: Settings → Devices →
   knob → entities; pick the entry ending in `operation_mode`.
   Triple-press is the only gesture that flips it, which is how the
   blueprint detects triple-presses.
3. **Speaker source** — from the speaker setup above:
   - room → `Room speakers (knob's MA room)`, plus the room name field.
   - one speaker → `Music Assistant integration entities`, then tick just
     that player.
   - several → `Pick specific speakers`, then tick them.
   - group → `Group player`, then pick the group.
4. **Seek latch** — required toggle. They must first create it: Settings →
   Devices & services → Helpers → + Create helper → Toggle, named e.g.
   "Knob seek" (one per knob). Then pick it here. Explain in one line:
   hold the knob, pause a beat, then turn to seek; the latch makes the
   blueprint ignore the first second of turning.
5. **Memory (only if several speakers share the knob).** Create a Text
   helper (Helpers → + Create helper → Text), pick it in the memory field,
   and switch on **"Knob remembers last speaker"**. From then on every
   gesture records the speaker used, so the knob finds it next time
   everything is idle. Single speaker? Skip both fields entirely.
6. **Announce (optional).** Prefilled message
   `Added {song} by {artist} to favourites`. Pick a TTS voice to hear it
   after each favourite, on the picked speaker (or the knob's current
   speaker if that box is empty). **Announce speed** slider: 0.5×–1.5×,
   1.0 is natural pace, lower is slower — Piper/Wyoming voices only, other
   engines ignore it. For silence: clear the message or leave the voice
   empty.
7. **Tuning** (collapsed): per-detent volume step (default +2 dB), seek jump
   (default 10 s), hold-to-seek window (default 2 s). Leave alone unless the
   user complains volume moves too fast/slow.

Save with a clear name, e.g. "Lounge knob — volume + favourites".

## Verify with the user (do all five)

1. Play music on the intended speaker, turn the knob → volume moves.
2. Stop everything, turn the knob → volume moves on the fallback speaker.
3. Hold the knob → current song lands in MA favourites (check in the MA app).
4. Triple-press → next/previous track mode; triple-press again → back to
   volume.
5. If announce is on: hold the knob → spoken confirmation at the set speed.

## If it misbehaves

- **Nothing happens at all:** wrong action topic is the #1 cause — re-check
  it against the Zigbee2MQTT UI. #2: automation is off or never saved.
- **Volume moves on the wrong speaker:** speaker source/room is wrong, or a
  stale memory helper points elsewhere — clear the Text helper (set it
  empty) and test again.
- **Seeking instead of volume (or vice versa):** the latch toggle wasn't
  created/picked, or the hold wasn't held a full beat before turning.
- **Triple-press does nothing:** wrong `operation_mode` entity picked, or
  the knob model doesn't expose one (some firmware needs a Z2M OTA update).
- **No voice confirmation:** voice entity empty, message cleared, or the
  announce speaker is off. Speed slider affects Piper/Wyoming voices only.
- **Knob paired via ZHA:** stop — this blueprint cannot work. Migrate the
  knob to Zigbee2MQTT first.

## Files in this repo you may point the user at

- `README.md` — the human-readable setup guide (same steps, more prose).
- `examples/ma-active-player-memory.yaml` — optional tracker automation
  that also records playback started outside the knob (phone app, voice
  assistant). Only needed with several speakers.
- `examples/ma-gesture-wiring.yaml`, `examples/ha-automations.yaml` —
  reference wirings, not required for setup.
