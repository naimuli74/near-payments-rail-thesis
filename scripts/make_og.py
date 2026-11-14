"""Open Graph image (1200x630) for the dashboard, rendered with headless Chrome from
data/processed/summary.json so every number matches the data. Usage: python3 scripts/make_og.py"""
import json, os, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = json.load(open(os.path.join(ROOT, "data", "processed", "summary.json")))
FONT = os.path.join(ROOT, "site", "fonts", "inter-var.woff2")
LOGO = os.path.join(ROOT, "site", "brand", "near-logo-rev.svg")  # official NEAR logo, unmodified (see README)
pct = lambda x, d=0: f"{x*100:.{d}f}%"
usd = lambda x: f"${x/1e6:.1f}M" if x >= 1e6 else f"${x:,.0f}"
dots = "".join(f'<span class="d {"p" if t["pass"] else "f"}">{t["id"]} {"&#10003;" if t["pass"] else "&#10007;"}</span>' for t in S["tests"])
html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:I;src:url(file://{FONT}) format('woff2');font-weight:100 900}}
*{{box-sizing:border-box;margin:0}}body{{width:1200px;height:630px;overflow:hidden;font-family:I,sans-serif;color:#eaf0f5;
background:radial-gradient(700px 420px at 92% -10%,rgba(0,236,151,.22),transparent 60%),radial-gradient(600px 400px at -5% 110%,rgba(23,214,200,.12),transparent 60%),#070b10;padding:56px 64px;display:flex;flex-direction:column}}
.top{{display:flex;align-items:center;gap:14px;font-size:22px;font-weight:700;color:#c2ccd7}}.top svg{{width:40px;height:40px}}
.nl{{height:30px;margin-left:auto;margin-right:28px}}.pill{{font-size:17px;font-weight:600;color:#00ec97;border:1px solid rgba(0,236,151,.35);background:rgba(0,236,151,.08);padding:8px 16px;border-radius:999px;letter-spacing:.04em}}
h1{{font-size:74px;line-height:1.02;letter-spacing:-.04em;font-weight:780;margin-top:44px}}h1 span{{background:linear-gradient(92deg,#00ec97,#17d6c8 60%,#7fe3ff);-webkit-background-clip:text;color:transparent}}
.row{{display:flex;gap:18px;margin-top:auto;align-items:stretch}}
.v{{flex:1.5;border:1px solid rgba(255,181,71,.35);background:linear-gradient(140deg,rgba(255,181,71,.13),rgba(14,21,29,.9) 70%);border-radius:22px;padding:22px 26px}}
.v .l{{font-size:15px;letter-spacing:.14em;font-weight:700;color:#ffb547}}.v .b{{font-size:58px;font-weight:820;color:#ffb547;letter-spacing:-.04em;line-height:1.05;margin-top:4px}}
.s{{font-size:19px;font-weight:600;color:#eaf0f5;margin-top:4px}}.dots{{display:flex;gap:7px;margin-top:14px}}.d{{white-space:nowrap;font-size:15px;font-weight:700;padding:3px 10px;border-radius:999px}}.d.p{{color:#00ec97;background:rgba(0,236,151,.12);border:1px solid rgba(0,236,151,.4)}}.d.f{{color:#ff8f8f;background:rgba(255,107,107,.1);border:1px solid rgba(255,107,107,.32)}}
.k{{flex:1;background:#0e151d;border:1px solid #1d2834;border-radius:22px;padding:22px 24px;position:relative}}.k:before{{content:"";position:absolute;left:24px;right:24px;top:0;height:3px;background:var(--a)}}
.k .n{{font-size:50px;font-weight:780;letter-spacing:-.04em;line-height:1.1}}.k .t{{font-size:18px;color:#8996a6;margin-top:6px;line-height:1.3}}
.tm{{font-size:13px;color:#4c5865;margin-top:6px}}.foot{{display:flex;justify-content:space-between;margin-top:18px;font-size:17px;color:#64717f}}.foot b{{color:#c2ccd7}}
</style></head><body>
<div class="top"><svg viewBox="0 0 32 32"><rect width="32" height="32" rx="9" fill="#00ec97"/><path d="M8 12.5h16M8 19.5h16M11.5 9v14M16 9v14M20.5 9v14" stroke="#00140c" stroke-width="2.4" stroke-linecap="round" fill="none"/></svg>NEAR Payments Rail Thesis<img class="nl" src="file://{LOGO}" alt="NEAR"><span class="pill">NEAR HACKATHON &middot; Investment Thesis</span></div>
<h1>Is NEAR already a <span>payments rail?</span></h1>
<div class="row">
 <div class="v"><div class="l">VERDICT</div><div class="b">Not yet.</div><div class="s">{S['passed']} of {len(S['tests'])} pre-registered tests pass</div><div class="dots">{dots}</div></div>
 <div class="k" style="--a:#ff6b6b"><div class="n">{pct(S['share_of_transfers']['dex'])}</div><div class="t">of stablecoin transfers go through a DEX</div></div>
 <div class="k" style="--a:#00ec97"><div class="n">{pct(S['share_of_transfers']['p2p'],1)}</div><div class="t">wallet-to-wallet</div></div>
 <div class="k" style="--a:#ffb547"><div class="n">{usd(S['intents']['avg_daily_volume']['deposit'])}</div><div class="t">a day into NEAR Intents</div></div>
</div>
<div class="foot"><span>{S['window']['days']} days of on-chain USDC/USDT &middot; six pre-registered tests &middot; open data</span><b>near.darkhouse.online</b></div>
<div class="tm">Independent analysis by Naimul Islam. NEAR and the NEAR logo are trademarks of NEAR Foundation; not affiliated.</div>
</body></html>"""
assert S["passed"] < 3, "verdict text in the OG image assumes 'Not yet'"
tmp = "/tmp/og.html"; open(tmp, "w").write(html)
out = os.path.join(ROOT, "site", "og.png")
subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                "--window-size=1200,630", "--force-device-scale-factor=1", "--virtual-time-budget=3000", f"--screenshot={out}", "file://" + tmp],
               check=True, capture_output=True)
print("wrote", out)
