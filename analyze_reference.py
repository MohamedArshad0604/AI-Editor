"""AI Editor - reference analyzer (study only).
Reads every .mp4 in the references folder and writes, per video, into
references/_analysis/ :
  <name>_report.txt      numbers: cuts, shot length, pauses, loudness, speech pace
  <name>_words.txt       word-level transcript with timestamps
  <name>_first3s.png     contact sheet of the first 3 seconds (4 frames per second)
  <name>_full.png        contact sheet of the whole video (20 frames)
Run from the AI Editor folder with the venv active:  python analyze_reference.py
"""
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).parent
REFS = ROOT / "references"
OUT = REFS / "_analysis"
OUT.mkdir(parents=True, exist_ok=True)
_model = None


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def probe(f):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,r_frame_rate:format=duration",
             "-of", "json", str(f)])
    d = json.loads(r.stdout)
    s = d["streams"][0]
    num, den = s["r_frame_rate"].split("/")
    return {"width": s["width"], "height": s["height"],
            "fps": round(int(num) / int(den), 2),
            "duration": float(d["format"]["duration"])}


def scene_cuts(f, thr=0.3):
    r = run(["ffmpeg", "-hide_banner", "-i", str(f), "-vf",
             f"select='gt(scene,{thr})',showinfo", "-an", "-f", "null", "-"])
    return [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr)]


def silences(f):
    r = run(["ffmpeg", "-hide_banner", "-i", str(f), "-af",
             "silencedetect=noise=-35dB:d=0.25", "-vn", "-f", "null", "-"])
    return [float(d) for d in re.findall(r"silence_duration: ([0-9.]+)", r.stderr)]


def loudness(f):
    r = run(["ffmpeg", "-hide_banner", "-i", str(f), "-af", "volumedetect",
             "-vn", "-f", "null", "-"])
    mean = re.search(r"mean_volume: (-?[0-9.]+) dB", r.stderr)
    peak = re.search(r"max_volume: (-?[0-9.]+) dB", r.stderr)
    return (float(mean.group(1)) if mean else None,
            float(peak.group(1)) if peak else None)


def sheet(f, out, vf, extra=()):
    run(["ffmpeg", "-y", "-hide_banner", "-i", str(f), *extra,
         "-vf", vf, "-frames:v", "1", str(out)])


def transcribe(f):
    global _model
    from faster_whisper import WhisperModel
    if _model is None:
        _model = WhisperModel("base", device="cpu", compute_type="int8")
    segs, info = _model.transcribe(str(f), word_timestamps=True)
    words = [(w.start, w.end, w.word.strip()) for s in segs for w in s.words]
    return words, info.language


def analyze(f):
    name = f.stem
    p = probe(f)
    dur = p["duration"]
    cuts = scene_cuts(f)
    pauses = silences(f)
    mean_v, peak_v = loudness(f)
    words, lang = transcribe(f)

    sheet(f, OUT / f"{name}_first3s.png", "fps=4,scale=270:-1,tile=4x3", ["-t", "3"])
    sheet(f, OUT / f"{name}_full.png",
          f"fps={20 / dur:.4f},scale=216:-1,tile=5x4")

    bounds = [0.0] + cuts + [dur]
    shots = [b - a for a, b in zip(bounds, bounds[1:])]
    lines = [
        f"File: {f.name}",
        f"Size: {p['width']}x{p['height']} @ {p['fps']} fps, {dur:.1f} s",
        f"Cuts detected: {len(cuts)}  (cuts in first 3 s: {sum(1 for c in cuts if c <= 3)})",
        f"Shot length: avg {dur / (len(cuts) + 1):.2f} s, "
        f"shortest {min(shots):.2f} s, longest {max(shots):.2f} s",
        f"Cut times (s): {', '.join(f'{c:.1f}' for c in cuts)}",
        f"Pauses >= 0.25 s: {len(pauses)}"
        + (f", avg {sum(pauses) / len(pauses):.2f} s, longest {max(pauses):.2f} s" if pauses else ""),
        f"Loudness: mean {mean_v} dB, peak {peak_v} dB",
        f"Speech: language {lang}, {len(words)} words, "
        f"{len(words) / dur * 60:.0f} words/min",
        f"First words: {' '.join(w for _, _, w in words[:12])}",
    ]
    (OUT / f"{name}_report.txt").write_text("\n".join(lines), encoding="utf-8")
    (OUT / f"{name}_words.txt").write_text(
        "\n".join(f"{s:6.2f} {e:6.2f} {w}" for s, e, w in words), encoding="utf-8")
    print("\n".join(lines))
    print()


videos = sorted(REFS.glob("*.mp4"))
if not videos:
    print("No .mp4 files found in references/. Download or copy the reels there first.")
for v in videos:
    print(f"Analyzing {v.name} ...")
    analyze(v)
print(f"Done. Open the folder: {OUT}")
