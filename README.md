# BlueDrive 🚗📱  
**In-Car Bluetooth Communication System for Linux (Python + DBus + FastAPI)**

**BlueDrive** is a Linux-only Python service that transforms your embedded device (like a Raspberry Pi) into a smart, Bluetooth-enabled in-car communication system. It supports media playback metadata, phone call handling, and device monitoring via DBus, BlueZ, and oFono — with real-time WebSocket communication to a frontend (Flutter recommended).

🎯 Perfect for DIY smart dashboards, retrofitted infotainment systems, or Raspberry Pi-powered car computers.

## 🔧 Features

🎵 Media & AVRCP  
- Fetch real-time song info (title, artist, album)  
- Supports A2DP + AVRCP metadata  
- Compatible with Spotify, Apple Music, YouTube Music  

📞 Phone Call Management (HFP)  
- Detect incoming calls  
- Show caller ID  
- Answer or hang up calls via DBus/oFono  

📡 Modem & Network Info  
- Signal strength  
- Battery level of connected device  
- Mobile operator (via oFono or HFP AT commands)  

🌐 Real-time WebSocket Integration  
- Send HFP + Media metadata to frontend instantly  
- Compatible with Flutter apps  

🧪 Extensible  
- Future support for: PBAP (phonebook), MAP (SMS), OBEX (file transfer), Car sensor data via UDP (speed, RPM)

## 🖼️ System Architecture

+-------------------+       WebSocket       +--------------------+  
|  Python Service   |  <----------------->  |   Flutter Frontend |  
|  (FastAPI + DBus) |                       |    (Car UI)        |  
+-------------------+                       +--------------------+  
        |  
        |  DBus + BlueZ + oFono  
        v  
+------------------------------+  
| Linux Bluetooth Subsystem   |  
| - MediaPlayer1 (AVRCP)      |  
| - HandsFree (HFP)           |  
| - NetworkRegistration (SIM) |  
+------------------------------+

## ⚙️ Requirements (Linux Only)

✅ System  
- Raspberry Pi OS / Ubuntu / Debian-based Linux  
- Python 3.9+

✅ Linux Packages  
Run the following:

```bash
sudo apt update
sudo apt install bluez ofono dbus pulseaudio python3-dbus python3-gi
✅ Python Dependencies
Install with pip:

pip install -r requirements.txt
Contents of requirements.txt:

fastapi
uvicorn
dbus-python
python-dotenv

🚀 Installation

git clone https://github.com/KeremEski/BlueDrive.git
cd bluedrive
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
Enable oFono:

sudo systemctl enable ofono
sudo systemctl start ofono
Run the app:

python -m app.main
🎧 Spotify Metadata (Optional)

To enhance metadata (cover image, duration, etc.) from Spotify, create a .env file in your root directory like this:

SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REFRESH_TOKEN=your_refresh_token

These values are used to access Spotify’s Web API.
Create your app at: https://developer.spotify.com/dashboard
Follow the Authorization Code Flow to get a refresh token.

📦 Project Structure

bluedrive/
├── app/
│ ├── services/
│ │ ├── media_service.py
│ │ ├── call_service.py
│ │ └── bluetooth_service.py
│ ├── controllers/
│ │ ├── media_controller.py
│ │ └── call_controller.py
│ ├── utils/
│ │ └── spotify_utils.py
│ └── main.py
├── .env (optional)
├── requirements.txt
├── README.md
└── deploy/
└── bluedrive.service (systemd unit)

🌐 API Endpoints

/media/metadata — GET — AVRCP or Spotify now playing
/media/next — GET — Skip to next track
/media/previous — GET — Go to previous track
/media/toggle — GET — Play/Pause toggle
/call/status — GET — Returns call activity info
/call/hangup — GET — Hangs up current call
/call/answer — GET — Answers incoming call

🔌 WebSocket Channels

/ws/phone-data — HFP updates (caller, signal, etc)
/ws/spotify-metadata— Media metadata updates

Example JSON: (/ws/phone-data)

{
  "device_name": "Kerem's iPhone",
  "call_active": true,
  "caller_info": "+90 555 123 4567",
}
Example JSON: (/ws/spotify-metadata)

{
  "title": "Kostak Ali",
  "artist": "CVRTOON",
  "album": none,
  "release_date": none,
  "cover_url": "spotify_link",
  "spotify_url": "spotify_link",
  "popularity": 2,
  "duration_ms": 23091,
  "position": 23912,
  "status": playing
}
🛠 systemd Service (Autostart on Boot)

To run BlueDrive on boot, create this file:
/etc/systemd/system/bluedrive.service

[Unit]
Description=BlueDrive Service
After=network.target

[Service]
ExecStart=/home/pi/bluedrive/venv/bin/python -m app.main
WorkingDirectory=/home/pi/bluedrive
Environment="PYTHONUNBUFFERED=1"
Restart=always
User=pi

[Install]
WantedBy=multi-user.target

Enable the service:

sudo systemctl daemon-reexec
sudo systemctl enable bluedrive
sudo systemctl start bluedrive
🤝 Contributing

Want to help expand the system to include PBAP, MAP, OBEX, or even Android Auto?
Open a pull request or start a discussion — all contributions welcome.

📘 License

MIT License — free for personal and commercial use.

✨ Credits

BlueZ — Linux Bluetooth stack
oFono — Telephony stack used by Ubuntu Touch
DBus — Interprocess communication
Spotify API — For optional rich metadata