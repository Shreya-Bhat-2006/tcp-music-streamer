import socket, struct, threading, time
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
MAX_BUFFER  = 5

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Socket closed")
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

class MusicClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🎵 Music Streamer")
        self.geometry("900x620")
        self.resizable(False, False)

        self.buffer       = deque()
        self.is_streaming = False
        self.is_playing   = False
        self.qos          = None
        self.stream       = None
        self.sock         = None
        self.audio        = pyaudio.PyAudio()
        self.channels = 2; self.sampwidth = 2; self.rate = 44100
        self.current_song = None
        self.song_list = []
        self.stream_start = None

        self.show_home()

    # ── Pages ─────────────────────────────────────────────────────────

    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    def show_home(self):
        self.clear()

        # Sidebar
        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#121212")
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        ctk.CTkLabel(sidebar, text="🎵", font=ctk.CTkFont(size=40)).pack(pady=(40,4))
        ctk.CTkLabel(sidebar, text="StreamFi",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color="white").pack()
        ctk.CTkLabel(sidebar, text="Online Music Streamer",
                     font=ctk.CTkFont(size=11),
                     text_color="gray").pack(pady=(2,40))

        for label, cmd in [("🏠  Home", self.show_home),
                           ("🎵  Library", self.show_library)]:
            ctk.CTkButton(sidebar, text=label, anchor="w",
                          fg_color="transparent", hover_color="#1e1e1e",
                          font=ctk.CTkFont(size=13), height=40,
                          command=cmd).pack(fill="x", padx=10, pady=2)

        # Main area
        main = ctk.CTkFrame(self, fg_color="#181818", corner_radius=0)
        main.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(main, text="Welcome to StreamFi",
                     font=ctk.CTkFont(size=28, weight="bold"),
                     text_color="white").pack(pady=(50,8))
        ctk.CTkLabel(main, text="Stream music in real-time over TCP",
                     font=ctk.CTkFont(size=14), text_color="gray").pack()

        # Feature cards
        cards = ctk.CTkFrame(main, fg_color="transparent")
        cards.pack(pady=40)

        features = [
            ("🔊", "Real-Time\nStreaming", "Audio streamed live\nover TCP"),
            ("📦", "Buffer\nManagement", "Smooth playback\nwith smart buffering"),
            ("📊", "QoS\nMetrics", "Latency & packet\nloss tracking"),
        ]
        for icon, title, desc in features:
            card = ctk.CTkFrame(cards, width=180, height=160, corner_radius=16, fg_color="#282828")
            card.pack(side="left", padx=12)
            card.pack_propagate(False)
            ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=32)).pack(pady=(20,4))
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=13, weight="bold"),
                         text_color="white").pack()
            ctk.CTkLabel(card, text=desc, font=ctk.CTkFont(size=11),
                         text_color="gray").pack(pady=(4,0))

        ctk.CTkButton(main, text="Browse Library  →",
                      command=self.show_library,
                      width=180, height=44, corner_radius=22,
                      font=ctk.CTkFont(size=14, weight="bold")).pack(pady=20)

    def show_library(self):
        self.clear()

        # Sidebar
        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#121212")
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        ctk.CTkLabel(sidebar, text="🎵", font=ctk.CTkFont(size=40)).pack(pady=(40,4))
        ctk.CTkLabel(sidebar, text="StreamFi",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color="white").pack()
        ctk.CTkLabel(sidebar, text="Online Music Streamer",
                     font=ctk.CTkFont(size=11),
                     text_color="gray").pack(pady=(2,40))

        for label, cmd in [("🏠  Home", self.show_home),
                           ("🎵  Library", self.show_library)]:
            ctk.CTkButton(sidebar, text=label, anchor="w",
                          fg_color="transparent", hover_color="#1e1e1e",
                          font=ctk.CTkFont(size=13), height=40,
                          command=cmd).pack(fill="x", padx=10, pady=2)

        # Main
        main = ctk.CTkFrame(self, fg_color="#181818", corner_radius=0)
        main.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(main, text="Your Library",
                     font=ctk.CTkFont(size=24, weight="bold"),
                     text_color="white").pack(anchor="w", padx=30, pady=(30,4))
        ctk.CTkLabel(main, text="Click a song to start streaming",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w", padx=30)

        # Song list
        scroll = ctk.CTkScrollableFrame(main, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=16)

        songs = fetch_song_list()
        self.song_list = songs
        if not songs:
            ctk.CTkLabel(scroll, text="No songs found. Is the server running?",
                         text_color="gray").pack(pady=40)
        else:
            for i, song in enumerate(songs):
                row = ctk.CTkFrame(scroll, fg_color="#282828", corner_radius=12, height=64)
                row.pack(fill="x", pady=4)
                row.pack_propagate(False)

                ctk.CTkLabel(row, text=f"  {i+1}",
                             font=ctk.CTkFont(size=13), text_color="gray",
                             width=36).pack(side="left", padx=(12,0))
                ctk.CTkLabel(row, text="🎵",
                             font=ctk.CTkFont(size=20)).pack(side="left", padx=8)
                ctk.CTkLabel(row, text=song.replace(".wav",""),
                             font=ctk.CTkFont(size=14, weight="bold"),
                             text_color="white").pack(side="left")
                ctk.CTkButton(row, text="▶ Play",
                              width=90, height=34, corner_radius=17,
                              font=ctk.CTkFont(size=12, weight="bold"),
                              command=lambda s=song: self.show_player(s)).pack(side="right", padx=16)

    def show_player(self, song):
        self.clear()
        self.current_song = song

        # Sidebar
        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#121212")
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        ctk.CTkLabel(sidebar, text="🎵", font=ctk.CTkFont(size=40)).pack(pady=(40,4))
        ctk.CTkLabel(sidebar, text="StreamFi",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color="white").pack()
        ctk.CTkLabel(sidebar, text="Online Music Streamer",
                     font=ctk.CTkFont(size=11),
                     text_color="gray").pack(pady=(2,40))

        for label, cmd in [("🏠  Home", self.go_home_safe),
                           ("🎵  Library", self.go_library_safe)]:
            ctk.CTkButton(sidebar, text=label, anchor="w",
                          fg_color="transparent", hover_color="#1e1e1e",
                          font=ctk.CTkFont(size=13), height=40,
                          command=cmd).pack(fill="x", padx=10, pady=2)

        # Main player
        main = ctk.CTkFrame(self, fg_color="#181818", corner_radius=0)
        main.pack(side="left", fill="both", expand=True)

        # Album art placeholder
        art = ctk.CTkFrame(main, width=180, height=180, corner_radius=16, fg_color="#282828")
        art.pack(pady=(40,16))
        art.pack_propagate(False)
        ctk.CTkLabel(art, text="🎵", font=ctk.CTkFont(size=72)).pack(expand=True)

        ctk.CTkLabel(main, text=song.replace(".wav",""),
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color="white").pack()
        ctk.CTkLabel(main, text="StreamFi Radio",
                     font=ctk.CTkFont(size=13), text_color="gray").pack(pady=(2,16))

        # Progress bar
        self.progress = ctk.CTkProgressBar(main, width=400, height=6, corner_radius=3)
        self.progress.set(0)
        self.progress.pack(pady=(0,16))

        # Controls
        ctrl = ctk.CTkFrame(main, fg_color="transparent")
        ctrl.pack()

        ctk.CTkButton(ctrl, text="⏮", command=self.prev_song,
                      width=54, height=46, corner_radius=23,
                      fg_color="#333", hover_color="#444",
                      font=ctk.CTkFont(size=18)).grid(row=0, column=0, padx=6)

        self.play_btn = ctk.CTkButton(ctrl, text="▶  Play",
                                      command=self.toggle_play,
                                      width=130, height=46, corner_radius=23,
                                      font=ctk.CTkFont(size=15, weight="bold"))
        self.play_btn.grid(row=0, column=1, padx=6)

        ctk.CTkButton(ctrl, text="⏹  Stop",
                      command=self.stop_audio,
                      width=110, height=46, corner_radius=23,
                      fg_color="#e53e3e", hover_color="#c53030",
                      font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=2, padx=6)

        ctk.CTkButton(ctrl, text="⏭", command=self.next_song,
                      width=54, height=46, corner_radius=23,
                      fg_color="#333", hover_color="#444",
                      font=ctk.CTkFont(size=18)).grid(row=0, column=3, padx=6)

        self.status_label = ctk.CTkLabel(main, text="Ready to stream",
                                         font=ctk.CTkFont(size=12), text_color="gray")
        self.status_label.pack(pady=12)

        # QoS
        qos_frame = ctk.CTkFrame(main, corner_radius=12, fg_color="#282828", width=440)
        qos_frame.pack(pady=8, padx=30, fill="x")

        ctk.CTkLabel(qos_frame, text="QoS Report",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="gray").pack(anchor="w", padx=16, pady=(10,4))

        self.qos_box = ctk.CTkTextbox(qos_frame, height=100,
                                      font=ctk.CTkFont(family="Courier", size=12),
                                      corner_radius=8, fg_color="#1e1e1e", state="disabled")
        self.qos_box.pack(fill="x", padx=16, pady=(0,12))

        # Auto-start
        self.after(300, lambda: self.start_stream(song))

    # ── Safe navigation (stops stream first) ──────────────────────────

    def go_home_safe(self):
        self._stop_stream()
        self.show_home()

    def go_library_safe(self):
        self._stop_stream()
        self.show_library()

    def _stop_stream(self):
        self.is_streaming = False
        self.is_playing   = False
        self.buffer.clear()
        try: self.sock.close()
        except: pass

    # ── Streaming ─────────────────────────────────────────────────────

    def open_audio_stream(self):
        if self.stream:
            try: self.stream.stop_stream(); self.stream.close()
            except: pass
        self.stream = self.audio.open(
            format=self.audio.get_format_from_width(self.sampwidth),
            channels=self.channels, rate=self.rate,
            output=True, frames_per_buffer=CHUNK)

    def start_stream(self, song):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((SERVER, PORT))
            self.sock.send(song.encode())
            status = recv_exact(self.sock, 5)
            if status == b"ERROR":
                messagebox.showerror("Error", "Song not found on server")
                return False
            props = recv_exact(self.sock, 8)
            self.channels, self.sampwidth, self.rate = struct.unpack("H H I", props)
            self.open_audio_stream()
            self.buffer.clear()
            self.is_streaming = True
            self.is_playing   = True
            self.stream_start = time.time()
            self.progress.set(0)
            self.qos = QoS()
            self.play_btn.configure(text="⏸  Pause")
            self.set_status("Streaming...", "#22c55e")
            threading.Thread(target=self.receive_stream, daemon=True).start()
            threading.Thread(target=self.play_audio,    daemon=True).start()
            threading.Thread(target=self.update_progress, daemon=True).start()
            return True
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            return False

    def receive_stream(self):
        try:
            while self.is_streaming:
                while len(self.buffer) >= MAX_BUFFER and self.is_streaming:
                    time.sleep(0.05)
                if not self.is_streaming:
                    break
                raw = recv_exact(self.sock, HEADER_SIZE)
                if raw[:9] == b"ENDSTREAM":
                    break
                seq, send_time = struct.unpack(HEADER_FMT, raw)
                latency = time.time() - send_time
                length  = struct.unpack("I", recv_exact(self.sock, 4))[0]
                data    = recv_exact(self.sock, length)
                self.buffer.append(data)
                self.qos.packet_received(latency)
        except Exception:
            pass
        self.is_streaming = False
        self.after(0, self.show_qos)

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
        if not self.is_streaming:
            self.start_stream(self.current_song)
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
        self._stop_stream()
        try: self.play_btn.configure(text="▶  Play")
        except: pass
        try: self.progress.set(0)
        except: pass
        self.set_status("Stopped", "gray")
        if self.qos:
            self.show_qos()

    def set_status(self, text, color="gray"):
        try: self.status_label.configure(text=text, text_color=color)
        except: pass

    def show_qos(self):
        if not self.qos: return
        try:
            self.qos_box.configure(state="normal")
            self.qos_box.delete("1.0", "end")
            self.qos_box.insert("end", self.qos.get_report())
            self.qos_box.configure(state="disabled")
            self.set_status("Stream ended", "gray")
            self.progress.set(1)
        except: pass

    def prev_song(self):
        if not self.song_list:
            return
        idx = self.song_list.index(self.current_song) if self.current_song in self.song_list else 0
        if idx == 0:
            messagebox.showinfo("StreamFi", "No previous song available.")
            return
        self._stop_stream()
        self.show_player(self.song_list[idx - 1])

    def next_song(self):
        if not self.song_list:
            return
        idx = self.song_list.index(self.current_song) if self.current_song in self.song_list else 0
        if idx >= len(self.song_list) - 1:
            messagebox.showinfo("StreamFi", "No next song available.")
            return
        self._stop_stream()
        self.show_player(self.song_list[idx + 1])

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

