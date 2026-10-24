# LinguaFlame promo video

A 15-second promo for the Telegram bot in two cuts — vertical 9:16 and
landscape 16:9 — rendered fully in code: Pillow draws every frame, numpy
synthesises the soundtrack, ffmpeg muxes and encodes. No footage, no stock
audio, no external render service.

## Deliverables

| File | Format | Specs | Size |
|---|---|---|---|
| `out/LinguaFlame_Promo_1080x1920.mp4` | H.264 + AAC, faststart | 1080x1920, 30 fps, 15.0 s, CRF 18 | ~4.9 MB |
| `out/LinguaFlame_Promo_Loop.gif` | GIF, infinite loop | 405x720, 12 fps, 96 colours | ~4.4 MB |
| `out/poster.png` | PNG cover frame | 1080x1920 | ~1.3 MB |
| `out/LinguaFlame_Promo_1920x1080.mp4` | H.264 + AAC, faststart | 1920x1080, 30 fps, 15.0 s, CRF 18 | ~5.1 MB |
| `out/LinguaFlame_Promo_Loop_16x9.gif` | GIF, infinite loop | 720x405, 12 fps, 96 colours | ~4.6 MB |
| `out/poster_16x9.png` | PNG cover frame | 1920x1080 | ~1.3 MB |

Platform limits: the vertical MP4 fits Reels / Shorts / TikTok, the landscape
cut fits YouTube, Telegram and slide embeds. Both GIFs stay under 5 MB so they
can be posted in chat clients and README previews.

## Storyboard

| Time | Scene |
|---|---|
| 0.0–3.0 s | Hook: mascot waves, "English that people don't quit." |
| 3.0–7.1 s | Telegram mockup: `/level_detector` typing, result card "Your level: B2" |
| 7.1–11.1 s | Streak: flame, counter 1 → 12, week bar fills, "Show up daily." |
| 11.1–15.0 s | CTA: mascot, wordmark, `@LinguaFlameBot`, QR card, "Start in 5 minutes a day." |

Everything eases in and out; the final 0.4 s fades back to navy so the GIF loops
without a visible seam.

## Rebuild

Requirements: Python 3.12 with Pillow and numpy (already in `pyproject.toml`),
and `ffmpeg` on `PATH`.

```bash
python promo/prepare_assets.py      # mascot cutout + QR card from source art
python promo/make_music.py          # 15 s lo-fi soundtrack (procedural)
python promo/render.py              # vertical 1080x1920: MP4, GIF, poster
python promo/render_wide.py         # landscape 1920x1080: MP4, GIF, poster
```

Useful flags:

```bash
python promo/render.py --stills 3.0 9.7 13.4        # quick PNG previews only
python promo/render.py --no-gif                     # skip the GIF pass
python promo/render_wide.py --stills 5.6 9.7 13.4   # landscape previews
```

Both cuts share the timeline, soundtrack and drawing primitives: `render.py`
owns the scene logic, `render_wide.py` imports it and re-lays out the same
elements for 16:9 (text left, phone / streak card / QR right).

`prepare_assets.py` expects `Avatars/photo_2026-10-21_19-09-38.jpg` (mascot art)
and `presentation/assets/bot_qr.png` (QR source). The mascot is matted with a
red-channel key plus a corner flood fill, so the result has no halo on the navy
background.

## Music

`make_music.py` composes the track from oscillators and noise: no samples and no
third-party loops, so the audio is royalty-free by construction. The mix is
normalised to about -17 dBFS RMS with a -1 dBFS peak and no DC offset.

## Brand

- Navy `#0B1426`, orange `#FF8A2A`, mint `#5EEAD4`
- Type: Rubik Bold for headlines, Segoe UI for body and UI chrome
- Sparkles and glow are deterministic (fixed seed), so re-renders are identical

The GIF encoder is deliberately conservative: 96 colours with Bayer dithering
keep it under 5 MB while the QR code in the last scene stays scannable.
