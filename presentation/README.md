# LinguaFlame presentation

Employer-facing pitch deck: 10 slides, 16:9, in English.

## Files

| File | What it is |
|---|---|
| `LinguaFlame_Presentation.pptx` | Main deck (PowerPoint / Google Slides / Keynote). Every slide has speaker notes with the talking points. |
| `LinguaFlame_Presentation.pdf` | The same deck as PDF, in case PowerPoint is not available on the presenting machine. |
| `build_deck.py` | Build script: HTML/CSS → PNG (headless Edge) → PPTX and PDF. |
| `assets/bot_qr.png` | QR code for `@LinguaFlameBot` (used on the closing slide). |

The mascot and the bot emblem come from `../Avatars`.

## Structure

1. Title — "English that people don't quit" + author name
2. Problem — why motivation ends before progress does
3. Solution — a four-step loop (diagnose, practise, feedback, habit)
4. Product — three key screens (placement test, lesson, IELTS essay)
5. Flows — the 8 bot commands
6. Architecture — aiogram 3, services, PostgreSQL, Redis, AI client
7. Level algorithm — weighted score, speed bonus, CEFR thresholds
8. Retention — streaks, reminders, quick start
9. Quality — 253 tests, 74 % coverage, Ruff, live AI check
10. Summary — contacts, QR code to the bot, GitHub link

## Rebuilding

Needs Python 3.11+, `python-pptx`, `Pillow` and Microsoft Edge (for headless screenshots).

```bash
pip install python-pptx Pillow
python presentation/build_deck.py
```

The script regenerates `presentation/.build/` (HTML + PNG) and overwrites the PPTX and PDF.

## Presenting

- Aim for 7–10 minutes: roughly 30 seconds per slide, and go deeper on 4, 6, 7 and 9.
- Slides 4 and 8 show the mechanics as examples, not as real user statistics — they are labelled as such on the slides.
- Close with the QR code and the repository link `github.com/aresdev09/linguaflame`.
