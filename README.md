# 🎵 StreamFi

A real-time TCP-based music streaming app with buffer management and QoS metrics, built in Python.

Built as a Computer Networks mini project.

---

## Features

- Stream WAV audio files over TCP in real-time
- Spotify-style UI built with CustomTkinter
- Buffer management for smooth uninterrupted playback
- QoS metrics — latency, packet loss, streaming time
- Prev / Next song navigation
- Play, Pause, Stop controls

---

## Project Structure

```
streamfi/
├── Server.py          # TCP server — streams audio to clients
├── Client.py          # GUI client — receives and plays audio
├── buffer.py          # Buffer management class
├── qos.py             # QoS tracking and reporting
├── convert_songs.py   # Utility to convert songs to WAV
└── Songs/             # Place your .wav files here
    ├── song1.wav
    └── song2.wav
```

---

## Requirements

```
pip install customtkinter pyaudio
```

> On Windows, if `pyaudio` fails to install, use:
> ```
> pip install pipwin
> pipwin install pyaudio
> ```

---

## How to Run

1. Add `.wav` files to the `Songs/` folder

2. Start the server:
```bash
python Server.py
```

3. Start the client:
```bash
python Client.py
```

4. Browse the library, pick a song, and stream it.

---

## How It Works

### TCP Communication
- Server listens on port `5000`
- Client connects and sends the song name as a request
- Server responds with audio properties (channels, sample rate, bit depth) followed by audio chunks
- Each chunk has a header containing sequence number and timestamp for QoS measurement

### Buffer Management
- Incoming audio packets are stored in a thread-safe buffer (`buffer.py`)
- A separate thread reads from the buffer and plays audio
- Back-pressure limits the buffer to prevent memory overflow
- Decouples receiving from playback — network hiccups don't interrupt audio

### QoS Metrics
After streaming, the app reports:
- Packets received
- Packets lost
- Packet loss percentage
- Average latency (ms)
- Total streaming time

### Packet Loss
- TCP handles retransmission automatically — no custom code needed
- `qos.py` tracks and reports the metrics

---

## Tech Stack

- Python 3
- `socket` — TCP networking
- `pyaudio` — audio playback
- `customtkinter` — modern UI
- `wave` — WAV file parsing
- `threading` — concurrent receive and playback

---

## Architecture

```
Server                          Client
------                          ------
WAV File
   ↓
read frames (CHUNK=4096)
   ↓
pack header (seq + timestamp)
   ↓
send over TCP ──────────────→ receive_stream()
                                   ↓
                              buffer.add_packet()
                                   ↓
                              play_audio() → PyAudio output
                                   ↓
                              qos.get_report() → UI display
```

---

## Demo

1. Run server and client on the same machine or local network
2. Open the Library page
3. Click Play on any song
4. Use Pause / Stop / Next / Prev controls
5. QoS report appears after stream ends

---

## License

MIT
