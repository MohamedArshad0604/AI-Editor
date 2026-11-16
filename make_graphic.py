"""AI Editor - render the keyword graphic with your own text.
Run from the AI Editor folder (venv active):
    python make_graphic.py "AI Editor"
    python make_graphic.py "No hours" --color "#FFD400"
It writes graphics/props.json and renders graphics/out/keyword-pop.mov
(transparent ProRes), which edit.py --overlay-at uses by default.
"""
import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
GFX = ROOT / "graphics"

ap = argparse.ArgumentParser(description="Render the keyword graphic with custom text")
ap.add_argument("text", help="text shown on the graphic, for example: AI Editor")
ap.add_argument("--color", default="#FFFFFF", help="bar color, default white")
opts = ap.parse_args()

if not (GFX / "package.json").exists():
    sys.exit("graphics/ project not found. Run this from the AI Editor folder.")

# Props go through a file because inline JSON does not survive Windows quoting.
(GFX / "props.json").write_text(
    json.dumps({"text": opts.text, "color": opts.color}), encoding="utf-8"
)

# Fixed command, no user text in it, so running it through the shell is safe.
cmd = ("npx remotion render KeywordPop out/keyword-pop.mov --props=props.json "
       "--codec=prores --prores-profile=4444 --image-format=png "
       "--pixel-format=yuva444p10le")
print(f"Rendering graphic: '{opts.text}' ...")
result = subprocess.run(cmd, cwd=GFX, shell=True)
if result.returncode != 0:
    sys.exit("Render failed. Check the messages above.")
print(f"\nDone: {GFX / 'out' / 'keyword-pop.mov'}")
