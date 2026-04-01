import socket
import threading
import wave
import struct
import time
import os

HOST  = "0.0.0.0"
PORT  = 5000
CHUNK = 4096
SONGS_DIR = "Songs"


def get_song_list():
    return [f for f in os.listdir(SONGS_DIR) if f.endswith(".wav")]


def handle_client(client_socket, addr):
    print(f"[CONNECTED] {addr}")
    try:
        request = client_socket.recv(1024).decode().strip()

        # Song list request
        if request == "LIST":
            songs = get_song_list()
            payload = "\n".join(songs).encode()
            client_socket.sendall(struct.pack("I", len(payload)) + payload)
            return

        # Partial stream request — STREAM_FROM <song> <frame_offset>
        if request.startswith("STREAM_FROM "):
            parts = request.split(" ", 2)
            filename = f"{SONGS_DIR}/{parts[1]}"
            frame_offset = int(parts[2])
        else:
            # Normal full stream request
            filename = f"{SONGS_DIR}/{request}"
            frame_offset = 0

        try:
            wf = wave.open(filename, "rb")
        except:
            client_socket.sendall(b"ERROR")
            return

        channels  = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        props     = struct.pack("H H I", channels, sampwidth, framerate)
        client_socket.sendall(b"START" + props)

        # Seek to frame offset if partial request
        if frame_offset > 0:
            wf.setpos(frame_offset)

        bytes_per_sec  = framerate * channels * sampwidth
        chunk_duration = (CHUNK * channels * sampwidth) / bytes_per_sec

        seq = frame_offset // CHUNK  # start seq from offset
        while True:
            data = wf.readframes(CHUNK)
            if not data:
                break
            header = struct.pack("I d", seq, time.time())
            client_socket.sendall(header + struct.pack("I", len(data)) + data)
            seq += 1
            time.sleep(chunk_duration * 0.9)

        wf.close()
        client_socket.sendall(b"ENDSTREAM\x00\x00\x00")
        print(f"[DONE] {addr}")

    except Exception:
        pass
    finally:
        client_socket.close()


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(10)
    print(f"Music Streaming Server started on port {PORT}")
    while True:
        s, addr = server.accept()
        threading.Thread(target=handle_client, args=(s, addr), daemon=True).start()


if __name__ == "__main__":
    start_server()
