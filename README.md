# 🎵 StreamFi

A real-time TCP-based music streaming app with buffer management, caching, adaptive latency control, and QoS metrics, built in Python.

Built as a Computer Networks mini project.

---

## Features

- Stream WAV audio files over TCP in real-time
- Spotify-style UI built with CustomTkinter
- Buffer management with adaptive sizing based on network latency
- Smart caching — partial and full song caching with resume support
- Background download — continues caching even after switching songs
- QoS metrics — latency, packet loss, streaming time per song
- Prev / Next song navigation
- Play / Pause controls

---

## Project Structure

```
streamfi/
├── Server.py          # TCP server — streams audio to clients
├── Client.py          # GUI client — receives, caches, and plays audio
├── buffer.py          # Thread-safe buffer management class
├── qos.py             # QoS tracking and reporting
├── convert_songs.py   # Utility to convert songs to WAV
├── Songs/             # Place your .wav files here
│   ├── song1.wav
│   └── song2.wav
└── cache/             # Auto-created — stores cached songs locally
    ├── song1.wav.raw  # Raw PCM audio cache
    └── song1.wav.meta # Tracks partial download progress
```

---

## Requirements

```
pip install customtkinter pyaudio
```

> On Windows, if `pyaudio` fails to install:
> ```
> pip install pipwin
> pipwin install pyaudio
> ```

---

## How to Run

### Same machine
1. Add `.wav` files to the `Songs/` folder
2. Start the server:
```bash
python Server.py
```
3. Start the client:
```bash
python Client.py
```

### Different machines (same WiFi)
1. On server machine — run `ipconfig`, note the WiFi IPv4 address
2. In `Client.py`, change:
```python
SERVER = "127.0.0.1"  # replace with server machine's IP
```
3. Run `python Server.py` on server machine
4. Run `python Client.py` on client machine

---

## How It Works

### TCP Communication
- Server listens on port `5000`
- Client connects and sends song name or `STREAM_FROM <song> <offset>` for partial resume
- Server responds with audio properties + audio chunks with sequence number and timestamp headers
- TCP guarantees reliable ordered delivery — no custom packet loss handling needed

### Buffer Management
- Incoming audio packets stored in a `deque` buffer
- Separate threads handle receiving and playback simultaneously
- Back-pressure pauses receiving when buffer is full — prevents memory overflow
- Adaptive buffer size based on measured latency:
  - Latency < 50ms → buffer = 2 (minimal delay)
  - Latency 50–150ms → buffer = 5 (default)
  - Latency > 150ms → buffer = 10 (prevents stuttering)

### Caching
- First play — streams from server, saves raw PCM to `cache/songname.wav.raw`
- Frame count tracked in `cache/songname.wav.meta`
- Second play — plays cached portion first, then resumes remaining from server
- Full song cached — `.meta` deleted, next play is entirely local (latency = 0ms)
- Background download — continues even after switching songs

### QoS Metrics
Shown when switching songs, includes:
- Song name
- Packets received / lost
- Packet loss percentage
- Average latency (ms)
- Total streaming time

### Latency Reduction
- Cache eliminates network latency for previously streamed portions
- Adaptive buffer reduces audio delay on low-latency networks
- Background download ensures future plays are instant

---

## Tech Stack

- Python 3
- `socket` — TCP networking
- `pyaudio` — audio playback
- `customtkinter` — modern dark UI
- `wave` — WAV file parsing
- `threading` — concurrent receive, playback, and download

---

## Architecture

```
Server                              Client
------                              ------
WAV File
   ↓
read frames (CHUNK=4096)
   ↓
pack header (seq + timestamp)
   ↓
send over TCP ──────────────→ receive_stream()
                                   ↓
                              buffer (deque)     ←→ cache/song.raw (background save)
                                   ↓
                              play_audio() → PyAudio output
                                   ↓
                         _adjust_buffer(latency) → adaptive buffer size
                                   ↓
                         qos.get_report() → shown on song switch
```

---

## License

MIT
