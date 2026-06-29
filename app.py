"""
app.py

Flask web server for a roller shutter controlled by two GPIO relays
(UP / DOWN), meant to run on a Raspberry Pi and be reachable only on
your local network. There is no login/authentication - do not expose
this port to the internet.

Run with:  python3 app.py
Then visit http://<pi-ip-address>:5000 from any device on the LAN.
"""

import logging
import signal

from flask import Flask, request, jsonify, render_template

import config
from relay_controller import ShutterController
from scheduler import Scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app")

app = Flask(__name__)

_cfg = config.load()
controller = ShutterController(
    up_pin=_cfg["up_pin"],
    down_pin=_cfg["down_pin"],
    travel_seconds=_cfg["travel_seconds"],
)
scheduler = Scheduler(controller)
scheduler.start()


@app.route("/")
def index():
    cfg = config.load()
    return render_template("index.html", open_time=cfg["open_time"], close_time=cfg["close_time"])


@app.route("/api/status")
def api_status():
    cfg = config.load()
    state = controller.get_state()
    state["open_time"] = cfg["open_time"]
    state["close_time"] = cfg["close_time"]
    return jsonify(state)


@app.route("/api/settings", methods=["POST"])
def api_settings():
    data = request.get_json(silent=True) or request.form
    open_time = data.get("open_time")
    close_time = data.get("close_time")

    if not open_time or not close_time:
        return jsonify({"error": "open_time and close_time are required"}), 400
    if not _valid_time(open_time) or not _valid_time(close_time):
        return jsonify({"error": "times must be in HH:MM format"}), 400

    new_cfg = config.update_times(open_time, close_time)
    scheduler._last_open_date = None
    scheduler._last_close_date = None
    logger.info("Schedule updated: open=%s close=%s", open_time, close_time)
    return jsonify({"open_time": new_cfg["open_time"], "close_time": new_cfg["close_time"]})


@app.route("/api/manual/<action>", methods=["POST"])
def api_manual(action):
    if action == "open":
        started = controller.open()
    elif action == "close":
        started = controller.close()
    elif action == "stop":
        controller.stop()
        started = True
    else:
        return jsonify({"error": "unknown action"}), 400

    if not started:
        return jsonify({"error": "shutter is already moving"}), 409

    return jsonify(controller.get_state())


def _valid_time(value):
    try:
        hh, mm = value.split(":")
        return 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59
    except (ValueError, AttributeError):
        return False


if __name__ == "__main__":
    def _handle_sigterm(signum, frame):
        # systemd's `systemctl stop` sends SIGTERM. Python's default
        # disposition for SIGTERM is to terminate immediately, which would
        # skip the finally block below and could leave a relay energised
        # mid-travel. Converting it into SystemExit lets the existing
        # cleanup run normally, same as a Ctrl+C (SIGINT) would.
        logger.info("Received SIGTERM, shutting down cleanly")
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _handle_sigterm)

    try:
        # debug=False on purpose: Flask's debug reloader spawns a second
        # process, which would start a second scheduler thread and risk
        # double-triggering the relays.
        app.run(host="0.0.0.0", port=5000, debug=False)
    finally:
        scheduler.stop()
        controller.cleanup()
