import os
import sys
import socket
import struct
import threading
import time
import tkinter as tk
from tkinter import messagebox
from collections import deque
import pyaudio
from qos import QoS

SERVER = "127.0.0.1"
PORT   = 5000
CHUNK  = 4096
HEADER_FMT  = "I d"
HEADER_SIZE = struct.calcsize(HEADER_FMT)

BG = "#0f172a"
CARD = "#1e293b"
ACCENT = "#22c55e"
TEXT = "#e2e8f0"
ERR = "#ef4444"


def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Socket closed")
        buf += chunk
    return buf


class MusicClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Music Streamer")
        self.root.geometry("650x520")
        self.root.configure(bg=BG)
        self.buffer = deque()
        self.is_streaming = False
        self.is_playing = False
        self.qos = None
        self.stream = None
        self.audio = pyaudio.PyAudio()
        self.build_ui()

    def build_ui(self):
        tk.Label(self.root, text="Real-Time Music Streamer",
                 font=("Segoe UI", 20, "bold"), fg=TEXT, bg=BG).pack(pady=15)
        card = tk.Frame(self.root, bg=CARD)
        card.pack(padx=20, pady=10, fill="x")
        tk.Label(card, text="Song filename (e.g. song1.wav):",
                 fg=TEXT, bg=CARD, font=("Segoe UI", 10)).pack(anchor="w", padx=10, pady=(10, 0))
        self.song_entry = tk.Entry(card, font=("Segoe UI", 12))
        self.song_entry.insert(0, "song1.wav")
        self.song_entry.pack(fill="x", padx=10, pady=6)
        bf = tk.Frame(card, bg=CARD)
        bf.pack(pady=10)
        self.play_btn = tk.Button(bf, text="Play", command=self.toggle_play,
                                  bg=ACCENT, fg="white", font=("Segoe UI", 11), width=12)
        self.play_btn.grid(row=0, column=0, padx=10)
        tk.Button(bf, text="Stop", command=self.stop_audio,
                  bg=ERR, fg="white", font=("Segoe UI", 11), width=10).grid(row=0, column=1, padx=10)
        self.status = tk.StringVar(value="Ready")
        tk.Label(card, textvariable=self.status, fg=ACCENT, bg=CARD,
                 font=("Segoe UI", 10)).pack(pady=6)
        tk.Label(self.root, text="QoS Report", fg=TEXT, bg=BG,
                 font=("Segoe UI", 12, "bold")).pack(pady=(10, 0))
        self.qos_box = tk.Text(self.root, height=7, bg=CARD, fg=ACCENT,
                               font=("Courier", 10), state="disabled", relief="flat")
        self.qos_box.pack(padx=20, fill="x")

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
            channels, sampwidth, rate = struct.unpack("H H I", props)
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            self.stream = self.audio.open(
                format=self.audio.get_format_from_width(sampwidth),
                channels=channels, rate=rate,
                output=True, frames_per_buffer=CHUNK
            )
            self.buffer.clear()
            self.is_streaming = True
            self.qos = QoS()
            threading.Thread(target=self.receive_stream, daemon=True).start()
            threading.Thread(target=self.play_audio, daemon=True).start()
            return True
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            return False

    def receive_stream(self):
        try:
            while self.is_streaming:
                raw = recv_exact(self.sock, HEADER_SIZE)
                if raw[:9] == b"ENDSTREAM":
                    break
                seq, send_time = struct.unpack(HEADER_FMT, raw)
                latency = time.time() - send_time
                length = struct.unpack("I", recv_exact(self.sock, 4))[0]
                audio_data = recv_exact(self.sock, length)
                self.buffer.append(audio_data)
                self.qos.packet_received(latency)
        except Exception:
            pass
        self.is_streaming = False
        self.root.after(0, self.show_qos)

    def play_audio(self):
        while self.is_streaming or self.buffer:
            if self.is_playing and self.buffer:
                try:
                    self.stream.write(self.buffer.popleft())
                except OSError:
                    break
            else:
                time.sleep(0.01)

    def toggle_play(self):
        song = self.song_entry.get().strip()
        if not self.is_streaming:
            if not self.start_stream(song):
                return
        if not self.is_playing:
            self.is_playing = True
            self.play_btn.config(text="Pause")
            self.status.set("Playing...")
        else:
            self.is_playing = False
            self.play_btn.config(text="Play")
            self.status.set("Paused")

    def stop_audio(self):
        self.is_streaming = False
        self.is_playing = False
        self.play_btn.config(text="Play")
        self.status.set("Stopped")
        if self.qos:
            self.show_qos()

    def show_qos(self):
        if not self.qos:
            return
        self.qos_box.config(state="normal")
        self.qos_box.delete("1.0", tk.END)
        self.qos_box.insert(tk.END, self.qos.get_report())
        self.qos_box.config(state="disabled")
        self.status.set("Stream ended")

    def close(self):
        self.is_streaming = False
        self.is_playing = False
        time.sleep(0.15)
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
        self.audio.terminate()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MusicClient(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()
