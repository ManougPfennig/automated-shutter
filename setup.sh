#!/bin/bash

# Remember to adjust the file setup/shutter.service if your project lives somewhere else.
sudo cp setup/shutter.service /etc/systemd/system/.
sudo systemctl daemon-reload
sudo systemctl enable --now shutter.service
sudo systemctl status shutter.service   # check it's running
journalctl -u shutter.service -f        # watch logs live
