# Volume knob for Music Assistant (relay version)

> **Superseded.** This relay setup still works, but the
> [relay-free blueprint](README.md) replaces it: one import, no hosted
> code, same gestures plus triple-press previous and press-and-turn
> seek. Use the blueprint for new setups; this page stays for existing
> relay installs only.

Turn a Zigbee knob into a volume knob for Music Assistant via a small
Python relay: **turn** for volume, **press** for play/pause,
**double-press** for next track, **hold** to favourite the song with a
spoken confirmation.

```
Zigbee knob ──MQTT──→ HA automation ──rest_command──→ relay:8699 ──MA API──→ Music Assistant
                        (dumb pipe)                   (the brains)
```

**Which version should I use?** The
[relay-free blueprint](README.md) does all of this with one import and
no hosted code — use it for new setups. Keep this relay version only
if you already run it, or if you want its extras (dashboard buttons
beside the knob, dry-run testing of the wiring). Both versions require
Zigbee2MQTT — the gestures arrive over MQTT topics, which the built-in
Zigbee integration (ZHA) doesn't publish, so a ZHA-paired knob works
with neither version.

## How the volume works

Home Assistant stays dumb on purpose: the automation forwards each
gesture and nothing else, so routing changes never need an HA restart —
only the relay restarts (~2 s). The relay resolves the **active
speaker** on every gesture, so the knob follows the music around the
house:

1. your quality endpoint while playing/paused,
2. else whichever speaker is playing,
3. else the last-used speaker (a paused client looks identical to an
   idle one, so the relay remembers),
4. else any paused speaker. TVs are always excluded.

Volume moves in logarithmic steps that feel even from quiet to loud
(×/÷ ~1.122 per detent, with a small silence kick so level 1 is never
dead). Hold-to-favourite is committed ~2 s after the hold so a
hold-turn can cancel it into a seek (±10 s per detent).

## Requirements

- Music Assistant 2.10.x (API at `http://<ha-host>:8095/api`)
- Home Assistant with the Music Assistant integration
- A host for the relay: any always-on Linux box with Python 3.11+
  (standard library only — no dependencies)
- A long-lived Music Assistant access token
- A Zigbee2MQTT knob (e.g. HOBEIAN ZG-101ZD)

## Setup

1. Copy `ma-fav-button-relay.py` to the relay host, e.g.
   `/opt/ma-fav-button/`.
2. Create the env file (mode 600) with your token:
   `MA_MCP_TOKEN=<token>`. (Any path works — update `ENV_FILE`.)
3. Adjust the constants at the top: `MA_API`, `FAV_NAME` (your quality
   endpoint), `GROUP_NAME`, `ANN_RATIO`, `ANN_FLOOR`.
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
6. Add the automations (`examples/ha-automations.yaml`, knob section)
   or wire the gesture blueprint (below), then hit **Automations →
   Reload** — no restart needed for automations.
7. Dry-run test before touching the knob:
   ```bash
   curl -X POST localhost:8699/fav-button \
     -d '{"source":"single","dry_run":true}'
   ```

## Knob wiring

`blueprints/automation/kiwipaulrob/zg101zd_knob_gestures.yaml` turns
the knob's raw MQTT actions into per-gesture slots you fill in the HA
UI; point them at `rest_command.ma_dimmer` as in
`examples/ma-gesture-wiring.yaml`:

| Gesture | `event_type` | Relay action |
|---|---|---|
| Turn right / left | `rotate_right` / `rotate_left` | Volume ± (log taper) |
| Press | `press` | Play / pause |
| Double-press | `rotate_right_pressed` | Next track |
| Hold | `long_press` | Favourite + voice |
| Hold-turn right / left | `seek_fwd` / `seek_back` | Seek ±10 s per detent |

The knob's triple-press sends no action (it only flips the Z2M
`operation_mode` select), so previous-track is handled by the
dual-edge proxy in `examples/ha-automations.yaml`, which fires on
either flip direction.

## Voice confirmations

- **Proportional voice:** confirmations speak at 50% of the music's
  current level (floor of 1/100) — no shouting over quiet late-night
  listening. Ratio and floor are constants (`ANN_RATIO`, `ANN_FLOOR`).
- **Group-aware:** speaks on the speaker's sync group when it has 2+
  live members, direct otherwise.

## Troubleshooting

- **Nothing happens:** check the relay is up (`/health`), then dry-run
  (step 7) to prove the wiring end to end without touching the knob.
- **Announce plays silence:** never announce into a group the speaker
  isn't a member of — daemon restarts can leave ghost members; MA
  accepts the announcement and plays it to nobody. Regrouping after a
  restart is normal maintenance.
- **An automation that never fired:** HA's `as_timestamp()` rejects a
  never-fired `last_triggered` (`None`) — guard with `is none` instead
  of `as_timestamp(x or 0)`.
- Every action accepts `"dry_run": true` and resolves without touching
  anything — safe to test wiring freely.

## Files

- `ma-fav-button-relay.py` — the relay (stdlib only)
- `tests/` — unit tests; run `python3 -m pytest tests/ -q`
- `examples/ma-fav-button.service` — systemd unit
- `examples/configuration-rest-command.yaml` — HA `rest_command`
- `examples/ha-automations.yaml` — button + knob automations (plain YAML)
- `examples/ma-gesture-wiring.yaml` — pre-wired blueprint inputs
- `blueprints/automation/kiwipaulrob/zg101zd_knob_gestures.yaml` — knob gestures → UI-picked actions

## License

MIT — do what you like, no warranty. Not affiliated with Music
Assistant, Nabu Casa, or HOBEIAN.
