// Builds the static dashboard into a single Cloudflare Worker (dist/worker.js) plus a
// deploy snippet (dist/deploy.js). Text takeaways are generated from site/data.json so
// every sentence matches the numbers. Usage: node scripts/build_site.mjs
import fs from 'fs';
import { gzipSync } from 'node:zlib';
const REPO = process.env.REPO_URL || 'https://github.com/naimuli74/near-payments-rail-thesis';
const WORKER = process.env.WORKER_NAME || 'near-payments-rail';
const D = JSON.parse(fs.readFileSync('site/data.json', 'utf8'));
const S = D.summary;
const pct = (x, d = 0) => (x * 100).toFixed(d) + '%';
const fmt = (x, d = 0) => Number(x).toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d });
const usd = x => x >= 1e9 ? '$' + fmt(x / 1e9, 2) + 'B' : x >= 1e6 ? '$' + fmt(x / 1e6, 1) + 'M' : x >= 1e3 ? '$' + fmt(x / 1e3, 1) + 'K' : '$' + fmt(x, 2);
const sv = S.share_of_volume, sn = S.share_of_transfers;
const passed = S.passed, total = S.tests.length;
const failed = S.tests.filter(t => !t.pass).map(t => t.name.toLowerCase());
const verdict = passed >= 5 ? 'Yes. NEAR stablecoin flow already behaves like a payments rail.'
  : passed >= 3 ? 'Partly. A real payments layer exists, but trading still sets the pace.'
  : 'Not yet. NEAR stablecoins mostly move like a trading venue, not a payments network.';
const vsub = `${passed} of ${total} tests pass. ${pct(sn.dex)} of USDC/USDT transfers on NEAR go through a DEX, and wallet-to-wallet transfers are only ${pct(sn.p2p, 1)} of transfers.` + (failed.length ? ` Failed: ${failed.join(', ')}.` : '');
const p2pSize = D.size.p2p, dexSize = D.size.dex;
const share = (arr, from) => { const t = arr.reduce((a, b) => a + b, 0); return t ? arr.slice(from).reduce((a, b) => a + b, 0) / t : 0; };
const rd = S.round_dollar_share;
const c = S.correlations;
const sup = S.supply;
const T = {
  T1: `<b>${pct(sn.dex)}</b> of transfers and <b>${pct(sv.dex)}</b> of volume involve a DEX. Wallet-to-wallet is <b>${pct(sn.p2p)}</b> of transfers but only <b>${pct(sv.p2p, 1)}</b> of the dollars.`,
  T2: `Volume is estimated at <b>${usd(S.estimates.avg_daily_volume_usd)}</b> a day on average (95% CI ${usd(S.estimates.avg_daily_volume_ci95[0])} to ${usd(S.estimates.avg_daily_volume_ci95[1])}). Counted by transfers, DEX flow (red) is most of every week. Switch to Volume to see how a single large transfer can dominate a week.`,
  T3: `Wallet-to-wallet transfers have a median of <b>$${fmt(S.median_p2p_transfer_usd, 2)}</b>, and <b>${pct(S.p2p_under_100_share)}</b> are under $100. That is what consumer payments look like. ${pct(share(dexSize, 4))} of DEX legs are $1K or more.`,
  T4: `<b>${pct(rd.p2p ?? 0)}</b> of wallet-to-wallet transfers are whole-dollar amounts, against <b>${pct(rd.dex ?? 0, 1)}</b> for DEX legs. Humans paying humans leave a different fingerprint than bots.`,
  T5: `Spearman correlation with NEAR's absolute daily return: all volume <b>${c.v_all.vs_abs_return.toFixed(2)}</b>, DEX volume <b>${c.v_dex.vs_abs_return.toFixed(2)}</b>, wallet-to-wallet volume <b>${c.v_p2p.vs_abs_return.toFixed(2)}</b>. With price level: wallet-to-wallet count <b>${c.n_p2p.vs_price.toFixed(2)}</b>.`,
  T6: `Stablecoins on NEAR went from <b>${usd(sup.start)}</b> to <b>${usd(sup.end)}</b> over the window while NEAR moved from $${S.price.start.toFixed(2)} to $${S.price.end.toFixed(2)}. Each dollar turns over about <b>${(S.velocity_daily * 100).toFixed(1)}%</b> a day.`,
  T7: `The top counterparty, <span class="acct">${S.top_counterparties[0].account}</span>, is on one side of <b>${pct(S.top_counterparties[0].share_of_transfers_volume)}</b> of sampled volume. The largest 1% of transfers carry <b>${pct(S.top1pct_transfer_volume_share)}</b> of all dollars.`,
};
const IS = S.intents;
const iv = IS.avg_daily_volume, ic = IS.avg_daily_count;
const topChain = Object.entries(IS.chain_volume_share)[0] || ['n/a', 0];
T.T8 = `About <b>${usd(iv.deposit)}</b> a day of stablecoins enters Intents and <b>${usd(iv.withdrawal)}</b> leaves, against <b>${usd(iv.swap)}</b> of swap flow. Most stablecoin activity at NEAR's edge is cross-chain movement, not native-token trading.` + (IS.defillama_avg_daily_volume ? ` Cross-check: DefiLlama puts all NEAR Intents volume (every asset) at ${usd(IS.defillama_avg_daily_volume)} a day over the same days.` : '');
T.T9 = `<b>${pct(topChain[1])}</b> of the sampled stablecoin flow is ${topChain[0]} dollars. NEAR is settling other chains' stablecoins, which is a different role from issuing its own.`;
T.T10 = `An estimated <b>${fmt(ic.peer_transfer)}</b> stablecoin peer transfers a day happen inside Intents (median $${fmt(IS.peer_median_usd ?? 0, 2)}, ${pct(IS.peer_under_100_share ?? 0)} under $100). Small, but this is the payment-shaped flow to watch.`;
const SB = S.sensitivity.largest;
T.SENS = `<b>Robustness check (not a test):</b> one sampled transfer, <a href="https://nearblocks.io/txns/${SB.largest_transfer_tx}">${usd(SB.largest_transfer_usd)} to ${SB.largest_transfer_to.length > 30 ? SB.largest_transfer_to.slice(0, 12) + '…' : SB.largest_transfer_to}</a>, is ${pct(SB.largest_transfer_share_of_sampled_volume)} of all sampled dollars. Without it, DEX + Intents + lending carry <b>${pct(SB.trading_share_excl_largest)}</b> of volume and wallet-to-wallet <b>${pct(SB.share_of_volume_excl_largest.p2p)}</b>. Volume shares in a block sample are fragile; transfer counts are not.`;
const change = `We would call NEAR a payments rail when these move, measured with the same script:`;
const changelist = [
  `Wallet-to-wallet share of volume rises from ${pct(sv.p2p, 1)} to above 25% for a full quarter.`,
  (S.trading_share_of_volume < 0.5 ? `DEX + Intents + lending share of volume falls below 50% even with the single largest transfer set aside (now ${pct(S.trading_share_of_volume)} overall, ${pct(S.sensitivity.largest.trading_share_excl_largest)} without it).` : `DEX + Intents + lending share of volume falls from ${pct(S.trading_share_of_volume)} to below 50%.`),
  `Daily stablecoin volume stops tracking NEAR volatility (|rho| below 0.3; now ${Math.abs(c.v_all.vs_abs_return).toFixed(2)}).`,
  `Round-dollar transfers (invoices, payroll) grow as a share of all transfers (now ${pct(rd.all, 1)}).`,
].map(x => `<li>${x}</li>`).join('');
const impl = passed >= 5
  ? `NEAR can be valued partly as payments infrastructure. Track wallet-to-wallet volume as the core KPI.`
  : `Do not underwrite NEAR as a payments network today. The data shows a trading venue with a small but real payments layer: ${usd(S.estimates.avg_daily_p2p_volume_usd)} a day of wallet-to-wallet stablecoin flow with consumer-sized tickets, sitting on a growing stablecoin base (${usd(sup.end)}). The long-term bet is optionality: if that layer's share of volume grows, the thesis flips. This dashboard is the tripwire, and anyone can re-run it.`;
const repoShort = REPO.replace('https://github.com/', 'github.com/');
let html = fs.readFileSync('site/index.html', 'utf8')
  .replaceAll('__REPO_SHORT__', repoShort).replaceAll('__REPO__', REPO)
  .replace('__VERDICT__', () => JSON.stringify(verdict)).replace('__VERDICT_SUB__', () => JSON.stringify(vsub))
  .replace('__CHANGE__', () => JSON.stringify(change)).replace('__CHANGELIST__', () => JSON.stringify(changelist)).replace('__IMPL__', () => JSON.stringify(impl));
for (const [k, v] of Object.entries(T)) html = html.replace(`__${k}__`, () => JSON.stringify(v));
html = html.replace('__LABELS__', () => JSON.stringify(JSON.parse(fs.readFileSync('labels/known_accounts.json', 'utf8'))));
html = html.replace('__DATA__', () => JSON.stringify(D));
fs.mkdirSync('dist', { recursive: true });
fs.writeFileSync('dist/index.html', html);
fs.writeFileSync('dist/chart.js', fs.readFileSync('site/vendor/chart.umd.min.js'));
// Static assets: self-hosted Inter (OFL), favicon and the Open Graph image (scripts/make_og.py).
const FAVICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="9" fill="#00ec97"/><path d="M9 23V9h2.6l7.6 10.4V9H23v14h-2.6L12.8 12.6V23z" fill="#00140c"/></svg>';
const ASSETS = { '/fonts/inter-var.woff2': ['site/fonts/inter-var.woff2', 'font/woff2'], '/og.png': ['site/og.png', 'image/png'] };
fs.mkdirSync('dist/fonts', { recursive: true });
fs.writeFileSync('dist/favicon.svg', FAVICON);
const BIN = {};
for (const [path, [file, type]] of Object.entries(ASSETS)) {
  if (!fs.existsSync(file)) { console.warn('missing asset', file); continue; }
  const buf = fs.readFileSync(file); fs.writeFileSync('dist' + path, buf); BIN[path] = [buf.toString('base64'), type];
}
fs.writeFileSync('site/narrative.json', JSON.stringify({ verdict, vsub, ...T, changelist, impl }, null, 1));
const chart = fs.readFileSync('site/vendor/chart.umd.min.js', 'utf8');
const LIVE = fs.readFileSync('scripts/live_api.js', 'utf8').replace('__LABELS__', () => fs.readFileSync('labels/known_accounts.json', 'utf8').trim());
const worker = LIVE + `\nconst HTML=${JSON.stringify(html)};const CHART=${JSON.stringify(chart)};const DATA=${JSON.stringify(JSON.stringify(D))};
const FAV=${JSON.stringify(FAVICON)};const BIN=${JSON.stringify(BIN)};const B={};for(const k in BIN){const s=atob(BIN[k][0]);const a=new Uint8Array(s.length);for(let i=0;i<s.length;i++)a[i]=s.charCodeAt(i);B[k]=[a,BIN[k][1]];}
export default{async fetch(req){const u=new URL(req.url);const h={'x-content-type-options':'nosniff','cache-control':'public, max-age=300','referrer-policy':'strict-origin-when-cross-origin'};
if(B[u.pathname])return new Response(B[u.pathname][0],{headers:{...h,'content-type':B[u.pathname][1],'cache-control':'public, max-age=86400','access-control-allow-origin':'*'}});
if(u.pathname==='/favicon.svg'||u.pathname==='/favicon.ico')return new Response(FAV,{headers:{...h,'content-type':'image/svg+xml','cache-control':'public, max-age=86400'}});
if(u.pathname==='/api/live')return liveApi(req);
if(u.pathname==='/robots.txt')return new Response('User-agent: *\\nAllow: /\\n',{headers:{...h,'content-type':'text/plain'}});
if(u.pathname==='/chart.js')return new Response(CHART,{headers:{...h,'content-type':'application/javascript; charset=utf-8','cache-control':'public, max-age=86400'}});
if(u.pathname==='/data.json')return new Response(DATA,{headers:{...h,'content-type':'application/json','access-control-allow-origin':'*'}});
if(u.pathname==='/'||u.pathname==='/index.html')return new Response(HTML,{headers:{...h,'content-type':'text/html; charset=utf-8'}});
return new Response('Not found',{status:404});}};`;
fs.writeFileSync('dist/worker.js', worker);
const meta = { main_module: 'worker.js', compatibility_date: '2025-09-01' };
const deploy = `async () => {
  const packed = Uint8Array.from(atob(${JSON.stringify(gzipSync(worker).toString('base64'))}), c => c.charCodeAt(0));
  const code = await new Response(new Blob([packed]).stream().pipeThrough(new DecompressionStream('gzip'))).text();
  const form = new FormData();
  form.append('metadata', new Blob([JSON.stringify(${JSON.stringify(meta)})], { type: 'application/json' }));
  form.append('worker.js', new Blob([code], { type: 'application/javascript+module' }), 'worker.js');
  const r = await cloudflare.request({ method: 'PUT', path: \`/accounts/\${accountId}/workers/scripts/${WORKER}\`, body: form });
  let s; try { s = await cloudflare.request({ method: 'POST', path: \`/accounts/\${accountId}/workers/scripts/${WORKER}/subdomain\`, body: { enabled: true, previews_enabled: false } }); } catch (e) { s = String(e); }
  let sub; try { sub = await cloudflare.request({ method: 'GET', path: \`/accounts/\${accountId}/workers/subdomain\` }); } catch (e) { sub = String(e); }
  return { ok: r.success, errors: r.errors, enable: s && (s.result || s), subdomain: sub && (sub.result || sub) };
}`;
fs.writeFileSync('dist/deploy.js', deploy);
console.log('html', html.length, 'worker', worker.length, 'deploy', deploy.length);
