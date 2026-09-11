"""
relay_controller.py

Drives two relays that replace the original 3-position (UP / NEUTRAL / DOWN)
switch for an electric roller shutter motor. The motor has no built-in
limit switches, so each relay must stay energised for a fixed travel time
and then switch off on its own.

Safety rules enforced here:
  - The UP and DOWN relays are never energised at the same time.
  - Only one operation (open or close) can run at a time.
  - Every operation has a hard time limit (travel_seconds) after which the
    relay switches off automatically, even if something else goes wrong.
  - stop() interrupts an in-progress operation immediately.

If no GPIO hardware is detected (e.g. you're running this on a laptop to
test the web UI), it automatically falls back to a simulated relay that
just logs what it would have done.
"""

import threading
import time
import logging

logger = logging.getLogger("relay_controller")

try:
    from gpiozero import OutputDevice
    from gpiozero import Button
    GPIO_AVAILABLE = True
except Exception as exc:  # pragma: no cover - depends on host hardware
    logger.warning("gpiozero not available, using simulated relays: %s", exc)
    GPIO_AVAILABLE = False


class _SimulatedRelay:
    """Stand-in for gpiozero.OutputDevice when no GPIO hardware is present."""

    def __init__(self, pin, **kwargs):
        self.pin = pin
        self._on = False

    def on(self):
        self._on = True
        logger.info("[SIMULATED] relay pin %s -> ON", self.pin)

    def off(self):
        self._on = False
        logger.info("[SIMULATED] relay pin %s -> OFF", self.pin)

    def close(self):
        pass

class _SimulatedButton:
    """Stand-in for gpiozero.Button when no GPIO hardware is present."""

    def __init__(self, pin, **kwargs):
        self.pin = pin
        self._pressed = False

    def pressed(self):
        self._pressed = True
        logger.info("[SIMULATED] button pin %s -> PRESSED", self.pin)

    def released(self):
        self._pressed = False
        logger.info("[SIMULATED] button pin %s -> RELEASED", self.pin)

    def close(self):
        pass


def _make_relay(pin):
    if GPIO_AVAILABLE:
        try:
            return OutputDevice(pin)
        except Exception as exc:  # pragma: no cover
            logger.warning("Falling back to simulated relay for pin %s: %s", pin, exc)
    return _SimulatedRelay(pin)

def _make_button(pin):
    if GPIO_AVAILABLE:
        try:
            return Button(pin)
        except Exception as exc:  # pragma: no cover
            logger.warning("Falling back to simulated button for pin %s: %s", pin, exc)
    return _SimulatedButton(pin)


class ShutterController:
    def __init__(self, up_pin, down_pin, button_up_pin, button_down_pin, travel_seconds=15.0):
        self.relay_up = _make_relay(up_pin)
        self.relay_up.on() # Never start in an energised state, regardless of prior run.
        self.relay_down = _make_relay(down_pin)
        self.relay_down.on() # Same here.

        self.button_up = _make_button(button_up_pin)
        self.button_down = _make_button(button_down_pin)
        self.travel_seconds = float(travel_seconds)

        print("up_pin:", up_pin, "down_pin:", down_pin, "button_up_pin:", button_up_pin, "button_down_pin:", button_down_pin)

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker = None

        self.status = "idle"            # idle | opening | closing
        self.last_action = None         # open | close | stop
        self.last_action_time = None

        # Setting physical buttons callbacks
        self.button_up.when_pressed = self._button_up
        self.button_up.when_released = self.stop
        self.button_down.when_pressed = self._button_down
        self.button_down.when_released = self.stop

    def is_busy(self):
        return self._worker is not None and self._worker.is_alive()

    def _button_up(self):
        self._start("up")

    def _button_down(self):
        self._start("down")

    def _run(self, direction):
        relay_on, relay_off = (
            (self.relay_up, self.relay_down) if direction == "up"
            else (self.relay_down, self.relay_up)
        )

        # Belt-and-braces: make sure the opposite relay is off first.
        relay_off.on()

        self.status = "opening" if direction == "up" else "closing"
        self.last_action = "open" if direction == "up" else "close"
        self.last_action_time = time.time()

        relay_on.off()
        logger.info("Shutter %s started (max %.1fs)", self.status, self.travel_seconds)

        interrupted = self._stop_event.wait(timeout=self.travel_seconds)

        relay_on.on()
        self.status = "idle"
        logger.info(
            "Shutter operation %s",
            "stopped early by user" if interrupted else f"finished ({direction})",
        )

    def _run_and_release(self, direction):
        try:
            self._run(direction)
        finally:
            self._lock.release()

    def _start(self, direction):
        if not self._lock.acquire(blocking=False):
            logger.warning("Ignored %s request: shutter is already moving", direction)
            return False

        self._stop_event.clear()
        self._worker = threading.Thread(target=self._run_and_release, args=(direction,), daemon=True)
        self._worker.start()
        return True

    def open(self):
        return self._start("up")

    def close(self):
        return self._start("down")

    def stop(self):
        """Interrupt whatever is currently running. Safe to call anytime."""
        self._stop_event.set()
        if not self.is_busy():
            self.last_action = "stop"
            self.last_action_time = time.time()

    def get_state(self):
        return {
            "status": self.status,
            "last_action": self.last_action,
            "last_action_time": self.last_action_time,
            "busy": self.is_busy(),
            "simulated": isinstance(self.relay_up, _SimulatedRelay),
        }

    def cleanup(self):
        self.stop()
        self.relay_up.off()
        self.relay_down.off()
        self.relay_up.close()
        self.relay_down.close()
        self.button_up.close()
        self.button_down.close()
