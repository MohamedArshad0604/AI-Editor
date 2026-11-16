"""AI Editor - step 4: transcribe a recording with word-level timestamps.
Usage (venv active, from the AI Editor folder):
    python transcribe.py                 # uses the newest file in raw/
    python transcribe.py raw\\myvideo.mp4
Writes into work/ :
    <name>_words.json    every word with start, end, confidence
    <name>_review.txt    full transcript + list of doubtful words to check
"""
import json
import pathlib
import sys

from faster_whisper import WhisperModel

ROOT = pathlib.Path(__file__).parent
RAW = ROOT / "raw"
WORK = ROOT / "work"
WORK.mkdir(exist_ok=True)
EXTS = {".mp4", ".mov", ".mkv", ".m4a", ".wav", ".mp3"}
DOUBT = 0.60          # words below this confidence are flagged
MODEL = "small"       # "base" is faster, "medium" is more accurate


def pick_source():
    if len(sys.argv) > 1:
        return pathlib.Path(sys.argv[1])
    files = [p for p in RAW.iterdir() if p.suffix.lower() in EXTS]
    if not files:
        print("No recording found in raw/. Put your voiceover video or audio there first.")
        sys.exit(1)
    return max(files, key=lambda p: p.stat().st_mtime)


src = pick_source()
print(f"Transcribing {src.name} with the '{MODEL}' model (first run downloads it)...")
model = WhisperModel(MODEL, device="cpu", compute_type="int8")
segments, info = model.transcribe(
    str(src), language="en", word_timestamps=True, beam_size=5
)

words = []
for seg in segments:
    for w in seg.words:
        words.append({
            "start": round(w.start, 2),
            "end": round(w.end, 2),
            "word": w.word.strip(),
            "prob": round(w.probability, 2),
        })

(WORK / f"{src.stem}_words.json").write_text(
    json.dumps(words, indent=2), encoding="utf-8"
)

text = " ".join(w["word"] for w in words)
doubtful = [i for i, w in enumerate(words) if w["prob"] < DOUBT]

lines = [f"File: {src.name}",
         f"Duration: {info.duration:.1f} s, words: {len(words)}, "
         f"pace: {len(words) / info.duration * 60:.0f} words/min",
         "", "TRANSCRIPT", text, "",
         f"DOUBTFUL WORDS (confidence below {DOUBT:.0%})"]
if doubtful:
    for i in doubtful:
        ctx = " ".join(w["word"] for w in words[max(0, i - 3): i + 4])
        lines.append(f"  {words[i]['start']:6.2f}s  '{words[i]['word']}'  "
                     f"({words[i]['prob']:.0%})  ...{ctx}...")
else:
    lines.append("  none")

report = "\n".join(lines)
(WORK / f"{src.stem}_review.txt").write_text(report, encoding="utf-8")
print()
print(report)
print(f"\nSaved to {WORK}")
