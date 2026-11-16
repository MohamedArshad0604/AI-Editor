# AI Video Editor

A local, step-by-step AI video editor for voiceover reels. Give it a recording and it produces a finished vertical (1080x1920) video: it transcribes your voice with word-level timing, removes repeated takes and silent pauses, burns in word-by-word captions, adds an optional hook title and an animated keyword graphic, balances the loudness, and writes notes on every edit it made.

Everything runs on your own computer. No video is uploaded anywhere.

## What it does

1. **Transcribe** with [faster-whisper](https://github.com/SYSTRAN/faster-whisper), keeping a timestamp and a confidence score for every word, and flagging words it is unsure about.
2. **Cut** long pauses (only where the audio is truly silent) and, optionally, repeated takes (keeping the last one).
3. **Caption** word by word in a configurable style (default: yellow, uppercase, outlined, centered).
4. **Hook title** (optional): text at the top of the screen for the first 3 seconds.
5. **Keyword graphic** (optional): an animated highlight bar built with [Remotion](https://www.remotion.dev), rendered with a transparent background and placed on the exact moment a chosen word is spoken.
6. **Music** (optional): a track named `references/music.mp3` is mixed quietly under the voice.
7. **Export** to `done/draft-vN.mp4` plus `done/edit-notes.md` listing every cut, the audio levels, and the settings used. Each run saves a new draft number.

## Requirements

- Python 3.10 or newer (tested on Windows with Python 3.14)
- FFmpeg with libass, available on your PATH
- Node.js 20.19+, 22.13+, or 24+ (only for the keyword graphic)

## Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

mkdir raw, references, done
cd graphics
npm install
cd ..

python check_tools.py     # verifies FFmpeg, subtitles, Whisper, yt-dlp, Node
```

## Usage

Put your recording in `raw/`, then:

```powershell
python transcribe.py
python make_graphic.py "KEYWORD"
python edit.py --drop-repeats --title "Your hook" --overlay-at keyword
```

| Option | Effect |
|---|---|
| `--drop-repeats` | removes a repeated sentence and everything before the retake |
| `--title "text"` | hook title for the first 3 seconds |
| `--overlay-at word` | shows the keyword graphic when this word is spoken |
| `--graphic path.mov` | use a different transparent clip |

Fix a wrongly transcribed word by adding a line to `work/corrections.txt`, using the word's start time in seconds:

```
26.84=reel
```

Style settings (caption font, color, position, loudness target, pause lengths) are at the top of `edit.py`. `style.md` documents the current style and which setting controls each part.

## Project layout

```
transcribe.py         word-level transcript + doubtful-word list
edit.py               cuts, captions, title, graphic overlay, audio, export
make_graphic.py       renders the keyword graphic with your text
analyze_reference.py  measures pacing, loudness and frames of a reel you want to study
check_tools.py        checks that every tool is installed and working
style.md              the editing style and where each value is set
graphics/             Remotion project for the animated keyword graphic
```

## Notes

- Reference reels used to design the style were for private study only and are not included in this repository.
- Remotion has its own license terms; see [remotion.dev](https://www.remotion.dev) before using it commercially.
