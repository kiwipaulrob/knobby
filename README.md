# ma-fav-button — a music button for Music Assistant

One physical (or dashboard) button that follows you around the house:
**single-press** toggles play/pause, **double-press** skips to the next
track, **hold** favourites the current song and has a voice confirm it —
all on *whichever Music Assistant player is currently playing*. No
rewiring when you switch rooms; no dead buttons when players rename.

Built against Music Assistant 2.10.x + Home Assistant, with Zigbee
buttons via Zigbee2MQTT (a Tuya IH-K663 "Music button" for
single/double, a HOBEIAN ZG-101ZD "knob 2" for hold) and an HA
dashboard button as the trigger sources. A small Python relay does
the thinking; HA just forwards presses to it.

![HOBEIAN ZG-101ZD smart knob](https://www.zigbee2mqtt.io/images/devices/ZG-101Z-D.png)
*The HOBEIAN / Moes ZG-101ZD knob — image: zigbee2mqtt.io device
database. Send a photo of your own knob and it goes here.*

> **Status:** daily-driver code, running in production since Oct 2026.
> The lean/tilt volume-gesture experiment in this repo is **parked**
> (documented below) — everything else is live.

---

## How it works

```
Zigbee button ──MQTT device trigger──┐
                                     ├─→ HA automation ──rest_command──→  relay:8699 ──MA JSON-RPC──→ Music Assistant
HA dashboard button ──state trigger──┘        (dumb pipe)                (the brains)
```

**HA stays dumb on purpose.** The automation forwards `{source}` and
nothing else, so routing changes never need an HA restart — only the
relay restarts (2 s). The Music Assistant token lives in a root-only
`.env` on the relay host, never in HA.

**The relay resolves the *active* device on every press:**

1. `moode-sendspin` while playing/paused (the quality endpoint wins),
2. else whichever non-TV device is playing (follows you to e.g. a
   browser player with zero reconfiguration),
3. else the last-used device (a paused client reports `idle`, not
   `paused` — memory covers that),
4. else any paused device. TVs are excluded by name and player ID.

It also remembers the last-used device across presses, because a
paused web/Sendspin client looks identical to an idle one.

## Features

| Press | Action |
|---|---|
| Single | Play/pause toggle on the active device's **own queue** (see lesson 2) |
| Double | Next track on the active queue |
| Hold / dashboard | Favourite the song + spoken confirmation, then resume the track |
| Zigbee knob hold (knob 2) | Long-press publishes `hue_move` (twice per hold) → favourite + voice, same relay path as dimmer hold; 10 s debounce in `knob_2_hold_fav` |
| Knob 2 hold + turn | Twist while held publishes `color_temperature_step_up/down` → seek ±10 s per detent on the active queue (`seek_fwd`/`seek_back` in `knob_2_rotary_control`); the old held-turn track skip is gone, but knob double-press still skips |
| Dimmer rotate | Volume ±(steps × 2) on the active device (YLKG08YL event) |
| Dimmer press / long-press | Single press = instant toggle, long-press = favourite + voice |
| Dimmer twist-while-pressed | Twist right = next track, twist left = previous (double-press is unworkable: fastest achievable pair is ~4 s apart, proven live) |
| Announce button | Speaks the current song ("Now playing: …") without favouriting — same proportional voice and resume handling |

- **Proportional voice:** the confirmation speaks at 50% of the
  music's current level (floor of 1/100) instead of a fixed level —
  no more shouting over quiet late-night listening. Ratio and floor
  are constants (`ANN_RATIO`, `ANN_FLOOR`).
- **Group-aware announcements:** speaks on the device's sync group
  when the group has 2+ live members, direct otherwise (skips MA's
  slow ungroup/regroup dance around dead members).
- **Dry-run mode:** every action accepts `"dry_run": true` and resolves
  without touching anything — safe to test wiring end to end.
- **Health endpoint:** `GET /health` → `{"status": "ok"}`.

## Requirements

- Music Assistant 2.10.x (JSON-RPC at `http://<ha-host>:8095/api`)
- Home Assistant with the Music Assistant integration (for the
  dashboard button; the relay itself only needs MA's API)
- A host for the relay: any always-on Linux box with Python 3.11+
  (no dependencies beyond the standard library)
- A long-lived MA access token (`MA_MCP_TOKEN` or any valid bearer
  token) and, for the dormant lean poll only, an HA token
- Optional: Zigbee2MQTT button (any model exposing single/hold/double)

## Installation

1. Copy `ma-fav-button-relay.py` to the relay host, e.g.
   `/opt/ma-fav-button/`.
2. Create `/root/.hermes/.env` (mode 600) with your token:
   `MA_MCP_TOKEN=<token>`. (Any path works — update `ENV_FILE`.)
3. Adjust constants at the top of the file: `MA_API`, `FAV_NAME`
   (your quality endpoint), `GROUP_NAME`, `ANN_RATIO`, `ANN_FLOOR`.
4. Install and start the service (`examples/ma-fav-button.service`):
   ```bash
   sudo cp examples/ma-fav-button.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now ma-fav-button.service
   curl localhost:8699/health
   ```
5. Add the `rest_command` (`examples/configuration-rest-command.yaml`)
   to HA's `configuration.yaml` — **this needs one full HA restart**
   (`rest_command` has no reload service; stage everything first).
6. Add the automation (`examples/ha-automations.yaml`) and hit
   **Automations → Reload** (no restart needed for automations).
   Using a ZG-101ZD-style knob? Prefer the **Blueprint** below.
7. Dry-run test:
   ```bash
   curl -X POST localhost:8699/fav-button \
     -d '{"source":"single","dry_run":true}'
   ```

## Home Assistant Blueprint (ZG-101ZD knob)

One-click import — no YAML editing for the knob side:

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fkiwipaulrob%2Fma-fav-button%2Fmain%2Fblueprints%2Fautomation%2Fkiwipaulrob%2Fzg101zd_knob_gestures.yaml)

`blueprints/automation/kiwipaulrob/zg101zd_knob_gestures.yaml` turns the
knob's raw MQTT action strings into seven per-gesture action slots you
fill in the UI (rotate ×2, press, double-press, hold, hold-turn ×2).
It works for any use — lights, scripts, anything — and knows the
hardware's quirks: the bare-hold double `hue_move` echo is debounced
internally via `this.attributes.last_triggered` (no hardcoded entity
id), and the knob must be in command mode (triple-press toggles
command/event; event mode publishes `rotate_right` instead of
`brightness_step_up`).

To drive **Music Assistant**, fill the slots with `rest_command.ma_dimmer`
calls as in `examples/ma-gesture-wiring.yaml`:

| Gesture | `event_type` | Relay action |
|---|---|---|
| Rotate right/left | `rotate_right` / `rotate_left` | Volume ± (log taper) |
| Press | `press` | Play/pause toggle |
| Double-press | `rotate_right_pressed` | Next track |
| Hold | `long_press` | Favourite + voice |
| Hold-turn right/left | `seek_fwd` / `seek_back` | Seek ±10 s per detent |

Requires the relay running and `rest_command.ma_dimmer` configured
(steps 1–5 above). The storyboard version of these two automations
lives in `examples/ha-automations.yaml` (knob section) if you prefer
plain YAML.

## Lessons encoded here (read before simplifying)

1. **Announcing into a dead group plays silence with no error.**
   Daemon restarts can drop a player from its sync group, leaving only
   a ghost member; MA accepts the announcement and plays it to nobody,
   which reads as "the button died". The relay never announces into a
   group the target isn't a member of, and regrouping is a normal
   post-restart chore.
2. **Resume the player's OWN queue, never the global one.**
   `players/cmd/play` resumes the server-global active queue and 500s
   with `QueueEmpty` when that queue is empty (e.g. group queue empty
   while the member's own queue holds the position). Always resolve the
   queue scoped to the player first, `get_active_queue` fallback second.
3. **HA `as_timestamp(x or 0)` bricks a never-fired automation.**
   Proven live 2026-11-06 on `knob_2_hold_fav`: with `last_triggered`
   still `None`, the debounce template evaluated `as_timestamp(0)`,
   which this HA version rejects — the condition errored, failed
   closed, and the automation could never fire to set the very
   attribute it needed. Guard with `is none` instead:
   `{{ state_attr('…','last_triggered') is none or (now() - …).total_seconds() > 10 }}`.
4. **Mute/fade cannot fix a lock-loss relay click.** Proven: the pause/
   resume click on a USB DAC (SMSL/XMOS muting relay) sounds identical
   through full digital silence — it's hardware, not signal. Fixed
   separately in the Sendspin client (keep the stream open on pause);
   see [sendspin-python-cli PR #304](https://github.com/Sendspin/sendspin-python-cli/pull/304).
5. **Announcement clicks are genuine format switches.** TTS arrives as
   FLAC 48 kHz/16-bit, music as 44.1 kHz/24-bit — two real stream
   rebuilds per voice message, correct behaviour. Silencing them needs
   MA to announce at the current stream format (upstream work, not here).

## The parked lean experiment

A Tuya TS0601 vibration sensor ("volume") was trialled as a
tip-to-adjust volume remote: X-axis excursion = down, Y-axis = up,
settle-and-classify in a 2 s poll loop (threshold crossings alone are
unusable — a round puck tumbles through every threshold mid-gesture).
Findings: UP worked first try; DOWN needed per-axis sustain (cross-axis
stillness vetoes real holds) plus a wide re-arm band (rest Y drifts
2→35 with seating). Parked because hand-held holds rock too much for
daily reliability — a real rotary knob is the right hardware. The code
path remains (`LEAN_ENABLE = False`, automation off); the HA
automation file documents the trigger shapes tried. If you revive it,
start with the calibration table in the relay comments.

## Files

- `ma-fav-button-relay.py` — the relay (stdlib only, ~340 lines)
- `tests/test_relay.py` — unit tests (group guard, paused priority,
  empty-queue guard, dry-run purity); run `python3 -m pytest tests/ -q`
- `examples/ma-fav-button.service` — systemd unit
- `examples/configuration-rest-command.yaml` — HA `rest_command`
- `examples/ha-automations.yaml` — button + dimmer + knob automations
  (plain-YAML storyboard, incl. parked lean)
- `examples/ma-gesture-wiring.yaml` — pre-wired blueprint inputs
  mapping every knob gesture to the MA relay
- `blueprints/automation/kiwipaulrob/zg101zd_knob_gestures.yaml` —
  HA Blueprint: knob gestures → UI-picked actions (import button above)

## License

MIT — do what you like, no warranty. Not affiliated with Music
Assistant, Nabu Casa, Tuya, or SMSL.
