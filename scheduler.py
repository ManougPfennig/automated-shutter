"""
scheduler.py

A simple background thread that wakes up every CHECK_INTERVAL_SECONDS,
re-reads config.json, and triggers the shutter to open/close when the
current time matches the configured open_time/close_time. Because it
re-reads the config every cycle, changes made from the web UI take effect
on the next check without restarting the server.
"""

import threading
import time
import logging
from datetime import date, datetime

import config

logger = logging.getLogger("scheduler")

CHECK_INTERVAL_SECONDS = 15


class Scheduler:
    def __init__(self, controller):
        self.controller = controller
        self._last_open_date = None
        self._last_close_date = None
        self._thread = None
        self._stop = threading.Event()

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Scheduler started (checking every %ss)", CHECK_INTERVAL_SECONDS)

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._check_once()
            except Exception:
                logger.exception("Scheduler check failed")
            time.sleep(CHECK_INTERVAL_SECONDS)

    def _check_once(self):
        cfg = config.load()
        now = datetime.now()
        current_hhmm = now.strftime("%H:%M")
        today = date.today()

        if current_hhmm == cfg["open_time"] and self._last_open_date != today:
            logger.info("Scheduled OPEN triggered at %s", current_hhmm)
            self.controller.open()
            self._last_open_date = today

        if current_hhmm == cfg["close_time"] and self._last_close_date != today:
            logger.info("Scheduled CLOSE triggered at %s", current_hhmm)
            self.controller.close()
            self._last_close_date = today
