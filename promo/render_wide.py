"""LinguaFlame — 15-second landscape promo (1920x1080, 30 fps).

Same timeline and soundtrack as the vertical cut, re-laid out for 16:9:
text on the left, phone / streak card / QR on the right. Drawing primitives
are shared with ``render.py``; only the composition is new.

    python promo/render_wide.py               # full render (MP4 + GIF + poster)
    python promo/render_wide.py --stills 1.6 9.6 13.4
"""

from __future__ import annotations

import argparse
import math
import random
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import render as V  # noqa: E402

OUT = V.OUT
AUDIO = V.AUDIO

W, H = 1920, 1080
FPS = V.FPS
DUR = V.DUR
FRAMES = int(round(DUR * FPS))

RB = str(V.RUBIK)
SG = str(V.SEGOE)
SGB = str(V.SEGOE_B)

# Phone mockup, scaled to fit the 1080 px frame height.
PHONE_S = 0.74
PHONE_W, PHONE_H = int(V.PW * PHONE_S), int(V.PH * PHONE_S)
PHONE_X, PHONE_Y = 1230, 25

QR = V.QR


# --- stage -------------------------------------------------------------------
def new_layer() -> Image.Image:
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def build_stage() -> Image.Image:
    stage = Image.new("RGBA", (W, H), V.NAVY + (255,))
    d = ImageDraw.Draw(stage)
    top, mid, bottom = (10, 17, 33), (12, 22, 41), (6, 11, 22)
    for y in range(H):
        p = y / (H - 1)
        if p < 0.45:
            c = V.mix(top, mid, p / 0.45)
        else:
            c = V.mix(mid, bottom, (p - 0.45) / 0.55)
        d.line([(0, y), (W, y)], fill=c + (255,))

    stage.alpha_composite(V.glow_sprite(1500, V.ORANGE_HOT, 2.4, 40), (-560, 380))
    stage.alpha_composite(V.glow_sprite(1300, V.MINT, 2.6, 20), (1080, -460))
    stage.alpha_composite(V.glow_sprite(1000, (70, 110, 220), 2.8, 24), (1180, 720))

    noise = Image.effect_noise((W, H), 22).convert("L").point(lambda v: int((v - 128) * 0.55 + 128))
    grain = Image.merge("RGBA", (noise, noise, noise, Image.new("L", (W, H), 8)))
    stage.alpha_composite(grain)
    return stage


def build_vignette() -> Image.Image:
    vig = Image.new("RGB", (W, H))
    vd = ImageDraw.Draw(vig)
    for y in range(0, H, 4):
        p = abs(y - H * 0.45) / (H * 0.62)
        value = int(255 - 40 * min(1.0, p) ** 2.6)
        vd.rectangle((0, y, W, y + 4), fill=(value, value, value))
    return vig.filter(ImageFilter.GaussianBlur(30))


STAGE = ImageChops.multiply(build_stage().convert("RGB"), build_vignette()).convert("RGBA")
NAVY_IMG = Image.new("RGB", (W, H), V.NAVY)


# --- particles ---------------------------------------------------------------
def build_sparks(count: int = 62, seed: int = 17) -> list[V.Spark]:
    rng = random.Random(seed)
    palette = [V.ORANGE, V.ORANGE_SOFT, V.MINT, (200, 220, 240)]
    return [
        V.Spark(
            x=rng.uniform(40, W - 40),
            y=rng.uniform(0, H),
            vx=rng.uniform(-8, 8),
            vy=rng.uniform(-22, -7),
            size=rng.uniform(1.6, 4.4),
            phase=rng.uniform(0, math.tau),
            speed=rng.uniform(0.7, 1.8),
            color=rng.choice(palette),
            amp=rng.uniform(0.25, 0.85),
        )
        for _ in range(count)
    ]


SPARKS = build_sparks()


def draw_sparks(layer: Image.Image, t: float, strength: float = 1.0) -> None:
    for s in SPARKS:
        y = (s.y + s.vy * t) % (H + 120)
        x = s.x + s.vx * t + math.sin(t * 0.7 + s.phase) * 14
        twinkle = 0.35 + 0.65 * V.pulse(t, s.speed, s.phase)
        alpha = int(255 * s.amp * twinkle * strength)
        if alpha < 8:
            continue
        bucket = min(255, (alpha // 32) * 32)
        r = int(round(s.size * 5.5))
        V.blit(layer, V.glow_sprite(r * 2, s.color, 2.0, bucket), x - r, y - r)
        core = max(2, int(round(s.size)))
        V.blit(
            layer,
            V.glow_sprite(core * 4, s.color, 1.4, min(255, bucket + 64)),
            x - core * 2,
            y - core * 2,
        )


# --- layout helpers ----------------------------------------------------------
def draw_words_left(
    layer: Image.Image,
    words: list[str],
    font_path: str,
    size: int,
    baseline: float,
    x: float,
    t: float,
    start: float,
    stagger: float,
    color: tuple[int, int, int],
) -> None:
    f = V.font(font_path, size)
    space = f.getlength(" ")
    widths = [f.getlength(w) for w in words]
    for i, (word, wd) in enumerate(zip(words, widths, strict=True)):
        p = V.seg(t, start + i * stagger, start + i * stagger + 0.55)
        if p > 0:
            e = V.ease_out_quint(p)
            img = V.text_image(word, font_path, size, fill=color, alpha=int(255 * e))
            ascent, _ = f.getmetrics()
            V.blit(layer, img, x - 8, baseline + (1 - e) * 44 - ascent - 8)
        x += wd + space


def tracked_pill(
    layer: Image.Image,
    text: str,
    font_size: int,
    x: float,
    y: float,
    k: float,
    tracking: float = 3.4,
) -> None:
    f = V.font(SGB, font_size)
    tw = V.text_width(text, f, tracking)
    pw, ph = tw + 64, 54
    pill = V.rrect((int(pw), ph), 27, (255, 255, 255, 20))
    V.blit(layer, V.with_alpha(pill, k), x, y + (1 - k) * 16)
    img = V.text_image(text, SGB, font_size, fill=V.MINT, alpha=int(255 * k))
    V.blit(layer, img, x + 32 - 8, y + ph / 2 - font_size / 2 - 8 + (1 - k) * 16)


# --- scene 1: hook -----------------------------------------------------------
def scene_hook(t: float) -> Image.Image:
    layer = new_layer()

    k = V.seg(t, 0.18, 0.55)
    if k > 0:
        tracked_pill(layer, "AI ENGLISH COACH  ·  TELEGRAM", 22, 150, 250, k)

    entrance = V.seg(t, 0.05, 0.8)
    if entrance > 0:
        e = V.ease_out_back(entrance, 1.5)
        size = int(760 * V.lerp(0.86, 1.0, e))
        bob = math.sin(t * 2.3) * 9
        wave = 2.6 * math.sin(t * 4.4 + 0.4) * V.seg(t, 0.5, 1.2)
        sprite = V.mascot_sprite(size, angle=wave, squash=1 + 0.012 * math.sin(t * 3.1))
        cx, cy = 1490, 560 + bob
        V.glow(layer, cx, cy + 30, 470, V.ORANGE_HOT, int(46 + 14 * V.pulse(t, 0.9)))
        V.blit(
            layer,
            V.with_alpha(sprite, V.segment_alpha(entrance)),
            cx - sprite.width / 2,
            cy - sprite.height / 2,
        )

    ws, stagger = 0.34, 0.085
    draw_words_left(layer, ["English", "that"], RB, 118, 400, 150, t, ws, stagger, V.WHITE)
    draw_words_left(
        layer, ["people", "don't"], RB, 118, 530, 150, t, ws + 2 * stagger, stagger, V.WHITE
    )

    p3 = V.seg(t, 1.02, 1.55)
    if p3 > 0:
        e = V.ease_out_back(p3, 1.3)
        size = int(138 * V.lerp(0.9, 1.0, e))
        img = V.text_image(
            "quit.",
            RB,
            size,
            stops=((0.0, V.ORANGE), (0.55, (255, 180, 90)), (1.0, V.MINT)),
            alpha=int(255 * min(1, p3 * 1.6)),
        )
        ascent = V.font(RB, size).getmetrics()[0]
        V.blit(layer, img, 150 - 8, 672 + (1 - e) * 40 - ascent - 8)

    sk = V.seg(t, 1.35, 1.9)
    if sk > 0:
        V.blit_text(
            layer,
            "Measure your level. Practise five minutes a day.",
            SG,
            31,
            150,
            820 + (1 - V.ease_out_cubic(sk)) * 24,
            fill=(160, 178, 198),
            alpha=int(255 * sk),
        )

    return layer


# --- scene 2: level detector -------------------------------------------------
def phone_scaled(t: float) -> Image.Image:
    return V.phone_frame(t).resize((PHONE_W, PHONE_H), Image.Resampling.LANCZOS)


def scene_phone(t: float) -> Image.Image:
    layer = new_layer()

    hk = V.seg(t, 3.16, 3.55)
    if hk > 0:
        e = V.ease_out_cubic(hk)
        V.blit_text(
            layer,
            "STEP 1 · FIND YOUR LEVEL",
            SGB,
            21,
            150,
            318 + (1 - e) * 14,
            fill=V.MINT,
            alpha=int(255 * hk),
        )
        V.blit_text(
            layer,
            "Know your level",
            RB,
            76,
            150,
            430 + (1 - e) * 26,
            fill=V.WHITE,
            alpha=int(255 * hk),
        )
        V.blit_text(
            layer,
            "in 50 questions.",
            RB,
            76,
            150,
            528 + (1 - e) * 30,
            fill=V.MINT,
            alpha=int(255 * hk),
        )

    sk = V.seg(t, 3.5, 3.9)
    if sk > 0:
        e = V.ease_out_cubic(sk)
        V.blit_text(
            layer,
            "Fifty questions, adaptive difficulty.",
            SG,
            30,
            150,
            626 + (1 - e) * 20,
            fill=(160, 178, 198),
            alpha=int(255 * sk),
        )
        V.blit_text(
            layer,
            "One clear CEFR level, saved to your profile.",
            SG,
            30,
            150,
            674 + (1 - e) * 24,
            fill=(160, 178, 198),
            alpha=int(255 * sk),
        )

    pk = V.seg(t, V.S2_START, 3.62)
    if pk <= 0:
        return layer
    pe = V.ease_out_quint(pk)
    offset_y = (1 - pe) * 150
    opacity = int(255 * V.clamp(pk * 1.35))

    V.glow(layer, PHONE_X + PHONE_W - 40, PHONE_Y + 340, 460, V.MINT, int(22 * pe))
    V.glow(layer, PHONE_X + 60, PHONE_Y + PHONE_H - 320, 500, V.ORANGE, int(30 * pe))

    pad = int(90 * PHONE_S)
    shadow = V.with_alpha(V.phone_shadow(), 0.85 * pe).resize(
        (V.phone_shadow().width * PHONE_W // V.PW, V.phone_shadow().height * PHONE_H // V.PH),
        Image.Resampling.LANCZOS,
    )
    V.blit(layer, shadow, PHONE_X - pad, PHONE_Y - int(70 * PHONE_S) + offset_y)

    V.blit(layer, V.with_alpha(phone_scaled(t), opacity / 255), PHONE_X, PHONE_Y + offset_y)
    return layer


# --- scene 3: streak ---------------------------------------------------------
def scene_streak(t: float) -> Image.Image:
    layer = new_layer()

    hk = V.seg(t, 7.2, 7.55)
    if hk > 0:
        e = V.ease_out_cubic(hk)
        V.blit_text(
            layer,
            "STEP 2 · KEEP THE FLAME",
            SGB,
            21,
            150,
            252 + (1 - e) * 14,
            fill=V.MINT,
            alpha=int(255 * hk),
        )
        V.blit_text(
            layer,
            "Show up daily.",
            RB,
            82,
            150,
            360 + (1 - e) * 24,
            fill=V.WHITE,
            alpha=int(255 * hk),
        )
        V.blit_text(
            layer,
            "The streak does the motivating.",
            SG,
            30,
            150,
            418 + (1 - e) * 24,
            fill=V.MUTED,
            alpha=int(255 * hk),
        )

    fk = V.seg(t, 7.18, 7.6)
    if fk > 0:
        e = V.ease_out_back(fk, 1.4)
        V.flame(
            layer, 400, 716, 220 * V.lerp(0.8, 1.0, e), 246 * V.lerp(0.8, 1.0, e), t, intensity=e
        )

    start, end = 7.55, 9.25
    p = V.seg(t, start, end)
    value = 1 + int(round(V.ease_out_quint(p) * 11))
    if t < start:
        value = 1
    bump = 0.0
    if 0 < p < 1:
        frac = (V.ease_out_quint(p) * 11) % 1
        bump = 0.07 * (1 - frac) ** 3
    size = int(292 * (1 + 0.05 * bump / 0.07))
    num_alpha = int(255 * V.seg(t, 7.3, 7.7))
    V.glow(layer, 400, 840, 280, V.ORANGE, int(50 + 30 * (value / 12)))
    V.blit_text(layer, str(value), RB, size, 400, 950, fill=V.WHITE, alpha=num_alpha, center=True)

    lab = V.seg(t, 7.6, 7.95)
    if lab > 0:
        V.blit_text(
            layer,
            "DAY STREAK",
            SGB,
            28,
            400,
            1010,
            fill=V.MUTED,
            alpha=int(255 * lab),
            center=True,
        )

    wk = V.seg(t, 8.3, 8.7)
    if wk > 0:
        e = V.ease_out_cubic(wk)
        cw, chh = 840, 300
        cx, cy = 980, 420 + (1 - e) * 30
        heights = [0.52, 0.76, 0.94, 0.6, 0.86, 0.7, 1.0]
        days = ["M", "T", "W", "T", "F", "S", "S"]
        bw, gap = 78, 28
        total = len(heights) * bw + (len(heights) - 1) * gap
        x0 = (cw - total) / 2
        base_y = 232

        card = Image.new("RGBA", (cw, chh), (0, 0, 0, 0))
        card.alpha_composite(V.rrect((cw, chh), 32, (255, 255, 255, 10)))
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
        cd.text((36, 46), "THIS WEEK", font=V.font(SGB, 17), fill=(255, 176, 102, 255))
        cd.text(
            (cw - 36, 46),
            "7 active days",
            font=V.font(SG, 19),
            fill=(140, 160, 182, 255),
            anchor="rs",
        )
        for i, (factor, day) in enumerate(zip(heights, days, strict=True)):
            bx = x0 + i * (bw + gap)
            p_i = V.ease_out_back(V.seg(t, 8.55 + i * 0.13, 9.05 + i * 0.13), 1.2)
            hh = 132 * factor * p_i
            if hh > 2:
                bar = V.rrect_gradient(
                    (bw, int(hh)), 16, ((0.0, (255, 150, 60)), (1.0, (255, 110, 30))), False
                )
                card.alpha_composite(bar, (int(bx), int(base_y - hh)))
            cd.text(
                (bx + bw / 2, base_y + 26),
                day,
                font=V.font(SGB, 18),
                fill=(130, 150, 174, 255),
                anchor="ms",
            )

        if V.seg(t, 9.55, 9.9) > 0:
            m = V.ease_out_cubic(V.seg(t, 9.55, 9.9))
            mx, my = x0 + 6 * (bw + gap) + bw / 2, base_y - 132.0 - 16
            dot = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
            ImageDraw.Draw(dot).ellipse((4, 4, 16, 16), fill=(94, 234, 212, int(255 * m)))
            card.alpha_composite(dot, (int(mx) - 10, int(my) - 10))
        V.blit(layer, card, cx, cy)

    cap = V.seg(t, 9.55, 9.95)
    if cap > 0:
        V.blit_text(
            layer,
            "A five-minute lesson keeps it alive.",
            SG,
            29,
            980,
            792,
            fill=V.MUTED,
            alpha=int(255 * cap),
        )

    rng = random.Random(31)
    for _ in range(18):
        ph = rng.uniform(0, math.tau)
        sp = rng.uniform(0.5, 1.1)
        life = (t * sp + ph) % 1.0
        ex = 400 + math.sin(ph * 7 + t * 1.3) * (60 + 120 * life)
        ey = 720 - life * 520
        a = int(95 * (1 - life) * V.seg(t, 7.2, 7.6))
        if a > 4:
            r = 3 + 5 * (1 - life)
            V.blit(layer, V.glow_sprite(int(r * 6), V.ORANGE_SOFT, 2.0, a), ex - r * 3, ey - r * 3)

    return layer


# --- scene 4: CTA ------------------------------------------------------------
def scene_cta(t: float) -> Image.Image:
    layer = new_layer()

    mk = V.seg(t, 11.2, 11.75)
    if mk > 0:
        e = V.ease_out_back(mk, 1.35)
        size = int(600 * V.lerp(0.84, 1.0, e))
        sprite = V.mascot_sprite(
            size, angle=2.0 * math.sin(t * 2.6), squash=1 + 0.012 * math.sin(t * 3.4)
        )
        cx, cy = 340, 560 + math.sin(t * 2.2) * 8
        V.glow(layer, cx, cy + 30, 360, V.ORANGE_HOT, int(58 + 12 * V.pulse(t, 1.1)))
        V.blit(
            layer,
            V.with_alpha(sprite, V.segment_alpha(mk)),
            cx - sprite.width / 2,
            cy - sprite.height / 2,
        )

    wk = V.seg(t, 11.32, 11.75)
    if wk > 0:
        e = V.ease_out_cubic(wk)
        V.blit_text(
            layer,
            "LinguaFlame",
            RB,
            88,
            720,
            350 + (1 - e) * 22,
            fill=V.WHITE,
            alpha=int(255 * wk),
        )

    p1 = V.seg(t, 11.5, 11.95)
    if p1 > 0:
        e = V.ease_out_quint(p1)
        V.blit_text(
            layer,
            "Start in 5 minutes",
            SGB,
            54,
            720,
            452 + (1 - e) * 26,
            fill=(226, 236, 246),
            alpha=int(255 * p1),
        )

    p2 = V.seg(t, 11.62, 12.08)
    if p2 > 0:
        e = V.ease_out_quint(p2)
        img = V.text_image(
            "a day.",
            RB,
            78,
            stops=((0.0, V.ORANGE), (0.6, (255, 190, 110)), (1.0, V.MINT)),
            alpha=int(255 * p2),
        )
        ascent = V.font(RB, 78).getmetrics()[0]
        V.blit(layer, img, 720 - 8, 562 + (1 - e) * 26 - ascent - 8)

    hk = V.seg(t, 11.9, 12.3)
    if hk > 0:
        e = V.ease_out_back(hk, 1.3)
        label = "@LinguaFlameBot"
        f = V.font(SGB, 36)
        tw = f.getlength(label)
        pw, ph = tw + 132, 80
        px, py = 720, 622 + (1 - e) * 26
        pill = Image.new("RGBA", (int(pw), int(ph)), (0, 0, 0, 0))
        pd = ImageDraw.Draw(pill)
        pd.rounded_rectangle((0, 0, pw - 1, ph - 1), radius=40, fill=(15, 30, 48, 255))
        pd.rounded_rectangle(
            (0, 0, pw - 1, ph - 1), radius=40, outline=(94, 234, 212, 150), width=2
        )
        ix, iy = 46, ph / 2
        pd.polygon(
            [(ix - 15, iy - 10), (ix + 16, iy), (ix - 15, iy + 10), (ix - 8, iy)],
            fill=V.MINT + (255,),
        )
        pd.text((92, ph / 2 + 1), label, font=f, fill=V.WHITE + (255,), anchor="lm")
        V.blit(layer, V.with_alpha(pill, hk), px, py)

    qk = V.seg(t, 12.12, 12.55)
    if qk > 0:
        e = V.ease_out_cubic(qk)
        cw, chh = 400, 452
        cx, cy = 1400, 272 + (1 - e) * 36
        card = Image.new("RGBA", (cw, chh), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((0, 0, cw - 1, chh - 1), radius=36, fill=(255, 255, 255, 255))
        card.paste(QR.resize((300, 300), Image.Resampling.NEAREST), (50, 26))
        cd.text(
            (cw / 2, 372),
            "Scan to start",
            font=V.font(SGB, 31),
            fill=(20, 32, 52, 255),
            anchor="ms",
        )
        cd.text(
            (cw / 2, 406),
            "Telegram · free to start",
            font=V.font(SG, 21),
            fill=(110, 126, 148, 255),
            anchor="ms",
        )
        V.blit(layer, V.with_alpha(card, min(1, qk * 1.5)), cx, cy)

    foot = V.seg(t, 12.4, 12.8)
    if foot > 0:
        V.blit_text(
            layer,
            "AI English coach · Telegram",
            SG,
            21,
            W / 2,
            1036,
            fill=(110, 126, 146),
            alpha=int(230 * foot),
            center=True,
        )

    return layer


# --- compositing -------------------------------------------------------------
def render_frame(t: float) -> Image.Image:
    frame = STAGE.copy()

    V.glow(
        frame,
        300 + 90 * math.sin(t * 0.42),
        880 + 40 * math.cos(t * 0.33),
        700,
        V.ORANGE_HOT,
        int(26 + 10 * V.pulse(t, 0.5)),
    )
    V.glow(
        frame,
        1560 + 60 * math.sin(t * 0.37 + 1.2),
        220 + 40 * math.sin(t * 0.51),
        600,
        V.MINT,
        int(16 + 8 * V.pulse(t, 0.62, 1.0)),
    )

    draw_sparks(frame, t, 0.85)

    scenes = (
        (scene_hook, 0.0, V.S1_END, 0.42),
        (scene_phone, V.S2_START, V.S2_END, 0.26),
        (scene_streak, V.S3_START, V.S3_END, 0.26),
        (scene_cta, V.S4_START, DUR, 0.4),
    )
    for builder, start, end, fade in scenes:
        a = V.scene_alpha(t, start, end, fade)
        if a <= 0.002:
            continue
        layer = builder(t)
        if a < 0.995:
            layer = V.with_alpha(layer, a)
        frame.alpha_composite(layer)

    rgb = frame.convert("RGB")
    if t > 14.62:
        rgb = Image.blend(rgb, NAVY_IMG, V.seg(t, 14.62, 15.0) ** 1.15)
    if t < 0.12:
        rgb = Image.blend(NAVY_IMG, rgb, V.seg(t, 0.0, 0.12))
    return rgb


# --- encode ------------------------------------------------------------------
def encode_video(dest: Path) -> None:
    audio = AUDIO if AUDIO.exists() else None
    cmd = [
        V.ffmpeg_path(),
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
            proc.stdin.write(render_frame(t).tobytes())
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
    vf = (
        "fps=12,scale=720:405:flags=lanczos,split[a][b];"
        "[a]palettegen=max_colors=96:stats_mode=diff[p];"
        "[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
    )
    subprocess.run(
        [
            V.ffmpeg_path(),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(mp4),
            "-vf",
            vf,
            "-loop",
            "0",
            str(dest),
        ],
        check=True,
    )
    print(f"gif:   {dest} ({dest.stat().st_size / 1024 / 1024:.2f} MB)")


def render_stills(times: list[float]) -> None:
    OUT.mkdir(exist_ok=True)
    for t in times:
        path = OUT / f"wide_still_{t:05.2f}.png"
        render_frame(t).save(path)
        print(f"still: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stills", nargs="*", type=float)
    parser.add_argument("--no-gif", action="store_true")
    args = parser.parse_args()

    OUT.mkdir(exist_ok=True)
    if args.stills:
        render_stills(args.stills)
        return

    mp4 = OUT / "LinguaFlame_Promo_1920x1080.mp4"
    encode_video(mp4)
    if not args.no_gif:
        encode_gif(mp4, OUT / "LinguaFlame_Promo_Loop_16x9.gif")
    render_frame(13.4).save(OUT / "poster_16x9.png")
    print("done")


if __name__ == "__main__":
    main()
