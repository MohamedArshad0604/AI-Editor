# My editing style (v1)

**Measured** = taken from the reference reels. **Chosen** = my decision. **Setting** = the line in the script that controls it.

## Format
- Voiceover, English voice and English on-screen text (chosen)
- 1080x1920 (9:16), 30 fps (measured from references)

## Pacing
- Reference rhythm: a new shot about every 2.8 s, range 2.0 to 4.0 s, first cut near 3 s (measured)
- My voiceover edit removes repeated takes (keeps the last one) and long pauses where the audio is truly silent (chosen)
- Setting: `--drop-repeats`, `SILENCE_DB`, `PAUSE_SENTENCE`, `PAUSE_OTHER` in edit.py

## Audio
- Reference loudness: mean about -16 dB, peaks below -2 dB (measured)
- My exports measure about -17.5 dB mean, about 1 dB under the references, accepted for now (measured on my drafts)
- Voice never sped up (chosen); `references/music.mp3` mixed quietly under the voice if present (chosen)
- Setting: `LOUDNESS_I`, `MUSIC_VOLUME` in edit.py

## Subtitles: "yellow punch"
- One word at a time, uppercase, yellow #FFD400, heavy black outline, centered on screen (chosen)
- Arial 100, outline 9, small pop-in zoom on each word (chosen)
- Setting: the `SUB` line in edit.py (`alignment=5` center, `2` bottom, `8` top)

## Hook title (optional)
- Shown for the first 3 s at the top of the screen, white uppercase with outline, fades in and out (chosen)
- Setting: `--title "text"`, `TITLE` line in edit.py

## Keyword graphic (optional)
- White highlight bar with dark uppercase text, wipes in, pops, fades out after 1.5 s, upper third of the screen (chosen)
- Appears at the moment a chosen word is spoken (chosen)
- Setting: `python make_graphic.py "TEXT" --color "#FFFFFF"`, then `--overlay-at word` in edit.py; design lives in graphics/src/Composition.tsx

## One reel, start to finish
```
python transcribe.py
python make_graphic.py "KEYWORD"
python edit.py --drop-repeats --title "Hook" --overlay-at keyword
```
Fix wrong words first in `work/corrections.txt` (line format: `26.84=reel`).

## Do not copy
- No shots, text, logos, or brand elements from the reference reels. Only rhythm and structure are inspiration.
