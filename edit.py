"""AI Editor - step 5: first edit (draft).
Run transcribe.py first. Then, from the AI Editor folder with the venv active:
    python edit.py                    # edit the newest file in raw/
    python edit.py --drop-repeats     # also remove repeated takes (keeps the last one)
    python edit.py --title "Your hook"  # add a hook title in the first 3 seconds
    python edit.py --overlay-at hours   # show graphics/out/keyword-pop.mov when "hours" is said
    (--graphic path\\to\\other.mov uses a different transparent clip)
    python edit.py raw\\myvideo.mp4   # a specific file
What it does:
  1. cuts long pauses (only where the audio is really silent)
  2. optionally removes repeated takes
  3. burns word-by-word subtitles (edit the SUB settings below)
  4. mixes references/music.mp3 quietly under the voice, if that file exists
  5. normalizes loudness, exports 1080x1920 to done/draft-vN.mp4 + done/edit-notes.md
Fix a wrong word by adding a line to work/corrections.txt, for example:
    26.84=reel
(the number is the word's start time in seconds from the *_words.json or review file;
 a line like 33.16= with nothing after the = removes that word)
"""
import argparse
import difflib
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
RAW, WORK, DONE, REFS = ROOT / "raw", ROOT / "work", ROOT / "done", ROOT / "references"
WORK.mkdir(exist_ok=True)
DONE.mkdir(exist_ok=True)
EXTS = {".mp4", ".mov", ".mkv", ".m4a", ".wav", ".mp3"}

# ---------------- settings you can change ----------------
SILENCE_DB = -35          # below this level counts as silence
PAUSE_SENTENCE = 0.30     # pause kept after a sentence (s)
PAUSE_OTHER = 0.12        # pause kept between other words (s)
TRIM_START = 0.10         # silence kept before the first word (s)
TRIM_END = 0.30           # silence kept after the last word (s)
MUSIC = REFS / "music.mp3"
MUSIC_VOLUME = 0.12       # about -18 dB under the voice
LOUDNESS_I = -14          # louder = closer to 0 (references measured about -16 dB mean)
# Style 2 "yellow punch": one word at a time, yellow, heavy outline, centered.
# alignment: 2 = bottom center, 5 = middle center, 8 = top center
SUB = dict(font="Arial", size=100, uppercase=True, color="FFD400", alignment=5,
           margin_v=0, outline=9, pop=True)
# Hook title (only when you pass --title "text"): top of the screen, first seconds
TITLE = dict(size=78, margin_v=260, seconds=3.0)
# ----------------------------------------------------------

ap = argparse.ArgumentParser(description="AI Editor: first edit")
ap.add_argument("source", nargs="?", help="file to edit (default: newest in raw/)")
ap.add_argument("--drop-repeats", action="store_true", help="remove repeated takes")
ap.add_argument("--title", default="", help="hook title shown in the first 3 seconds")
ap.add_argument("--overlay-at", default="", help="show the graphic when this word is spoken")
ap.add_argument("--graphic", default="", help="transparent .mov to overlay (default: graphics/out/keyword-pop.mov)")
opts = ap.parse_args()
DROP_REPEATS = opts.drop_repeats
GRAPHIC = (pathlib.Path(opts.graphic).resolve() if opts.graphic
           else ROOT / "graphics" / "out" / "keyword-pop.mov")


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def pick_source():
    if opts.source:
        return pathlib.Path(opts.source).resolve()
    files = [p for p in RAW.iterdir() if p.suffix.lower() in EXTS]
    if not files:
        sys.exit("No recording found in raw/.")
    return max(files, key=lambda p: p.stat().st_mtime)


def duration_of(f):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(f)])
    return float(r.stdout.strip())


def has_video(f):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(f)])
    return "video" in r.stdout


def silence_intervals(f, total):
    r = run(["ffmpeg", "-hide_banner", "-i", str(f), "-af",
             f"silencedetect=noise={SILENCE_DB}dB:d=0.12", "-vn", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: (-?[0-9.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[0-9.]+)", r.stderr)]
    out = []
    for i, s in enumerate(starts):
        out.append((max(0.0, s), ends[i] if i < len(ends) else total))
    return out


def ass_color(hex_rgb):
    """RRGGBB -> ASS colour digits (BBGGRR)."""
    return (hex_rgb[4:6] + hex_rgb[2:4] + hex_rgb[0:2]).upper()


def ass_time(t):
    cs = int(round(max(t, 0) * 100))
    return f"{cs // 360000}:{(cs // 6000) % 60:02d}:{(cs // 100) % 60:02d}.{cs % 100:02d}"


# ---------------- load words + corrections ----------------
src = pick_source()
words_file = WORK / f"{src.stem}_words.json"
if not words_file.exists():
    sys.exit(f"{words_file.name} not found. Run transcribe.py first.")
words = json.loads(words_file.read_text(encoding="utf-8"))
total = duration_of(src)

corrections_applied = []
corr_file = WORK / "corrections.txt"
if corr_file.exists():
    for line in corr_file.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        t, new = line.split("=", 1)
        try:
            t = float(t)
        except ValueError:
            continue
        w = min(words, key=lambda x: abs(x["start"] - t))
        if abs(w["start"] - t) <= 0.15:
            corrections_applied.append(f"{t:.2f}s: '{w['word']}' -> '{new.strip()}'")
            w["word"] = new.strip()
words = [w for w in words if w["word"]]
if not words:
    sys.exit("No words in the transcript, nothing to edit.")

# ---------------- decide what to remove ----------------
silences = silence_intervals(src, total)
removals = []  # (start, end, reason)


def add_removal(a, b, reason, need_silence=True):
    if b - a <= 0.05:
        return
    if not need_silence:
        removals.append((a, b, reason))
        return
    for s0, s1 in silences:
        lo, hi = max(a, s0), min(b, s1)
        if hi - lo > 0.05:
            removals.append((lo, hi, reason))


# pauses
add_removal(0.0, words[0]["start"] - TRIM_START, "leading silence")
for i in range(len(words) - 1):
    a, b = words[i]["end"], words[i + 1]["start"]
    target = PAUSE_SENTENCE if re.search(r"[.!?]$", words[i]["word"]) else PAUSE_OTHER
    if b - a > target + 0.10:
        add_removal(a + target / 2, b - target / 2, "pause")
add_removal(words[-1]["end"] + TRIM_END, total, "trailing silence")

# repeated takes
sentences, cur = [], []
for i, w in enumerate(words):
    cur.append(i)
    if re.search(r"[.!?]$", w["word"]):
        sentences.append(cur)
        cur = []
if cur:
    sentences.append(cur)


def norm(idx):
    return re.sub(r"[^a-z0-9 ]", "", " ".join(words[i]["word"] for i in idx).lower())


repeat_notes = []
for a in range(len(sentences)):
    for b in range(a + 1, min(a + 4, len(sentences))):
        if difflib.SequenceMatcher(None, norm(sentences[a]), norm(sentences[b])).ratio() >= 0.85:
            s = max(0.0, words[sentences[a][0]]["start"] - 0.05)
            e = words[sentences[b][0]]["start"] - 0.05
            text = " ".join(words[i]["word"] for i in sentences[a])
            repeat_notes.append((s, e, text))
            if DROP_REPEATS:
                add_removal(s, e, "repeated take", need_silence=False)
            break

# merge removals, build keep segments
removals.sort()
merged = []
for a, b, why in removals:
    if merged and a <= merged[-1][1] + 0.01:
        merged[-1] = (merged[-1][0], max(merged[-1][1], b), merged[-1][2] + "+" + why)
    else:
        merged.append((a, b, why))

segments, pos, new_pos = [], 0.0, 0.0   # (old_start, old_end, new_start)
for a, b, _ in merged + [(total, total, "end")]:
    if a - pos > 0.05:
        segments.append((pos, a, new_pos))
        new_pos += a - pos
    pos = max(pos, b)
if not segments:
    sys.exit("Nothing left after cutting. Check the settings.")


def locate(t):
    for a, b, n in segments:
        if a - 0.001 <= t <= b + 0.001:
            return a, b, n
    return None


# ---------------- subtitles ----------------
kept = []
for w in words:
    seg = locate((w["start"] + w["end"]) / 2)
    if seg is None:
        continue
    a, b, n = seg
    ns = n + max(0.0, w["start"] - a)
    ne = n + min(w["end"], b) - a
    kept.append((ns, max(ne, ns + 0.05), w["word"]))

events = []
for k, (ns, ne, text) in enumerate(kept):
    nxt = kept[k + 1][0] if k + 1 < len(kept) else None
    end = nxt if (nxt is not None and nxt - ns < 0.5) else ne + 0.15
    shown = re.sub(r"[.,!?;:]+$", "", text).replace("{", "").replace("}", "")
    if SUB["uppercase"]:
        shown = shown.upper()
    pop = r"{\fscx80\fscy80\t(0,90,\fscx100\fscy100)}" if SUB["pop"] else ""
    events.append(f"Dialogue: 0,{ass_time(ns)},{ass_time(max(end, ns + 0.05))},Word,,0,0,0,,{pop}{shown}")

title_events = []
if opts.title:
    t_end = min(TITLE["seconds"], new_pos)
    t_text = opts.title.replace("{", "").replace("}", "")
    if SUB["uppercase"]:
        t_text = t_text.upper()
    title_events.append(
        f"Dialogue: 1,{ass_time(0)},{ass_time(t_end)},Title,,0,0,0,,{{\\fad(200,200)}}{t_text}")

ass = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,{SUB['font']},{SUB['size']},&H00{ass_color(SUB['color'])},&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{SUB['outline']},0,{SUB['alignment']},60,60,{SUB['margin_v']},1
Style: Title,{SUB['font']},{TITLE['size']},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{SUB['outline']},0,8,60,60,{TITLE['margin_v']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" + "\n".join(title_events + events) + "\n"
(WORK / "subs.ass").write_text(ass, encoding="utf-8")

# ---------------- render ----------------
nums = [int(m.group(1)) for p in DONE.glob("draft-v*.mp4")
        if (m := re.match(r"draft-v(\d+)\.mp4$", p.name))]
version = max(nums, default=0) + 1
out = DONE / f"draft-v{version}.mp4"

inputs = ["-i", str(src)]
vsrc, nxt_idx = "0:v", 1
if not has_video(src):
    inputs += ["-f", "lavfi", "-i", f"color=c=black:s=1080x1920:r=30:d={total:.2f}"]
    vsrc, nxt_idx = "1:v", 2
music_idx = None
if MUSIC.exists():
    inputs += ["-stream_loop", "-1", "-i", str(MUSIC)]
    music_idx = nxt_idx
    nxt_idx += 1

graphic_idx, overlay_t, graphic_note = None, None, "none"
if opts.overlay_at:
    target = re.sub(r"[^a-z0-9']", "", opts.overlay_at.lower())
    for g_ns, g_ne, g_text in kept:
        if re.sub(r"[^a-z0-9']", "", g_text.lower()) == target:
            overlay_t = g_ns
            break
    if overlay_t is None:
        graphic_note = f"skipped: word '{opts.overlay_at}' not found in the edited video"
    elif not GRAPHIC.exists():
        graphic_note = f"skipped: {GRAPHIC} not found"
        overlay_t = None
    else:
        inputs += ["-i", str(GRAPHIC)]
        graphic_idx = nxt_idx
        graphic_note = f"{GRAPHIC.name} at {overlay_t:.2f} s (word '{opts.overlay_at}')"
    if graphic_idx is None:
        print("Graphic " + graphic_note)

parts = []
for k, (a, b, _) in enumerate(segments):
    parts.append(f"[{vsrc}]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS,"
                 f"scale=1080:1920:force_original_aspect_ratio=decrease,"
                 f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{k}]")
    parts.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[a{k}]")
parts.append("".join(f"[v{k}][a{k}]" for k in range(len(segments)))
             + f"concat=n={len(segments)}:v=1:a=1[vc][ac]")
vlabel = "vc"
if graphic_idx is not None:
    parts.append(f"[{graphic_idx}:v]format=yuva420p,setpts=PTS-STARTPTS+{overlay_t:.3f}/TB[gfx]")
    parts.append("[vc][gfx]overlay=0:0:eof_action=pass[vg]")
    vlabel = "vg"
parts.append(f"[{vlabel}]subtitles=subs.ass[vout]")
alabel = "ac"
if music_idx is not None:
    parts.append(f"[{music_idx}:a]volume={MUSIC_VOLUME}[mus]")
    parts.append("[ac][mus]amix=inputs=2:duration=first:normalize=0[am]")
    alabel = "am"
parts.append(f"[{alabel}]loudnorm=I={LOUDNESS_I}:TP=-2:LRA=11[aout]")

cmd = ["ffmpeg", "-y", "-hide_banner", *inputs, "-filter_complex", ";".join(parts),
       "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-crf", "18",
       "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
       "-movflags", "+faststart", str(out)]
print(f"Rendering {out.name} ...")
r = run(cmd, cwd=WORK)
if r.returncode != 0 or not out.exists():
    print("\n".join(r.stderr.splitlines()[-15:]))
    sys.exit("Render failed.")

# ---------------- check the result ----------------
new_total = duration_of(out)
vol = run(["ffmpeg", "-hide_banner", "-i", str(out), "-af", "volumedetect",
           "-vn", "-f", "null", "-"]).stderr
mean = re.search(r"mean_volume: (-?[0-9.]+) dB", vol)
peak = re.search(r"max_volume: (-?[0-9.]+) dB", vol)
size = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
            "stream=width,height", "-of", "csv=p=0:s=x", str(out)]).stdout.strip()

notes = [f"# Edit notes: draft-v{version}", "",
         f"- Source: {src.name} ({total:.1f} s)",
         f"- Result: {new_total:.1f} s, {size}, {len(segments)} segments, "
         f"{total - new_total:.1f} s removed",
         f"- Audio: mean {mean.group(1) if mean else '?'} dB, "
         f"peak {peak.group(1) if peak else '?'} dB (target about -16 / below -2)",
         f"- Music: {'references/music.mp3 at volume ' + str(MUSIC_VOLUME) if music_idx else 'none (no references/music.mp3)'}",
         f"- Subtitles: word by word, {SUB['font']} {SUB['size']}, "
         f"{'uppercase, ' if SUB['uppercase'] else ''}color #{SUB['color']}, outline {SUB['outline']}, "
         f"alignment {SUB['alignment']}",
         f"- Title: {opts.title or 'none'}",
         f"- Graphic: {graphic_note}",
         f"- Repeated takes: {'REMOVED' if DROP_REPEATS else 'not removed (run with --drop-repeats to remove)'}",
         "", "## Cuts (original timeline)"]
for a, b, why in merged:
    notes.append(f"- {a:.2f} s to {b:.2f} s ({b - a:.2f} s): {why}")
if not merged:
    notes.append("- none")
notes += ["", "## Repeated takes found"]
for s, e, text in repeat_notes:
    notes.append(f"- {s:.2f} s to {e:.2f} s starts with: \"{text}\"")
if not repeat_notes:
    notes.append("- none")
notes += ["", "## Word corrections applied"]
notes += [f"- {c}" for c in corrections_applied] or ["- none"]
(DONE / "edit-notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")

print(f"\nDone: {out}")
print(f"Length {total:.1f} s -> {new_total:.1f} s, {size}, "
      f"mean {mean.group(1) if mean else '?'} dB, peak {peak.group(1) if peak else '?'} dB")
print(f"Notes: {DONE / 'edit-notes.md'}")
