// 레퍼런스 듣기 — AI 가 곡 이름이나 링크를 주면, 숨은 창에서 직접 찾아 재생하고 그 창의 소리만 받아 넘긴다.
//   POST http://127.0.0.1:47803/listen  {query?: "kanye west through the wire", url?: "...", clips?: 3, seconds?: 20}
//   → {meta: {title, channel, url, duration, at: [...]}, sample_rate, clips: [base64 Int16 스테레오 인터리브, ...]}
// 소리는 메모리로만 오간다(디스크에 쓰지 않음). 창의 소리는 Web Audio 로 가로채므로 스피커로 나가지 않는다.
// 분석(템포·조성·그루브·대역…)은 파이썬 musicoma/listen.py 가 한다.
'use strict';

const { BrowserWindow } = require('electron');
const http = require('http');

const PORT = 47803;
const PARTITION = 'persist:musicoma-listen';
let busy = false;

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

// 페이지 안에서 도는 녹음 스크립트(문자열로 주입). 광고가 끝나길 기다렸다가 곡의 여러 지점을 잠깐씩 듣는다.
const CAPTURE = String.raw`(async (clips, seconds, speed) => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let v = null;
  for (let i = 0; i < 150 && !(v = document.querySelector('video, audio')); i++) await sleep(200);
  if (!v) throw new Error('재생할 영상/소리를 찾지 못함');
  const player = document.querySelector('#movie_player');
  const isAd = () => !!(player && player.classList.contains('ad-showing'));
  const skipAds = async () => {
    for (let i = 0; i < 240 && isAd(); i++) {
      const b = document.querySelector('.ytp-skip-ad-button, .ytp-ad-skip-button, .ytp-ad-skip-button-modern');
      if (b) b.click();
      await sleep(500);
    }
  };
  v.muted = false; v.volume = 1;
  const setSpeed = (s) => { v.preservesPitch = false; v.playbackRate = s; };
  try { await v.play(); } catch (_) {}
  await skipAds();
  for (let i = 0; i < 80 && !(v.duration > 0 && isFinite(v.duration)); i++) await sleep(250);
  const dur = v.duration;
  if (!(dur > 0 && isFinite(dur))) throw new Error('길이를 알 수 없음(라이브 방송?)');
  // 빨리 듣기: 음정 보정 없이 speed 배로 틀고(= 그냥 빨리 돌린 테이프) 48k×speed 로 받으면,
  // 그 샘플을 48k 로 읽는 것만으로 원래 소리가 된다(대역도 그대로 — 받는 쪽 샘플레이트를 같이 올리므로).
  // 단, 아주 높은 대역(10 kHz 위)은 빨리 틀면 재생기 쪽에서 깎인다(10-17 실측: 2배속 air -4 dB) — 그래서 한 구간은 1배속으로
  // 들어 소리 색을 재고(가운데 구간), 나머지 구간만 빨리 들어 리듬·조성을 잰다(10-17: 4배속도 템포·조성·스윙 1배속과 같음).
  const ctx = new AudioContext({ sampleRate: 48000 * speed });
  const src = ctx.createMediaElementSource(v);          // 이 순간부터 소리는 스피커가 아니라 여기로
  const proc = ctx.createScriptProcessor(4096, 2, 2);   // 출력 버퍼를 안 채우므로 무음
  let rec = null;
  proc.onaudioprocess = (e) => {
    if (!rec || v.paused || isAd()) return;
    rec.L.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    rec.R.push(new Float32Array(e.inputBuffer.getChannelData(1)));
    rec.n += e.inputBuffer.length;
  };
  src.connect(proc); proc.connect(ctx.destination);
  await ctx.resume();
  const want = Math.min(seconds, Math.max(5, dur / clips - 2));
  const spots = [];
  for (let i = 0; i < clips; i++) spots.push(Math.max(0, Math.min(dur - want - 1, dur * (0.12 + 0.76 * (clips === 1 ? 0.3 : i / (clips - 1))))));
  const out = [];
  for (let ci = 0; ci < spots.length; ci++) {
    const at = spots[ci];
    const sp = ci === Math.floor(spots.length / 2) ? 1 : speed;   // 가운데(대개 후렴 근처) 구간만 1배속
    v.currentTime = at;
    await new Promise((r) => { const f = () => { v.removeEventListener('seeked', f); r(); }; v.addEventListener('seeked', f); setTimeout(f, 4000); });
    try { await v.play(); } catch (_) {}
    for (let i = 0; i < 40 && (v.readyState < 3 || v.paused); i++) await sleep(150);
    await skipAds();
    setSpeed(sp);
    rec = { L: [], R: [], n: 0 };
    const t0 = Date.now();
    const need = want * ctx.sampleRate / sp;      // 원래 소리 want 초 = 이 컨텍스트 샘플 수
    while (rec.n < need && Date.now() - t0 < (want / sp + 15) * 1000) await sleep(50);
    const r = rec; rec = null;
    const pcm = new Int16Array(r.n * 2);
    let k = 0;
    for (let b = 0; b < r.L.length; b++) {
      const L = r.L[b], R = r.R[b];
      for (let j = 0; j < L.length; j++) {
        pcm[k++] = Math.max(-1, Math.min(1, L[j])) * 32767;
        pcm[k++] = Math.max(-1, Math.min(1, R[j])) * 32767;
      }
    }
    const b64 = await new Promise((res) => {
      const fr = new FileReader();
      fr.onload = () => res(String(fr.result).split(',')[1] || '');
      fr.readAsDataURL(new Blob([pcm.buffer]));
    });
    out.push({ at: Math.round(at * 10) / 10, speed: sp, rate: ctx.sampleRate / sp, seconds: Math.round(r.n * sp / ctx.sampleRate * 10) / 10, pcm: b64 });
  }
  v.pause();
  let title = document.title.replace(/ - YouTube$/, ''), channel = null;
  try { const d = player && player.getVideoData && player.getVideoData(); if (d) { title = d.title || title; channel = d.author || null; } } catch (_) {}
  await ctx.close();
  return { title, channel, url: location.href, duration: Math.round(dur * 10) / 10, sample_rate: 48000, speed, clips: out };
})`;

async function findOnYouTube(win, query) {
  await win.loadURL('https://www.youtube.com/results?search_query=' + encodeURIComponent(query));
  for (let i = 0; i < 60; i++) {
    const href = await win.webContents.executeJavaScript(
      `(() => { const a = document.querySelector('a#video-title[href^="/watch"], a#video-title-link[href^="/watch"], ytd-video-renderer a[href^="/watch"]'); return a ? a.href : null; })()`);
    if (href) return href.split('&')[0];
    await sleep(250);
  }
  throw new Error(`유튜브에서 '${query}' 를 찾지 못함`);
}

async function listen({ query, url, clips = 3, seconds = 20, speed = 4 }, log) {
  const win = new BrowserWindow({
    show: false, width: 1280, height: 800,
    webPreferences: {
      partition: PARTITION, sandbox: true, contextIsolation: true, nodeIntegration: false,
      backgroundThrottling: false, autoplayPolicy: 'no-user-gesture-required',
    },
  });
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  try {
    const target = url || await findOnYouTube(win, query);
    log(`listen: ${target}`);
    await win.loadURL(target);
    const r = await win.webContents.executeJavaScript(`${CAPTURE}(${Number(clips) | 0 || 3}, ${Number(seconds) || 20}, ${Math.min(4, Math.max(1, Number(speed) || 4))})`, true);
    return { meta: { title: r.title, channel: r.channel, url: r.url, duration: r.duration, at: r.clips.map((c) => c.at),
                     query: query || null, speed: r.speed },
             sample_rate: r.sample_rate, clips: r.clips.map((c) => c.pcm), rates: r.clips.map((c) => c.rate),
             speeds: r.clips.map((c) => c.speed) };
  } finally {
    if (!win.isDestroyed()) win.destroy();
  }
}

function start(log) {
  const server = http.createServer((req, res) => {
    const send = (code, obj) => { res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' }); res.end(JSON.stringify(obj)); };
    if (req.method !== 'POST' || req.url !== '/listen') return send(404, { error: 'POST /listen' });
    let body = '';
    req.on('data', (d) => { body += d; if (body.length > 1e5) req.destroy(); });
    req.on('end', async () => {
      let a;
      try { a = JSON.parse(body || '{}'); } catch (_) { return send(400, { error: 'JSON' }); }
      if (!a.query && !a.url) return send(400, { error: 'query 또는 url' });
      if (busy) return send(409, { error: '이미 듣는 중' });
      busy = true;
      const timer = setTimeout(() => { if (!res.writableEnded) send(504, { error: '시간 초과(4분)' }); }, 240000);
      try {
        const r = await listen(a, log);
        if (!res.writableEnded) send(200, r);
      } catch (e) {
        log(`listen failed: ${e.message}`);
        if (!res.writableEnded) send(500, { error: e.message });
      } finally {
        clearTimeout(timer);
        busy = false;
      }
    });
  });
  server.on('error', (e) => log(`listen server: ${e.message}`));
  server.listen(PORT, '127.0.0.1', () => log(`listen server on 127.0.0.1:${PORT}`));
  return server;
}

module.exports = { start, PORT };
