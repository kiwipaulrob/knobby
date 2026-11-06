# Snapshot of the working relay-based knob installation, taken 2026-11-07
# immediately before switching to the relay-free blueprint version.
# Restore = copy automations.yaml.live back / re-enable the three knob
# automations (knob_2_rotary_control, knob_2_hold_fav, knob_2_triple_click_proxy).

- automations.yaml.live-20261107 — full live /config/automations.yaml (652 lines).
  Knob wiring = 3 automations (ids above), MQTT topic `zigbee2mqtt/knob 2/action`,
  mode select `select.knob_2_operation_mode`, all calling rest_command.ma_dimmer.
- rest_command.live-20261107.yaml — configuration.yaml lines 353-367
  (ma_fav_button + ma_dimmer → http://192.168.214.10:8699/fav-button).
- ma-fav-button.service — systemd unit for the relay (host 192.168.214.10).
- ma-fav-button-last.json — relay's remembered-speaker memory at snapshot time.
- Relay script itself (/root/.hermes/scripts/ma-fav-button-relay.py) was
  byte-identical to repo ma-fav-button-relay.py at snapshot — no copy needed.
