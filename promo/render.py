"""LinguaFlame — 15-second vertical promo (1080x1920, 30 fps).

Pure Pillow + ffmpeg: every layer is drawn programmatically, frames are piped
straight into libx264, then a palette-optimised GIF is derived from the MP4.

    python promo/render.py                # full render (MP4 + GIF + poster)
    python promo/render.py --stills 1.6 5.2 9.0 12.6
"""

from __future__ import annotations

import argparse
import math
import random
import shutil
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
OUT = ROOT / "out"
AUDIO = ROOT / "audio" / "soundtrack.wav"

W, H = 1080, 1920
FPS = 30
DUR = 15.0
FRAMES = int(round(DUR * FPS))

# Brand -----------------------------------------------------------------------
NAVY = (11, 20, 38)
NAVY_DEEP = (6, 12, 23)
NAVY_CARD = (17, 30, 50)
ORANGE = (255, 138, 42)
ORANGE_HOT = (255, 107, 26)
ORANGE_SOFT = (255, 176, 102)
MINT = (94, 234, 212)
MINT_DIM = (60, 180, 165)
WHITE = (248, 250, 252)
MUTED = (143, 163, 186)
MUTED_DIM = (100, 118, 140)

FONT_DIR = Path("C:/Windows/Fonts")
RUBIK = FONT_DIR / "Rubik-Bold.ttf"
SEGOE = FONT_DIR / "segoeui.ttf"
SEGOE_B = FONT_DIR / "segoeuib.ttf"
CONSOLAS = FONT_DIR / "consola.ttf"

# Timeline --------------------------------------------------------------------
S1_END = 3.02
S2_START, S2_END = 3.04, 7.15
S3_START, S3_END = 7.15, 11.15
S4_START = 11.18

# Phone geometry --------------------------------------------------------------
PW, PH = 700, 1390
PX, PY = 190, 500


# --- math --------------------------------------------------------------------
def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def seg(t: float, start: float, end: float) -> float:
    if end <= start:
        return 1.0 if t >= end else 0.0
    return clamp((t - start) / (end - start))


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_out_quint(t: float) -> float:
    return 1 - (1 - t) ** 5


def ease_out_back(t: float, s: float = 1.7) -> float:
    c3 = s + 1
    return 1 + c3 * (t - 1) ** 3 + s * (t - 1) ** 2


def ease_in_out(t: float) -> float:
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_expo(t: float) -> float:
    return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)


def pulse(t: float, speed: float, phase: float = 0.0) -> float:
    return 0.5 + 0.5 * math.sin(t * speed * math.tau + phase)


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(lerp(a[0], b[0], t)),
        int(lerp(a[1], b[1], t)),
        int(lerp(a[2], b[2], t)),
    )


# --- image helpers -----------------------------------------------------------
def new_layer() -> Image.Image:
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def blit(dst: Image.Image, src: Image.Image, x: float, y: float) -> None:
    x, y = int(round(x)), int(round(y))
    sx = max(0, -x)
    sy = max(0, -y)
    dx = max(0, x)
    dy = max(0, y)
    w = min(src.width - sx, dst.width - dx)
    h = min(src.height - sy, dst.height - dy)
    if w <= 0 or h <= 0:
        return
    if (sx, sy, w, h) != (0, 0, src.width, src.height):
        src = src.crop((sx, sy, sx + w, sy + h))
    dst.alpha_composite(src, (dx, dy))


def with_alpha(img: Image.Image, k: float) -> Image.Image:
    if k >= 0.999:
        return img
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: int(v * k)))
    return out


@lru_cache(maxsize=2048)
def glow_sprite(
    size: int, color: tuple[int, int, int], power: float = 2.3, opacity: int = 255
) -> Image.Image:
    size = max(4, int(size))
    ramp = Image.radial_gradient("L").resize((size, size), Image.Resampling.BILINEAR)
    mask = Image.eval(ramp, lambda v: 255 - v).point(lambda v: int((v / 255) ** power * opacity))
    sprite = Image.new("RGBA", (size, size), color + (0,))
    sprite.putalpha(mask)
    return sprite


def glow(
    layer: Image.Image, cx: float, cy: float, radius: float, color: tuple[int, int, int], alpha: int
) -> None:
    alpha = int(clamp(alpha, 0, 255))
    if alpha <= 2:
        return
    bucket = max(1, alpha // 8)
    sprite = glow_sprite(int(radius * 2), color, 2.3, bucket * 8)
    blit(layer, sprite, cx - radius, cy - radius)


@lru_cache(maxsize=128)
def rrect(size: tuple[int, int], radius: int, fill: tuple[int, ...]) -> Image.Image:
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=fill
    )
    return img


@lru_cache(maxsize=64)
def gradient_rgb(size: tuple[int, int], stops: tuple, horizontal: bool = True) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    n = w if horizontal else h
    for i in range(n):
        c = sample_stops(stops, i / max(1, n - 1))
        if horizontal:
            d.line([(i, 0), (i, h)], fill=c)
        else:
            d.line([(0, i), (w, i)], fill=c)
    return img


def sample_stops(stops: tuple, p: float) -> tuple[int, int, int]:
    p = clamp(p)
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if p <= p1:
            local = 0.0 if p1 == p0 else (p - p0) / (p1 - p0)
            return mix(c0, c1, local)
    return stops[-1][1]


def rrect_gradient(
    size: tuple[int, int], radius: int, stops: tuple, horizontal: bool = True
) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255
    )
    img = gradient_rgb(size, stops, horizontal).convert("RGBA")
    img.putalpha(mask)
    return img


@lru_cache(maxsize=64)
def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def text_width(text: str, f: ImageFont.FreeTypeFont, tracking: float = 0.0) -> float:
    if not text:
        return 0.0
    return f.getlength(text) + tracking * (len(text) - 1)


def draw_tracked(
    d: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, f, fill, tracking: float
) -> None:
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill, anchor="ls")
        x += f.getlength(ch) + tracking


@lru_cache(maxsize=512)
def text_image(
    text: str,
    font_path: str,
    size: int,
    fill: tuple[int, int, int] | None = None,
    stops: tuple | None = None,
    alpha: int = 255,
    pad: int = 8,
) -> Image.Image:
    f = font(font_path, size)
    w = int(math.ceil(text_width(text, f))) + pad * 2
    ascent, descent = f.getmetrics()
    h = ascent + descent + pad * 2
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((pad, pad + ascent), text, font=f, fill=255, anchor="ls")
    if alpha < 255:
        mask = mask.point(lambda v: int(v * alpha / 255))
    if stops is not None:
        img = gradient_rgb((w, h), stops, True).convert("RGBA")
    else:
        img = Image.new("RGBA", (w, h), (fill or WHITE) + (255,))
    img.putalpha(mask)
    return img


def blit_text(
    layer: Image.Image,
    text: str,
    font_path: str,
    size: int,
    x: float,
    baseline: float,
    fill: tuple[int, int, int] | None = None,
    stops: tuple | None = None,
    alpha: int = 255,
    center: bool = False,
) -> None:
    img = text_image(text, font_path, int(size), fill, stops, int(clamp(alpha, 0, 255)))
    f = font(font_path, int(size))
    ascent, _ = f.getmetrics()
    if center:
        x = x - (img.width - 16) / 2
    blit(layer, img, x - 8, baseline - ascent - 8)


# --- stage -------------------------------------------------------------------
def build_stage() -> Image.Image:
    stage = Image.new("RGBA", (W, H), NAVY + (255,))
    d = ImageDraw.Draw(stage)
    top = (10, 17, 33)
    mid = (12, 22, 41)
    bottom = (6, 11, 22)
    for y in range(H):
        p = y / (H - 1)
        if p < 0.45:
            c = mix(top, mid, p / 0.45)
        else:
            c = mix(mid, bottom, (p - 0.45) / 0.55)
        d.line([(0, y), (W, y)], fill=c + (255,))

    # baked ambience
    stage.alpha_composite(glow_sprite(1500, ORANGE_HOT, 2.4, 42), (-420, 640))
    stage.alpha_composite(glow_sprite(1200, MINT, 2.6, 22), (420, -360))
    stage.alpha_composite(glow_sprite(900, (70, 110, 220), 2.8, 26), (-260, 1180))

    # static dither so the navy gradient never bands after encoding
    noise = Image.effect_noise((W, H), 22).convert("L").point(lambda v: int((v - 128) * 0.55 + 128))
    grain = Image.merge("RGBA", (noise, noise, noise, Image.new("L", (W, H), 8)))
    stage.alpha_composite(grain)
    return stage


VIGNETTE = Image.new("RGB", (W, H))
_vd = ImageDraw.Draw(VIGNETTE)
for _y in range(0, H, 4):
    _p = abs(_y - H * 0.45) / (H * 0.62)
    _v = int(255 - 46 * min(1.0, _p) ** 2.6)
    _vd.rectangle((0, _y, W, _y + 4), fill=(_v, _v, _v))
VIGNETTE = VIGNETTE.filter(ImageFilter.GaussianBlur(30))

STAGE = ImageChops.multiply(build_stage().convert("RGB"), VIGNETTE).convert("RGBA")

NAVY_IMG = Image.new("RGB", (W, H), NAVY)


# --- particles ---------------------------------------------------------------
class Spark:
    __slots__ = ("x", "y", "vy", "vx", "size", "phase", "speed", "color", "amp")

    def __init__(self, x, y, vx, vy, size, phase, speed, color, amp):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.size = size
        self.phase = phase
        self.speed = speed
        self.color = color
        self.amp = amp


def build_sparks(count: int = 46, seed: int = 7) -> list[Spark]:
    rng = random.Random(seed)
    palette = [ORANGE, ORANGE_SOFT, MINT, (200, 220, 240)]
    out = []
    for _ in range(count):
        out.append(
            Spark(
                x=rng.uniform(40, W - 40),
                y=rng.uniform(0, H),
                vx=rng.uniform(-6, 6),
                vy=rng.uniform(-26, -8),
                size=rng.uniform(1.6, 4.6),
                phase=rng.uniform(0, math.tau),
                speed=rng.uniform(0.7, 1.8),
                color=rng.choice(palette),
                amp=rng.uniform(0.25, 0.85),
            )
        )
    return out


SPARKS = build_sparks()


def draw_sparks(layer: Image.Image, t: float, strength: float = 1.0) -> None:
    for s in SPARKS:
        y = (s.y + s.vy * t) % (H + 120)
        x = s.x + s.vx * t + math.sin(t * 0.7 + s.phase) * 12
        twinkle = 0.35 + 0.65 * pulse(t, s.speed, s.phase)
        alpha = int(255 * s.amp * twinkle * strength)
        if alpha < 8:
            continue
        bucket = min(255, (alpha // 32) * 32)
        r = int(round(s.size * 5.5))
        blit(layer, glow_sprite(r * 2, s.color, 2.0, bucket), x - r, y - r)
        core = max(2, int(round(s.size)))
        blit(
            layer,
            glow_sprite(core * 4, s.color, 1.4, min(255, bucket + 64)),
            x - core * 2,
            y - core * 2,
        )


# --- mascot ------------------------------------------------------------------
MASCOT = Image.open(ASSETS / "mascot.png").convert("RGBA")
MASCOT_BIG = MASCOT.resize((1100, 1100), Image.Resampling.LANCZOS)
MASCOT_CRISP = {
    size: MASCOT.resize((size, size), Image.Resampling.LANCZOS) for size in (480, 760, 820)
}


def mascot_sprite(size: int, angle: float = 0.0, squash: float = 1.0) -> Image.Image:
    base = MASCOT_CRISP.get(size)
    if base is None:
        base = MASCOT_BIG.resize((size, size), Image.Resampling.BILINEAR)
    if squash != 1.0:
        base = base.resize((int(size * squash), int(size / squash)), Image.Resampling.BILINEAR)
    if abs(angle) > 0.05:
        base = base.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)
    return base


# --- phone chrome ------------------------------------------------------------
@lru_cache(maxsize=1)
def phone_shadow() -> Image.Image:
    pad = 90
    img = Image.new("RGBA", (PW + pad * 2, PH + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((pad, pad, pad + PW, pad + PH), radius=70, fill=(0, 0, 0, 170))
    return img.filter(ImageFilter.GaussianBlur(38))


@lru_cache(maxsize=1)
def phone_chrome() -> Image.Image:
    img = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # body
    d.rounded_rectangle((0, 0, PW - 1, PH - 1), radius=64, fill=(15, 27, 46, 255))
    d.rounded_rectangle((0, 0, PW - 1, PH - 1), radius=64, outline=(120, 150, 190, 60), width=2)

    # screen
    screen = Image.new("RGBA", (PW - 24, PH - 24), (0, 0, 0, 0))
    sd = ImageDraw.Draw(screen)
    sd.rounded_rectangle((0, 0, PW - 25, PH - 25), radius=54, fill=(10, 19, 34, 255))

    # header
    sd.rounded_rectangle((0, 0, PW - 25, 112), radius=54, fill=(15, 27, 47, 255))
    sd.rectangle((0, 70, PW - 25, 112), fill=(15, 27, 47, 255))
    sd.line([(0, 112), (PW - 25, 112)], fill=(255, 255, 255, 18), width=1)

    # avatar
    avatar = MASCOT.resize((58, 58), Image.Resampling.LANCZOS)
    mask = Image.new("L", (58, 58), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 57, 57), fill=255)
    sd.ellipse((31, 27, 91, 87), fill=(255, 138, 42, 255))
    screen.paste(avatar, (32, 28), mask)

    f_name = font(str(SEGOE_B), 27)
    f_sub = font(str(SEGOE), 18)
    sd = ImageDraw.Draw(screen)
    sd.text((104, 40), "LinguaFlame", font=f_name, fill=WHITE + (255,), anchor="ls")
    sd.text((104, 72), "bot", font=f_sub, fill=MINT + (235,), anchor="ls")
    for i in range(3):
        sd.ellipse((PW - 78 + i * 13, 56, PW - 72 + i * 13, 62), fill=(150, 168, 190, 220))

    # input bar
    sd.rounded_rectangle((0, PH - 124, PW - 25, PH - 24), radius=44, fill=(15, 27, 47, 255))
    sd.rectangle((0, PH - 124, PW - 25, PH - 90), fill=(15, 27, 47, 255))
    sd.rounded_rectangle((22, PH - 106, PW - 148, PH - 42), radius=32, fill=(24, 39, 62, 255))
    sd.text(
        (46, PH - 64), "Message", font=font(str(SEGOE), 22), fill=(120, 138, 160, 255), anchor="ls"
    )
    sd.ellipse((PW - 122, PH - 110, PW - 52, PH - 40), fill=ORANGE + (255,))
    # send plane
    cx, cy = PW - 87, PH - 75
    sd.polygon(
        [(cx - 15, cy - 10), (cx + 17, cy), (cx - 15, cy + 10), (cx - 9, cy), (cx - 15, cy - 10)],
        fill=NAVY + (255,),
    )

    img.alpha_composite(screen, (12, 12))
    return img


def chat_origin() -> tuple[int, int]:
    return 12, 12


# --- scene 1: hook -----------------------------------------------------------
def scene_hook(t: float) -> Image.Image:
    layer = new_layer()

    # kicker
    k = seg(t, 0.18, 0.55)
    if k > 0:
        f = font(str(SEGOE_B), 22)
        text = "AI ENGLISH COACH  ·  TELEGRAM"
        tw = text_width(text, f, 3.4)
        pill_w, pill_h = tw + 64, 54
        px, py = W / 2 - pill_w / 2, 232
        pill = rrect((int(pill_w), pill_h), 27, (255, 255, 255, 20))
        blit(layer, with_alpha(pill, k), px, py + (1 - k) * 16)
        img = text_image(text, str(SEGOE_B), 22, fill=MINT, alpha=int(255 * k))
        blit(layer, img, W / 2 - (img.width - 16) / 2, py + pill_h / 2 - 11 - 8 + (1 - k) * 16)

    # mascot
    entrance = seg(t, 0.05, 0.8)
    if entrance > 0:
        e = ease_out_back(entrance, 1.5)
        size = int(780 * lerp(0.86, 1.0, e))
        bob = math.sin(t * 2.3) * 9
        wave = 2.6 * math.sin(t * 4.4 + 0.4) * seg(t, 0.5, 1.2)
        squash = 1.0 + 0.012 * math.sin(t * 3.1)
        sprite = mascot_sprite(size, angle=wave, squash=squash)
        cx, cy = W / 2, 1245 + bob
        glow(layer, cx, cy + 30, 500, ORANGE_HOT, int(46 + 14 * pulse(t, 0.9)))
        blit(
            layer,
            with_alpha(sprite, segment_alpha(entrance)),
            cx - sprite.width / 2,
            cy - sprite.height / 2,
        )

    # headline
    word_start = 0.34
    stagger = 0.085
    line1 = ["English", "that"]
    line2 = ["people", "don't"]
    draw_word_line(layer, line1, str(RUBIK), 112, 470, W / 2, t, word_start, stagger, WHITE)
    draw_word_line(
        layer, line2, str(RUBIK), 112, 604, W / 2, t, word_start + 2 * stagger, stagger, WHITE
    )

    p3 = seg(t, 1.02, 1.55)
    if p3 > 0:
        e = ease_out_back(p3, 1.3)
        size = int(132 * lerp(0.9, 1.0, e))
        img = text_image(
            "quit.",
            str(RUBIK),
            size,
            stops=((0.0, ORANGE), (0.55, (255, 180, 90)), (1.0, MINT)),
            alpha=int(255 * min(1, p3 * 1.6)),
        )
        ascent = font(str(RUBIK), size).getmetrics()[0]
        blit(layer, img, W / 2 - (img.width - 16) / 2, 748 + (1 - e) * 40 - ascent - 8)

    # subtitle
    sk = seg(t, 1.35, 1.9)
    if sk > 0:
        blit_text(
            layer,
            "Measure your level. Practise five minutes a day.",
            str(SEGOE),
            31,
            W / 2,
            1782 + (1 - ease_out_cubic(sk)) * 24,
            fill=(160, 178, 198),
            alpha=int(255 * sk),
            center=True,
        )

    return layer


def segment_alpha(p: float) -> float:
    return clamp(p * 1.6)


def draw_word_line(
    layer: Image.Image,
    words: list[str],
    fpath: str,
    size: int,
    baseline: float,
    cx: float,
    t: float,
    start: float,
    stagger: float,
    color: tuple[int, int, int],
) -> None:
    f = font(fpath, size)
    space = f.getlength(" ")
    widths = [f.getlength(w) for w in words]
    total = sum(widths) + space * (len(words) - 1)
    x = cx - total / 2
    for i, (word, wd) in enumerate(zip(words, widths, strict=True)):
        p = seg(t, start + i * stagger, start + i * stagger + 0.55)
        if p > 0:
            e = ease_out_quint(p)
            img = text_image(word, fpath, size, fill=color, alpha=int(255 * e))
            ascent, _ = f.getmetrics()
            blit(layer, img, x - 8, baseline + (1 - e) * 44 - ascent - 8)
        x += wd + space


# --- scene 2: phone / level detector ----------------------------------------
def scene_phone(t: float) -> Image.Image:
    layer = new_layer()

    # header
    hk = seg(t, 3.16, 3.55)
    if hk > 0:
        e = ease_out_cubic(hk)
        blit_text(
            layer,
            "Know your level",
            str(RUBIK),
            64,
            W / 2,
            344 + (1 - e) * 26,
            fill=WHITE,
            alpha=int(255 * hk),
            center=True,
        )
        blit_text(
            layer,
            "in 50 questions.",
            str(RUBIK),
            64,
            W / 2,
            420 + (1 - e) * 30,
            fill=MINT,
            alpha=int(255 * hk),
            center=True,
        )

    # phone entrance
    pk = seg(t, S2_START, 3.62)
    if pk <= 0:
        return layer
    pe = ease_out_quint(pk)
    offset_y = (1 - pe) * 210
    opacity = int(255 * clamp(pk * 1.35))

    glow(layer, W / 2 + 120, PY + 320, 520, MINT, int(22 * pe))
    glow(layer, W / 2 - 150, PY + PH - 280, 540, ORANGE, int(30 * pe))

    shadow = with_alpha(phone_shadow(), 0.85 * pe)
    blit(layer, shadow, PX - 90, PY - 70 + offset_y)

    phone = phone_frame(t)
    blit(layer, with_alpha(phone, opacity / 255), PX, PY + offset_y)
    return layer


def phone_frame(t: float) -> Image.Image:
    ui = phone_chrome().copy()
    d = ImageDraw.Draw(ui)
    sx, sy = chat_origin()

    # chat coordinates are relative to the screen origin
    def P(x: float, y: float) -> tuple[float, float]:
        return sx + x, sy + y

    # "today" divider
    tk = seg(t, 3.62, 3.85)
    if tk > 0:
        cy = sy + 132
        d.line([(sx + 40, cy), (sx + 300, cy)], fill=(255, 255, 255, int(24 * tk)), width=1)
        d.line([(sx + 384, cy), (sx + 644, cy)], fill=(255, 255, 255, int(24 * tk)), width=1)
        d.text(
            (sx + 342, cy + 7),
            "Today",
            font=font(str(SEGOE), 17),
            fill=(130, 150, 175, int(220 * tk)),
            anchor="ms",
        )

    # user bubble + typed command
    uk = seg(t, 3.66, 3.82)
    if uk > 0:
        bw, bh = 322, 74
        bx, by = sx + 666 - bw, sy + 168
        d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=24, fill=(255, 138, 42, 255))
        typed = "/level_detector"
        n = int(clamp((t - 3.72) / 0.5) * len(typed))
        if t > 3.72:
            d.text(
                (bx + 24, by + 47),
                typed[:n],
                font=font(str(CONSOLAS), 27),
                fill=(17, 26, 40, 255),
                anchor="ls",
            )
        if n < len(typed) and int(t * 8) % 2 == 0:
            cw = font(str(CONSOLAS), 27).getlength(typed[:n])
            d.rectangle((bx + 24 + cw + 2, by + 24, bx + 26 + cw, by + 62), fill=(17, 26, 40, 255))

    # typing indicator
    tk2 = seg(t, 4.18, 4.35) * (1 - seg(t, 4.62, 4.74))
    if tk2 > 0:
        bw, bh = 96, 56
        bx, by = sx + 30, sy + 268
        d.rounded_rectangle(
            (bx, by, bx + bw, by + bh), radius=22, fill=(25, 40, 63, int(255 * tk2))
        )
        for i in range(3):
            a = 0.5 + 0.5 * math.sin(t * 9 - i * 0.7)
            yy = by + 28 - 5 * a
            d.ellipse(
                (bx + 24 + i * 20, yy, bx + 34 + i * 20, yy + 10),
                fill=(170, 188, 210, int(230 * tk2)),
            )

    # result card
    rk = seg(t, 4.66, 5.0)
    if rk > 0:
        e = ease_out_cubic(rk)
        cw, ch = 566, 470
        cx, cy = sx + 30, sy + 338 + (1 - e) * 28
        card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=26, fill=(22, 37, 59, 255))
        cd.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=26, outline=(94, 234, 212, 40), width=1)

        # ring
        ring_p = ease_out_cubic(seg(t, 4.8, 5.55))
        _draw_ring(card, 112, 112, 78, 12, ring_p, 0.78)

        cd.text(
            (232, 84),
            "YOUR LEVEL",
            font=font(str(SEGOE_B), 17),
            fill=(120, 200, 190, 255),
            anchor="ls",
        )
        cd.text(
            (230, 136),
            "Upper-Intermediate",
            font=font(str(SEGOE_B), 26),
            fill=WHITE + (255,),
            anchor="ls",
        )
        cd.text(
            (232, 178),
            "39 / 50 correct",
            font=font(str(SEGOE_B), 22),
            fill=MINT + (255,),
            anchor="ls",
        )

        cd.line([(28, 214), (cw - 28, 214)], fill=(255, 255, 255, 22), width=1)
        rows = [("Grammar", 0.82, 254), ("Vocabulary", 0.74, 324)]
        for label, value, ry in rows:
            cd.text(
                (30, ry), label, font=font(str(SEGOE), 21), fill=(175, 192, 212, 255), anchor="ls"
            )
            cd.text(
                (cw - 30, ry),
                f"{int(value * 100)}%",
                font=font(str(SEGOE_B), 21),
                fill=WHITE + (255,),
                anchor="rs",
            )
            bar_p = ease_out_cubic(
                seg(
                    t,
                    5.05 + (0.14 if label == "Vocabulary" else 0),
                    5.75 + (0.1 if label == "Vocabulary" else 0),
                )
            )
            cd.rounded_rectangle((30, ry + 16, cw - 30, ry + 26), radius=5, fill=(40, 55, 78, 255))
            if bar_p > 0:
                bw = int((cw - 60) * value * bar_p)
                cd.rounded_rectangle(
                    (30, ry + 16, 30 + max(6, bw), ry + 26), radius=5, fill=MINT + (255,)
                )

        cd.text(
            (30, 404),
            "Level saved · adapts every lesson",
            font=font(str(SEGOE), 18),
            fill=(115, 135, 160, 255),
            anchor="ls",
        )
        blit(ui, with_alpha(card, e), cx, cy)

    # feedback message
    fk = seg(t, 5.55, 5.85)
    if fk > 0:
        e = ease_out_cubic(fk)
        bw, bh = 520, 124
        bx, by = sx + 30, sy + 838 + (1 - e) * 24
        d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=24, fill=(25, 40, 63, int(255 * e)))
        d.ellipse((bx + 24, by + 26, bx + 38, by + 40), fill=ORANGE + (int(255 * e),))
        d.ellipse((bx + 24, by + 70, bx + 38, by + 84), fill=MINT + (int(255 * e),))
        d.text(
            (bx + 54, by + 41),
            "Strong side: grammar",
            font=font(str(SEGOE_B), 23),
            fill=(235, 242, 250, int(255 * e)),
            anchor="ls",
        )
        d.text(
            (bx + 54, by + 85),
            "Worth improving: vocabulary",
            font=font(str(SEGOE_B), 23),
            fill=(235, 242, 250, int(255 * e)),
            anchor="ls",
        )

    # quick actions
    ck = seg(t, 5.98, 6.3)
    if ck > 0:
        e = ease_out_cubic(ck)
        labels = ["Daily lesson", "Vocabulary"]
        bw = 236
        for i, label in enumerate(labels):
            bx = sx + 30 + i * (bw + 16)
            by = sy + 1000 + (1 - e) * 24
            d.rounded_rectangle(
                (bx, by, bx + bw, by + 66), radius=20, fill=(20, 35, 56, int(255 * e))
            )
            d.rounded_rectangle(
                (bx, by, bx + bw, by + 66), radius=20, outline=MINT + (int(80 * e),), width=1
            )
            d.text(
                (bx + bw / 2, by + 41),
                label,
                font=font(str(SEGOE_B), 21),
                fill=(210, 230, 240, int(255 * e)),
                anchor="ms",
            )

        chk = seg(t, 6.15, 6.5)
        if chk > 0:
            d.text(
                (sx + 338, sy + 1112),
                "Next up: /daily_grammar",
                font=font(str(SEGOE), 19),
                fill=(115, 138, 162, int(210 * chk)),
                anchor="ms",
            )

    # chrome above content (header + input)
    ui.alpha_composite(phone_chrome_overlay())
    return ui


@lru_cache(maxsize=1)
def phone_chrome_overlay() -> Image.Image:
    """Header and input bar redrawn on top so scrolling bubbles never cover them."""
    overlay = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    chrome = phone_chrome()
    overlay.alpha_composite(chrome.crop((0, 0, PW, 124)))
    overlay.alpha_composite(chrome.crop((0, PH - 124, PW, PH)), (0, PH - 124))
    return overlay


def _draw_ring(
    layer: Image.Image,
    cx: float,
    cy: float,
    radius: float,
    width: float,
    progress: float,
    value: float,
) -> None:
    size = int(radius * 2 + width * 2)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    box = (width, width, size - width, size - width)
    d.ellipse(box, outline=(255, 255, 255, 18), width=int(width))
    if progress > 0.002:
        mask = Image.new("L", (size, size), 0)
        md = ImageDraw.Draw(mask)
        md.arc(box, -90, -90 + 360 * value * progress, fill=255, width=int(width))
        grad = gradient_rgb(
            (size, size), ((0.0, MINT), (0.55, (120, 240, 220)), (1.0, ORANGE)), False
        ).convert("RGBA")
        grad.putalpha(mask)
        canvas.alpha_composite(grad)
        # travelling head
        ang = math.radians(-90 + 360 * value * progress)
        hx = size / 2 + math.cos(ang) * (radius)
        hy = size / 2 + math.sin(ang) * (radius)
        d.ellipse((hx - 7, hy - 7, hx + 7, hy + 7), fill=(235, 255, 250, 255))
        d.ellipse((hx - 3, hy - 3, hx + 3, hy + 3), fill=(255, 255, 255, 255))
    canvas.alpha_composite(_ring_label(radius))
    blit(layer, canvas, cx - size / 2, cy - size / 2)


@lru_cache(maxsize=8)
def _ring_label(radius: float) -> Image.Image:
    size = int(radius * 2 + 24)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text(
        (size / 2, size / 2 - 8),
        "B2",
        font=font(str(RUBIK), int(radius * 0.78)),
        fill=WHITE + (255,),
        anchor="ms",
    )
    d.text(
        (size / 2, size / 2 + int(radius * 0.46)),
        "LEVEL",
        font=font(str(SEGOE_B), 13),
        fill=(120, 200, 190, 255),
        anchor="ms",
    )
    return img


# --- scene 3: streak ---------------------------------------------------------
def flame(
    layer: Image.Image,
    cx: float,
    base_y: float,
    w: float,
    h: float,
    t: float,
    intensity: float = 1.0,
) -> None:
    flick = 1 + 0.035 * math.sin(t * 6.1) + 0.02 * math.sin(t * 11.3 + 1)
    sway = 7 * math.sin(t * 3.7) + 3 * math.sin(t * 7.9 + 0.7)
    glow(
        layer,
        cx,
        base_y - h * 0.42,
        w * 1.5,
        ORANGE_HOT,
        int((70 + 26 * pulse(t, 2.4)) * intensity),
    )

    cw, chh = int(w * 2.0), int(h * 1.4)
    ox, oy = cw / 2, chh * 0.92
    layers = (
        (1.00, 1.00, ((0.0, (255, 90, 20)), (0.55, (255, 138, 42)), (1.0, (255, 196, 92)))),
        (0.66, 0.74, ((0.0, (255, 150, 40)), (0.6, (255, 190, 80)), (1.0, (255, 236, 170)))),
        (0.34, 0.44, ((0.0, (255, 236, 180)), (1.0, (255, 255, 240)))),
    )
    for fw, fh, stops in layers:
        hh = h * fh * flick
        ww = w * fw * (1 + 0.02 * math.sin(t * 5.1 + fw))
        canvas = Image.new("RGBA", (cw, chh), (0, 0, 0, 0))
        mask = Image.new("L", (cw, chh), 0)
        ImageDraw.Draw(mask).polygon(flame_points(ox, oy, ww, hh, sway), fill=255)
        grad = gradient_rgb((cw, chh), stops, False).convert("RGBA")
        grad.putalpha(mask.point(lambda v: int(v * 0.97)))
        canvas.alpha_composite(grad)
        blit(layer, canvas, cx - cw / 2, base_y - oy)
        oy -= hh * 0.1


def flame_points(
    cx: float, base_y: float, w: float, h: float, sway: float
) -> list[tuple[float, float]]:
    left, right = [], []
    steps = 70
    for i in range(steps + 1):
        u = i / steps
        half = (w / 2) * (math.sin(math.pi * (0.12 + 0.88 * u)) ** 0.62) * (1 - 0.58 * u)
        x = cx + sway * (math.sin(math.pi * u) ** 2) * 1.4
        y = base_y - h * u
        left.append((x - half, y))
        right.append((x + half, y))
    return left + right[::-1]


def scene_streak(t: float) -> Image.Image:
    layer = new_layer()

    # heading
    hk = seg(t, 7.2, 7.55)
    if hk > 0:
        e = ease_out_cubic(hk)
        blit_text(
            layer,
            "STEP 2 · KEEP THE FLAME",
            str(SEGOE_B),
            21,
            W / 2,
            268 + (1 - e) * 14,
            fill=MINT,
            alpha=int(255 * hk),
            center=True,
        )
        blit_text(
            layer,
            "Show up daily.",
            str(RUBIK),
            82,
            W / 2,
            392 + (1 - e) * 24,
            fill=WHITE,
            alpha=int(255 * hk),
            center=True,
        )
        blit_text(
            layer,
            "The streak does the motivating.",
            str(SEGOE),
            30,
            W / 2,
            452 + (1 - e) * 24,
            fill=MUTED,
            alpha=int(255 * hk),
            center=True,
        )

    # flame
    fk = seg(t, 7.18, 7.6)
    if fk > 0:
        e = ease_out_back(fk, 1.4)
        flame(layer, W / 2, 780, 250 * lerp(0.8, 1.0, e), 300 * lerp(0.8, 1.0, e), t, intensity=e)

    # counter
    start, end = 7.55, 9.25
    p = seg(t, start, end)
    value = 1 + int(round(ease_out_quint(p) * 11))
    if t < start:
        value = 1
    bump = 0.0
    if 0 < p < 1:
        frac = (ease_out_quint(p) * 11) % 1
        bump = 0.07 * (1 - frac) ** 3
    scale = 1 + 0.05 * bump / 0.07
    size = int(322 * scale)
    num_alpha = int(255 * seg(t, 7.3, 7.7))
    glow(layer, W / 2, 950, 300, ORANGE, int(50 + 30 * (value / 12)))
    blit_text(
        layer, str(value), str(RUBIK), size, W / 2, 1105, fill=WHITE, alpha=num_alpha, center=True
    )

    lab = seg(t, 7.6, 7.95)
    if lab > 0:
        blit_text(
            layer,
            "DAY STREAK",
            str(SEGOE_B),
            28,
            W / 2,
            1176,
            fill=MUTED,
            alpha=int(255 * lab),
            center=True,
        )

    # week card
    wk = seg(t, 8.3, 8.7)
    if wk > 0:
        e = ease_out_cubic(wk)
        cw, chh = 900, 300
        cx, cy = 90, 1250 + (1 - e) * 30
        heights = [0.52, 0.76, 0.94, 0.6, 0.86, 0.7, 1.0]
        days = ["M", "T", "W", "T", "F", "S", "S"]
        bw, gap = 84, 30
        total = len(heights) * bw + (len(heights) - 1) * gap
        x0 = (cw - total) / 2
        base_y = 236

        card = Image.new("RGBA", (cw, chh), (0, 0, 0, 0))
        card.alpha_composite(rrect((cw, chh), 32, (255, 255, 255, 10)))
        decor = Image.new("RGBA", (cw, chh), (0, 0, 0, 0))
        dd = ImageDraw.Draw(decor)
        dd.rounded_rectangle(
            (0, 0, cw - 1, chh - 1), radius=32, outline=(255, 255, 255, 26), width=1
        )
        dd.rectangle(
            (x0 + 6 * (bw + gap) - 8, base_y - 148, x0 + 6 * (bw + gap) + bw + 8, base_y + 12),
            fill=(94, 234, 212, 16),
        )
        card.alpha_composite(decor)

        cd = ImageDraw.Draw(card)
        cd.text((36, 46), "THIS WEEK", font=font(str(SEGOE_B), 17), fill=(255, 176, 102, 255))
        cd.text(
            (cw - 36, 46),
            "7 active days",
            font=font(str(SEGOE), 19),
            fill=(140, 160, 182, 255),
            anchor="rs",
        )
        for i, (factor, day) in enumerate(zip(heights, days, strict=True)):
            bx = x0 + i * (bw + gap)
            p_i = ease_out_back(seg(t, 8.55 + i * 0.13, 9.05 + i * 0.13), 1.2)
            hh = 132 * factor * p_i
            if hh > 2:
                bar = rrect_gradient(
                    (bw, int(hh)), 16, ((0.0, (255, 150, 60)), (1.0, (255, 110, 30))), False
                )
                card.alpha_composite(bar, (int(bx), int(base_y - hh)))
            cd.text(
                (bx + bw / 2, base_y + 26),
                day,
                font=font(str(SEGOE_B), 18),
                fill=(130, 150, 174, 255),
                anchor="ms",
            )

        if seg(t, 9.55, 9.9) > 0:
            m = ease_out_cubic(seg(t, 9.55, 9.9))
            mx, my = x0 + 6 * (bw + gap) + bw / 2, base_y - 132 * 1.0 - 16
            dot = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
            ImageDraw.Draw(dot).ellipse((4, 4, 16, 16), fill=(94, 234, 212, int(255 * m)))
            card.alpha_composite(dot, (int(mx) - 10, int(my) - 10))
        blit(layer, card, cx, cy)

    cap = seg(t, 9.55, 9.95)
    if cap > 0:
        blit_text(
            layer,
            "A five-minute lesson keeps it alive.",
            str(SEGOE),
            30,
            W / 2,
            1660,
            fill=MUTED,
            alpha=int(255 * cap),
            center=True,
        )

    # embers
    rng = random.Random(31)
    for _ in range(18):
        ph = rng.uniform(0, math.tau)
        sp = rng.uniform(0.5, 1.1)
        life = (t * sp + ph) % 1.0
        ex = W / 2 + math.sin(ph * 7 + t * 1.3) * (70 + 150 * life)
        ey = 800 - life * 620
        a = int(95 * (1 - life) * seg(t, 7.2, 7.6))
        if a > 4:
            r = 3 + 5 * (1 - life)
            blit(layer, glow_sprite(int(r * 6), ORANGE_SOFT, 2.0, a), ex - r * 3, ey - r * 3)

    return layer


# --- scene 4: CTA ------------------------------------------------------------
def scene_cta(t: float) -> Image.Image:
    layer = new_layer()

    # mascot
    mk = seg(t, 11.2, 11.75)
    if mk > 0:
        e = ease_out_back(mk, 1.35)
        size = int(520 * lerp(0.84, 1.0, e))
        sprite = mascot_sprite(
            size, angle=2.0 * math.sin(t * 2.6), squash=1 + 0.012 * math.sin(t * 3.4)
        )
        cx, cy = W / 2, 612 + math.sin(t * 2.2) * 8
        glow(layer, cx, cy + 30, 360, ORANGE_HOT, int(58 + 12 * pulse(t, 1.1)))
        blit(
            layer,
            with_alpha(sprite, segment_alpha(mk)),
            cx - sprite.width / 2,
            cy - sprite.height / 2,
        )

    # wordmark
    wk = seg(t, 11.32, 11.75)
    if wk > 0:
        e = ease_out_cubic(wk)
        blit_text(
            layer,
            "LinguaFlame",
            str(RUBIK),
            88,
            W / 2,
            985 + (1 - e) * 22,
            fill=WHITE,
            alpha=int(255 * wk),
            center=True,
        )

    # headline
    p1 = seg(t, 11.5, 11.95)
    if p1 > 0:
        e = ease_out_quint(p1)
        blit_text(
            layer,
            "Start in 5 minutes",
            str(SEGOE_B),
            58,
            W / 2,
            1095 + (1 - e) * 26,
            fill=(226, 236, 246),
            alpha=int(255 * p1),
            center=True,
        )
    p2 = seg(t, 11.62, 12.08)
    if p2 > 0:
        e = ease_out_quint(p2)
        img = text_image(
            "a day.",
            str(RUBIK),
            78,
            stops=((0.0, ORANGE), (0.6, (255, 190, 110)), (1.0, MINT)),
            alpha=int(255 * p2),
        )
        ascent = font(str(RUBIK), 78).getmetrics()[0]
        blit(layer, img, W / 2 - (img.width - 16) / 2, 1188 + (1 - e) * 26 - ascent - 8)

    # handle pill
    hk = seg(t, 11.9, 12.3)
    if hk > 0:
        e = ease_out_back(hk, 1.3)
        label = "@LinguaFlameBot"
        f = font(str(SEGOE_B), 36)
        tw = f.getlength(label)
        pw, ph = tw + 132, 80
        px, py = W / 2 - pw / 2, 1240 + (1 - e) * 26
        pill = Image.new("RGBA", (int(pw), int(ph)), (0, 0, 0, 0))
        pd = ImageDraw.Draw(pill)
        pd.rounded_rectangle((0, 0, pw - 1, ph - 1), radius=40, fill=(15, 30, 48, 255))
        pd.rounded_rectangle(
            (0, 0, pw - 1, ph - 1), radius=40, outline=(94, 234, 212, 150), width=2
        )
        ix, iy = 46, ph / 2
        pd.polygon(
            [(ix - 15, iy - 10), (ix + 16, iy), (ix - 15, iy + 10), (ix - 8, iy)],
            fill=MINT + (255,),
        )
        pd.text((92, ph / 2 + 1), label, font=f, fill=WHITE + (255,), anchor="lm")
        blit(layer, with_alpha(pill, hk), px, py)

    # QR card
    qk = seg(t, 12.12, 12.55)
    if qk > 0:
        e = ease_out_cubic(qk)
        cw = 460
        chh = 452
        cx, cy = W / 2 - cw / 2, 1348 + (1 - e) * 36
        card = Image.new("RGBA", (cw, chh), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, cw - 1, chh - 1), radius=36, fill=(255, 255, 255, 255))
        qr = QR.resize((300, 300), Image.Resampling.NEAREST)
        card.paste(qr, (80, 26))
        cd.text(
            (cw / 2, 372),
            "Scan to start",
            font=font(str(SEGOE_B), 31),
            fill=(20, 32, 52, 255),
            anchor="ms",
        )
        cd.text(
            (cw / 2, 406),
            "Telegram · free to start",
            font=font(str(SEGOE), 21),
            fill=(110, 126, 148, 255),
            anchor="ms",
        )
        blit(layer, with_alpha(card, min(1, qk * 1.5)), cx, cy)

    foot = seg(t, 12.4, 12.8)
    if foot > 0:
        blit_text(
            layer,
            "AI English coach · Telegram",
            str(SEGOE),
            21,
            W / 2,
            1862,
            fill=(110, 126, 146),
            alpha=int(230 * foot),
            center=True,
        )

    return layer


QR = Image.open(ASSETS / "qr.png").convert("RGB")


# --- compositing -------------------------------------------------------------
def scene_alpha(t: float, start: float, end: float, fade: float) -> float:
    if t < start or t > end:
        return 0.0
    return clamp((end - t) / fade)


def render_frame(t: float) -> Image.Image:
    frame = STAGE.copy()

    # drifting ambient light
    glow(
        frame,
        260 + 70 * math.sin(t * 0.42),
        1420 + 50 * math.cos(t * 0.33),
        700,
        ORANGE_HOT,
        int(26 + 10 * pulse(t, 0.5)),
    )
    glow(
        frame,
        880 + 50 * math.sin(t * 0.37 + 1.2),
        300 + 40 * math.sin(t * 0.51),
        620,
        MINT,
        int(16 + 8 * pulse(t, 0.62, 1.0)),
    )

    draw_sparks(frame, t, 0.85)

    scenes = (
        (scene_hook, 0.0, S1_END, 0.42),
        (scene_phone, S2_START, S2_END, 0.26),
        (scene_streak, S3_START, S3_END, 0.26),
        (scene_cta, S4_START, DUR, 0.4),
    )
    for builder, start, end, fade in scenes:
        a = scene_alpha(t, start, end, fade)
        if a <= 0.002:
            continue
        layer = builder(t)
        if a < 0.995:
            layer = with_alpha(layer, a)
        frame.alpha_composite(layer)

    rgb = frame.convert("RGB")

    # loop-friendly outro
    if t > 14.62:
        k = seg(t, 14.62, 15.0) ** 1.15
        rgb = Image.blend(rgb, NAVY_IMG, k)
    if t < 0.12:
        rgb = Image.blend(NAVY_IMG, rgb, seg(t, 0.0, 0.12))
    return rgb


# --- encode ------------------------------------------------------------------
def ffmpeg_path() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise SystemExit("ffmpeg not found on PATH")
    return exe


def encode_video(dest: Path, stills_mode: bool = False) -> None:
    audio = AUDIO if AUDIO.exists() else None
    cmd = [
        ffmpeg_path(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W}x{H}",
        "-r",
        str(FPS),
        "-i",
        "-",
    ]
    if audio:
        cmd += ["-i", str(audio)]
    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "high",
        "-level",
        "4.2",
        "-x264-params",
        "keyint=60:min-keyint=30",
    ]
    if audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-movflags", "+faststart", str(dest)]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    started = time.perf_counter()
    try:
        for i in range(FRAMES):
            t = i / FPS
            frame = render_frame(t)
            proc.stdin.write(frame.tobytes())
            if i % 30 == 0:
                elapsed = time.perf_counter() - started
                rate = (i + 1) / elapsed if elapsed else 0
                print(f"  frame {i:3d}/{FRAMES}  {rate:5.1f} fps", flush=True)
    finally:
        proc.stdin.close()
        code = proc.wait()
    if code != 0:
        raise SystemExit(f"ffmpeg failed with code {code}")
    print(f"video: {dest} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")


def encode_gif(mp4: Path, dest: Path) -> None:
    base = [
        ffmpeg_path(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(mp4),
    ]
    vf = (
        "fps=12,scale=405:720:flags=lanczos,split[a][b];"
        "[a]palettegen=max_colors=96:stats_mode=diff[p];"
        "[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
    )
    subprocess.run(base + ["-vf", vf, "-loop", "0", str(dest)], check=True)
    size_mb = dest.stat().st_size / 1024 / 1024
    print(f"gif:   {dest} ({size_mb:.2f} MB)")


def render_stills(times: list[float]) -> None:
    OUT.mkdir(exist_ok=True)
    for t in times:
        frame = render_frame(t)
        path = OUT / f"still_{t:05.2f}.png"
        frame.save(path)
        print(f"still: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stills", nargs="*", type=float, help="render PNG stills at these times")
    parser.add_argument("--no-gif", action="store_true")
    args = parser.parse_args()

    OUT.mkdir(exist_ok=True)
    if args.stills:
        render_stills(args.stills)
        return

    mp4 = OUT / "LinguaFlame_Promo_1080x1920.mp4"
    encode_video(mp4)
    if not args.no_gif:
        encode_gif(mp4, OUT / "LinguaFlame_Promo_Loop.gif")
    render_frame(12.7).save(OUT / "poster.png")
    print("done")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
