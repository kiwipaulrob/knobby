# Volume-knob setup playbook (for a local model guiding the user)

You are helping the user set up a Zigbee smart knob (HOBEIAN / Moes
ZG-101ZD or similar Tuya knob) so that turning it changes Music
Assistant volume, pressing toggles play/pause, double-pressing skips to
the next track, triple-pressing goes back to the previous track, a bare
hold adds the current song to favourites (with optional spoken
confirmation), and turning while held seeks through the track. The
automation doing all of this is the **native blueprint** in this
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
2. **Zigbee2MQTT** with the knob already paired. The blueprint triggers on
   MQTT action topics, so the knob must come from Zigbee2MQTT — check
   Settings → Devices → the knob: the device page must say Zigbee2MQTT
   (with an Exposes section showing Action). A knob paired to HA's
   built-in Zigbee (ZHA / "native" Zigbee) shows no Action field and no
   `operation_mode` select, and stays invisible to this blueprint —
   migrate it first: remove it from ZHA, pair it in Zigbee2MQTT, and use
   its new `zigbee2mqtt/<name>/action` topic below.
3. The knob shows an **Action** value changing in the Zigbee2MQTT UI when
   pressed/turned (proves gestures are reaching MQTT).
4. The user can install blueprints (a HA user with automation rights).

## Information to collect first

Ask for these; each has a fallback the user can accept:

- **Knob's MQTT action topic.** Default: `zigbee2mqtt/knob/action`. If they
  renamed the device in Z2M or changed the base topic (Z2M Settings → MQTT),
  the topic differs — have them open the knob in the Zigbee2MQTT UI and read
  you the exact topic.
- **Speaker source** — one of the blueprint's three options (field
  `Which speakers can the knob control?`):
  a) **Knob's room (recommended)** — the knob controls the Music Assistant
     players in the same HA room as the knob itself. No entities to
     collect — but confirm the knob is assigned to its room (Settings →
     Devices → the knob; room mode reads it from the `operation_mode`
     entity below).
  b) **Choose players** — hand-picked MA `media_player` entities,
     most-used first (the order is the idle fallback order). Collect each
     entity ID.
  c) **Choose a group** — one speaker-group helper holding the MA players.
     Collect the group entity.

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
3. **Speaker source** (`Which speakers can the knob control?`) — from the
   speaker setup above:
   - room → `Knob's room (recommended)`. Nothing else to pick; the knob
     must just be assigned to its room (see above).
   - one/several → `Choose players` (field `Players`), then tick the MA
     players most-used first. The `Players` field only appears in this
     mode.
   - group → `Choose a group` (field `Speaker group`), then pick the
     group helper. Only appears in this mode.
4. **Seek latch** (`Seek latch helper`) — required toggle. They must first
   create it: Settings → Devices & services → Helpers → + Create helper →
   Toggle, named e.g. "Knob seek" (one per knob; leave it off — the
   blueprint switches it on and off by itself). Then pick it here. Explain
   in one line: press, pause a beat, then turn to seek; rotations while
   held seek instead of changing volume, and the favourite waits out the
   2-second hold-to-seek window to make sure they weren't turning.
5. **Memory (only if several speakers share the knob).** Create a Text
   helper (Helpers → + Create helper → Text), pick it in the memory field,
   and switch on **"Knob remembers last speaker"**. From then on every
   gesture records the speaker used, so the knob finds it next time
   everything is idle. Single speaker? Skip both fields entirely.
6. **Announce (optional).** Prefilled message
   `Added {song} by {artist} to favourites`. Pick a TTS voice to hear it
   after each favourite, on the picked speaker (or the knob's current
   speaker if that box is empty). **Announce speed** slider: 0.5–1.5,
   default 1.0 = natural pace (0.8 = slower, 1.2 = faster) — passed to the
   voice as Piper/Wyoming `length_scale`, so other engines ignore it. For silence: clear the message or leave the voice
   empty.
7. **Tuning** (collapsed): Volume step, default 1 dB (0.5–3 dB);
   Seek step, default 10 s (5–60 s); Hold-to-seek window, default 2 s
   (longer is more forgiving, but the favourite lands that much later).
   Leave alone unless the user complains volume moves too fast/slow.

Save with a clear name, e.g. "Lounge knob — volume + favourites".

## Verify with the user (do all five)

1. Play music on the intended speaker, turn the knob → volume moves.
2. Stop everything, turn the knob → volume moves on the fallback speaker.
3. Hold the knob → current song lands in MA favourites (check in the MA app).
4. Triple-press → previous track (the knob's mode flips event↔command
   instead of emitting an action — that flip is what the blueprint fires
   on; a very fast triple may parse as a double/next-track instead).
5. If announce is on: hold the knob → spoken confirmation at the set speed.

## If it misbehaves

- **Nothing happens at all:** wrong action topic is the #1 cause — re-check
  it against the Zigbee2MQTT UI. #2: automation is off or never saved.
- **Volume moves on the wrong speaker:** speaker source/room is wrong, or a
  stale memory helper points elsewhere — clear the Text helper (set it
  empty) and test again.
- **Seeking instead of volume (or vice versa):** the latch toggle wasn't
  created/picked, or the hold wasn't held a full beat before turning.
- **Triple-press does nothing:** wrong `operation_mode` entity picked.
  Every Z2M device has one, and triple-clicking the knob is the only thing
  that flips it — watch the select flip event↔command in HA while
  triple-pressing to confirm.
- **No voice confirmation:** voice entity empty, message cleared, or the
  announce speaker is off. Speed slider affects Piper/Wyoming voices only.
- **Knob paired via ZHA (native HA Zigbee):** this blueprint cannot work —
  it triggers on MQTT action topics, which ZHA never publishes. Signs
  you're on ZHA: the device page has no Exposes/Action section and no
  `operation_mode` select. To migrate: remove the knob from ZHA
  (Settings → Devices → knob → Delete), put it in pairing mode, pair it
  in the Zigbee2MQTT UI, then use its new `zigbee2mqtt/<name>/action`
  topic and `operation_mode` select in the form above.

## Files in this repo you may point the user at

- `README.md` — the human-readable setup guide (same steps, more prose).
- `examples/ma-active-player-memory.yaml` — optional tracker automation
  that also records playback started outside the knob (phone app, voice
  assistant). Only needed with several speakers.
- `examples/ma-gesture-wiring.yaml`, `examples/ha-automations.yaml` —
  reference wirings, not required for setup.
