"""AI Editor - tool check.
Tests each tool for real and prints a table: tool, version, works or not.
Run from the AI Editor folder with the venv active:  python check_tools.py
"""
import importlib.metadata as md
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).parent
TMP = ROOT / "_tooltest"
TMP.mkdir(exist_ok=True)
results = []


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def record(tool, version, ok, note=""):
    results.append((tool, version, "works" if ok else "FAILED", note))


# 1. FFmpeg installed
ffmpeg_ok = shutil.which("ffmpeg") is not None
if ffmpeg_ok:
    first_line = run(["ffmpeg", "-version"]).stdout.splitlines()[0]
    version = first_line.split()[2] if len(first_line.split()) > 2 else "?"
    record("FFmpeg", version, True)
else:
    record("FFmpeg", "-", False, "not on PATH (open a NEW PowerShell window)")

# 2. libass: burn a subtitle into a test clip
if ffmpeg_ok:
    (TMP / "test.srt").write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nHello subtitle test\n", encoding="utf-8"
    )
    out = TMP / "burn_test.mp4"
    if out.exists():
        out.unlink()
    r = run(
        ["ffmpeg", "-y", "-hide_banner", "-f", "lavfi",
         "-i", "color=c=black:s=640x360:d=2",
         "-vf", "subtitles=test.srt", "burn_test.mp4"],
        cwd=TMP,
    )
    ok = out.exists() and out.stat().st_size > 0
    record("libass (burn subtitles)", "-", ok, "" if ok else r.stderr.strip().splitlines()[-1] if r.stderr else "")
else:
    record("libass (burn subtitles)", "-", False, "needs FFmpeg")

# 3. faster-whisper: transcribe 5 seconds of audio
try:
    wav = TMP / "test.wav"
    run(["ffmpeg", "-y", "-hide_banner", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=5", str(wav)])
    from faster_whisper import WhisperModel

    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(wav), word_timestamps=True)
    list(segments)  # forces the transcription to actually run
    record("faster-whisper", md.version("faster-whisper"), True,
           "ran OK (a sine tone has no speech, so no text is expected)")
except Exception as e:  # noqa: BLE001
    record("faster-whisper", "-", False, str(e)[:80])

# 4. yt-dlp
r = run([sys.executable, "-m", "yt_dlp", "--version"])
record("yt-dlp", r.stdout.strip() or "-", r.returncode == 0,
       "" if r.returncode == 0 else "run: pip install yt-dlp")

# 5. Node.js (only needed later for Remotion / HyperFrames)
if shutil.which("node"):
    v = run(["node", "--version"]).stdout.strip()
    major = int(v.lstrip("v").split(".")[0])
    record("Node.js", v, major >= 22, "" if major >= 22 else "need 22 or newer")
else:
    record("Node.js", "-", False, "not installed (not needed until graphics step)")

# Table
print()
print(f"{'Tool':<26}{'Version':<14}{'Status':<9}Note")
print("-" * 78)
for tool, version, status, note in results:
    print(f"{tool:<26}{version:<14}{status:<9}{note}")
print()
