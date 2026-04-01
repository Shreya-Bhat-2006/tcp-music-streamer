import socket, struct, threading, time, wave, os
import customtkinter as ctk
from tkinter import messagebox
from collections import deque
import pyaudio
from qos import QoS

SERVER      = "127.0.0.1"
PORT        = 5000
CHUNK       = 4096
HEADER_FMT  = "I d"
HEADER_SIZE = struct.calcsize(HEADER_FMT)
MAX_BUFFER  = 5  # default, adjusted dynamically based on latency
CACHE_DIR   = "cache"  # folder to store cached songs locally on client

# Create cache folder if it doesn't exist on this machine
os.makedirs(CACHE_DIR, exist_ok=True)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

def recv_exact(sock, n):
    # Packet loss handling: keeps reading until ALL expected bytes are received
    # TCP automatically retransmits any lost packets, so this loop waits until data is complete
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Socket closed")  # connection dropped, stream ends gracefully
        buf += chunk
    return buf

def fetch_song_list():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((SERVER, PORT))
        s.send(b"LIST")
        length = struct.unpack("I", recv_exact(s, 4))[0]
        data   = recv_exact(s, length).decode()
        s.close()
        return [x for x in data.split("\n") if x]
    except:
        return []

def is_cached(song):
    # Check if song already exists in local cache folder
    return os.path.exists(os.path.join(CACHE_DIR, song + ".raw"))

def is_fully_cached(song):
    # Fully cached means .raw exists but no .meta file
    return is_cached(song) and not os.path.exists(os.path.join(CACHE_DIR, song + ".meta"))

def get_cached_frames(song):
    meta = os.path.join(CACHE_DIR, song + ".meta")
    try:
        return int(open(meta).read().strip())
    except:
        return 0

def save_meta(song, frames):
    with open(os.path.join(CACHE_DIR, song + ".meta"), "w") as f:
        f.write(str(frames))

def clear_meta(song):
    try: os.remove(os.path.join(CACHE_DIR, song + ".meta"))
    except: pass

def get_cache_path(song):
    return os.path.join(CACHE_DIR, song + ".raw")  # raw PCM data

class MusicClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🎵 StreamFi")
        self.geometry("900x620")
        self.resizable(False, False)
        self.buffer       = deque()
        self.is_streaming = False
        self.is_playing   = False
        self.is_downloading = False  # tracks if background download is still running
        self.qos          = None
        self.stream       = None
        self.sock         = None
        self.audio        = pyaudio.PyAudio()
        self.channels = 2; self.sampwidth = 2; self.rate = 44100
        self.current_song = None
        self.song_list    = []
        self.stream_start = None
        self.cache_writer = None
        self._qos_shown   = False
        self.max_buffer   = MAX_BUFFER  # dynamically adjusted based on latency
        self.show_home()

    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _sidebar(self, parent):
        sidebar = ctk.CTkFrame(parent, width=220, corner_radius=0, fg_color="#121212")
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        ctk.CTkLabel(sidebar, text="🎵", font=ctk.CTkFont(size=40)).pack(pady=(40,4))
        ctk.CTkLabel(sidebar, text="StreamFi", font=ctk.CTkFont(size=22, weight="bold"), text_color="white").pack()
        ctk.CTkLabel(sidebar, text="Online Music Streamer", font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(2,40))
        for label, cmd in [("🏠  Home", self.show_home), ("🎵  Library", self.show_library)]:
            ctk.CTkButton(sidebar, text=label, anchor="w", fg_color="transparent", hover_color="#1e1e1e",
                          font=ctk.CTkFont(size=13), height=40, command=cmd).pack(fill="x", padx=10, pady=2)
        return sidebar

    def show_home(self):
        self._stop_stream()
        self.clear()
        self._sidebar(self)
        main = ctk.CTkFrame(self, fg_color="#181818", corner_radius=0)
        main.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(main, text="Welcome to StreamFi", font=ctk.CTkFont(size=28, weight="bold"), text_color="white").pack(pady=(50,8))
        ctk.CTkLabel(main, text="Stream music in real-time over TCP", font=ctk.CTkFont(size=14), text_color="gray").pack()
        cards = ctk.CTkFrame(main, fg_color="transparent")
        cards.pack(pady=40)
        for icon, title, desc in [
            ("🔊", "Real-Time\nStreaming", "Audio streamed live\nover TCP"),
            ("📦", "Buffer\nManagement", "Smooth playback\nwith smart buffering"),
            ("📊", "QoS\nMetrics", "Latency and packet\nloss tracking"),
        ]:
            card = ctk.CTkFrame(cards, width=180, height=160, corner_radius=16, fg_color="#282828")
            card.pack(side="left", padx=12)
            card.pack_propagate(False)
            ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=32)).pack(pady=(20,4))
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=13, weight="bold"), text_color="white").pack()
            ctk.CTkLabel(card, text=desc, font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(4,0))
        ctk.CTkButton(main, text="Browse Library  →", command=self.show_library,
                      width=180, height=44, corner_radius=22, font=ctk.CTkFont(size=14, weight="bold")).pack(pady=20)

    def show_library(self):
        self._stop_stream()
        self.clear()
        self._sidebar(self)
        main = ctk.CTkFrame(self, fg_color="#181818", corner_radius=0)
        main.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(main, text="Your Library", font=ctk.CTkFont(size=24, weight="bold"), text_color="white").pack(anchor="w", padx=30, pady=(30,4))
        ctk.CTkLabel(main, text="Click a song to start streaming", font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w", padx=30)
        scroll = ctk.CTkScrollableFrame(main, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=16)
        songs = fetch_song_list()
        self.song_list = songs
        if not songs:
            ctk.CTkLabel(scroll, text="No songs found. Is the server running?", text_color="gray").pack(pady=40)
        else:
            for i, song in enumerate(songs):
                row = ctk.CTkFrame(scroll, fg_color="#282828", corner_radius=12, height=64)
                row.pack(fill="x", pady=4)
                row.pack_propagate(False)
                ctk.CTkLabel(row, text=f"  {i+1}", font=ctk.CTkFont(size=13), text_color="gray", width=36).pack(side="left", padx=(12,0))
                ctk.CTkLabel(row, text="🎵", font=ctk.CTkFont(size=20)).pack(side="left", padx=8)
                ctk.CTkLabel(row, text=song.replace(".wav",""), font=ctk.CTkFont(size=14, weight="bold"), text_color="white").pack(side="left")
                if is_cached(song):
                    ctk.CTkLabel(row, text="💾 cached", font=ctk.CTkFont(size=10), text_color="#22c55e").pack(side="right", padx=(0,4))
                ctk.CTkButton(row, text="▶ Play", width=90, height=34, corner_radius=17,
                              font=ctk.CTkFont(size=12, weight="bold"),
                              command=lambda s=song: self.show_player(s)).pack(side="right", padx=16)

    def show_player(self, song, prev_qos=None, prev_name=None):
        self.clear()
        self.current_song = song
        self._sidebar(self)
        main = ctk.CTkFrame(self, fg_color="#181818", corner_radius=0)
        main.pack(side="left", fill="both", expand=True)
        art = ctk.CTkFrame(main, width=180, height=180, corner_radius=16, fg_color="#282828")
        art.pack(pady=(40,16))
        art.pack_propagate(False)
        ctk.CTkLabel(art, text="🎵", font=ctk.CTkFont(size=72)).pack(expand=True)
        ctk.CTkLabel(main, text=song.replace(".wav",""), font=ctk.CTkFont(size=22, weight="bold"), text_color="white").pack()
        ctk.CTkLabel(main, text="StreamFi Radio", font=ctk.CTkFont(size=13), text_color="gray").pack(pady=(2,16))
        self.progress = ctk.CTkProgressBar(main, width=400, height=6, corner_radius=3)
        self.progress.set(0)
        self.progress.pack(pady=(0,16))
        ctrl = ctk.CTkFrame(main, fg_color="transparent")
        ctrl.pack()
        ctk.CTkButton(ctrl, text="⏮", command=self.prev_song, width=54, height=46, corner_radius=23,
                      fg_color="#333", hover_color="#444", font=ctk.CTkFont(size=18)).grid(row=0, column=0, padx=6)
        self.play_btn = ctk.CTkButton(ctrl, text="▶  Play", command=self.toggle_play,
                                      width=130, height=46, corner_radius=23, font=ctk.CTkFont(size=15, weight="bold"))
        self.play_btn.grid(row=0, column=1, padx=6)
        ctk.CTkButton(ctrl, text="⏭", command=self.next_song, width=54, height=46, corner_radius=23,
                      fg_color="#333", hover_color="#444", font=ctk.CTkFont(size=18)).grid(row=0, column=2, padx=6)
        self.status_label = ctk.CTkLabel(main, text="Ready to stream", font=ctk.CTkFont(size=12), text_color="gray")
        self.status_label.pack(pady=12)
        qos_frame = ctk.CTkFrame(main, corner_radius=12, fg_color="#282828", width=440)
        qos_frame.pack(pady=8, padx=30, fill="x")
        qos_title = f"QoS Report — {prev_name.replace('.wav','')}" if prev_name else "QoS Report"
        ctk.CTkLabel(qos_frame, text=qos_title,
                     font=ctk.CTkFont(size=13, weight="bold"), text_color="gray").pack(anchor="w", padx=16, pady=(10,4))
        self.qos_box = ctk.CTkTextbox(qos_frame, height=100, font=ctk.CTkFont(family="Courier", size=12),
                                      corner_radius=8, fg_color="#1e1e1e", state="disabled")
        self.qos_box.pack(fill="x", padx=16, pady=(0,12))
        # Show previous song's QoS report if available
        if prev_qos and prev_name:
            self.qos_box.configure(state="normal")
            self.qos_box.insert("end", f"Song: {prev_name.replace('.wav','')}\n{prev_qos.get_report()}")
            self.qos_box.configure(state="disabled")
        self.after(300, lambda: self.start_stream(song))

    def _stop_stream(self):
        self.is_streaming   = False
        self.is_playing     = False
        self.is_downloading = False
        self.buffer.clear()
        try: self.sock.close()
        except: pass
    def _stop_playback_only(self):
        # Stop audio only — keep download running in background
        self.is_streaming = False
        self.is_playing   = False
        self.buffer.clear()

    def _adjust_buffer(self, latency_ms):
        # Adaptive buffer size based on measured latency
        if latency_ms < 50:
            self.max_buffer = 2   # low latency — small buffer, less delay
        elif latency_ms < 150:
            self.max_buffer = 5   # medium latency — default buffer
        else:
            self.max_buffer = 10  # high latency — large buffer to prevent stutters

    def open_audio_stream(self):
        if self.stream:
            try: self.stream.stop_stream(); self.stream.close()
            except: pass
        self.stream = self.audio.open(
            format=self.audio.get_format_from_width(self.sampwidth),
            channels=self.channels, rate=self.rate,
            output=True, frames_per_buffer=CHUNK)

    def start_stream(self, song):
        # Check if fully cached — play entirely from local file
        if is_fully_cached(song):
            self.set_status("Playing from cache \U0001f4be", "#22c55e")
            self.play_btn.configure(text="\u23f8  Pause")
            self.is_streaming = True
            self.is_playing   = True
            self.stream_start = time.time()
            self.qos          = QoS()
            self._qos_shown   = False
            threading.Thread(target=self.play_from_cache, args=(song,), daemon=True).start()
            threading.Thread(target=self.update_progress, daemon=True).start()
            return True

        # Check if partially cached — play cached part then resume from server
        cached_frames = get_cached_frames(song) if is_cached(song) else 0

        try:
            new_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            new_sock.connect((SERVER, PORT))

            if cached_frames > 0:
                # Request only the remaining part from server
                new_sock.send(f"STREAM_FROM {song} {cached_frames}".encode())
            else:
                new_sock.send(song.encode())

            status = recv_exact(new_sock, 5)
            if status == b"ERROR":
                messagebox.showerror("Error", "Song not found on server")
                return False

            props = recv_exact(new_sock, 8)
            self.channels, self.sampwidth, self.rate = struct.unpack("H H I", props)
            self.open_audio_stream()
            self.buffer.clear()
            self.is_streaming   = True
            self.is_playing     = True
            self.is_downloading = True
            self.stream_start   = time.time()
            self.progress.set(0)
            self.qos          = QoS()
            self._qos_shown   = False
            self.sock = new_sock

            # Open raw cache file — append if partial, new if fresh
            if cached_frames > 0:
                local_cache_writer = open(get_cache_path(song), "ab")  # append raw PCM
                self.set_status("Resuming from cache \U0001f4be...", "#22c55e")
            else:
                local_cache_writer = open(get_cache_path(song), "wb")  # new raw PCM file
                self.set_status("Streaming...", "#22c55e")

            self.cache_writer = local_cache_writer
            self.play_btn.configure(text="\u23f8  Pause")

            threading.Thread(target=self.play_partial_then_stream,
                             args=(song, cached_frames, new_sock, local_cache_writer), daemon=True).start()
            threading.Thread(target=self.play_audio, daemon=True).start()
            threading.Thread(target=self.update_progress, daemon=True).start()
            return True
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            return False

    def play_from_cache(self, song):
        # Play audio directly from cached raw PCM file — no server request needed
        try:
            with open(get_cache_path(song), "rb") as f:
                self.open_audio_stream()
                while self.is_streaming:
                    data = f.read(CHUNK * self.channels * self.sampwidth)
                    if not data:
                        break
                    if self.is_playing:
                        self.stream.write(data)
                        self.qos.packet_received(0)
                    else:
                        time.sleep(0.01)
        except Exception:
            pass
        self.is_streaming = False

    def play_partial_then_stream(self, song, cached_frames, sock, cache_writer):
        # Step 1: Play cached raw PCM portion first
        if cached_frames > 0:
            try:
                with open(get_cache_path(song), "rb") as f:
                    self.open_audio_stream()
                    bytes_to_play = cached_frames * self.channels * self.sampwidth
                    bytes_played  = 0
                    while self.is_streaming and bytes_played < bytes_to_play:
                        chunk = f.read(CHUNK * self.channels * self.sampwidth)
                        if not chunk:
                            break
                        if self.is_playing:
                            self.buffer.append(chunk)
                            bytes_played += len(chunk)
                        else:
                            time.sleep(0.01)
            except Exception:
                pass

        # Step 2: Continue streaming remaining from server
        self.receive_stream(sock, cache_writer, song, start_frames=cached_frames)

    def receive_stream(self, sock, cache_writer, song, start_frames=0):
        stream_complete = False
        frames_received = start_frames
        try:
            while True:
                while self.is_streaming and len(self.buffer) >= self.max_buffer:
                    time.sleep(0.05)
                raw = recv_exact(sock, HEADER_SIZE)
                if raw[:9] == b"ENDSTREAM":
                    stream_complete = True
                    break
                seq, send_time = struct.unpack(HEADER_FMT, raw)
                latency = time.time() - send_time
                self._adjust_buffer(latency * 1000)  # adjust buffer based on current latency
                length  = struct.unpack("I", recv_exact(sock, 4))[0]
                data    = recv_exact(sock, length)
                if self.is_streaming:
                    self.buffer.append(data)
                if self.qos:
                    self.qos.packet_received(latency)
                # Save raw PCM to cache
                try:
                    cache_writer.write(data)
                    frames_received += CHUNK
                    save_meta(song, frames_received)
                except: pass
        except Exception:
            pass
        try: cache_writer.close()
        except: pass
        if stream_complete:
            clear_meta(song)  # remove .meta — song is fully cached now
        try: sock.close()
        except: pass
        if self.current_song == song:
            self.is_downloading = False
            self.is_streaming   = False

    def play_audio(self):
        while self.is_streaming or self.buffer:
            if self.is_playing and self.buffer:
                try:
                    self.stream.write(self.buffer.popleft())
                except OSError:
                    time.sleep(0.01)
            else:
                time.sleep(0.01)

    def update_progress(self):
        while self.is_streaming:
            elapsed = time.time() - self.stream_start
            val = min(elapsed / 180, 1.0)
            try: self.after(0, lambda v=val: self.progress.set(v))
            except: break
            time.sleep(0.5)

    def toggle_play(self):
        if not self.is_streaming and not self.is_downloading:
            # Fully stopped — start fresh stream
            self.start_stream(self.current_song)
            return
        if not self.is_streaming and self.is_downloading:
            # Background download running — just resume playback
            self.is_streaming = True
            self.is_playing   = True
            self.open_audio_stream()
            self.play_btn.configure(text="⏸  Pause")
            self.set_status("Streaming...", "#22c55e")
            threading.Thread(target=self.play_audio, daemon=True).start()
            return
        if self.is_playing:
            self.is_playing = False
            self.play_btn.configure(text="▶  Play")
            self.set_status("Paused", "orange")
        else:
            self.open_audio_stream()
            self.is_playing = True
            self.play_btn.configure(text="⏸  Pause")
            self.set_status("Streaming...", "#22c55e")

    def stop_audio(self):
        self._stop_playback_only()  # stop audio but keep downloading in background
        try: self.play_btn.configure(text="▶  Play")
        except: pass
        try: self.progress.set(0)
        except: pass
        self.set_status("Stopped — downloading in background...", "orange")
        if self.qos and not self._qos_shown:
            self._qos_shown = True
            self.show_qos()

    def set_status(self, text, color="gray"):
        try: self.status_label.configure(text=text, text_color=color)
        except: pass

    def show_qos(self):
        if not self.qos: return
        try:
            self.qos_box.configure(state="normal")
            self.qos_box.delete("1.0", "end")
            song_name = self.current_song.replace(".wav","") if self.current_song else "Unknown"
            self.qos_box.insert("end", f"Song: {song_name}\n{self.qos.get_report()}")
            self.qos_box.configure(state="disabled")
            self.set_status("Stream ended", "gray")
            self.progress.set(1)
        except: pass

    def prev_song(self):
        if not self.song_list: return
        idx = self.song_list.index(self.current_song) if self.current_song in self.song_list else 0
        if idx == 0:
            messagebox.showinfo("StreamFi", "No previous song available.")
            return
        prev_qos  = self.qos
        prev_name = self.current_song
        self._stop_stream()
        self.show_player(self.song_list[idx - 1], prev_qos=prev_qos, prev_name=prev_name)

    def next_song(self):
        if not self.song_list: return
        idx = self.song_list.index(self.current_song) if self.current_song in self.song_list else 0
        if idx >= len(self.song_list) - 1:
            messagebox.showinfo("StreamFi", "No next song available.")
            return
        prev_qos  = self.qos
        prev_name = self.current_song
        self._stop_stream()
        self.show_player(self.song_list[idx + 1], prev_qos=prev_qos, prev_name=prev_name)

    def close(self):
        self._stop_stream()
        time.sleep(0.15)
        if self.stream:
            try: self.stream.stop_stream(); self.stream.close()
            except: pass
        self.audio.terminate()
        self.destroy()

if __name__ == "__main__":
    app = MusicClient()
    app.protocol("WM_DELETE_WINDOW", app.close)
    app.mainloop()
