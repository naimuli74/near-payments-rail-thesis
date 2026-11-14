// /api/live: latest USDC/USDT transfers on NEAR mainnet, read from FASTNEAR neardata final blocks.
// Live feed only; NOT part of the pre-registered sample. Bundled into the Worker by build_site.mjs.
// The LABELS placeholder below is replaced with labels/known_accounts.json at build time.
const LIVE_TOKENS = { '17208628f84f5d6ad33f0da3bbbeb27ffcb398eac501a31bd6ad2011e36133a1': 'USDC', 'usdt.tether-token.near': 'USDT' };
const LABELS = __LABELS__;
const EXACT = Object.fromEntries(LABELS.accounts.filter(a => a.account).map(a => [a.account, a.category]));
const SUFFIX = LABELS.accounts.filter(a => a.suffix).map(a => [a.suffix, a.category]);
const EMPTY_CODE = '11111111111111111111111111111111';
const codeCache = new Map();             // account -> 'contract' | 'account' (per isolate)
let live = {}; // per-isolate response cache: { tip|init: { at, body } }
let backoffUntil = 0; // after a 429 from neardata, serve the last good response for a while
const ND = 'https://mainnet.neardata.xyz/v0';
const RPC = 'https://rpc.mainnet.fastnear.com';
const tmo = ms => AbortSignal.timeout(ms);

async function getBlock(h) {
  const r = await fetch(`${ND}/block/${h}`, { signal: tmo(4000), cf: { cacheEverything: true, cacheTtl: 600 } });
  if (!r.ok) return null;
  const t = await r.text();
  return t && t !== 'null' ? JSON.parse(t) : null;
}
async function codeKind(a) {
  if (codeCache.has(a)) return codeCache.get(a);
  if (/^[0-9a-f]{64}$/.test(a) || /^0x[0-9a-f]{40}$/.test(a)) { codeCache.set(a, 'account'); return 'account'; }
  try {
    const r = await fetch(RPC, { method: 'POST', signal: tmo(2500), headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'query', params: { request_type: 'view_account', finality: 'final', account_id: a } }) });
    const j = await r.json();
    const k = j.result ? (j.result.code_hash !== EMPTY_CODE ? 'contract' : 'account') : 'unknown';
    if (k !== 'unknown') { if (codeCache.size > 5000) codeCache.clear(); codeCache.set(a, k); }
    return k;
  } catch { return 'unknown'; }
}
function knownCat(a) {
  if (EXACT[a]) return EXACT[a];
  for (const [s, c] of SUFFIX) if (a.endsWith(s)) return c;
  return null;
}
function extract(b) {
  const out = []; let txs = 0;
  const h = b.block.header.height, ts = Math.floor(b.block.header.timestamp_nanosec / 1e6);
  for (const sh of b.shards || []) {
    txs += (sh.chunk && sh.chunk.transactions ? sh.chunk.transactions.length : 0);
    for (const ro of sh.receipt_execution_outcomes || []) {
      const oc = ro.execution_outcome.outcome, tok = LIVE_TOKENS[oc.executor_id];
      if (!tok || (oc.status && 'Failure' in oc.status)) continue;
      oc.logs.forEach((log, li) => {
        if (!log.startsWith('EVENT_JSON:')) return;
        let ev; try { ev = JSON.parse(log.slice(11)); } catch { return; }
        if (ev.standard !== 'nep141' || ev.event !== 'ft_transfer') return;
        (ev.data || []).forEach((d, di) => out.push({ id: `${ro.execution_outcome.id}:${li}:${di}`, h, ts, tx: ro.tx_hash, token: tok,
          usd: Number(d.amount) / 1e6, from: d.old_owner_id, to: d.new_owner_id }));
      });
    }
  }
  return { out, txs, h, ts };
}
async function classify(items) {
  const need = new Set();
  for (const t of items) for (const a of [t.from, t.to]) if (!knownCat(a) && !codeCache.has(a)) need.add(a);
  await Promise.all([...need].slice(0, 16).map(codeKind));
  for (const t of items) {
    const cats = [t.from, t.to].map(a => knownCat(a) || (codeCache.get(a) === 'account' ? 'user' : codeCache.get(a) === 'contract' ? 'other_contract' : 'unknown'));
    t.cats = cats;
    t.label = cats.includes('dex') ? 'dex' : (cats[0] === 'user' && cats[1] === 'user') ? 'p2p' : 'other';
  }
  return items;
}
export async function liveApi(req) {
  const u = new URL(req.url), init = u.searchParams.get('init') === '1';
  const ttl = init ? 15000 : 3000, key = init ? 'init' : 'tip', now = Date.now();
  const hdr = { 'content-type': 'application/json', 'cache-control': `public, max-age=${init ? 10 : 2}`, 'access-control-allow-origin': '*', 'x-content-type-options': 'nosniff' };
  if (live[key] && now - live[key].at < ttl) return new Response(live[key].body, { headers: hdr });
  const cache = typeof caches !== 'undefined' ? caches.default : null, ck = new Request(`https://near-live-cache.invalid/${key}`);
  if (cache) { try { const hit = await cache.match(ck); if (hit) return new Response(hit.body, { headers: hdr }); } catch {} }
  const stale = () => { const k = live[key] || live.tip || live.init; return k ? new Response(k.body, { headers: { ...hdr, 'x-live-stale': '1' } }) : null; };
  if (now < backoffUntil) { const st = stale(); if (st) return st; return new Response(JSON.stringify({ ok: false, error: 'rate limited, retry soon' }), { status: 503, headers: { ...hdr, 'cache-control': 'no-store', 'retry-after': '15' } }); }
  try {
    const r = await fetch(`${ND}/last_block/final`, { signal: tmo(4000), redirect: 'follow' });
    if (r.status === 429) backoffUntil = now + 20000;
    if (!r.ok) throw new Error('neardata ' + r.status);
    const tip = await r.json();
    const H = tip.block.header.height, n = init ? 4 : 1;
    const rest = await Promise.all(Array.from({ length: n - 1 }, (_, i) => getBlock(H - 1 - i).catch(() => null)));
    const blocks = [tip, ...rest].filter(Boolean);
    let items = []; for (const b of blocks) items.push(...extract(b).out);
    items = await classify(items.slice(0, 40));
    const t0 = extract(tip);
    const body = JSON.stringify({ ok: true, note: 'Live feed, not part of the pre-registered sample', block: { height: H, txs: t0.txs, ts: t0.ts },
      scanned: [H - n + 1, H], transfers: items.sort((a, b) => b.ts - a.ts) });
    live[key] = { at: now, body };
    if (cache) { try { await cache.put(ck, new Response(body, { headers: { 'content-type': 'application/json', 'cache-control': `public, max-age=${init ? 10 : 3}` } })); } catch {} }
    return new Response(body, { headers: hdr });
  } catch (e) {
    const st = stale(); if (st) return st;
    return new Response(JSON.stringify({ ok: false, error: String(e && e.message || e) }), { status: 502, headers: { ...hdr, 'cache-control': 'no-store' } });
  }
}
