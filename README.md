# The Toning Vault player

Phone app (a static web app on GitHub Pages) for The MMF Toning Vault. Every workout day with photos,
inline demo videos, rest and hold timers, a weight log, the Plug & Play calendar as a tappable week,
the Toning Ladder as a self-filling tracker, the Spice Rack, swaps from the Vault Coach matrices, the
Journal and the checklist. Everything is saved on the phone; nothing is sent anywhere.

## Pages
- `start.html` home: today's workout from the Climb, setup questions the first time
- `index.html#tt-1-d2` list view of a day (`#tt-1` a workout, `#tt` a phase, `#all` everything)
- `play.html#tt-1-d2` step by step
- `print.html#tt-1-d2` paper
- `week.html` this week · `climb.html` the Ladder · `spice.html` · `journal.html` · `checklist.html` · `guide.html` · `videos.html` · `install.html`

## Rebuilding the data
    pip install pymupdf pillow numpy
    python tools/build_workouts.py      # tools/pdf/*.pdf -> data/vault.json + images/<video>-pdf.webp
    python tools/split_photos.py        # composite photos -> Start / End pairs
    python tools/build_workouts.py      # again, to pick up the pairs

Swap rules live in `tools/swaps.py` and the Coach matrix in `tools/coach/gym.csv`.
Bump `VERSION` in `sw.js` after every change so phones refresh.
