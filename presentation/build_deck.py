"""Build the LinguaFlame pitch deck (HTML -> PNG -> PPTX/PDF).

Run from the repository root:
    python presentation/build_deck.py

Requires Microsoft Edge for headless screenshots and python-pptx/Pillow.
"""

from __future__ import annotations

import html
import subprocess
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.util import Inches

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
ASSETS = ROOT / "assets"
BUILD = ROOT / ".build"
SLIDES_DIR = BUILD / "slides"
HTML_DIR = BUILD / "html"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
AVATAR = REPO / "Avatars" / "photo_2026-10-21_19-09-38.jpg"
BANNER = REPO / "Avatars" / "photo_2026-10-21_19-09-43.jpg"

W, H = 1920, 1080
TOTAL = 12


ICONS: dict[str, str] = {
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/>',
    "book": '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>',
    "layers": '<path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 17 9 5 9-5"/>',
    "chat": '<path d="M21 15a4 4 0 0 1-4 4H8l-5 3V6a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v9Z"/><path d="M8 9h8"/><path d="M8 13h5"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h5"/>',
    "flame": '<path d="M12 22c4.4 0 8-3.4 8-7.7 0-3.1-1.7-5.3-4.2-7.8-.8 2.1-2.2 3.4-3.8 3.8.3-4.6-1.4-7.6-3.8-9.3.2 3.8-1.4 5.4-2.6 7.4A8.2 8.2 0 0 0 4 14.3C4 18.6 7.6 22 12 22Z"/><path d="M12 22c2.2 0 4-1.8 4-4 0-2.1-1.6-3.3-2.4-4.5-.4.9-1.1 1.5-1.9 1.7.1-1.5-.4-2.7-1.2-3.7-.1 2.4-1.7 3.3-2.1 5.2-.2.8-.1 1.5.1 2.2.8 1.9 2.2 3.1 3.5 3.1Z" fill="currentColor" stroke="none"/>',
    "chart": '<path d="M4 20V10"/><path d="M10 20V4"/><path d="M16 20v-7"/><path d="M22 20H2"/>',
    "sparkles": '<path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3Z"/><path d="m19 16 .8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16Z"/><path d="m5 2 .6 1.7L7.3 4l-1.7.6L5 6.3l-.6-1.7L2.7 4l1.7-.3L5 2Z"/>',
    "database": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "cpu": '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/><path d="M9 1v4M15 1v4M9 19v4M15 19v4M1 9h4M1 15h4M19 9h4M19 15h4"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/><path d="m9 12 2 2 4-5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c2.5 2.4 4 5.4 4 9s-1.5 6.6-4 9c-2.5-2.4-4-5.4-4-9s1.5-6.6 4-9Z"/>',
    "check": '<path d="m20 6-11 11-5-5"/>',
    "arrow": '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
    "play": '<path d="m7 4 13 8-13 8V4Z"/>',
    "users": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.9"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/>',
    "zap": '<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z"/>',
    "rocket": '<path d="M4.5 16.5c-1.5 1.3-2 5-2 5s3.7-.5 5-2c.8-.9.8-2.2-.1-3-.8-.8-2.1-.8-2.9 0Z"/><path d="M12 15 9 12a22 22 0 0 1 2.4-4.6A12.8 12.8 0 0 1 22 2c0 2.7-.8 7.5-5.4 10.6A22 22 0 0 1 12 15Z"/><path d="M9 12H4s.5-3.2 2-4.5C7.5 6 12 6 12 6"/><path d="M12 15v5s3.2-.5 4.5-2C18 16.5 18 12 18 12"/>',
    "message": '<path d="M21 15a4 4 0 0 1-4 4H8l-5 3V6a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v9Z"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "moon": '<path d="M21 12.8A8.5 8.5 0 1 1 11.2 3a6.6 6.6 0 0 0 9.8 9.8Z"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/><path d="M8 15h.01M12 15h.01M16 15h.01M8 18h.01M12 18h.01"/>',
    "lock": '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
    "code": '<path d="m8 7-5 5 5 5"/><path d="m16 7 5 5-5 5"/><path d="m14 4-4 16"/>',
    "cloud": '<path d="M17.5 19H7a5 5 0 0 1-.9-9.9A7 7 0 0 1 19.7 11a4 4 0 0 1-2.2 8Z"/>',
    "wrench": '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.5-2.5 2.5-2.5Z"/>',
    "graduation": '<path d="m2 9 10-5 10 5-10 5L2 9Z"/><path d="M6 11v5c3 2 9 2 12 0v-5"/><path d="M22 9v6"/>',
    "headphones": '<path d="M4 14v-2a8 8 0 0 1 16 0v2"/><path d="M4 14h3v6H5a1 1 0 0 1-1-1v-5Z"/><path d="M20 14h-3v6h2a1 1 0 0 0 1-1v-5Z"/>',
    "credit": '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
    "refresh": '<path d="M20 11a8 8 0 0 0-14.9-3M4 4v5h5"/><path d="M4 13a8 8 0 0 0 14.9 3M20 20v-5h-5"/>',
    "send": '<path d="m22 2-7 20-4-9-9-4 20-7Z"/><path d="M22 2 11 13"/>',
    "mic": '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><path d="M12 17v5M8 22h8"/>',
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    "flag": '<path d="M4 22V4"/><path d="M4 4c5-3 9 3 16 0v10c-7 3-11-3-16 0"/>',
    "scissors": '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="m20 4-9.5 9.5M8.5 8.5 20 20"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
}


def icon(name: str, size: int = 28, cls: str = "") -> str:
    return (
        f'<svg class="icon {cls}" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
        f'stroke-linejoin="round" aria-hidden="true">{ICONS[name]}</svg>'
    )


CSS = r"""
@font-face {
  font-family: 'ManropeFallback';
  src: local('Segoe UI');
}
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0; width: 1920px; height: 1080px;
  overflow: hidden; background: #07111f;
  font-family: 'Segoe UI', 'ManropeFallback', Arial, sans-serif;
  color: #f8fafc; -webkit-font-smoothing: antialiased;
}
body { position: relative; }
.slide {
  position: relative; width: 1920px; height: 1080px; overflow: hidden;
  padding: 62px 84px 58px;
  background:
    radial-gradient(1000px 650px at 88% -12%, rgba(255,122,24,.22), transparent 62%),
    radial-gradient(850px 650px at -12% 112%, rgba(45,212,191,.13), transparent 62%),
    linear-gradient(135deg, #07111f 0%, #081526 48%, #07111f 100%);
}
.slide:before {
  content: ''; position: absolute; inset: 0; pointer-events: none;
  background-image:
    linear-gradient(rgba(255,255,255,.032) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.032) 1px, transparent 1px);
  background-size: 64px 64px;
  mask-image: linear-gradient(to bottom, rgba(0,0,0,.75), transparent 82%);
  -webkit-mask-image: linear-gradient(to bottom, rgba(0,0,0,.75), transparent 82%);
}
.slide:after {
  content: ''; position: absolute; width: 760px; height: 760px; right: -240px; top: -280px;
  border-radius: 50%; pointer-events: none;
  background: radial-gradient(circle, rgba(255,122,24,.10), transparent 66%);
}
.slide.dark-tail:after {
  background: radial-gradient(circle, rgba(45,212,191,.10), transparent 66%);
}
.content { position: relative; z-index: 2; height: 100%; }
.icon { flex: none; }
.kicker {
  display: flex; align-items: center; gap: 14px;
  color: #ff9a5c; font-size: 15px; font-weight: 700; letter-spacing: 3.4px;
  text-transform: uppercase; margin-bottom: 18px;
}
.kicker .line { width: 46px; height: 2px; background: #ff7a18; border-radius: 2px; }
h1, h2, h3, p { margin: 0; }
h1 { font-size: 90px; line-height: .98; letter-spacing: -4.2px; font-weight: 700; }
h2 { font-size: 62px; line-height: 1.03; letter-spacing: -2.6px; font-weight: 700; }
h3 { font-size: 27px; line-height: 1.18; letter-spacing: -.6px; font-weight: 600; }
.lead { font-size: 25px; line-height: 1.5; color: #aab8cb; }
.muted { color: #93a3b8; }
.accent { color: #ff8a3d; }
.teal { color: #2dd4bf; }
.gradient {
  background: linear-gradient(92deg, #ffc266 0%, #ff7a18 62%, #ff5a1f 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.footer {
  position: absolute; z-index: 3; left: 84px; right: 84px; bottom: 27px;
  display: flex; align-items: center; justify-content: space-between;
  font-size: 13px; letter-spacing: 1.1px; color: #63758f; text-transform: uppercase;
}
.footer .f-brand { display: flex; align-items: center; gap: 10px; color: #8ea0b8; }
.footer .f-brand img { width: 22px; height: 22px; border-radius: 7px; }
.footer .f-brand b { color: #d8e2ef; font-weight: 600; letter-spacing: .6px; }
.footer .f-num { color: #ff9a5c; font-weight: 700; }
.slide-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 50px; }
.slide-note {
  max-width: 350px; padding-top: 22px; text-align: right;
  color: #7f91aa; font-size: 16px; line-height: 1.5;
}
.pill {
  display: inline-flex; align-items: center; gap: 9px;
  padding: 10px 17px; border-radius: 999px;
  background: rgba(255,255,255,.055); border: 1px solid rgba(255,255,255,.11);
  color: #c7d3e2; font-size: 15px; font-weight: 600; white-space: nowrap;
}
.pill .dot { width: 7px; height: 7px; border-radius: 50%; background: #ff7a18; box-shadow: 0 0 12px #ff7a18; }
.card {
  background: linear-gradient(145deg, rgba(255,255,255,.075), rgba(255,255,255,.025));
  border: 1px solid rgba(255,255,255,.105); border-radius: 28px;
  box-shadow: 0 24px 60px rgba(0,0,0,.2);
}
.num-badge {
  display: inline-flex; align-items: center; justify-content: center;
  width: 42px; height: 42px; border-radius: 13px;
  background: rgba(255,122,24,.13); border: 1px solid rgba(255,122,24,.28);
  color: #ff9a5c; font-size: 14px; font-weight: 700;
}
.icon-box {
  display: inline-flex; align-items: center; justify-content: center;
  width: 56px; height: 56px; border-radius: 17px;
  background: rgba(255,122,24,.12); border: 1px solid rgba(255,122,24,.2);
  color: #ff9a5c;
}
.icon-box.teal { background: rgba(45,212,191,.10); border-color: rgba(45,212,191,.22); color: #5eead4; }
.icon-box.violet { background: rgba(139,92,246,.12); border-color: rgba(139,92,246,.25); color: #c4b5fd; }
.icon-box.blue { background: rgba(56,189,248,.10); border-color: rgba(56,189,248,.22); color: #7dd3fc; }
.icon-box.green { background: rgba(74,222,128,.10); border-color: rgba(74,222,128,.22); color: #86efac; }

/* Hero */
.hero-grid { display: grid; grid-template-columns: 1.08fr .92fr; height: 100%; align-items: center; gap: 30px; }
.hero-copy { padding-top: 4px; }
.brand-line { display: flex; align-items: center; gap: 14px; margin-bottom: 64px; }
.brand-line img { width: 48px; height: 48px; border-radius: 14px; box-shadow: 0 0 28px rgba(255,122,24,.25); }
.brand-line .brand-name { font-size: 21px; font-weight: 700; letter-spacing: -.4px; }
.brand-tag { font-size: 11px; color: #ff9a5c; letter-spacing: 2.2px; font-weight: 700; padding-left: 6px; }
.hero-copy h1 { margin-bottom: 30px; }
.hero-copy .lead { width: 760px; font-size: 24px; }
.hero-pills { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 36px; width: 760px; }
.hero-meta { margin-top: 48px; color: #7f91aa; font-size: 15px; letter-spacing: .5px; }
.hero-meta b { color: #d8e2ef; font-weight: 600; }
.hero-visual { position: relative; height: 820px; }
.hero-visual .halo {
  position: absolute; width: 690px; height: 690px; left: 50%; top: 50%;
  transform: translate(-50%, -50%); border-radius: 50%;
  background: radial-gradient(circle, rgba(255,122,24,.24), rgba(255,122,24,.05) 48%, transparent 70%);
  filter: blur(6px);
}
.hero-visual .ring {
  position: absolute; width: 590px; height: 590px; left: 50%; top: 50%;
  transform: translate(-50%, -50%); border-radius: 50%;
  border: 1px solid rgba(255,154,92,.17);
}
.hero-visual .ring.r2 { width: 680px; height: 680px; border-color: rgba(45,212,191,.11); }
.logo-frame {
  position: absolute; width: 560px; height: 560px; left: 50%; top: 50%;
  transform: translate(-50%, -50%); padding: 9px; border-radius: 132px;
  background: linear-gradient(135deg, rgba(255,194,102,.9), rgba(255,90,31,.85) 55%, rgba(45,212,191,.55));
  box-shadow: 0 38px 100px rgba(0,0,0,.42), 0 0 80px rgba(255,122,24,.18);
}
.logo-frame img { width: 100%; height: 100%; display: block; border-radius: 124px; object-fit: cover; }
.float-card {
  position: absolute; display: flex; align-items: center; gap: 13px;
  padding: 16px 19px; border-radius: 19px;
  background: rgba(10,22,40,.82); border: 1px solid rgba(255,255,255,.14);
  box-shadow: 0 20px 45px rgba(0,0,0,.35); backdrop-filter: blur(14px);
}
.float-card .fc-icon { display: flex; color: #ff9a5c; }
.float-card b { display: block; font-size: 21px; letter-spacing: -.4px; }
.float-card span { display: block; color: #8fa2ba; font-size: 13px; margin-top: 2px; }
.fc1 { left: -10px; top: 128px; }
.fc2 { right: 16px; top: 472px; }
.fc3 { left: 32px; bottom: 92px; }

/* Problem */
.problem-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; margin-top: 78px; }
.problem-card { min-height: 292px; padding: 31px 30px; position: relative; overflow: hidden; }
.problem-card .num-badge { position: absolute; right: 25px; top: 25px; }
.problem-card .p-icon { margin-bottom: 34px; }
.problem-card h3 { font-size: 28px; margin-bottom: 13px; }
.problem-card p { color: #9daeC3; font-size: 17px; line-height: 1.55; }
.insight-bar {
  margin-top: 34px; display: flex; align-items: center; gap: 24px;
  padding: 28px 31px; border-radius: 24px;
  background: linear-gradient(100deg, rgba(255,122,24,.14), rgba(255,255,255,.035) 58%, rgba(45,212,191,.06));
  border: 1px solid rgba(255,154,92,.25);
}
.insight-bar .insight-icon { color: #ffb066; }
.insight-bar b { font-size: 14px; color: #ff9a5c; letter-spacing: 2px; text-transform: uppercase; }
.insight-bar p { font-size: 21px; line-height: 1.35; color: #e6edf5; margin-top: 5px; }
.insight-bar .target { margin-left: auto; display: flex; align-items: center; gap: 12px; color: #5eead4; font-size: 18px; font-weight: 600; white-space: nowrap; }

/* Solution */
.flow-grid { display: grid; grid-template-columns: 1fr 34px 1fr 34px 1fr 34px 1fr; gap: 16px; margin-top: 64px; }
.flow-card { padding: 30px 27px; min-height: 390px; position: relative; }
.flow-card .flow-num { color: #ff9a5c; font-size: 14px; font-weight: 700; letter-spacing: 2px; margin-bottom: 43px; }
.flow-card .icon-box { margin-bottom: 29px; }
.flow-card h3 { font-size: 26px; margin-bottom: 12px; }
.flow-card p { color: #9daeC3; font-size: 16px; line-height: 1.55; }
.flow-card .micro { margin-top: 20px; color: #ffb066; font-size: 14px; font-weight: 600; }
.flow-arrow { display: flex; align-items: center; justify-content: center; color: rgba(255,154,92,.55); }
.bottom-strip {
  display: flex; align-items: center; gap: 18px; margin-top: 34px;
  padding: 18px 25px; border-radius: 18px; border: 1px solid rgba(45,212,191,.2);
  background: rgba(45,212,191,.055); color: #b8e9e2; font-size: 18px;
}
.bottom-strip .icon { color: #5eead4; }
.bottom-strip b { color: #f8fafc; }
.problem-quote {
  display: flex; align-items: center; justify-content: space-between; gap: 30px;
  margin-top: 30px; padding: 27px 32px; border-radius: 23px;
  background: rgba(255,255,255,.035); border: 1px solid rgba(255,255,255,.085);
}
.problem-quote .q-text { font-size: 25px; line-height: 1.35; letter-spacing: -.4px; color: #dce6f1; }
.problem-quote .q-text b { color: #ffb066; font-weight: 600; }
.problem-quote .q-tags { display: flex; gap: 9px; flex-wrap: wrap; justify-content: flex-end; max-width: 560px; }
.problem-quote .q-tag { padding: 9px 12px; border-radius: 8px; background: rgba(45,212,191,.07); border: 1px solid rgba(45,212,191,.16); color: #a9e9df; font-size: 12px; white-space: nowrap; }
.dayline {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 13px; margin-top: 18px;
}
.day-item {
  display: flex; align-items: center; gap: 14px; padding: 15px 18px; border-radius: 15px;
  background: rgba(255,255,255,.035); border: 1px solid rgba(255,255,255,.075);
}
.day-item .d-icon { color: #ffb066; display: flex; }
.day-item b { display: block; font-size: 14px; }
.day-item span { display: block; color: #8fa3ba; font-size: 12px; margin-top: 2px; }
.request-flow {
  display: flex; align-items: center; gap: 13px; margin-top: 18px; padding: 16px 20px;
  border-radius: 15px; background: rgba(255,255,255,.03); border: 1px solid rgba(255,255,255,.075);
  color: #9fb0c5; font-size: 12.5px; overflow: hidden;
}
.request-flow .rf-label { color: #ffb066; font-size: 10px; font-weight: 700; letter-spacing: 1.6px; text-transform: uppercase; white-space: nowrap; }
.request-flow .rf-step { padding: 5px 8px; border-radius: 6px; background: rgba(255,255,255,.045); color: #dbe6f2; white-space: nowrap; }
.request-flow .rf-arrow { color: #63758f; }
.request-flow .rf-live { margin-left: auto; display: flex; align-items: center; gap: 6px; color: #86efac; white-space: nowrap; font-size: 11px; }
.request-flow .rf-live i { width: 6px; height: 6px; border-radius: 50%; background: #86efac; box-shadow: 0 0 10px #86efac; }
.level-summary {
  display: grid; grid-template-columns: 170px 170px 170px 1fr; gap: 12px; margin-top: 18px;
  padding: 17px 20px; border-radius: 18px; background: rgba(255,255,255,.03); border: 1px solid rgba(255,255,255,.075);
  align-items: center;
}
.level-summary .ls { display: flex; align-items: baseline; gap: 7px; }
.level-summary .ls b { font-size: 27px; letter-spacing: -1px; }
.level-summary .ls span { color: #8fa3ba; font-size: 12px; }
.level-summary p { color: #9fb0c5; font-size: 13px; line-height: 1.45; border-left: 1px solid rgba(255,255,255,.09); padding-left: 20px; }
.activity-strip {
  display: flex; align-items: center; gap: 16px; margin-top: 22px; padding: 18px 21px;
  border-radius: 16px; background: rgba(255,255,255,.035); border: 1px solid rgba(255,255,255,.075);
  color: #9fb0c5; font-size: 14px;
}
.activity-strip .a-icon { color: #ffb066; display: flex; }
.activity-strip b { color: #eef4fa; font-weight: 600; }
.activity-strip .a-plus { margin-left: auto; color: #ffb066; font-size: 13px; white-space: nowrap; font-weight: 600; }
.principles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 18px; }
.principle { padding: 15px 17px; border-radius: 14px; background: rgba(255,255,255,.035); border: 1px solid rgba(255,255,255,.075); }
.principle b { display: block; color: #e7eef7; font-size: 13px; margin-bottom: 4px; }
.principle span { display: block; color: #8fa3ba; font-size: 11.5px; line-height: 1.4; }
.deploy-steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-top: 23px; }
.deploy-step { padding: 15px 17px; border-radius: 15px; background: rgba(255,255,255,.035); border: 1px solid rgba(255,255,255,.075); }
.deploy-step .ds-num { color: #ffb066; font-family: Consolas, monospace; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
.deploy-step b { display: block; font-size: 14px; margin-top: 7px; }
.deploy-step span { display: block; color: #8fa3ba; font-size: 11.5px; margin-top: 3px; }
.success-panel {
  display: flex; align-items: center; gap: 22px; margin-top: 23px; padding: 19px 23px;
  border-radius: 17px; background: linear-gradient(100deg, rgba(255,122,24,.10), rgba(45,212,191,.06));
  border: 1px solid rgba(255,154,92,.19); color: #b9c8d9; font-size: 15px;
}
.success-panel .s-icon { color: #ffb066; display: flex; }
.success-panel b { color: #f8fafc; }
.success-panel .s-metrics { margin-left: auto; display: flex; gap: 8px; flex-wrap: wrap; }
.success-panel .s-metric { padding: 7px 10px; border-radius: 7px; background: rgba(255,255,255,.05); color: #cbd7e5; font-size: 11px; white-space: nowrap; }

/* Phones */
.phone-grid { display: grid; grid-template-columns: repeat(3, 380px); gap: 45px; justify-content: center; margin-top: 18px; }
.phone-wrap { text-align: center; }
.phone {
  width: 380px; height: 680px; border-radius: 44px; padding: 11px;
  background: linear-gradient(160deg, #2a3548, #111b2b 24%, #0b1321 100%);
  box-shadow: 0 35px 70px rgba(0,0,0,.38), 0 0 0 1px rgba(255,255,255,.08);
  position: relative;
}
.phone:before {
  content: ''; position: absolute; left: 50%; top: 17px; transform: translateX(-50%);
  width: 92px; height: 7px; border-radius: 99px; background: #050b13; z-index: 4;
}
.phone-screen {
  width: 100%; height: 100%; border-radius: 34px; overflow: hidden;
  background: #0e1624; border: 1px solid rgba(255,255,255,.06);
  display: flex; flex-direction: column;
}
.tg-head {
  display: flex; align-items: center; gap: 11px; padding: 27px 17px 13px;
  background: #172235; border-bottom: 1px solid rgba(255,255,255,.06);
}
.tg-head img { width: 35px; height: 35px; border-radius: 50%; object-fit: cover; }
.tg-head b { display: block; font-size: 14px; line-height: 1.2; }
.tg-head span { display: block; color: #8294aa; font-size: 10px; margin-top: 2px; }
.tg-head .more { margin-left: auto; color: #8fa3ba; font-size: 19px; letter-spacing: 1px; }
.chat { padding: 14px 13px; flex: 1; display: flex; flex-direction: column; gap: 10px; }
.bubble {
  max-width: 91%; padding: 10px 12px; border-radius: 15px 15px 15px 5px;
  background: #1c2a3c; color: #e7eef7; font-size: 12.5px; line-height: 1.42;
  align-self: flex-start; box-shadow: 0 4px 13px rgba(0,0,0,.12);
}
.bubble.user {
  align-self: flex-end; border-radius: 15px 15px 5px 15px;
  background: linear-gradient(135deg, #2b5770, #23445c); color: #f1f8fb;
}
.bubble .b-title { font-weight: 700; color: #ffb066; display: block; margin-bottom: 5px; font-size: 13px; }
.bubble .b-muted { color: #9aacc1; }
.bubble .b-big { font-size: 24px; font-weight: 700; color: #fff; letter-spacing: -.5px; }
.bubble .b-row { display: flex; justify-content: space-between; gap: 10px; color: #c4d1e0; }
.bubble .b-row b { color: #fff; }
.bubble .b-ok { color: #6ee7b7; }
.bubble .b-warn { color: #ffb066; }
.tg-buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; margin-top: 8px; }
.tg-btn {
  padding: 8px 6px; border-radius: 9px; text-align: center; font-size: 11.5px;
  background: rgba(45,212,191,.12); border: 1px solid rgba(45,212,191,.25); color: #8cf0e2;
}
.tg-input {
  margin: 0 12px 12px; padding: 9px 12px; border-radius: 99px;
  border: 1px solid rgba(255,255,255,.08); color: #6f8299; font-size: 11px;
  display: flex; align-items: center; justify-content: space-between;
}
.phone-caption { margin-top: 19px; }
.phone-caption b { display: block; font-size: 19px; letter-spacing: -.3px; }
.phone-caption span { display: block; margin-top: 5px; color: #8fa2ba; font-size: 14px; }
.example-note { text-align: right; color: #6e8199; font-size: 12px; margin-top: 7px; letter-spacing: .4px; }
.criteria { margin-top: 7px; display: grid; gap: 7px; }
.criteria .cr { display: grid; grid-template-columns: 1fr 42px; gap: 8px; align-items: center; }
.criteria .cr span { font-size: 10.5px; color: #b9c8d9; }
.criteria .cr b { font-size: 11px; color: #f6d29f; text-align: right; }
.criteria .bar { grid-column: 1 / -1; height: 4px; border-radius: 99px; background: rgba(255,255,255,.09); overflow: hidden; margin-top: -3px; }
.criteria .bar i { display: block; height: 100%; border-radius: 99px; background: linear-gradient(90deg, #ff7a18, #ffc266); }

/* Features */
.feature-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 19px; margin-top: 48px; }
.feature-card { min-height: 278px; padding: 27px 24px; }
.feature-card .icon-box { width: 47px; height: 47px; border-radius: 14px; margin-bottom: 21px; }
.feature-card .cmd { display: inline-block; color: #ffb066; font-family: Consolas, 'Segoe UI', sans-serif; font-size: 13px; font-weight: 700; letter-spacing: .2px; margin-bottom: 8px; }
.feature-card h3 { font-size: 20px; margin-bottom: 8px; }
.feature-card p { color: #93a5bb; font-size: 14.5px; line-height: 1.45; }
.feature-card .tag { display: inline-block; margin-top: 15px; padding: 4px 8px; border-radius: 6px; background: rgba(255,122,24,.1); color: #ffb066; font-size: 10px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; }

/* Architecture */
.arch-board { margin-top: 35px; display: grid; grid-template-columns: 1fr 74px 1.12fr 74px 1fr; align-items: center; }
.arch-col { display: flex; flex-direction: column; gap: 14px; }
.arch-col .col-label { color: #6f8299; font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 2px; }
.node {
  padding: 17px 18px; border-radius: 17px; background: rgba(255,255,255,.045);
  border: 1px solid rgba(255,255,255,.10); display: flex; align-items: center; gap: 13px;
  min-height: 72px;
}
.node .node-icon { color: #ff9a5c; display: flex; }
.node b { display: block; font-size: 16px; letter-spacing: -.2px; }
.node span { display: block; color: #8699b0; font-size: 12px; line-height: 1.35; margin-top: 3px; }
.node.accent { background: rgba(255,122,24,.09); border-color: rgba(255,122,24,.25); }
.node.accent .node-icon { color: #ffb066; }
.node.teal { background: rgba(45,212,191,.075); border-color: rgba(45,212,191,.22); }
.node.teal .node-icon { color: #5eead4; }
.node.violet { background: rgba(139,92,246,.075); border-color: rgba(139,92,246,.22); }
.node.violet .node-icon { color: #c4b5fd; }
.arch-arrow { display: flex; align-items: center; justify-content: center; color: rgba(255,154,92,.45); font-size: 28px; }
.arch-bottom {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 18px;
  padding-top: 18px; border-top: 1px dashed rgba(255,255,255,.12);
}
.arch-bottom .node { min-height: 62px; padding: 12px 15px; }
.arch-notes { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 19px; }
.arch-note { padding: 8px 12px; border-radius: 9px; background: rgba(255,255,255,.045); border: 1px solid rgba(255,255,255,.08); color: #9fb0c5; font-size: 12px; }
.arch-note b { color: #e3ebf4; font-weight: 600; }

/* Level */
.level-layout { display: grid; grid-template-columns: 1.04fr .96fr; gap: 27px; margin-top: 32px; }
.level-card { padding: 28px 30px; }
.level-card .card-title, .formula-card .card-title { display: flex; align-items: baseline; justify-content: space-between; gap: 20px; margin-bottom: 21px; }
.level-card .card-title b { font-size: 19px; }
.level-card .card-title span, .formula-card .card-title span { color: #7f91aa; font-size: 13px; white-space: nowrap; }
.level-row { display: grid; grid-template-columns: 55px 1fr 40px; gap: 14px; align-items: center; margin-bottom: 17px; }
.level-row .lv { font-size: 16px; font-weight: 700; color: #ffb066; }
.level-row .track { height: 14px; border-radius: 99px; background: rgba(255,255,255,.07); overflow: hidden; }
.level-row .track i { display: block; height: 100%; border-radius: 99px; background: linear-gradient(90deg, #ff7a18, #ffc266); box-shadow: 0 0 18px rgba(255,122,24,.25); }
.level-row .cnt { text-align: right; font-size: 14px; color: #cbd7e5; }
.formula-card { padding: 27px 29px; }
.formula {
  padding: 19px 21px; border-radius: 16px; background: rgba(255,122,24,.08);
  border: 1px solid rgba(255,122,24,.22); color: #ffd0a6;
  font-family: Consolas, 'Segoe UI', monospace; font-size: 18px; line-height: 1.55;
}
.formula b { color: #fff; }
.weight-row { display: flex; gap: 8px; margin-top: 19px; }
.weight {
  flex: 1; text-align: center; padding: 10px 4px; border-radius: 10px;
  background: rgba(255,255,255,.045); border: 1px solid rgba(255,255,255,.08);
}
.weight b { display: block; color: #fff; font-size: 19px; }
.weight span { display: block; color: #8498b0; font-size: 10px; margin-top: 2px; }
.thresholds { display: grid; grid-template-columns: repeat(6, 1fr); gap: 7px; margin-top: 18px; }
.th { padding: 10px 5px; border-radius: 9px; background: rgba(45,212,191,.07); border: 1px solid rgba(45,212,191,.16); text-align: center; }
.th b { display: block; font-size: 13px; color: #8cf0e2; }
.th span { display: block; font-size: 10px; color: #8fa3ba; margin-top: 3px; }
.level-callouts { display: grid; grid-template-columns: 1fr 1fr; gap: 17px; margin-top: 20px; }
.callout { padding: 17px 19px; border-radius: 16px; display: flex; gap: 12px; align-items: flex-start; background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); }
.callout .icon { color: #ffb066; margin-top: 2px; }
.callout b { font-size: 14px; color: #eef4fa; display: block; margin-bottom: 4px; }
.callout span { font-size: 12.5px; line-height: 1.4; color: #8fa3ba; display: block; }

/* Habit */
.habit-layout { display: grid; grid-template-columns: .9fr 1.1fr; gap: 29px; margin-top: 34px; }
.streak-card { padding: 31px; position: relative; overflow: hidden; min-height: 590px; }
.streak-card:after { content: ''; position: absolute; width: 430px; height: 430px; right: -130px; bottom: -180px; border-radius: 50%; background: radial-gradient(circle, rgba(255,122,24,.18), transparent 66%); }
.streak-top { display: flex; align-items: center; gap: 18px; color: #ffb066; }
.streak-top .big-flame { width: 78px; height: 78px; border-radius: 23px; background: rgba(255,122,24,.13); border: 1px solid rgba(255,122,24,.26); display: flex; align-items: center; justify-content: center; }
.streak-top span { color: #94a7bd; font-size: 13px; letter-spacing: 1.8px; text-transform: uppercase; }
.streak-number { margin-top: 24px; font-size: 106px; line-height: .9; letter-spacing: -5px; font-weight: 700; }
.streak-number small { font-size: 28px; letter-spacing: -.8px; color: #ffb066; font-weight: 600; }
.streak-sub { margin-top: 10px; color: #9aacc1; font-size: 17px; }
.streak-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 31px; }
.streak-stat { padding: 15px 16px; border-radius: 14px; background: rgba(255,255,255,.045); border: 1px solid rgba(255,255,255,.08); }
.streak-stat b { display: block; font-size: 25px; color: #fff; }
.streak-stat span { display: block; color: #8fa3ba; font-size: 12px; margin-top: 3px; }
.week-dots { display: flex; gap: 9px; margin-top: 24px; }
.week-dots .wd { flex: 1; text-align: center; }
.week-dots .dot { height: 38px; border-radius: 10px; background: rgba(255,255,255,.055); border: 1px solid rgba(255,255,255,.08); }
.week-dots .dot.on { background: linear-gradient(180deg, #ff9a5c, #ff6a1a); border-color: transparent; box-shadow: 0 0 18px rgba(255,122,24,.22); }
.week-dots span { display: block; font-size: 10px; color: #71849c; margin-top: 6px; }
.reminder-list { display: flex; flex-direction: column; gap: 12px; }
.reminder-item { display: flex; gap: 15px; align-items: flex-start; padding: 18px 20px; border-radius: 17px; background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); }
.reminder-item .r-icon { width: 40px; height: 40px; border-radius: 12px; display: flex; align-items: center; justify-content: center; background: rgba(255,122,24,.10); color: #ffb066; flex: none; }
.reminder-item .r-time { color: #ffb066; font-family: Consolas, monospace; font-size: 12px; font-weight: 700; white-space: nowrap; padding-top: 2px; }
.reminder-item b { display: block; font-size: 16px; margin-bottom: 4px; }
.reminder-item span { display: block; color: #8fa3ba; font-size: 13.5px; line-height: 1.4; }
.habit-quote { margin-top: 19px; padding: 17px 20px; border-radius: 16px; color: #b8e9e2; background: rgba(45,212,191,.065); border: 1px solid rgba(45,212,191,.18); font-size: 16px; }

/* Quality */
.metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 30px; }
.metric { padding: 18px 20px; border-radius: 18px; background: rgba(255,255,255,.045); border: 1px solid rgba(255,255,255,.09); }
.metric b { display: block; font-size: 40px; letter-spacing: -1.8px; line-height: 1; }
.metric span { display: block; color: #8fa3ba; font-size: 13px; margin-top: 7px; }
.metric .u { font-size: 19px; color: #ffb066; letter-spacing: 0; }
.quality-layout { display: grid; grid-template-columns: 1.06fr .94fr; gap: 20px; margin-top: 19px; }
.terminal { padding: 22px 24px; border-radius: 20px; background: #050b14; border: 1px solid rgba(255,255,255,.11); box-shadow: inset 0 1px 0 rgba(255,255,255,.04); }
.term-bar { display: flex; gap: 7px; margin-bottom: 17px; }
.term-bar i { width: 9px; height: 9px; border-radius: 50%; background: #ff6b5e; }
.term-bar i:nth-child(2) { background: #ffc266; }
.term-bar i:nth-child(3) { background: #5eead4; }
.term { font-family: Consolas, 'Cascadia Code', monospace; font-size: 13.5px; line-height: 1.7; color: #b8c7d9; white-space: pre-wrap; }
.term .p { color: #5eead4; }
.term .ok { color: #86efac; }
.term .dim { color: #64758d; }
.quality-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.quality-card { padding: 18px 17px; border-radius: 16px; background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); }
.quality-card .icon { color: #5eead4; margin-bottom: 12px; }
.quality-card b { display: block; font-size: 15px; margin-bottom: 5px; }
.quality-card span { display: block; color: #8fa3ba; font-size: 12.5px; line-height: 1.4; }

/* Deploy */
.deploy-layout { display: grid; grid-template-columns: .82fr 1.18fr; gap: 30px; margin-top: 34px; }
.cost-card { padding: 30px; min-height: 520px; position: relative; overflow: hidden; }
.cost-card:after { content: ''; position: absolute; width: 390px; height: 390px; left: -150px; bottom: -170px; border-radius: 50%; background: radial-gradient(circle, rgba(45,212,191,.15), transparent 68%); }
.cost-big { font-size: 132px; line-height: .82; letter-spacing: -7px; font-weight: 700; color: #fff; margin-top: 37px; }
.cost-big span { font-size: 40px; letter-spacing: -1px; color: #5eead4; }
.cost-label { margin-top: 13px; color: #8fa3ba; font-size: 16px; }
.cost-tags { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 26px; }
.cost-tag { padding: 8px 11px; border-radius: 8px; color: #b8e9e2; background: rgba(45,212,191,.075); border: 1px solid rgba(45,212,191,.18); font-size: 12px; font-weight: 600; }
.cost-list { margin-top: 26px; display: flex; flex-direction: column; gap: 11px; }
.cost-item { display: flex; align-items: center; gap: 11px; color: #b7c5d6; font-size: 14.5px; }
.cost-item .icon { color: #5eead4; }
.provider-list { display: flex; flex-direction: column; gap: 13px; }
.provider { display: flex; align-items: center; gap: 17px; padding: 17px 20px; border-radius: 18px; background: rgba(255,255,255,.045); border: 1px solid rgba(255,255,255,.09); }
.provider .p-logo { width: 48px; height: 48px; border-radius: 14px; display: flex; align-items: center; justify-content: center; font-size: 22px; font-weight: 700; flex: none; }
.provider .p-logo.w { background: rgba(255,122,24,.13); color: #ffb066; border: 1px solid rgba(255,122,24,.24); }
.provider .p-logo.s { background: rgba(74,222,128,.10); color: #86efac; border: 1px solid rgba(74,222,128,.22); }
.provider .p-logo.u { background: rgba(139,92,246,.12); color: #c4b5fd; border: 1px solid rgba(139,92,246,.24); }
.provider b { display: block; font-size: 17px; }
.provider span { display: block; color: #8fa3ba; font-size: 12.5px; margin-top: 3px; }
.provider .p-status { margin-left: auto; color: #86efac; font-size: 11px; font-weight: 700; letter-spacing: .8px; white-space: nowrap; }
.command-bar { margin-top: 21px; display: flex; align-items: center; gap: 16px; padding: 18px 21px; border-radius: 16px; background: #050b14; border: 1px solid rgba(255,255,255,.10); }
.command-bar code { font-family: Consolas, monospace; color: #5eead4; font-size: 16px; }
.command-bar span { color: #7e91a9; font-size: 13px; }
.deploy-note { margin-top: 18px; color: #6f8299; font-size: 12px; }

/* Roadmap */
.roadmap-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 22px; margin-top: 60px; position: relative; }
.roadmap-grid:before { content: ''; position: absolute; left: 5%; right: 5%; top: 25px; height: 1px; background: linear-gradient(90deg, rgba(255,122,24,.5), rgba(45,212,191,.4)); }
.phase { position: relative; padding-top: 61px; }
.phase .phase-dot { position: absolute; top: 17px; left: 0; width: 17px; height: 17px; border-radius: 50%; background: #ff7a18; box-shadow: 0 0 0 7px rgba(255,122,24,.12), 0 0 22px rgba(255,122,24,.4); }
.phase:nth-child(2) .phase-dot { background: #ffc266; box-shadow: 0 0 0 7px rgba(255,194,102,.10), 0 0 22px rgba(255,194,102,.3); }
.phase:nth-child(3) .phase-dot { background: #2dd4bf; box-shadow: 0 0 0 7px rgba(45,212,191,.10), 0 0 22px rgba(45,212,191,.3); }
.phase-card { padding: 27px 27px; min-height: 410px; }
.phase-card .phase-time { color: #ffb066; font-size: 12px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 12px; }
.phase-card h3 { font-size: 27px; margin-bottom: 22px; }
.phase-list { display: flex; flex-direction: column; gap: 14px; }
.phase-item { display: flex; gap: 10px; align-items: flex-start; color: #a6b6ca; font-size: 14.5px; line-height: 1.4; }
.phase-item .icon { color: #5eead4; margin-top: 1px; }
.phase-item b { color: #e4edf6; font-weight: 600; }
.metric-strip { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 23px; }
.metric-chip { padding: 10px 14px; border-radius: 9px; background: rgba(255,255,255,.045); border: 1px solid rgba(255,255,255,.08); color: #9fb0c5; font-size: 12.5px; }
.metric-chip b { color: #f8fafc; font-weight: 600; }

/* Final */
.final-grid { display: grid; grid-template-columns: 1.16fr .84fr; gap: 40px; align-items: center; height: 100%; }
.final-copy h2 { font-size: 78px; }
.final-copy .lead { margin-top: 27px; width: 760px; font-size: 24px; }
.final-checks { display: flex; gap: 11px; flex-wrap: wrap; margin-top: 34px; }
.final-check { display: flex; align-items: center; gap: 8px; padding: 10px 13px; border-radius: 9px; background: rgba(45,212,191,.065); border: 1px solid rgba(45,212,191,.18); color: #b8e9e2; font-size: 13px; }
.final-check .icon { color: #5eead4; }
.final-links { margin-top: 43px; display: flex; flex-direction: column; gap: 11px; color: #8fa3ba; font-size: 16px; }
.final-links b { color: #f8fafc; font-weight: 600; }
.qr-card { justify-self: end; width: 480px; padding: 23px; border-radius: 30px; background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.13); box-shadow: 0 30px 80px rgba(0,0,0,.3); text-align: center; }
.qr-card img.qr { width: 310px; height: 310px; border-radius: 18px; background: #fff; padding: 10px; }
.qr-card .qr-brand { display: flex; align-items: center; justify-content: center; gap: 11px; margin-bottom: 15px; }
.qr-card .qr-brand img { width: 39px; height: 39px; border-radius: 12px; }
.qr-card .qr-brand b { font-size: 18px; }
.qr-card .qr-handle { margin-top: 13px; color: #ffb066; font-weight: 700; font-size: 20px; }
.qr-card .qr-sub { color: #8fa3ba; font-size: 13px; margin-top: 5px; }
.banner-strip { position: absolute; left: 84px; right: 84px; bottom: 80px; height: 4px; border-radius: 99px; background: linear-gradient(90deg, #ff7a18, #ffc266 45%, #2dd4bf); opacity: .6; }
"""


def footer(number: int, section: str) -> str:
    return f"""
    <div class="footer">
      <div class="f-brand"><img src="file:///{AVATAR.as_posix()}" alt=""><b>LinguaFlame</b><span>· AI ENGLISH COACH</span></div>
      <div>{html.escape(section)}</div>
      <div><span class="f-num">{number:02d}</span> / {TOTAL:02d}</div>
    </div>
    """


def page(body: str, number: int, section: str) -> str:
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=1920, initial-scale=1">
<title>LinguaFlame — {number:02d}</title>
<style>{CSS}</style>
</head>
<body>
<div class="slide">
  <div class="content">{body}</div>
  {footer(number, section)}
</div>
</body>
</html>"""


def slide_01() -> str:
    return f"""
    <div class="hero-grid">
      <div class="hero-copy">
        <div class="brand-line">
          <img src="file:///{AVATAR.as_posix()}" alt="LinguaFlame">
          <span class="brand-name">LinguaFlame</span>
          <span class="brand-tag">AI ENGLISH COACH</span>
        </div>
        <div class="kicker"><span class="line"></span> ПРОДУКТ · 2026</div>
        <h1>Английский,<br>который <span class="gradient">не бросают.</span></h1>
        <p class="lead">AI-тренер в Telegram: определяет уровень, собирает ежедневную практику и возвращает к занятиям в нужный момент.</p>
        <div class="hero-pills">
          <span class="pill"><span class="dot"></span> 6 уровней CEFR</span>
          <span class="pill"><span class="dot"></span> 8 учебных сценариев</span>
          <span class="pill"><span class="dot"></span> 253 автотеста</span>
        </div>
        <div class="hero-meta"><b>Работающий продукт</b> · Python 3.12 / aiogram 3 · деплой за <b>0 ₽</b></div>
      </div>
      <div class="hero-visual">
        <div class="halo"></div>
        <div class="ring"></div><div class="ring r2"></div>
        <div class="logo-frame"><img src="file:///{AVATAR.as_posix()}" alt="LinguaFlame mascot"></div>
        <div class="float-card fc1">
          <div class="fc-icon">{icon("target", 27)}</div>
          <div><b>A1 → C2</b><span>диагностика за 50 вопросов</span></div>
        </div>
        <div class="float-card fc2">
          <div class="fc-icon">{icon("flame", 27)}</div>
          <div><b>Ежедневный цикл</b><span>5–15 минут в Telegram</span></div>
        </div>
        <div class="float-card fc3">
          <div class="fc-icon">{icon("shield", 27)}</div>
          <div><b>AI с fallback</b><span>NVIDIA NIM → DeepSeek</span></div>
        </div>
      </div>
    </div>
    """


def slide_02() -> str:
    cards = [
        (
            "01",
            "eye",
            "Не видно, где пробел",
            "Уровень определяют на глаз: непонятно, что именно подтягивать — грамматику, словарь или беглость.",
        ),
        (
            "02",
            "refresh",
            "Нет ежедневного цикла",
            "Длинные уроки и приложения не встраиваются в день. Мотивация падает раньше, чем появляется результат.",
        ),
        (
            "03",
            "clock",
            "Обратная связь слишком поздно",
            "Эссе и устную речь проверяют через дни. Ошибка повторяется, а уверенность не растёт.",
        ),
    ]
    cards_html = "".join(
        f"""<div class="card problem-card">
          <span class="num-badge">{num}</span>
          <div class="p-icon icon-box">{icon(icon_name, 27)}</div>
          <h3>{title}</h3><p>{text}</p>
        </div>"""
        for num, icon_name, title, text in cards
    )
    return f"""
    <div class="slide-head">
      <div>
        <div class="kicker"><span class="line"></span> 01 / ПРОБЛЕМА</div>
        <h2>Мотивация заканчивается<br>раньше, чем прогресс.</h2>
      </div>
      <div class="slide-note">Почему взрослые бросают английский,<br>даже когда «всё понимают»</div>
    </div>
    <div class="problem-grid">{cards_html}</div>
    <div class="insight-bar">
      <div class="insight-icon">{icon("sparkles", 29)}</div>
      <div><b>Инсайт</b><p>Нужен не ещё один курс, а короткий цикл: <b>диагностика → действие → обратная связь → возврат завтра.</b></p></div>
      <div class="target">{icon("arrow", 22)} LinguaFlame</div>
    </div>
    <div class="problem-quote">
      <div class="q-text">«Взрослому ученику нужно <b>не больше контента, а меньше трения</b>.»</div>
      <div class="q-tags"><span class="q-tag">5–15 минут</span><span class="q-tag">фидбек сразу</span><span class="q-tag">один интерфейс</span></div>
    </div>
    """


def slide_03() -> str:
    items = [
        (
            "01",
            "target",
            "Диагностика",
            "50 вопросов по грамматике и словарю. Уровень A1–C2 с учётом сложности и скорости.",
            "честная стартовая точка",
        ),
        (
            "02",
            "book",
            "Практика",
            "Слова, грамматика, квиз, эссе и свободный чат — в одном Telegram-интерфейсе.",
            "5–15 минут в день",
        ),
        (
            "03",
            "sparkles",
            "Обратная связь",
            "AI объясняет ошибки, проверяет эссе по критериям IELTS и мягко исправляет речь.",
            "сразу, а не через неделю",
        ),
        (
            "04",
            "flame",
            "Привычка",
            "Streak, напоминания и кнопка «5 слов» возвращают к занятию без чувства вины.",
            "цикл, а не разовый урок",
        ),
    ]
    cards_list = []
    for i, item in enumerate(items):
        num, icon_name, title, text, micro = item
        cards_list.append(
            f"""<div class="card flow-card">
              <div class="flow-num">{num} / 04</div>
              <div class="icon-box">{icon(icon_name, 28)}</div>
              <h3>{title}</h3><p>{text}</p><div class="micro">{micro}</div>
            </div>"""
        )
        if i < len(items) - 1:
            cards_list.append(f'<div class="flow-arrow">{icon("arrow", 28)}</div>')
    return f"""
    <div class="slide-head">
      <div>
        <div class="kicker"><span class="line"></span> 02 / РЕШЕНИЕ</div>
        <h2>Один бот. Четыре шага.<br>Каждый день.</h2>
      </div>
      <div class="slide-note">LinguaFlame встраивается в Telegram —<br>без установки и нового аккаунта</div>
    </div>
    <div class="flow-grid">{"".join(cards_list)}</div>
    <div class="bottom-strip">
      {icon("message", 24)}
      <span><b>Один интерфейс вместо пяти сервисов:</b> уровень, урок, проверка эссе, разговор и статистика — в переписке.</span>
    </div>
    <div class="dayline">
      <div class="day-item"><div class="d-icon">{icon("sun", 21)}</div><div><b>Утро · 5 слов</b><span>быстрый старт без домашнего задания</span></div></div>
      <div class="day-item"><div class="d-icon">{icon("book", 21)}</div><div><b>День · урок</b><span>объяснение и практика по шагам</span></div></div>
      <div class="day-item"><div class="d-icon">{icon("moon", 21)}</div><div><b>Вечер · эссе</b><span>фидбек по IELTS, пока текст свежий</span></div></div>
    </div>
    """


def phone_header() -> str:
    return f"""<div class="tg-head">
      <img src="file:///{AVATAR.as_posix()}" alt="">
      <div><b>LinguaFlame</b><span>bot · онлайн</span></div>
      <div class="more">⋯</div>
    </div>"""


def slide_04() -> str:
    phone1 = f"""
    <div class="phone-wrap">
      <div class="phone"><div class="phone-screen">
        {phone_header()}
        <div class="chat">
          <div class="bubble user">/level_detector</div>
          <div class="bubble">
            <span class="b-title">🎯 Твой уровень: B2</span>
            Правильных ответов: <b>39 из 50</b> (78%)<br>
            Среднее время: <b>8.4 с</b>
            <div style="height:8px"></div>
            <div class="b-row"><span>Грамматика</span><b class="b-ok">82%</b></div>
            <div class="b-row"><span>Словарь</span><b class="b-ok">74%</b></div>
          </div>
          <div class="bubble">
            💪 Сильная сторона: <b>грамматика</b>.<br>
            📌 Стоит подтянуть: <b>словарь</b>.
          </div>
          <div class="bubble b-muted" style="font-size:11.5px">Уровень обновлён. Продолжай заниматься: /daily_grammar и /daily_vocabulary.</div>
        </div>
        <div class="tg-input"><span>Написать сообщение…</span><span>{icon("send", 14)}</span></div>
      </div></div>
      <div class="phone-caption"><b>CEFR-диагностика</b><span>50 вопросов · 6 уровней · вес + скорость</span></div>
    </div>"""
    phone2 = f"""
    <div class="phone-wrap">
      <div class="phone"><div class="phone-screen">
        {phone_header()}
        <div class="chat">
          <div class="bubble user">/daily_grammar</div>
          <div class="bubble">
            <span class="b-title">📘 Present Perfect · шаг 2 из 6</span>
            Используем, когда важен <b>результат сейчас</b>:<br>
            «I have lost my keys» — ключи потеряны, я не могу войти.
            <div style="height:7px"></div>
            <span class="b-muted">Сравни: «I lost my keys yesterday» — просто факт в прошлом.</span>
          </div>
          <div class="bubble user">А в чём разница с Past Simple?</div>
          <div class="bubble">
            Past Simple — действие завершено в прошлом.<br>
            Present Perfect — прошлое действие связано с настоящим.
            <div class="tg-buttons"><div class="tg-btn">▶️ Дальше</div><div class="tg-btn">💬 Спросить</div></div>
          </div>
        </div>
        <div class="tg-input"><span>Написать сообщение…</span><span>{icon("send", 14)}</span></div>
      </div></div>
      <div class="phone-caption"><b>Урок по шагам</b><span>объяснение → примеры → упражнения → мини-тест</span></div>
    </div>"""
    phone3 = f"""
    <div class="phone-wrap">
      <div class="phone"><div class="phone-screen">
        {phone_header()}
        <div class="chat">
          <div class="bubble user">/essay_checker</div>
          <div class="bubble">
            <span class="b-title">📝 Оценка: 6.5 / 9</span>
            <div class="criteria">
              <div class="cr"><span>Task Response</span><b>7.0</b><div class="bar"><i style="width:78%"></i></div></div>
              <div class="cr"><span>Coherence</span><b>6.5</b><div class="bar"><i style="width:72%"></i></div></div>
              <div class="cr"><span>Lexical Resource</span><b>6.5</b><div class="bar"><i style="width:72%"></i></div></div>
              <div class="cr"><span>Grammar</span><b>6.0</b><div class="bar"><i style="width:66%"></i></div></div>
            </div>
          </div>
          <div class="bubble">
            <span class="b-title">⚠️ Слабое место</span>
            «Nowadays people <b>thinks</b>…» → <b>people think</b><br>
            <span class="b-muted">Согласование подлежащего и глагола.</span>
          </div>
          <div class="bubble b-muted" style="font-size:11px">🎯 Что улучшить: Grammatical Range — проверяй времена и порядок слов.</div>
        </div>
        <div class="tg-input"><span>Написать сообщение…</span><span>{icon("send", 14)}</span></div>
      </div></div>
      <div class="phone-caption"><b>IELTS-эссе</b><span>общий band · 4 критерия · разбор ошибок</span></div>
    </div>"""
    return f"""
    <div class="slide-head">
      <div>
        <div class="kicker"><span class="line"></span> 03 / ПРОДУКТ</div>
        <h2>Сценарии, которые<br>можно потрогать.</h2>
      </div>
      <div class="slide-note">Не «магия AI», а понятный путь:<br>увидеть уровень → сделать → получить фидбек</div>
    </div>
    <div class="phone-grid">{phone1}{phone2}{phone3}</div>
    <div class="example-note">Примеры интерфейса по реальным сценариям бота</div>
    """


def slide_05() -> str:
    features = [
        (
            "target",
            "/level_detector",
            "Определение уровня",
            "50 вопросов, A1–C2, взвешенный балл и бонус за скорость.",
            "CORE",
        ),
        (
            "book",
            "/daily_grammar",
            "Урок грамматики",
            "Объяснение, примеры, упражнения и мини-тест в конце.",
            "AI",
        ),
        (
            "layers",
            "/daily_vocabulary",
            "20 слов дня",
            "Транскрипция и перевод на родной язык; без повторов 7 дней.",
            "AI",
        ),
        (
            "chat",
            "/quiz",
            "Квиз A/B/C",
            "Вопросы по одному, обратная связь и финальный счёт.",
            "CORE",
        ),
        (
            "file",
            "/essay_checker",
            "Проверка эссе",
            "IELTS Task 2: band, 4 критерия и слабые места.",
            "AI",
        ),
        (
            "message",
            "/free_chat",
            "Свободный разговор",
            "Чат на любом языке; ошибки в английском мягко исправляются.",
            "AI",
        ),
        (
            "flame",
            "/stats",
            "Серия и рекорд",
            "Текущий streak, личный рекорд и активность за 7 дней.",
            "HABIT",
        ),
        (
            "graduation",
            "/start",
            "Онбординг",
            "Язык объяснений, часовой пояс и профиль пользователя.",
            "CORE",
        ),
    ]
    cards = "".join(
        f"""<div class="card feature-card">
          <div class="icon-box {("teal" if tag == "AI" else "violet" if tag == "HABIT" else "")}">{icon(icon_name, 25)}</div>
          <span class="cmd">{cmd}</span>
          <h3>{title}</h3><p>{text}</p>
          <span class="tag">{tag}</span>
        </div>"""
        for icon_name, cmd, title, text, tag in features
    )
    return f"""
    <div class="slide-head">
      <div>
        <div class="kicker"><span class="line"></span> 04 / ПРОДУКТ</div>
        <h2>8 сценариев —<br>полный учебный цикл.</h2>
      </div>
      <div class="slide-note">От первого /start до привычки:<br>каждый сценарий связан с прогрессом</div>
    </div>
    <div class="feature-grid">{cards}</div>
    <div class="bottom-strip" style="margin-top:19px">
      {icon("zap", 23)}
      <span><b>AI не ради AI:</b> он включается там, где нужен контекст — урок, эссе, слова и живой разговор.</span>
    </div>
    """


def slide_06() -> str:
    return f"""
    <div class="slide-head">
      <div>
        <div class="kicker"><span class="line"></span> 05 / АРХИТЕКТУРА</div>
        <h2>Async-ядро, которое<br>не падает от одного сбоя.</h2>
      </div>
      <div class="slide-note">Telegram → сервисы → данные + AI<br>каждый слой изолирован</div>
    </div>
    <div class="arch-board">
      <div class="arch-col">
        <div class="col-label">Клиент</div>
        <div class="node accent"><div class="node-icon">{icon("users", 25)}</div><div><b>Telegram</b><span>пользователи · RU / EN</span></div></div>
        <div class="arch-arrow">↓</div>
        <div class="node"><div class="node-icon">{icon("message", 25)}</div><div><b>aiogram 3</b><span>routers · FSM · middleware</span></div></div>
      </div>
      <div class="arch-arrow">→</div>
      <div class="arch-col">
        <div class="col-label">Бизнес-логика</div>
        <div class="node accent"><div class="node-icon">{icon("layers", 25)}</div><div><b>Services</b><span>quiz · grammar · essay · level · streak</span></div></div>
        <div class="node"><div class="node-icon">{icon("database", 25)}</div><div><b>Repositories</b><span>SQLAlchemy 2 async</span></div></div>
        <div class="node teal"><div class="node-icon">{icon("database", 25)}</div><div><b>PostgreSQL / SQLite</b><span>4 миграции Alembic</span></div></div>
      </div>
      <div class="arch-arrow">→</div>
      <div class="arch-col">
        <div class="col-label">AI sidecar</div>
        <div class="node violet"><div class="node-icon">{icon("cpu", 25)}</div><div><b>AI Client</b><span>JSON schema · retries · timeout 180s</span></div></div>
        <div class="node"><div class="node-icon">{icon("zap", 25)}</div><div><b>NVIDIA NIM</b><span>Nemotron 3 Ultra 550B</span></div></div>
        <div class="node"><div class="node-icon">{icon("refresh", 25)}</div><div><b>DeepSeek V4.1 Flash</b><span>fallback после ошибки / 404</span></div></div>
      </div>
    </div>
    <div class="arch-bottom">
      <div class="node"><div class="node-icon">{icon("database", 22)}</div><div><b>Redis</b><span>FSM + APScheduler job store</span></div></div>
      <div class="node"><div class="node-icon">{icon("clock", 22)}</div><div><b>APScheduler</b><span>напоминания по часовому поясу</span></div></div>
      <div class="node"><div class="node-icon">{icon("wrench", 22)}</div><div><b>Bootstrap</b><span>миграции + банк вопросов при старте</span></div></div>
    </div>
    <div class="arch-notes">
      <span class="arch-note"><b>async end-to-end</b> · без блокирующих вызовов</span>
      <span class="arch-note"><b>prompt injection guard</b> · текст в &lt;user_text&gt;</span>
      <span class="arch-note"><b>graceful degradation</b> · Redis → память, AI → fallback</span>
      <span class="arch-note"><b>structured logs</b> · время, уровень, контекст</span>
    </div>
    <div class="request-flow">
      <span class="rf-label">Один запрос</span>
      <span class="rf-step">Telegram update</span><span class="rf-arrow">→</span>
      <span class="rf-step">middleware</span><span class="rf-arrow">→</span>
      <span class="rf-step">router</span><span class="rf-arrow">→</span>
      <span class="rf-step">service</span><span class="rf-arrow">→</span>
      <span class="rf-step">repo / AI</span><span class="rf-arrow">→</span>
      <span class="rf-step">response</span>
      <span class="rf-live"><i></i> без блокировки event loop</span>
    </div>
    """


def slide_07() -> str:
    levels = [
        ("A1", 8, 80),
        ("A2", 8, 80),
        ("B1", 8, 80),
        ("B2", 8, 80),
        ("C1", 8, 80),
        ("C2", 10, 100),
    ]
    rows = "".join(
        f"""<div class="level-row">
          <div class="lv">{lv}</div>
          <div class="track"><i style="width:{pct}%"></i></div>
          <div class="cnt">{count}</div>
        </div>"""
        for lv, count, pct in levels
    )
    thresholds = [("A1", "0"), ("A2", "15"), ("B1", "30"), ("B2", "50"), ("C1", "70"), ("C2", "88")]
    ths = "".join(f'<div class="th"><b>{lv}</b><span>{val}%</span></div>' for lv, val in thresholds)
    weights = [("A1", "1"), ("A2", "2"), ("B1", "3"), ("B2", "4"), ("C1", "5"), ("C2", "6")]
    ws = "".join(f'<div class="weight"><b>{w}</b><span>{lv}</span></div>' for lv, w in weights)
    return f"""
    <div class="slide-head">
      <div>
        <div class="kicker"><span class="line"></span> 06 / АЛГОРИТМ</div>
        <h2>Уровень — это не просто<br>процент правильных.</h2>
      </div>
      <div class="slide-note">Сложные вопросы стоят дороже.<br>Скорость — бонус, а не главный критерий.</div>
    </div>
    <div class="level-layout">
      <div class="card level-card">
        <div class="card-title"><b>50 вопросов в тесте</b><span>180 в банке · 30 на уровень</span></div>
        {rows}
        <div style="margin-top:15px;color:#7f91aa;font-size:12.5px">Грамматика и словарь — по 4–5 вопросов на уровень.</div>
      </div>
      <div class="card formula-card">
        <div class="card-title"><b>Как считается балл</b><span>максимум 198</span></div>
        <div class="formula">балл = <b>вес(уровень)</b> × (1 + <b>0.10</b>)<br><span style="color:#8fa3ba;font-size:13px">бонус только за быстрый и верный ответ</span></div>
        <div class="weight-row">{ws}</div>
        <div class="card-title" style="margin-top:22px;margin-bottom:10px"><b>Пороги итогового %</b><span>CEFR</span></div>
        <div class="thresholds">{ths}</div>
        <div class="level-callouts">
          <div class="callout">{icon("zap", 20)}<div><b>+10% за скорость</b><span>B1+ быстрее 2 сек — угадывание; дольше 60 сек — без бонуса.</span></div></div>
          <div class="callout">{icon("shield", 20)}<div><b>Согласованность</b><span>60%+ на высоком уровне может поднять итог. Только вверх.</span></div></div>
        </div>
      </div>
    </div>
    <div class="level-summary">
      <div class="ls"><b>50</b><span>вопросов</span></div>
      <div class="ls"><b>198</b><span>макс. баллов</span></div>
      <div class="ls"><b>60%</b><span>порог согласованности</span></div>
      <p>Уровень обновляется только после завершения теста. Незавершённый тест можно продолжить с того же вопроса.</p>
    </div>
    """


def slide_08() -> str:
    reminders = [
        (
            "sun",
            "09:00",
            "Утренний старт",
            "Если сегодня ещё не было активности — короткое напоминание с кнопкой «5 слов».",
        ),
        (
            "moon",
            "20:00",
            "Вечерний огонёк",
            "Показывает текущую серию и оставляет один простой шаг до полуночи.",
        ),
        (
            "refresh",
            "пропуск",
            "«Где ты?»",
            "Мягко возвращает после пропуска, не обнуляя чувство прогресса.",
        ),
        (
            "calendar",
            "3 / 7 дней",
            "Долгое возвращение",
            "Дополнительные напоминания, потом пауза — без спама и давления.",
        ),
    ]
    rem_html = "".join(
        f"""<div class="reminder-item">
          <div class="r-icon">{icon(icon_name, 21)}</div>
          <div class="r-time">{time}</div>
          <div><b>{title}</b><span>{text}</span></div>
        </div>"""
        for icon_name, time, title, text in reminders
    )
    return f"""
    <div class="slide-head">
      <div>
        <div class="kicker"><span class="line"></span> 07 / RETENTION</div>
        <h2>Привычка — такая же фича,<br>как и урок.</h2>
      </div>
      <div class="slide-note">Цель — не идеальный урок,<br>а следующее действие</div>
    </div>
    <div class="habit-layout">
      <div class="card streak-card">
        <div class="streak-top"><div class="big-flame">{icon("flame", 43)}</div><span>Твой прогресс</span></div>
        <div class="streak-number">12 <small>дней</small></div>
        <div class="streak-sub">🔥 текущая серия — пример механики</div>
        <div class="streak-stats">
          <div class="streak-stat"><b>18</b><span>личный рекорд</span></div>
          <div class="streak-stat"><b>5</b><span>действий за неделю</span></div>
        </div>
        <div class="week-dots">
          <div class="wd"><div class="dot on"></div><span>Пн</span></div>
          <div class="wd"><div class="dot on"></div><span>Вт</span></div>
          <div class="wd"><div class="dot"></div><span>Ср</span></div>
          <div class="wd"><div class="dot on"></div><span>Чт</span></div>
          <div class="wd"><div class="dot on"></div><span>Пт</span></div>
          <div class="wd"><div class="dot"></div><span>Сб</span></div>
          <div class="wd"><div class="dot on"></div><span>Вс</span></div>
        </div>
      </div>
      <div>
        <div class="reminder-list">{rem_html}</div>
        <div class="habit-quote">{icon("message", 20)} <b>Максимум 2 сообщения в день.</b> Напоминания возвращают, а не превращаются в спам.</div>
      </div>
    </div>
    <div class="activity-strip">
      <div class="a-icon">{icon("flame", 21)}</div>
      <span><b>Действием считается:</b> квиз · урок · слова · эссе · свободный чат · тест уровня</span>
      <span class="a-plus">+1 день к серии</span>
    </div>
    """


def slide_09() -> str:
    return f"""
    <div class="slide-head">
      <div>
        <div class="kicker"><span class="line"></span> 08 / КАЧЕСТВО</div>
        <h2>Продукт, который<br>можно проверить.</h2>
      </div>
      <div class="slide-note">Не «на глаз»: тесты, линтер,<br>миграции и живой AI-запрос</div>
    </div>
    <div class="metrics-grid">
      <div class="metric"><b>253</b><span>автотеста · 1 opt-in live</span></div>
      <div class="metric"><b>74<span class="u">%</span></b><span>покрытие кода</span></div>
      <div class="metric"><b>180</b><span>вопросов в банке</span></div>
      <div class="metric"><b>6</b><span>уровней CEFR</span></div>
    </div>
    <div class="quality-layout">
      <div class="terminal">
        <div class="term-bar"><i></i><i></i><i></i></div>
        <div class="term"><span class="p">$</span> pytest -q
<span class="ok">253 passed, 1 skipped</span> in 21.35s

<span class="p">$</span> ruff check .
<span class="ok">All checks passed!</span>

<span class="p">$</span> ruff format --check .
<span class="ok">106 files already formatted</span>

<span class="dim"># live NVIDIA API проверен отдельным opt-in тестом</span>
<span class="dim"># fallback сработал после 404 основного модели</span></div>
      </div>
      <div class="quality-cards">
        <div class="quality-card">{icon("shield", 22)}<b>Live AI проверен</b><span>Реальный запрос к NVIDIA NIM, не только мок.</span></div>
        <div class="quality-card">{icon("refresh", 22)}<b>Fallback после 404</b><span>Пользователь не видит отказа основного провайдера.</span></div>
        <div class="quality-card">{icon("code", 22)}<b>JSON + retry</b><span>Схемы ответов, повторы и таймаут 180 секунд.</span></div>
        <div class="quality-card">{icon("lock", 22)}<b>Секреты в env</b><span>Токены и ключи не попадают в репозиторий.</span></div>
      </div>
    </div>
    <div class="principles">
      <div class="principle"><b>Тесты вместо веры</b><span>253 проверки на каждом коммите</span></div>
      <div class="principle"><b>Схемы вместо парсинга</b><span>AI отвечает валидируемым JSON</span></div>
      <div class="principle"><b>Fallback вместо 500</b><span>сбой модели не ломает урок</span></div>
      <div class="principle"><b>Миграции вместо ручных правок</b><span>схема воспроизводима с нуля</span></div>
    </div>
    """


def slide_10() -> str:
    return f"""
    <div class="slide-head">
      <div>
        <div class="kicker"><span class="line"></span> 09 / ДЕПЛОЙ</div>
        <h2>Работает 24/7<br>за 0 ₽ на старте.</h2>
      </div>
      <div class="slide-note">Free-tier без карты:<br>бот + PostgreSQL + Redis</div>
    </div>
    <div class="deploy-layout">
      <div class="card cost-card">
        <div class="pill"><span class="dot"></span> инфраструктура</div>
        <div class="cost-big">0 <span>₽ / мес</span></div>
        <div class="cost-label">на старте и демо, без привязки карты</div>
        <div class="cost-tags">
          <span class="cost-tag">Wispbyte Free</span>
          <span class="cost-tag">Supabase Free</span>
          <span class="cost-tag">Upstash Free</span>
        </div>
        <div class="cost-list">
          <div class="cost-item">{icon("check", 17)}<span>Процесс живёт 24/7</span></div>
          <div class="cost-item">{icon("check", 17)}<span>PostgreSQL 500 МБ + бэкапы</span></div>
          <div class="cost-item">{icon("check", 17)}<span>Redis 250 МБ для FSM и планировщика</span></div>
          <div class="cost-item">{icon("check", 17)}<span>Ни Docker, ни ручных миграций</span></div>
        </div>
        <div class="deploy-note">Free tier — для запуска и первых пользователей.<br>При росте — managed-стек и webhook.</div>
      </div>
      <div>
        <div class="provider-list">
          <div class="provider"><div class="p-logo w">W</div><div><b>Wispbyte Free</b><span>24/7 · Python 3.11+ · запуск из корня</span></div><div class="p-status">BOT</div></div>
          <div class="provider"><div class="p-logo s">S</div><div><b>Supabase Free</b><span>PostgreSQL 500 MB · без карты</span></div><div class="p-status">DB</div></div>
          <div class="provider"><div class="p-logo u">U</div><div><b>Upstash Free</b><span>Redis 250 MB · 500K команд / мес</span></div><div class="p-status">FSM</div></div>
        </div>
        <div class="command-bar"><code>$ python main.py</code><span>миграции → банк вопросов → polling</span></div>
        <div class="deploy-note">SQLite и in-memory Redis — автоматический fallback, если внешние сервисы недоступны.</div>
      </div>
    </div>
    <div class="deploy-steps">
      <div class="deploy-step"><div class="ds-num">01 / UPLOAD</div><b>Загрузить код</b><span>main.py · bot/ · migrations/</span></div>
      <div class="deploy-step"><div class="ds-num">02 / ENV</div><b>Добавить секреты</b><span>BOT_TOKEN · DATABASE_URL · AI_API_KEY</span></div>
      <div class="deploy-step"><div class="ds-num">03 / START</div><b>Запустить процесс</b><span>python main.py</span></div>
      <div class="deploy-step"><div class="ds-num">04 / CHECK</div><b>Проверить в Telegram</b><span>/start → /level_detector → /daily_grammar</span></div>
    </div>
    """


def slide_11() -> str:
    phases = [
        (
            "Сейчас",
            "Фундамент",
            [
                ("check", "<b>8 сценариев</b> и полный CEFR-тест"),
                ("check", "<b>253 теста</b>, Ruff, Alembic"),
                ("check", "<b>AI fallback</b> и live-проверка"),
                ("arrow", "Аналитика событий и воронки"),
            ],
        ),
        (
            "90 дней",
            "Персонализация",
            [
                ("arrow", "<b>Адаптивная сложность</b> по ошибкам"),
                ("arrow", "<b>Speaking</b>: STT/TTS и разговор"),
                ("arrow", "<b>Кабинет учителя</b> и отчёты"),
                ("arrow", "Подписка / пакеты занятий"),
            ],
        ),
        (
            "6 месяцев",
            "Масштаб",
            [
                ("arrow", "<b>B2B</b> для школ и курсов"),
                ("arrow", "<b>Telegram Mini App</b>"),
                ("arrow", "Локализация и контент-маркетплейс"),
                ("arrow", "ML-прогноз оттока и уровня"),
            ],
        ),
    ]
    phase_html = "".join(
        f"""<div class="phase"><div class="phase-dot"></div><div class="card phase-card">
          <div class="phase-time">{time}</div><h3>{title}</h3>
          <div class="phase-list">{"".join(f'<div class="phase-item">{icon(ic, 17)}<span>{text}</span></div>' for ic, text in items)}</div>
        </div></div>"""
        for time, title, items in phases
    )
    return f"""
    <div class="slide-head">
      <div>
        <div class="kicker"><span class="line"></span> 10 / ROADMAP</div>
        <h2>От бота к персональной<br>AI-школе.</h2>
      </div>
      <div class="slide-note">Сначала retention,<br>потом монетизация</div>
    </div>
    <div class="roadmap-grid">{phase_html}</div>
    <div class="metric-strip">
      <span class="metric-chip"><b>D1 / D7 retention</b></span>
      <span class="metric-chip"><b>lessons / week</b></span>
      <span class="metric-chip"><b>level-up rate</b></span>
      <span class="metric-chip"><b>AI cost / active user</b></span>
    </div>
    <div class="success-panel">
      <div class="s-icon">{icon("target", 23)}</div>
      <div><b>Критерий успеха:</b> пользователь возвращается на 7-й день и видит, что его уровень растёт.</div>
      <div class="s-metrics"><span class="s-metric">retention</span><span class="s-metric">level-up</span><span class="s-metric">AI cost</span></div>
    </div>
    """


def slide_12() -> str:
    qr_path = (ASSETS / "bot_qr.png").as_posix()
    return f"""
    <div class="final-grid">
      <div class="final-copy">
        <div class="kicker"><span class="line"></span> 11 / ИТОГ</div>
        <h2>Спасибо.<br>Давайте сделаем английский<br><span class="gradient">ежедневной привычкой.</span></h2>
        <p class="lead">LinguaFlame — не концепт на слайдах: работающий Telegram-продукт с AI, базой, напоминаниями и тестами. Его можно открыть и пройти путь пользователя прямо сейчас.</p>
        <div class="final-checks">
          <span class="final-check">{icon("check", 15)} Product thinking</span>
          <span class="final-check">{icon("check", 15)} Full-stack async</span>
          <span class="final-check">{icon("check", 15)} AI reliability</span>
          <span class="final-check">{icon("check", 15)} Shipping</span>
        </div>
        <div class="final-links">
          <div>Попробовать: <b>@LinguaFlameBot</b></div>
          <div>Код: <b>github.com/aresdev09/linguaflame</b></div>
          <div>Стек: <b>Python · aiogram 3 · PostgreSQL · Redis · NVIDIA NIM</b></div>
        </div>
      </div>
      <div class="qr-card">
        <div class="qr-brand"><img src="file:///{AVATAR.as_posix()}" alt=""><b>LinguaFlame</b></div>
        <img class="qr" src="file:///{qr_path}" alt="QR-код бота">
        <div class="qr-handle">@LinguaFlameBot</div>
        <div class="qr-sub">наведи камеру — и можно заниматься</div>
      </div>
    </div>
    <div class="banner-strip"></div>
    """


SLIDES = [
    ("Титул", slide_01, "AI-тренер, который возвращает к английскому каждый день"),
    (
        "Проблема",
        slide_02,
        "Контента много, а цикла нет: люди не видят пробел, не получают быструю обратную связь и бросают.",
    ),
    (
        "Решение",
        slide_03,
        "Четыре шага: диагностика, короткая практика, обратная связь и привычка — в одном Telegram-боте.",
    ),
    (
        "Продукт",
        slide_04,
        "Три ключевых экрана: CEFR-результат, пошаговый урок и IELTS-разбор эссе.",
    ),
    (
        "Сценарии",
        slide_05,
        "Восемь сценариев покрывают весь путь — от онбординга до статистики и возврата после пропуска.",
    ),
    (
        "Архитектура",
        slide_06,
        "Async-слои, PostgreSQL, Redis, APScheduler и AI-клиент с fallback. Каждый слой можно тестировать отдельно.",
    ),
    (
        "Алгоритм уровня",
        slide_07,
        "Уровень считается по взвешенному баллу: сложные вопросы дороже, скорость даёт бонус, согласованность может поднять итог.",
    ),
    (
        "Retention",
        slide_08,
        "Streak и напоминания построены вокруг следующего действия, а не вокруг идеального урока. Максимум два сообщения в день.",
    ),
    (
        "Качество",
        slide_09,
        "253 теста, 74% покрытия, Ruff, Alembic и проверенный live-запрос к NVIDIA NIM.",
    ),
    (
        "Деплой",
        slide_10,
        "Стартовый стек без фиксированных затрат: Wispbyte, Supabase и Upstash. Есть graceful degradation.",
    ),
    (
        "Roadmap",
        slide_11,
        "Сначала удержание и адаптивность, затем speaking, кабинет учителя и B2B.",
    ),
    (
        "Итог",
        slide_12,
        "Работающий продукт, который можно открыть в Telegram и пройти путь пользователя.",
    ),
]


def render() -> list[Path]:
    BUILD.mkdir(exist_ok=True)
    HTML_DIR.mkdir(exist_ok=True)
    SLIDES_DIR.mkdir(exist_ok=True)
    for old in SLIDES_DIR.glob("*.png"):
        old.unlink()
    paths: list[Path] = []
    for idx, (_, builder, _) in enumerate(SLIDES, start=1):
        body = builder()
        doc = page(body, idx, "PRODUCT PITCH · 2026")
        html_path = HTML_DIR / f"slide_{idx:02d}.html"
        html_path.write_text(doc, encoding="utf-8")
        png_path = SLIDES_DIR / f"slide_{idx:02d}.png"
        cmd = [
            str(EDGE),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            "--window-size=1920,1080",
            "--virtual-time-budget=2500",
            f"--screenshot={png_path}",
            html_path.as_uri(),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not png_path.exists():
            raise RuntimeError(f"Edge did not produce {png_path}")
        paths.append(png_path)
        print(f"rendered {png_path.name}")
    return paths


def build_pptx(paths: list[Path]) -> Path:
    prs = Presentation()
    prs.slide_width = Inches(13.333333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    for (_title, _, note), png in zip(SLIDES, paths, strict=True):
        slide = prs.slides.add_slide(blank)
        slide.shapes.add_picture(str(png), 0, 0, width=prs.slide_width, height=prs.slide_height)
        notes = slide.notes_slide.notes_text_frame
        notes.text = note
    out = ROOT / "LinguaFlame_Presentation.pptx"
    prs.core_properties.title = "LinguaFlame — AI English Coach"
    prs.core_properties.author = "aresdev09"
    prs.core_properties.subject = "Product pitch deck"
    prs.core_properties.comments = "Generated from the LinguaFlame repository"
    prs.save(out)
    return out


def build_pdf(paths: list[Path]) -> Path:
    images = [Image.open(p).convert("RGB") for p in paths]
    out = ROOT / "LinguaFlame_Presentation.pdf"
    images[0].save(
        out,
        "PDF",
        resolution=144.0,
        save_all=True,
        append_images=images[1:],
    )
    for image in images:
        image.close()
    return out


def main() -> None:
    paths = render()
    pptx_path = build_pptx(paths)
    pdf_path = build_pdf(paths)
    print(f"\nPPTX: {pptx_path}")
    print(f"PDF:  {pdf_path}")
    print(f"Slides: {len(paths)}")


if __name__ == "__main__":
    main()
