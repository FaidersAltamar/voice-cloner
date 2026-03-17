"""
Convert MP3 files to WAV (required for RVC training).
Run this after putting your MP3 files in the input/ folder.
"""
import os
import sys

try:
    from pydub import AudioSegment
except ImportError:
    print("Installing pydub...")
    os.system(f"{sys.executable} -m pip install pydub -q")
    from pydub import AudioSegment

INPUT_DIR = os.path.join(os.path.dirname(__file__), "input")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "rvc-webui", "datasets", "my_voice")

def convert():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    mp3_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".mp3")]
    if not mp3_files:
        print("No MP3 files found in input/ folder.")
        print("Put your MP3 samples in:", os.path.abspath(INPUT_DIR))
        return False
    
    print(f"Converting {len(mp3_files)} MP3 file(s) to WAV...")
    for f in mp3_files:
        path = os.path.join(INPUT_DIR, f)
        out_name = os.path.splitext(f)[0] + ".wav"
        out_path = os.path.join(OUTPUT_DIR, out_name)
        try:
            audio = AudioSegment.from_mp3(path)
            audio = audio.set_frame_rate(40000).set_channels(1)
            audio.export(out_path, format="wav", bitrate="320k")
            print(f"  OK: {f} -> {out_name}")
        except Exception as e:
            err = str(e).lower()
            if "ffmpeg" in err or "could not find" in err:
                print(f"  ERROR: FFmpeg not found. Install it: winget install ffmpeg")
                print("  Or put WAV files directly in rvc-webui/datasets/my_voice/")
                return False
            print(f"  ERROR: {f} - {e}")
    
    print(f"\nDone! WAV files saved to: {OUTPUT_DIR}")
    print("Now open RVC WebUI and go to Training -> Process Data")
    return True

if __name__ == "__main__":
    convert()
