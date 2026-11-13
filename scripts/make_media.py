"""Screenshots (desktop + mobile) and a captioned scroll-through demo video of the dashboard.
Needs google-chrome (headless), ffmpeg and Pillow. Usage: python3 scripts/make_media.py [URL]"""
import json, os, re, subprocess, sys, html as H
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA = os.path.join(ROOT, "media"); os.makedirs(MEDIA, exist_ok=True)
URL = sys.argv[1] if len(sys.argv) > 1 else "https://near.darkhouse.online/"
CHROME = ["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--virtual-time-budget=8000"]
FONT = "/usr/share/fonts/truetype/sand-box/google/Inter/Inter-VariableFont_opsz,wght.ttf"
S = json.load(open(os.path.join(ROOT, "data", "processed", "summary.json")))


def positions():
    probe = URL + ("&" if "?" in URL else "?") + "probe=1"
    js = ("<script>addEventListener('load',()=>setTimeout(()=>{const o={h:document.documentElement.scrollHeight};"
          "for(const id of ['tests','evidence','c1','c2','c3','c5','c6','toptable','intents','c8','c9','method'])"
          "{const e=document.getElementById(id);if(e){const c=e.closest('.card')||e;o[id]=c.getBoundingClientRect().top+scrollY}}"
          "document.title='POS'+JSON.stringify(o)},500))</script>")
    page = subprocess.run(["curl", "-s", URL], capture_output=True, text=True).stdout
    base = URL.rstrip("/")
    page = page.replace('<script src="/chart.js">', f'<script src="{base}/chart.js">').replace("</body>", js + "</body>")
    tmp = "/tmp/probe.html"; open(tmp, "w").write(page)
    out = subprocess.run(CHROME + ["--window-size=1440,900", "--dump-dom", "file://" + tmp], capture_output=True, text=True).stdout
    m = re.search(r"<title>POS(.*?)</title>", out)
    return json.loads(H.unescape(m.group(1)))


def shot(path, w, h, scale):
    subprocess.run(CHROME + [f"--window-size={w},{h}", f"--force-device-scale-factor={scale}", f"--screenshot={path}", URL],
                   check=True, capture_output=True)


pos = positions(); print("positions", pos)
full = os.path.join(MEDIA, "dashboard-desktop-full.png")
shot(full, 1440, int(pos["h"]) + 10, 4 / 3)
shot(os.path.join(MEDIA, "dashboard-desktop.png"), 1440, 900, 2)
shot(os.path.join(MEDIA, "dashboard-mobile.png"), 390, 844, 3)
shot("/tmp/mobile-full.png", 390, 5600, 2)
im = Image.open("/tmp/mobile-full.png"); im.crop((0, 0, im.width, min(im.height, 2 * 2600))).save(os.path.join(MEDIA, "dashboard-mobile-long.png"))

# ---- demo video
page = Image.open(full).convert("RGB"); k = page.width / 1440
W, Hh, FPS = 1920, 1080, 30
font = ImageFont.truetype(FONT, 40); font.set_variation_by_axes([14, 600]) if hasattr(font, "set_variation_by_axes") else None
big = ImageFont.truetype(FONT, 84); small = ImageFont.truetype(FONT, 38)
for f, wg in ((font, 600), (big, 800), (small, 500)):
    try: f.set_variation_by_axes([24, wg])
    except Exception: pass
E, sn, sv = S["estimates"], S["share_of_transfers"], S["share_of_volume"]
I = S["intents"]


def pct(x): return f"{x * 100:.0f}%"


def usd(x):
    return f"${x / 1e6:,.1f}M" if x >= 1e6 else f"${x / 1e3:,.0f}K" if x >= 1e3 else f"${x:,.2f}"


Y = lambda key, pad=90: max(0, pos[key] - pad)
steps = [
    (0, 5.5, "Question: does NEAR's stablecoin flow look like a payments network, or a trading venue?"),
    (Y("tests"), 6, f"Six tests, written down before looking at the data. Result: {S['passed']} of 6 pass."),
    (Y("c1"), 6, f"{pct(sn['dex'])} of USDC/USDT transfers on NEAR touch a DEX. Wallet-to-wallet: {pct(sn['p2p'])}."),
    (Y("c3"), 6, f"But wallet-to-wallet transfers look like payments: median {usd(S['median_p2p_transfer_usd'])}, {pct(S['p2p_under_100_share'])} under $100."),
    (Y("c5"), 6, "DEX flow follows NEAR's volatility. Wallet-to-wallet flow mostly does not."),
    (Y("intents"), 6, f"Inside NEAR Intents: about {usd(I['avg_daily_volume']['deposit'])} a day of stablecoins from other chains flows in."),
    (Y("c9"), 5.5, "Most of those dollars come from other chains. NEAR is settling them."),
    (Y("method"), 5, "Seeded block sample, cited labels, one command to rebuild. Anyone can re-run it."),
]


def caption(img, text):
    d = ImageDraw.Draw(img, "RGBA"); d.rectangle([0, Hh - 150, W, Hh], fill=(5, 8, 12, 225))
    d.rectangle([0, Hh - 150, 10, Hh], fill=(0, 236, 151, 255))
    words, lines, cur = text.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if d.textlength(t, font=font) > W - 160: lines.append(cur); cur = wd
        else: cur = t
    lines.append(cur)
    y0 = Hh - 75 - 26 * len(lines)
    for i, ln in enumerate(lines): d.text((60, y0 + i * 52), ln, font=font, fill=(240, 244, 248))
    return img


CW = 1640; CH = CW * 9 // 16  # crop the content column and scale it up for small screens


def frame_at(y):
    y = int(min(max(0, y * k), page.height - CH)); x = (page.width - CW) // 2
    return page.crop((x, y, x + CW, y + CH)).resize((W, Hh), Image.LANCZOS)


def card(title, lines):
    img = Image.new("RGB", (W, Hh), (11, 15, 20)); d = ImageDraw.Draw(img)
    d.text((140, 330), "NEAR HACKATHON  ·  INVESTMENT THESIS", font=small, fill=(0, 236, 151))
    d.text((140, 400), title, font=big, fill=(240, 244, 248))
    for i, ln in enumerate(lines): d.text((140, 540 + i * 64), ln, font=small, fill=(170, 182, 198))
    return img


fdir = "/tmp/frames"; subprocess.run(["rm", "-rf", fdir]); os.makedirs(fdir)
n = 0
def emit(img, secs):
    global n
    for _ in range(int(secs * FPS)):
        img.save(f"{fdir}/{n:05d}.jpg", quality=90); n += 1

emit(card("Is NEAR already a payments rail?", ["90 days of on-chain USDC and USDT transfers,", "tested against six rules fixed in advance."]), 3.5)
prev = None
for y, hold, text in steps:
    if prev is not None:
        for i in range(int(0.9 * FPS)):
            t = (i + 1) / (0.9 * FPS); e = t * t * (3 - 2 * t)
            caption(frame_at(prev + (y - prev) * e), text).save(f"{fdir}/{n:05d}.jpg", quality=90); n += 1
    emit(caption(frame_at(y), text), hold); prev = y
emit(card("Live dashboard + code", ["near.darkhouse.online", "github.com/naimuli74/near-payments-rail-thesis", "Built at NEAR HACKATHON  ·  @NEARProtocol  #NEARHackathon"]), 4.5)
out = os.path.join(MEDIA, "demo.mp4")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"{fdir}/%05d.jpg", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium", "-movflags", "+faststart", out], check=True)
print("frames", n, "seconds", n / FPS, "->", out)
