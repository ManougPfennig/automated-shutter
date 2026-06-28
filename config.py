"""
config.py

Loads/saves the shutter schedule and hardware settings to a JSON file
next to this script, so changes made from the web UI survive reboots
without touching code.
"""

import json
import os
import threading

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULTS = {
    "open_time": "08:00",
    "close_time": "20:00",
    "up_pin": 2,
    "down_pin": 4,
    "travel_seconds": 15,
}

_lock = threading.Lock()


def load():
    """Return the current config, creating the file with defaults if missing."""
    with _lock:
        if not os.path.exists(CONFIG_PATH):
            _write(DEFAULTS)
            return dict(DEFAULTS)
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
        merged = dict(DEFAULTS)
        merged.update(data)
        return merged


def save(data):
    with _lock:
        _write(data)


def _write(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


def update_times(open_time, close_time):
    data = load()
    data["open_time"] = open_time
    data["close_time"] = close_time
    save(data)
    return data
