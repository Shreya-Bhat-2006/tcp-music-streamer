"""Run this once to convert all MP3s in Songs/ to WAV format."""
from pydub import AudioSegment
import os

input_dir = "Songs"
output_dir = "music"

os.makedirs(output_dir, exist_ok=True)

for filename in os.listdir(input_dir):
    if filename.endswith(".mp3"):
        name = os.path.splitext(filename)[0]
        src = os.path.join(input_dir, filename)
        dst = os.path.join(output_dir, name + ".wav")
        print(f"Converting {src} -> {dst}")
        AudioSegment.from_mp3(src).export(dst, format="wav")
        print(f"  Done.")

print("All songs converted.")
