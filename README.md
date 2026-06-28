# Shutter Control

A bare-bones Flask web app for a Raspberry Pi that opens/closes an electric
roller shutter through two relays, on a schedule you set from a web page on
your local network.

## How it matches your wiring

If your original switch has three positions (UP / NEUTRAL / DOWN) that route
the same input current to either the "up" or "down" wire. This app replaces
that switch with **two relays** — one wired in place of the UP contact, one
in place of the DOWN contact:

- Both relays off → equivalent to NEUTRAL.
- UP relay on → equivalent to flipping the switch to UP.
- DOWN relay on → equivalent to flipping the switch to DOWN.

The code **never turns both relays on at once**, and always switches the
opposite relay off before energising the other one, so you can't
accidentally feed both the up and down wires together.

Each relay stays on for a fixed `travel_seconds` (15s by default) and then
switches off automatically — this is the same as how long you would
hold/leave the switch over when operating it manually.
**Time this yourself** on the real shutter (full close, full open) and
set `travel_seconds` in `config.json` a couple of seconds longer than
the slowest direction, so it always finishes the travel.

## Wiring

| Relay      | Raspberry Pi GPIO (default) | Replaces              |
|------------|-----------------------------|-----------------------|
| UP relay   | GPIO 2 (5V)                 | "up" switch contact   |
| DOWN relay | GPIO 4 (5V)                 | "down" switch contact |

Change `up_pin` / `down_pin` in `config.json` if you wire them to different
GPIOs. I personnally used solid state relay modules rated for my house's and
motor's voltage/current (theses can pass up to 260V AC and 25A).
Since they could be triggered by a current as low as 3V, i had no issues
when using the raspberry pi's GPIO pins (3.3V to 5V).


**Important:** mains wiring to the shutter motor is not something this
project can make safe by itself. If the motor runs on mains voltage and
you're not absolutely sure what you're doing please have your wiring
done or checked by a qualified electrician.

## Files

- `app.py` — Flask routes (web page + JSON API)
- `relay_controller.py` — GPIO/relay logic with the up/down safety interlock
- `scheduler.py` — background thread that checks the configured times every 15s
- `config.py` / `config.json` — persisted schedule + pin settings (created on first run)
- `index.html` — the web page (schedule form, manual buttons, live status)

## Install on the Pi

```bash
sudo apt update
sudo apt install -y python3-pip
git clone https://github.com/ManougPfennig/automated-shutter
cd automated-shutter
pip install -r requirements.txt --break-system-packages
```

## Run it

```bash
python3 app.py
```

Find the Pi's IP on the Pi with ;
```
hostname -I
```

Or, from a machine on the same network :
```
nmap -sn 192.168.1.0/24
```

Then from any device on the same LAN, visit :
```
http://<raspberry-pi-ip-address>:5000
```


If you don't have the relay hardware connected yet, the app still runs —
it detects that GPIO isn't available and logs simulated relay on/off
events instead, so you can test the web page and scheduling first.

## Run it automatically on boot (systemd)

Create `/etc/systemd/system/shutter.service`:

```ini
[Unit]
Description=Shutter Control Web App
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/automated-shutter
ExecStart=/usr/bin/python3 /home/pi/automated-shutter/app.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Adjust the path/user if your project lives somewhere else. Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now shutter.service
sudo systemctl status shutter.service   # check it's running
journalctl -u shutter.service -f        # watch logs live
```

### Stopping / restarting the service

```bash
sudo systemctl stop shutter.service              # stop now (will still start on next boot)
sudo systemctl disable --now shutter.service      # stop now AND stop auto-starting on boot
sudo systemctl restart shutter.service            # restart (e.g. after editing config.json)
```

`systemctl stop` sends SIGTERM, which `app.py` catches in order to switch any
energised relay off before exiting — even if it lands mid-travel. A plain
`stop` doesn't disable the boot-time autostart by itself; use `disable --now`
if you want it to stay off after a reboot too.

## Notes & limits

- **No login/authentication.** Anyone on your LAN can open the page and
  trigger the shutter. That's fine for a trusted home network, but don't
  port-forward this to the internet as-is.
- **No position feedback.** The app doesn't know if the shutter is
  physically open or closed — only whether a relay is currently energised.
  After a power cut during travel, the position may not match what you
  expect; use the manual buttons to re-sync if needed.
- Editing pin numbers or `travel_seconds` is done directly in
  `config.json` (stop the app first, edit, restart) — only the open/close
  times are exposed in the web page itself.
