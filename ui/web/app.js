// Musicoma UI — AI(프로듀서)와 함께, 잘 아는 사람은 직접. 엔진과 같은 명령을 쓴다.
let ws, nextId = 1;
const pending = new Map();
let info = null, song = {}, selected = null, playing = false, pollTimer = null;
let pxPerBeat = null, laneH = 26, sounds = [], cat = "SFZ", busy = false;
let selClip = null;            // {track, clip}
let timeSel = null;            // {a, b, track} 박 단위
let pr = null;                 // PianoRoll
const faders = new Map();      // track name → Fader
let masterFader = null;
const armed = new Set();        // 녹음 대기 트랙
let scenePlaying = null;        // 세션 뷰에서 띄운 섹션 인덱스

const $ = (s) => document.querySelector(s);
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const store = { get: (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
                set: (k, v) => { try { localStorage.setItem(k, v); } catch {} } };
const PALETTE = ["#c9a24a", "#b7c27a", "#8fbf8a", "#7fb5a8", "#86a9c4", "#8f96c8", "#a98bc4", "#c58db4", "#cf8f84",
                 "#d1a272", "#a3a97a", "#7aa39b", "#7d93ad", "#9b8bb0", "#b58a8a", "#c8b46a", "#94b4c9", "#b4a090"];
const colorFor = (idx, ci) => PALETTE[(ci ?? idx * 5 + 1) % PALETTE.length];
const barOf = (beat) => Math.floor(beat / 4) + 1;

// ---------------------------------------------------------------- 스프링(끊을 수 있음, 현재 값에서 출발)
function spring(obj, key, target, { response = 0.3, damping = 1.0, onUpdate, onDone } = {}) {
  const k = (2 * Math.PI / response) ** 2, c = 4 * Math.PI * damping / response;
  cancelAnimationFrame(obj["_raf_" + key]);
  let v = obj["_vel_" + key] || 0, last = performance.now();
  const step = (now) => {
    const dt = Math.min(0.032, (now - last) / 1000); last = now;
    const x = obj[key];
    v += (-k * (x - target) - c * v) * dt;
    obj[key] = x + v * dt; obj["_vel_" + key] = v;
    onUpdate && onUpdate(obj[key]);
    if (Math.abs(obj[key] - target) < 0.001 && Math.abs(v) < 0.01) { obj[key] = target; obj["_vel_" + key] = 0; onUpdate && onUpdate(target); onDone && onDone(); return; }
    obj["_raf_" + key] = requestAnimationFrame(step);
  };
  obj["_raf_" + key] = requestAnimationFrame(step);
}
const ctxState = { p: 0 };
function showCtx(on) {
  const bar = $("#ctxbar");
  if (on) bar.hidden = false;
  spring(ctxState, "p", on ? 1 : 0, {
    response: 0.32,
    onUpdate: (p) => {
      bar.style.opacity = Math.max(0, Math.min(1, p));
      bar.style.transform = `translateX(-50%) translateY(${(1 - p) * 12}px) scale(${0.96 + 0.04 * p})`;
    },
    onDone: () => { if (!on) bar.hidden = true; },
  });
}

// ---------------------------------------------------------------- 통신
function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}
function connect() {
  ws = new WebSocket("ws://127.0.0.1:47801");
  ws.onopen = boot;
  ws.onclose = () => setTimeout(connect, 1000);
  ws.onmessage = (m) => {
    const msg = JSON.parse(m.data);
    if (msg.claude) return onClaude(msg);
    if (msg.event) return onEvent(msg);
    const p = pending.get(msg.id);
    if (!p) return;
    pending.delete(msg.id);
    msg.ok ? p.resolve(msg.result) : p.reject(new Error(msg.error));
  };
}
let refreshTimer = null;
async function onEngineRestarted() {
  // 엔진이 다시 떴다 — 새 엔진은 빈 상태이므로 보던 곡을 다시 연다
  status("엔진이 다시 시작됨 — 곡을 다시 엽니다");
  const song = $("#project").value;
  if (song && song !== "__new") {
    try {
      const ep = await (await fetch(`/api/edit_path?song=${encodeURIComponent(song)}`)).json();
      await call("edit.load", { path: ep.path });
    } catch (e) { status("곡을 다시 열지 못했습니다: " + e.message); }
  }
  loadDevices();   // 고른 출력 장치도 새 엔진에 다시
  refresh();
}
function onEvent(ev) {
  if (ev.event === "engine_restarted") return onEngineRestarted();
  if (ev.client && ev.client.startsWith("claude")) {
    const c = $("#claude");
    c.classList.add("live"); c.textContent = "AI · " + ev.method;
    clearTimeout(c._t); c._t = setTimeout(() => { c.classList.remove("live"); c.textContent = ""; }, 2500);
  }
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(refresh, 200);
}
function status(t) { $("#status").textContent = t; }

// ---------------------------------------------------------------- 시작
async function boot() {
  hydrateIcons();
  document.documentElement.dataset.theme = store.get("theme2", "studio");
  laneH = parseInt(store.get("laneH", "26"));
  setMode(store.get("mode", "simple"));
  if (store.get("view", "arrange") === "session") setView("session");
  const projects = await (await fetch("/api/projects")).json();
  const sel = $("#project");
  sel.innerHTML = "";
  sel.append(new Option("＋ 새 곡…", "__new"));
  let ping = null;
  for (let i = 0; i < 20 && !ping; i++) {                       // 엔진이 아직 붙는 중이면 잠깐 기다려 다시(앱 첫 실행)
    try { ping = await call("ping"); } catch (e) { status("엔진 기다리는 중… " + e.message); await new Promise((r) => setTimeout(r, 1000)); }
  }
  if (!ping) { status("엔진에 연결하지 못했습니다 — 앱을 다시 켜 보세요"); return; }
  const current = (ping.edit || "").split(/[\\/]/).slice(-2, -1)[0];
  for (const p of projects) sel.append(new Option(p, p, false, p === current));
  sel.onchange = async () => {
    if (sel.value === "__new") { info = null; drawWelcome(); return; }
    const ep = await (await fetch(`/api/edit_path?song=${encodeURIComponent(sel.value)}`)).json();
    await call("edit.load", { path: ep.path });
    pxPerBeat = null; selClip = null; setTimeSel(null);
    $("#feed").innerHTML = "";
    refresh();
  };
  loadDevices(); loadSounds(); drawChips();
  $("#ai").value = store.get("ai", "claude");
  $("#ai").onchange = () => { store.set("ai", $("#ai").value); if (!aiReady()) drawConnect(); };
  await checkAI();
  if (!aiReady()) drawConnect();
  else if (!current) { sel.value = "__new"; drawWelcome(); }
  if (current) refresh().then(() => { if (selected) call("track.select", { track: selected }).catch(() => {}); });
  call("transport.state").then((st) => { startMarker = st.position; dawOnState(st); }).catch(() => {});
}

function setMode(m) {
  document.body.classList.toggle("simple", m === "simple");
  $("#mode").textContent = m === "simple" ? "쉬운 모드" : "프로 모드";
  $("#mode").classList.toggle("on", m === "pro");
  store.set("mode", m);
  if (m === "simple" && $("#devices").classList.contains("on")) showTab("mixer");
}
$("#mode").onclick = () => setMode(document.body.classList.contains("simple") ? "pro" : "simple");

async function loadDevices() {
  const d = await call("audio.devices");
  const sel = $("#device"); sel.innerHTML = "";
  const t = d.types.find((x) => x.type === d.current_type) || d.types[0];
  // 첫 항목 = Windows 기본 따라가기(값 ""). 따로 고른 장치는 기억했다가 다음 실행·엔진 재시작 때 다시 적용
  sel.append(new Option(`시스템 기본${d.default ? ` (${d.default})` : ""}`, "", false, !!d.follows_default));
  for (const n of t.outputs) sel.append(new Option(n, n, false, !d.follows_default && n === d.current));
  sel.onchange = () => { store.set("device", sel.value); call("audio.set", { device: sel.value }); };
  const want = store.get("device", "");
  if (want && t.outputs.includes(want) && (d.follows_default || want !== d.current)) { sel.value = want; call("audio.set", { device: want }); }
}

// ---------------------------------------------------------------- AI 연결 · 처음 화면
let aiStatus = {};
async function checkAI() { aiStatus = await (await fetch("/api/ai-status")).json(); return aiStatus; }
function aiReady() { return !!aiStatus[$("#ai").value]?.logged_in; }
const aiName = () => ($("#ai").value === "codex" ? "GPT" : "Claude");

function drawConnect() {
  const feed = $("#feed"); feed.innerHTML = "";
  const w = el("div", "welcome");
  w.append(el("h3", null, "먼저 함께 일할 AI 를 연결해요"),
           el("p", null, "가지고 있는 계정 하나만 연결하면 돼요. 로그인은 브라우저에서 직접 하시고, 비밀번호는 Musicoma 가 보지 않아요."));
  const ex = el("div", "ex");
  for (const [id, name, desc] of [["claude", "Claude", "Anthropic 계정 (Pro/Max 또는 API)"], ["codex", "GPT", "ChatGPT 계정 (Plus/Pro)"]]) {
    const st = aiStatus[id] || {};
    const b = el("button");
    b.innerHTML = `<span><b>${name}</b> — ${desc}<br><small>${!st.installed ? "프로그램이 설치되어 있지 않아요" : st.logged_in ? "✓ 연결됨 · 눌러서 이걸로 시작" : "연결 안 됨 · 눌러서 로그인 창 열기"}</small></span>`;
    b.onclick = async () => {
      if (st.logged_in) { $("#ai").value = id; store.set("ai", id); drawWelcome(); return; }
      if (!st.installed) return;
      await fetch("/api/ai-login?provider=" + id);
      feedMsg("tool", `${name} 로그인 창을 열었어요. 로그인을 마치면 ‘다시 확인’을 눌러 주세요.`);
    };
    ex.append(b);
  }
  const again = el("button", null, "다시 확인");
  again.onclick = async () => { await checkAI(); aiReady() ? drawWelcome() : drawConnect(); };
  w.append(ex, again);
  feed.append(w);
}

async function drawWelcome() {
  const styles = await (await fetch("/api/styles")).json();
  if (!info) { $("#hdr-list").innerHTML = ""; $("#lanes").innerHTML = ""; $("#ruler").innerHTML = ""; }
  const feed = $("#feed"); feed.innerHTML = "";
  const w = el("div", "welcome");
  w.append(el("h3", null, "어떤 곡을 만들까요?"),
           el("p", null, `원하는 느낌을 말로 적어 주세요. ${aiName()} 가 곡을 짓고, 다 되면 바로 들어볼 수 있어요. 직접 만지고 싶으면 ‘프로 모드’를 켜세요.`));
  const ex = el("div", "ex");
  for (const t of ["올드 칸예 스타일에 시티팝 샘플링, 88BPM", "비 오는 밤 듣는 로파이 힙합, 피아노 중심",
                   "80년대 일본 시티팝, 슬랩 베이스와 브라스", "유튜브 브이로그 BGM, 밝고 가벼운 어쿠스틱 1분"]) {
    const b = el("button", null, "“" + t + "”"); b.onclick = () => { $("#ask").value = t; $("#ask").focus(); }; ex.append(b);
  }
  w.append(ex, el("p", "help", "익숙한 장르: " + styles.map((s) => s.name.split(" (")[0]).join(" · ") + " · 그 밖의 장르도 말하면 새로 공부해서 만듭니다."));
  feed.append(w);
  $("#ask-new").checked = true;
}

// ---------------------------------------------------------------- 프로듀서 패널
const CHIPS = [["더 따뜻하게", "전체적으로 더 따뜻하게 해줘"], ["킥 펀치", "킥을 더 펀치있게"], ["스네어 뒤로", "스네어를 살짝 레이드백"],
  ["공간감", "공간감을 조금 더"], ["빈티지", "더 빈티지하고 먼지낀 느낌으로"], ["에너지 ↑", "훅의 에너지를 올려줘"],
  ["단순하게", "너무 복잡해, 조금 단순하게"], ["밸런스 점검", "믹스 밸런스를 측정해서 문제 있으면 고쳐줘"], ["이 버전 저장", "지금 상태 좋아, 버전으로 저장해줘"]];
function drawChips() {
  const c = $("#chips"); c.innerHTML = "";
  for (const [label, text] of CHIPS) { const b = el("button", null, label); b.dataset.tip = text; b.onclick = () => ask(text); c.append(b); }
}
function feedMsg(cls, text) {
  const f = $("#feed"); f.querySelector(".welcome")?.remove();
  const m = el("div", "msg " + cls, text); f.append(m); f.scrollTop = f.scrollHeight; return m;
}
function ask(text, extra = "") {
  text = (text ?? $("#ask").value).trim();
  if (!text || busy) return;
  if (!aiReady()) { drawConnect(); return; }
  const sel = $("#project").value;
  feedMsg("me", text + (extra ? "\n· " + extra : ""));
  $("#ask").value = "";
  busy = true; $("#ask-send").lastChild.textContent = "작업 중…";
  ws.send(JSON.stringify({ ask: extra ? `${text}\n(${extra})` : text, ai: $("#ai").value,
                           song: sel === "__new" ? "" : sel, track: selected || "", new: $("#ask-new").checked }));
  $("#ask-new").checked = false;
}
$("#ask-send").onclick = () => ask();
$("#ask").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); } });

const TOOL_LABEL = { song_status: "곡 상태 확인", render: "렌더·측정", render_stems: "트랙별 측정", build_spec: "곡 짓기",
  knowledge_style: "장르 카드 읽기", knowledge_tweak: "조정 방법 찾기", balance: "밸런스 맞추기", engine: "엔진 조작", compose: "작곡",
  crate: "샘플 가공", snapshot: "버전 저장", song_log: "기록", song_track: "트랙 조정", song_new: "새 곡", song_section: "섹션",
  show_device: "플러그인 창", transcribe: "채보", knowledge_sounds: "소리 목록", recipe_chipmunk_soul: "칩멍크 소울 레시피" };
async function onClaude(m) {
  if (m.claude === "start") feedMsg("tool", aiName() + " 가 곡을 보는 중…");
  else if (m.claude === "tool") feedMsg("tool", "▸ " + (TOOL_LABEL[m.name] || m.name) + (m.detail ? " · " + m.detail : ""));
  else if (m.claude === "text") feedMsg("ai", m.text);
  else if (m.claude === "error") feedMsg("err", "오류: " + m.text);
  else if (m.claude === "done") {
    busy = false; $("#ask-send").lastChild.textContent = "보내기";
    const projects = await (await fetch("/api/projects")).json();
    const sel = $("#project"), known = [...sel.options].map((o) => o.value);
    for (const p of projects) if (!known.includes(p)) sel.append(new Option(p, p));
    const ping = await call("ping");
    const current = (ping.edit || "").split(/[\\/]/).slice(-2, -1)[0];
    if (current && sel.value !== current) { sel.value = current; pxPerBeat = null; }
    refresh();
  }
}

async function drawRenders() {
  const name = $("#project").value, box = $("#renders"); box.innerHTML = "";
  if (!name || name === "__new") return;
  const list = await (await fetch("/api/renders?name=" + encodeURIComponent(name))).json();
  if (!list.length) { box.append(el("div", "help", "아직 렌더가 없어요. ‘들어볼래’라고 요청하면 만들어 드려요.")); return; }
  for (const r of list.slice(0, 6)) {
    const row = el("div", "rnd");
    row.append(el("span", "lbl", r.name.replace(name + "_", "")), el("span", "meta", new Date(r.mtime * 1000).toLocaleTimeString().slice(0, 5)));
    const a = el("audio"); a.controls = true; a.preload = "none"; a.src = "/api/file?path=" + encodeURIComponent(r.wav);
    a.onplay = () => r.png && showEars(r);
    row.append(a); box.append(row);
  }
  if (list[0].png) showEars(list[0], false);
}
function showEars(r, switchTab = true) {
  const e = $("#ears"); e.innerHTML = "";
  if (r.png) { const img = el("img"); img.src = "/api/file?path=" + encodeURIComponent(r.png); e.append(img); }
  e.append(el("div", "ears-nums", r.name + "\n\n파형 · 스펙트로그램 · 대역 에너지\nAI 가 이 그림과 숫자로 '듣고' 고칩니다."));
  if (switchTab) showTab("ears");
}

// ---------------------------------------------------------------- 브라우저
async function loadSounds() {
  sounds = await (await fetch("/api/sounds")).json();
  const groups = ["SFZ", "Surge XT", ...new Set(sounds.map((s) => s.group).filter((g) => g.startsWith("Surge:"))), "Effects"];
  const cats = $("#cats"); cats.innerHTML = "";
  for (const g of groups) { const b = el("button", g === cat ? "on" : "", g.replace("Surge: ", "")); b.onclick = () => { cat = g; loadSounds(); }; cats.append(b); }
  drawItems();
}
function drawItems() {
  const q = $("#search").value.toLowerCase(), list = $("#items"); list.innerHTML = "";
  for (const s of sounds.filter((s) => (q ? (s.name + s.note).toLowerCase().includes(q) : s.group === cat)).slice(0, 400)) {
    const it = el("div", "item"); it.append(document.createTextNode(s.name));
    if (q) it.append(el("span", "g", s.group));
    it.dataset.tip = (s.note ? s.note + " — " : "") + "더블클릭: 선택한 트랙에 넣기";
    it.ondblclick = () => addSound(s);
    list.append(it);
  }
}
$("#search").oninput = drawItems;
async function addSound(s) {
  if (!selected) return;
  if (s.group === "Effects") await call("device.add", { track: selected, device: s.name });
  else {
    const r = await (await fetch("/api/resolve?name=" + encodeURIComponent(s.name))).json();
    const dev = await call("device.add", { track: selected, device: r.device, ...(r.sfz ? { sfz: r.sfz } : {}), index: 0 });
    if (r.patch) await call("device.load_file", { track: selected, device: dev.device, path: r.patch });
  }
  refresh();
}

// ---------------------------------------------------------------- 어레인지먼트
async function refresh() {
  try { info = await call("edit.info"); } catch (e) { info = null; }
  const name = $("#project").value;
  song = name && name !== "__new" ? await (await fetch("/api/song?name=" + encodeURIComponent(name))).json() : {};
  if (!info) return;
  $("#bpm").value = info.bpm.toFixed(1);
  const isRet = (t) => /return/i.test(((song.tracks || {})[t.name] || {}).role || "");
  info.tracks.sort((a, b) => isRet(a) - isRet(b) || a.track - b.track);
  if (selected == null || !info.tracks.find((t) => t.name === selected)) selected = info.tracks[0]?.name;
  if (pxPerBeat == null) fit();
  drawArrange(); drawDetail(); drawRenders();
}
const totalBeats = () => Math.max(32, Math.ceil(info.length_beats / 4) * 4 + 8);
function fit() { pxPerBeat = Math.max(1.2, (($("#lanes-wrap").clientWidth || 1000) - 20) / totalBeats()); }
// 격자: 확대 정도에 맞춘 기본 단위 × 2^gridShift (Ctrl+1 촘촘히 · Ctrl+2 넓게), snapOn=false 면 자유(Ctrl+4) — daw.js
let gridShift = parseInt(store.get("gridShift", "0")) || 0, snapOn = store.get("snapOn", "1") !== "0";
const autoUnit = () => (pxPerBeat * 4 < 24 ? 4 : pxPerBeat < 10 ? 1 : 0.25);
const snapUnit = () => Math.min(16, Math.max(1 / 16, autoUnit() * 2 ** gridShift));
const snapB = (b, free) => (free || !snapOn ? b : Math.round(b / snapUnit()) * snapUnit());

function drawArrange() {
  const tb = totalBeats(), width = tb * pxPerBeat;
  const hdr = $("#hdr-list"), lanes = $("#lanes"), ruler = $("#ruler");
  hdr.innerHTML = ""; lanes.innerHTML = ""; ruler.innerHTML = "";
  ruler.style.width = lanes.style.width = width + "px";
  const barStep = pxPerBeat * 4 < 20 ? (pxPerBeat * 16 < 20 ? 16 : 4) : 1;
  for (let b = 0; b < tb / 4; b += barStep) { const bar = el("div", "bar", String(b + 1)); bar.style.left = b * 4 * pxPerBeat + "px"; ruler.append(bar); }
  for (const s of song.sections || []) {
    const sec = el("div", "sec", s.name);
    sec.style.left = s.start_bar * 4 * pxPerBeat + "px"; sec.style.width = Math.max(4, s.bars * 4 * pxPerBeat - 2) + "px";
    sec.dataset.tip = `${s.name} · ${s.start_bar + 1}마디부터 ${s.bars}마디 — 클릭: 구간 선택 · 더블클릭: 여기서 재생`;
    sec.onclick = (e) => { e.stopPropagation(); setTimeSel({ a: s.start_bar * 4, b: (s.start_bar + s.bars) * 4, track: null }); };
    sec.ondblclick = (e) => { e.stopPropagation(); call("transport.play", { from: s.start_bar * 4 }).then(startPoll); };
    ruler.append(sec);
  }
  const noteJobs = [];
  let prevRet = false;
  info.tracks.forEach((t, i) => {
    const meta = (song.tracks || {})[t.name] || {}, col = colorFor(i, meta.color), ret = /return/i.test(meta.role || "");
    const h = el("div", "th" + (t.name === selected ? " sel" : ""));
    h.style.height = laneH + "px";
    const chip = el("div", "chip"); chip.style.background = col;
    const m = el("button", "m" + (t.mute ? " on" : ""), "M"); m.dataset.tip = "뮤트(소리 끄기)";
    const s = el("button", "s" + (t.solo ? " on" : ""), "S"); s.dataset.tip = "솔로(이 트랙만 듣기)";
    m.onpointerdown = (e) => { e.stopPropagation(); call("track.set", { track: t.name, mute: !t.mute }).then(refresh); };
    s.onpointerdown = (e) => { e.stopPropagation(); call("track.set", { track: t.name, solo: !t.solo }).then(refresh); };
    h.dataset.tip = (meta.role || "") + (t.devices.length ? " · " + t.devices.map((d) => d.name).join(", ") : "");
    const arm = el("button", "arm" + (armed.has(t.name) ? " on" : "")); arm.dataset.icon = "arm"; arm.dataset.iconSize = "10";
    arm.dataset.tip = "녹음 대기(암) — 켜면 MIDI 키보드 연주가 이 트랙에 녹음됩니다";
    arm.onpointerdown = (e) => { e.stopPropagation(); toggleArm(t.name); };
    h.append(chip, el("div", "name", t.name), arm, m, s);
    h.onpointerdown = () => select(t.name);
    hdr.append(h);
    const lane = el("div", "lane" + (t.name === selected ? " sel" : "") + (ret && !prevRet ? " ret" : ""));
    prevRet = ret; lane.style.height = laneH + "px"; lane.dataset.track = t.name;
    for (const c of t.clips) {
      const box = el("div", "clip" + (c.type === "audio" ? " audio" : "") +
        (selClip && selClip.track === t.name && selClip.clip === c.clip ? " sel" : ""));
      box.style.left = c.start * pxPerBeat + "px";
      box.style.width = Math.max(2, (c.end - c.start) * pxPerBeat - 1) + "px";
      box.style.background = col;
      box.dataset.tip = `${c.name} · ${barOf(c.start)}마디부터 ${((c.end - c.start) / 4).toFixed(1)}마디 — 끌기: 이동 · Alt+끌기: 복제 · 오른쪽 끝: 길이 · ${c.type === "midi" ? "더블클릭: 피아노롤 · " : ""}Del: 삭제 · Ctrl+E: 재생 위치에서 자르기`;
      if (laneH >= 20 && (c.end - c.start) * pxPerBeat > 30) box.append(el("span", "label", c.name));
      const rz = el("div", "rz"); box.append(rz);
      clipHandlers(box, rz, t, c);
      lane.append(box);
      if (c.type === "midi" && c.notes && laneH >= 22) noteJobs.push([box, t.name, c]);
    }
    lane.onpointerdown = (e) => { if (e.target === lane) startTimeSel(e, t.name); };
    lanes.append(lane);
  });
  for (const [box, track, c] of noteJobs) drawNotes(box, track, c);
  hydrateIcons(hdr);
  drawOverview(); drawTimeSel(); dawDecorate();
  if (document.body.classList.contains("session-view")) drawSession();
}

function select(name) {
  selected = name;
  call("track.select", { track: name }).catch(() => {});      // 고른 트랙으로 연주가 들어간다(Ableton 처럼)
  document.querySelectorAll(".th").forEach((h, i) => h.classList.toggle("sel", info.tracks[i]?.name === name));
  document.querySelectorAll(".lane").forEach((l, i) => l.classList.toggle("sel", info.tracks[i]?.name === name));
  drawDetail();
}

// 클립: 1:1 끌기(잡은 지점 유지) · Alt=복제 · 오른쪽 끝=길이 · 더블클릭=피아노롤
function clipHandlers(box, rz, t, c) {
  box.onpointerdown = (e) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    selClip = { track: t.name, clip: c.clip, start: c.start, end: c.end, type: c.type };
    document.querySelectorAll(".clip.sel").forEach((x) => x.classList.remove("sel")); box.classList.add("sel");
    if (selected !== t.name) select(t.name);
    const resizing = e.target === rz, x0 = e.clientX, left0 = c.start * pxPerBeat, w0 = (c.end - c.start) * pxPerBeat;
    let moved = false, ghost = null;
    box.setPointerCapture(e.pointerId);
    box.onpointermove = (ev) => {
      const dx = ev.clientX - x0;
      if (!moved && Math.abs(dx) < 4) return;                           // 작은 떨림은 무시(히스테리시스)
      moved = true;
      if (resizing) {
        const len = Math.max(snapUnit(), snapB((w0 + dx) / pxPerBeat, ev.shiftKey));
        box.style.width = len * pxPerBeat - 1 + "px";
        status(`길이 ${(len / 4).toFixed(2)}마디`);
      } else {
        if (ev.altKey && !ghost) { ghost = box.cloneNode(true); ghost.classList.add("ghost"); box.parentElement.append(ghost); }
        const nb = Math.max(0, snapB((left0 + dx) / pxPerBeat, ev.shiftKey));
        (ghost || box).style.left = nb * pxPerBeat + "px";
        status(`${ghost ? "복제" : "이동"} → ${barOf(nb)}마디 ${((nb % 4) + 1).toFixed(2)}박  (Shift: 격자 무시)`);
      }
    };
    box.onpointerup = async (ev) => {
      box.onpointermove = null;
      if (!moved) return;
      const dx = ev.clientX - x0;
      if (resizing) await call("clip.set", { track: t.name, clip: c.clip, length: Math.max(snapUnit(), snapB((w0 + dx) / pxPerBeat, ev.shiftKey)) });
      else {
        const nb = Math.max(0, snapB((left0 + dx) / pxPerBeat, ev.shiftKey));
        if (ghost) await call("clip.duplicate", { track: t.name, clip: c.clip, start: nb });
        else await call("clip.set", { track: t.name, clip: c.clip, start: nb });
      }
      refresh();
    };
  };
  box.ondblclick = () => { if (c.type === "midi") openPiano(t.name, c); };
}

// 시간 구간 선택 → 떠 있는 AI 입력줄
function startTimeSel(e, track) {
  const wrap = $("#lanes-wrap"), r = wrap.getBoundingClientRect();
  const beatAt = (cx) => Math.max(0, snapB((cx - r.left + wrap.scrollLeft) / pxPerBeat));
  const a = beatAt(e.clientX);
  if (selected !== track) select(track);
  const lane = e.currentTarget; lane.setPointerCapture(e.pointerId);
  let b = a;
  lane.onpointermove = (ev) => { b = beatAt(ev.clientX); timeSel = { a: Math.min(a, b), b: Math.max(a, b), track }; drawTimeSel(); };
  lane.onpointerup = () => {
    lane.onpointermove = null;
    if (Math.abs(b - a) < snapUnit()) { setTimeSel(null); dawLocate(a); return; }   // 그냥 클릭 = 시작 마커(재생 중이면 그 자리로)
    setTimeSel({ a: Math.min(a, b), b: Math.max(a, b), track });
  };
}
function setTimeSel(s) { timeSel = s; drawTimeSel(); showCtx(!!s); if (s) setTimeout(() => $("#ctx-ask").focus(), 30); }
function drawTimeSel() {
  const box = $("#selection");
  if (!timeSel || !info) { box.style.display = "none"; return; }
  box.style.display = "block";
  box.style.left = timeSel.a * pxPerBeat + "px"; box.style.width = (timeSel.b - timeSel.a) * pxPerBeat + "px";
  const bars = `${barOf(timeSel.a)}–${barOf(timeSel.b - 0.001)}마디`;
  $("#ctx-range").textContent = timeSel.track ? `${bars} · ${timeSel.track}` : `${bars} · 전체 트랙`;
}
function ctxAsk() {
  const t = $("#ctx-ask").value.trim(); if (!t || !timeSel) return;
  const scope = `범위: ${barOf(timeSel.a)}~${barOf(timeSel.b - 0.001)}마디 (박 ${timeSel.a}~${timeSel.b})` + (timeSel.track ? `, 트랙 '${timeSel.track}'` : ", 전체 트랙") + " — 이 범위 밖은 바꾸지 말 것";
  $("#ctx-ask").value = "";
  ask(t, scope);
}
$("#ctx-send").onclick = ctxAsk;
$("#ctx-ask").addEventListener("keydown", (e) => { if (e.key === "Enter") ctxAsk(); if (e.key === "Escape") setTimeSel(null); });
$("#ctx-close").onclick = () => setTimeSel(null);
$("#ctx-loop").onclick = () => timeSel && call("transport.play", { loop: [timeSel.a, timeSel.b], from: timeSel.a }).then(startPoll);

const noteCache = new Map();
async function drawNotes(box, track, clip) {
  const key = `${$("#project").value}/${track}/${clip.clip}/${clip.notes}/${clip.start}/${clip.end}`;
  let notes = noteCache.get(key);
  if (!notes) { notes = await call("clip.notes", { track, clip: clip.clip }); noteCache.set(key, notes); }
  if (!notes.length) return;
  const cv = el("canvas"); box.append(cv);
  const w = box.clientWidth, h = box.clientHeight;
  const g = setupCanvas(cv, w, h);
  const lo = Math.min(...notes.map((n) => n.pitch)), hi = Math.max(...notes.map((n) => n.pitch));
  const span = Math.max(12, hi - lo + 1), len = clip.end - clip.start, top = 12;
  g.fillStyle = "rgba(0,0,0,.6)";
  for (const n of notes) g.fillRect((n.start / len) * w, h - 2 - ((n.pitch - lo + 1) / span) * (h - top - 2), Math.max(1, (n.length / len) * w - 0.5), Math.max(1, (h - top) / span));
}

function drawOverview() {
  const ov = $("#overview"); ov.querySelector("canvas")?.remove();
  const cv = el("canvas"); ov.prepend(cv);
  const w = ov.clientWidth, h = ov.clientHeight, g = setupCanvas(cv, w, h), tb = totalBeats();
  const rowH = Math.max(1, (h - 2) / Math.max(1, info.tracks.length));
  info.tracks.forEach((t, i) => {
    g.fillStyle = colorFor(i, ((song.tracks || {})[t.name] || {}).color);
    for (const c of t.clips) g.fillRect((c.start / tb) * w, 1 + i * rowH, Math.max(1, ((c.end - c.start) / tb) * w), Math.max(1, rowH - 0.5));
  });
  updateOvView();
  ov.onclick = (e) => { const x = e.clientX - ov.getBoundingClientRect().left, wrap = $("#lanes-wrap"); wrap.scrollLeft = (x / w) * tb * pxPerBeat - wrap.clientWidth / 2; };
}
function updateOvView() {
  if (!info) return;
  const wrap = $("#lanes-wrap"), ov = $("#overview"), v = $("#ov-view"), total = totalBeats() * pxPerBeat;
  v.style.left = (wrap.scrollLeft / total) * ov.clientWidth + "px";
  v.style.width = Math.min(1, wrap.clientWidth / total) * ov.clientWidth + "px";
}
$("#lanes-wrap").addEventListener("scroll", () => { $("#hdr-list").style.transform = `translateY(${-$("#lanes-wrap").scrollTop}px)`; updateOvView(); });
$("#lanes-wrap").addEventListener("wheel", (e) => {
  if (!e.ctrlKey) return; e.preventDefault();
  zoom(e.deltaY < 0 ? 1.25 : 0.8, e.clientX - $("#lanes-wrap").getBoundingClientRect().left);
}, { passive: false });
function zoom(f, anchorX = null) {
  const wrap = $("#lanes-wrap"), ax = anchorX ?? wrap.clientWidth / 2, beatAt = (wrap.scrollLeft + ax) / pxPerBeat;
  pxPerBeat = Math.min(120, Math.max(1, pxPerBeat * f)); drawArrange(); wrap.scrollLeft = beatAt * pxPerBeat - ax;
}
$("#zin").onclick = () => zoom(1.4);
$("#zout").onclick = () => zoom(1 / 1.4);
$("#zfit").onclick = () => { fit(); drawArrange(); $("#lanes-wrap").scrollLeft = 0; };
$("#lanesz").onclick = () => { laneH = laneH === 26 ? 48 : laneH === 48 ? 18 : 26; store.set("laneH", laneH); drawArrange(); };
$("#theme").onclick = () => {
  const t = document.documentElement.dataset.theme === "studio" ? "night" : "studio";
  document.documentElement.dataset.theme = t; store.set("theme2", t);
  if (info) { drawArrange(); drawDetail(); } if (pr) pr.draw();
};
$("#toggle-browser").onclick = () => { $("#main").classList.toggle("no-browser"); $("#toggle-browser").classList.toggle("on"); };
$("#toggle-producer").onclick = () => { $("#main").classList.toggle("no-producer"); $("#toggle-producer").classList.toggle("on"); };

// ---------------------------------------------------------------- 피아노롤
async function openPiano(track, clip) {
  const host = $("#piano");
  if (!pr) {
    pr = new PianoRoll(host, { onSave: async (notes) => {
      if (!pr.target) return;
      await call("clip.set_notes", { track: pr.target.track, clip: pr.target.clip, notes, replace: true });
      status(`노트 ${notes.length}개 저장됨`);
    } });
    pr.onClose = () => { document.body.classList.remove("piano-open"); showTab("mixer"); };
  }
  pr.target = { track, clip: clip.clip };
  const notes = await call("clip.notes", { track, clip: clip.clip });
  document.body.classList.add("piano-open");
  showTab("piano");
  document.body.classList.add("piano-open");
  pr.load(`${track} · ${clip.name} (${barOf(clip.start)}마디부터 ${((clip.end - clip.start) / 4).toFixed(1)}마디)`, notes, clip.end - clip.start);
}

// ---------------------------------------------------------------- 디바이스 · 믹서
function showTab(id) {
  document.querySelectorAll("#detail nav button[data-tab]").forEach((x) => x.classList.toggle("on", x.dataset.tab === id));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t.id === id));
  if (id !== "piano") document.body.classList.remove("piano-open");
}
document.querySelectorAll("#detail nav button[data-tab]").forEach((b) => b.onclick = () => showTab(b.dataset.tab));

let presetList = null;
async function drawTone(t) {
  if (!presetList) presetList = await (await fetch("/api/presets")).json();
  const sel = $("#tone"); sel.innerHTML = "";
  const cur = ((song.tracks || {})[t?.name] || {}).preset || "";
  sel.append(new Option(cur ? "현재: " + cur : "— 음색 고르기 —", ""));
  for (const [role, list] of Object.entries(presetList)) {
    const g = document.createElement("optgroup"); g.label = role;
    for (const p of list) g.append(new Option(p.name, role + "/" + p.key, false, role + "/" + p.key === cur));
    sel.append(g);
  }
  sel.disabled = !t;
  sel.onchange = async () => {
    if (!sel.value || !t) return;
    const [role, key] = sel.value.split("/");
    status("음색 바꾸는 중…");
    const r = await (await fetch(`/api/preset-apply?song=${encodeURIComponent($("#project").value)}&track=${encodeURIComponent(t.name)}&role=${role}&key=${key}`)).json();
    status(r.error ? "실패: " + r.error : `${t.name} → ${r.preset}`);
    refresh();
  };
}

async function drawDetail() {
  const t = info.tracks.find((x) => x.name === selected);
  $("#detail-title").textContent = t ? t.name : "";
  drawTone(t);
  const dev = $("#devices"); dev.innerHTML = "";
  drawMixer();
  if (!t) return;
  if (!t.devices.length) dev.append(el("div", "empty", "이 트랙에 악기·이펙트가 없어요. 왼쪽 브라우저에서 더블클릭하거나, 프로듀서 패널에 ‘이 트랙에 피아노 넣어줘’라고 말해 보세요."));
  for (const d of t.devices) {
    const card = el("div", "dev" + (d.enabled ? "" : " off")), top = el("div", "top");
    const pw = el("button", d.enabled ? "on" : ""); pw.dataset.icon = "power"; pw.dataset.tip = "켜기/끄기(바이패스)";
    pw.onclick = () => call("device.set", { track: t.name, device: d.device, enabled: !d.enabled }).then(refresh);
    const open = el("button"); open.dataset.icon = "open"; open.dataset.tip = "플러그인 원래 창 열기 — 모든 파라미터 직접 조작";
    open.onclick = () => call("device.show", { track: t.name, device: d.device });
    const del = el("button"); del.dataset.icon = "close"; del.dataset.tip = "디바이스 빼기";
    del.onclick = () => call("device.remove", { track: t.name, device: d.device }).then(refresh);
    top.append(pw, el("b", null, d.name), open, del);
    const knobs = el("div", "knobs");
    card.append(top, knobs); dev.append(card);
    hydrateIcons(top);
    call("device.params", { track: t.name, device: d.device }).then((r) => {
      for (const p of r.params.slice(0, 8)) {
        const k = el("div", "knob"), v = el("div", "v", p.text);
        let busyK = false, queued = null;
        const send = (val) => {
          if (busyK) { queued = val; return; }
          busyK = true;
          call("device.set", { track: t.name, device: d.device, params: { [p.id]: val } })
            .then((res) => { if (res.changed[0]) v.textContent = res.changed[0].text; })
            .finally(() => { busyK = false; if (queued != null) { const q = queued; queued = null; send(q); } });
        };
        const kn = new Knob(p.value, { min: p.min, max: p.max, size: 30, onChange: send, tip: p.name });
        Object.assign(k.dataset, { track: t.name, device: d.device, param: p.id, name: p.name });   // MIDI 맵(daw.js)
        k.append(kn.el, el("div", "n", p.name), v); knobs.append(k);
      }
      dawMarkMaps();
    });
  }
}

function drawMixer() {
  const mx = $("#mixer"); mx.innerHTML = ""; faders.clear();
  info.tracks.forEach((t, i) => {
    const s = el("div", "strip");
    const chip = el("div", "chip"); chip.style.background = colorFor(i, ((song.tracks || {})[t.name] || {}).color);
    const pan = new Knob(t.pan ?? 0, { min: -1, max: 1, center: 0, size: 24, tip: "좌우 위치(팬)",
                                       onChange: (v) => call("track.set", { track: t.name, pan: Math.round(v * 100) / 100 }) });
    const db = el("div", "db", (t.volume_db ?? 0).toFixed(1));
    const f = new Fader(t.volume_db ?? 0, (v) => { db.textContent = v <= -99 ? "-∞" : v.toFixed(1); call("track.set", { track: t.name, volume_db: v }); });
    faders.set(t.name, f);
    const btns = el("div", "btns");
    const m = el("button", "m" + (t.mute ? " on" : ""), "M"), so = el("button", "s" + (t.solo ? " on" : ""), "S");
    m.onpointerdown = () => call("track.set", { track: t.name, mute: !t.mute }).then(refresh);
    so.onpointerdown = () => call("track.set", { track: t.name, solo: !t.solo }).then(refresh);
    btns.append(m, so);
    s.append(chip, el("div", "name", t.name), pan.el, f.el, db, btns);
    s.onpointerdown = () => { if (selected !== t.name) select(t.name); };
    mx.append(s);
  });
  const ms = el("div", "strip master");
  masterFader = new Fader(0, () => {}, {});
  masterFader.el.dataset.tip = "마스터 레벨 (0 dB 넘으면 빨간색 — 렌더 때는 마스터링이 맞춰 줍니다)";
  ms.append(el("div", "name", "Master"), masterFader.el, el("div", "db", "out"));
  mx.append(ms);
}

// ---------------------------------------------------------------- 트랜스포트 · 미터
function fmtPos(b) { return `${Math.floor(b / 4) + 1}. ${Math.floor(b % 4) + 1}. ${Math.floor((b % 1) * 4) + 1}`; }
let meterBusy = false;
async function poll() {
  const st = await call("transport.state");
  playing = st.playing;
  $("#play").classList.toggle("on", playing);
  $("#rec").classList.toggle("on", !!st.recording);
  $("#metro").classList.toggle("on", !!st.metronome);
  setPlayheadUI(st.position);
  dawOnState(st);
  if (!meterBusy && $("#mixer").classList.contains("on")) {
    meterBusy = true;
    call("meters").then((m) => {
      for (const [name, f] of faders) f.meter(m.tracks[name]);
      masterFader && masterFader.meter(m.master);
    }).finally(() => { meterBusy = false; });
  }
  if (!playing && scenePlaying != null) { scenePlaying = null; if (document.body.classList.contains("session-view")) drawSession(); }
  if (!playing) { clearInterval(pollTimer); pollTimer = null; for (const f of faders.values()) f.meter(null); masterFader && masterFader.meter(null); }
}
function startPoll() { if (!pollTimer) pollTimer = setInterval(poll, 50); poll(); }
$("#play").onclick = () => (playing ? Promise.resolve() : dawPlay());
let lastStop = 0;
$("#stop").onclick = () => {
  const now = performance.now();
  // 두 번 누르면 처음으로(시작 마커도 0) — Ableton 과 같다
  const twice = now - lastStop < 600;
  const p = call("transport.stop").then(() => (twice ? dawLocate(0, true) : null));
  lastStop = now; p.then(poll);
};
$("#loop").onclick = () => setLoop(!loopSt.on, !loopSt.on && timeSel ? [timeSel.a, timeSel.b] : null);   // 루프 막대는 daw.js
// ---------------------------------------------------------------- 녹음 · 메트로놈 · 탭 템포 · 트랙 추가 · 내보내기
async function toggleArm(name) {
  const on = !armed.has(name);
  try {
    const r = await call("track.arm", { track: name, armed: on });
    on ? armed.add(name) : armed.delete(name);
    status(on ? `${name} 녹음 대기 — 입력: ${r.input}` : `${name} 녹음 대기 해제`);
  } catch (err) { status("녹음 대기 실패: " + err.message + " — MIDI 키보드를 연결했는지 확인하세요"); }
  drawArrange();
}
async function record() {
  if (playing && $("#rec").classList.contains("on")) { await call("transport.stop"); refresh(); return poll(); }
  if (!armed.size) status("녹음 대기(●) 트랙이 없어요 — 트랙 이름 옆 ● 를 먼저 켜세요");
  await call("transport.record"); startPoll();
}
$("#rec").onclick = record;
$("#metro").onclick = () => call("transport.metronome", {}).then((st) => { $("#metro").classList.toggle("on", !!st.metronome); status(st.metronome ? "메트로놈 켬" : "메트로놈 끔"); });
let taps = [];
$("#tap").onclick = () => {
  const now = performance.now();
  taps = taps.filter((t) => now - t < 2500); taps.push(now);
  if (taps.length >= 3) {
    const iv = (taps[taps.length - 1] - taps[0]) / (taps.length - 1), bpm = Math.round(60000 / iv * 10) / 10;
    $("#bpm").value = bpm.toFixed(1); call("edit.set", { bpm }); status(`탭 템포 ${bpm} BPM`);
  } else status("계속 박자에 맞춰 누르세요…");
};
async function addTrack() {
  const n = info ? info.tracks.length + 1 : 1;
  const name = prompt("새 트랙 이름", `Track ${n}`);
  if (!name) return;
  await call("track.add", { name }); selected = name; refresh();
}
$("#addtrack").onclick = addTrack;
async function exportAudio() {
  const name = $("#project").value; if (!name || name === "__new") return;
  status("내보내는 중… (렌더 + 측정)");
  const r = await (await fetch("/api/export?song=" + encodeURIComponent(name))).json();
  status(r.error ? "내보내기 실패: " + r.error : `내보냄 · ${r.file} · ${r.loudness?.lufs_integrated ?? ""} LUFS`);
  drawRenders();
}
$("#export").onclick = exportAudio;

// ---------------------------------------------------------------- 흥얼거리기(마이크) → 알아듣기 → 넣을 곳을 AI 에게
let humRec = null;
async function hum() {
  const btn = $("#hum");
  if (humRec) { humRec.stop(); return; }
  let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch (e) { status("마이크를 쓸 수 없어요: " + e.message); return; }
  const chunks = [];
  humRec = new MediaRecorder(stream);
  humRec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  humRec.onstop = async () => {
    stream.getTracks().forEach((t) => t.stop());
    btn.classList.remove("on"); humRec = null;
    status("알아듣는 중…");
    const blob = new Blob(chunks, { type: "audio/webm" });
    const name = $("#project").value;
    const r = await (await fetch(`/api/hum?song=${encodeURIComponent(name === "__new" ? "" : name)}`, { method: "POST", body: blob })).json();
    if (r.error) { status("못 알아들었어요: " + r.error); return; }
    // 말과 흥얼거림을 나눠 들었다(10-15). 말로 지시까지 했으면 바로 프로듀서에게 보낸다 — 음성 대화로 만드는 첫 단계
    const parts = r.music.map((m, i) => `흥얼거림${r.music.length > 1 ? i + 1 : ""}(${m.mode === "melody" ? "멜로디" : "비트박스"}, ${m.bars}마디, 녹음 템포 ${m.recording_bpm}): ${m.heard.join(" ")} — 파일 ${m.path}`);
    if (r.said) feedMsg("tool", `🎤 들은 말: “${r.said}”`);
    parts.forEach((p) => feedMsg("tool", "🎤 " + p));
    const where = r.place && Object.keys(r.place).length ? ` · 말에서 찾은 배치 ${JSON.stringify(r.place)}` : "";
    if (r.said && r.music.length) {
      ask(r.said, parts.join(" / ") + where + " · hum_listen 결과를 hum_place 로 넣기");
    } else if (r.said) {
      ask(r.said);
    } else {
      $("#ask").value = `방금 흥얼거린 거(${r.music[0].path}) — 어디에 넣을까: 예) 1:20 부터 4번 반복, 플루트로`;
      $("#ask").focus();
      status("들은 것을 프로듀서 패널에 적었어요. 넣을 위치·반복·악기를 말해 주세요.");
    }
  };
  humRec.start(); btn.classList.add("on"); status("말하거나 부르세요(섞어도 돼요)… 다시 누르면 끝");
}
$("#hum").onclick = hum;

// ---------------------------------------------------------------- 딸깍 기능(10-17 외부 피드백): 흥얼거림→악기 · 튜닝/박자/마스터 · 내 목소리 등록
// 소리 얻기: 파일을 올리거나(취소하면) 마이크로 녹음. 둘 다 서버의 sounds/inbox 에 wav 로 남고 경로가 돌아온다.
async function getAudioPath(hint) {
  const useFile = confirm(`${hint}\n\n[확인] 파일 올리기   [취소] 마이크로 녹음`);
  let blob, name = "rec.webm";
  if (useFile) {
    blob = await new Promise((res) => { const i = $("#upl"); i.value = ""; i.onchange = () => res(i.files[0] || null); i.click(); });
    if (!blob) return null;
    name = blob.name;
  } else {
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
    catch (e) { status("마이크를 쓸 수 없어요: " + e.message); return null; }
    const chunks = [], rec = new MediaRecorder(stream);
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    status("녹음 중… 끝나면 확인을 누르세요");
    rec.start();
    await new Promise((res) => setTimeout(res, 300));
    alert("녹음 중입니다 — 다 불렀으면 [확인]");
    await new Promise((res) => { rec.onstop = res; rec.stop(); });
    stream.getTracks().forEach((t) => t.stop());
    blob = new Blob(chunks, { type: "audio/webm" });
  }
  status("올리는 중…");
  const r = await (await fetch(`/api/upload?name=${encodeURIComponent(name)}`, { method: "POST", body: blob })).json();
  if (r.error) { status("실패: " + r.error); return null; }
  return r.path;
}
const curSong = () => { const n = $("#project").value; return n === "__new" ? "" : n; };
$("#hum2inst").onclick = async () => {
  const song = curSong(); if (!song) { status("먼저 곡을 고르세요"); return; }
  const path = await getAudioPath("흥얼거림(또는 연주 녹음)을 악기 연주로 바꿉니다."); if (!path) return;
  const presets = await (await fetch("/api/presets")).json();
  const list = Object.entries(presets).flatMap(([r, v]) => v.map((p) => `${r}/${p.key}`));
  const preset = prompt("어떤 악기로? (role/key)\n" + list.join("  "), "keys/rhodes"); if (!preset) return;
  const at = prompt("어디에? (예: 0 · bar 9 · 1:20)", "0") || "0";
  status("알아듣고 연주하는 중…");
  const r = await (await fetch(`/api/hum_place?song=${encodeURIComponent(song)}&path=${encodeURIComponent(path)}&preset=${encodeURIComponent(preset)}&at=${encodeURIComponent(at)}&lock=0.85`)).json();
  if (r.error) { status("실패: " + r.error); return; }
  feedMsg("tool", `🎵 ${r.track} ← ${preset} · 들은 음: ${(r.heard || []).join(" ")} · ${r.bars}마디 · 마디 ${Math.floor(r.start_beat / 4) + 1}부터`);
  status(`넣었어요: ${r.track} (${r.notes}음)`); refresh();
};
$("#polish").onclick = async () => {
  const song = curSong();
  const kind = prompt("무엇을 다듬을까요?\n tune = 녹음 음정 보정(튜닝)\n tighten = 녹음 박자 보정\n master = 이 곡 최신 렌더 마스터", "tune");
  if (!kind) return;
  let path = "";
  if (kind !== "master") { path = await getAudioPath(kind === "tune" ? "음정을 보정할 녹음(노래·단선율 악기)." : "박자를 보정할 녹음."); if (!path) return; }
  else if (!song) { status("먼저 곡을 고르세요"); return; }
  status("다듬는 중…");
  const r = await (await fetch(`/api/polish?kind=${kind}&song=${encodeURIComponent(song)}&path=${encodeURIComponent(path)}`)).json();
  if (r.error) { status("실패: " + r.error); return; }
  const line = kind === "tune" ? `음 ${r.notes}개 중 ${r.corrected}개 보정 · 어긋남 ${r.mean_cents_before}→${r.mean_cents_after}센트`
             : kind === "tighten" ? `덩어리 ${r.chunks}개 · 평균 ${r.moved_ms_mean} ms 이동` : `${r.result?.lufs} LUFS · 피크 ${r.result?.true_peak}`;
  feedMsg("tool", `✨ ${kind}: ${line}\n파일 ${r.out}`);
  if (kind !== "master") { $("#ask").value = `방금 다듬은 녹음(${r.out})을 곡에 넣어 줘 — 어디에: `; $("#ask").focus(); }
  status("다듬었어요 — 파일 경로를 프로듀서 패널에 적었어요");
};
$("#myvoice").onclick = async () => {
  const path = await getAudioPath("내 목소리 등록 — 아무 노래나 10~20초, 낮은 음부터 높은 음까지 편하게."); if (!path) return;
  const name = prompt("목소리 이름", "my-voice") || "my-voice";
  status("음역대 재는 중…");
  const r = await (await fetch(`/api/voice_register?name=${encodeURIComponent(name)}&path=${encodeURIComponent(path)}`)).json();
  if (r.error) { status("실패: " + r.error); return; }
  feedMsg("tool", `👤 ${name}: 음역 ${r.range[0]}~${r.range[1]} · 편한 음역 ${r.comfortable[0]}~${r.comfortable[1]} · 중앙 ${r.median} · ${r.voice_type} · 음정 흔들림 ${r.pitch_scatter_cents}센트`);
  status("등록했어요 — 앞으로 새 곡의 조성을 이 음역에 맞춥니다(voice_fit)");
};

// ---------------------------------------------------------------- 세션 뷰(섹션 = 씬, 트랙 × 섹션 = 슬롯)
function setView(v) {
  const ses = v === "session";
  document.body.classList.toggle("session-view", ses);
  $("#session").hidden = !ses;
  $("#view-arr").classList.toggle("on", !ses); $("#view-ses").classList.toggle("on", ses);
  store.set("view", v);
  if (ses) drawSession();
}
$("#view-arr").onclick = () => setView("arrange");
$("#view-ses").onclick = () => setView("session");
function launchScene(i, track) {
  const s = (song.sections || [])[i]; if (!s) return;
  scenePlaying = i;
  if (track) select(track);
  call("transport.play", { loop: [s.start_bar * 4, (s.start_bar + s.bars) * 4], from: s.start_bar * 4 }).then(startPoll);
  $("#loop").classList.add("on");
  drawSession();
}
// 슬롯이 '찼는지' = 그 섹션 안에 실제 노트(또는 2박 이상 오디오)가 있는지. 트랙당 긴 MIDI 클립 하나여도 정확히.
const slotNotes = new Map();
async function slotFull(t, a, b) {
  for (const c of t.clips) {
    if (!(c.start < b && c.end > a)) continue;
    if (c.type !== "midi") { if (Math.min(b, c.end) - Math.max(a, c.start) >= 2) return true; continue; }
    const key = `${$("#project").value}/${t.name}/${c.clip}/${c.notes}/${c.start}`;
    if (!slotNotes.has(key)) slotNotes.set(key, await call("clip.notes", { track: t.name, clip: c.clip }));
    if (slotNotes.get(key).some((n) => c.start + n.start >= a && c.start + n.start < b)) return true;
  }
  return false;
}
async function drawSession() {
  const box = $("#session");
  if (!info) { box.innerHTML = ""; return; }
  const full = new Map();
  for (const s of song.sections || []) for (const t of info.tracks)
    full.set(t.name + "|" + s.start_bar, await slotFull(t, s.start_bar * 4, (s.start_bar + s.bars) * 4));
  box.innerHTML = "";
  const secs = song.sections || [];
  if (!secs.length) { box.append(el("div", "empty", "섹션이 없는 곡이에요. 프로듀서에게 ‘구성을 나눠줘’라고 하거나 어레인지먼트에서 작업하세요.")); return; }
  const tbl = el("table"), head = el("tr");
  head.append(el("th", null, "#"));
  info.tracks.forEach((t, i) => {
    const th = el("th"); const c = el("span", "chip"); c.style.background = colorFor(i, ((song.tracks || {})[t.name] || {}).color);
    th.append(c, document.createTextNode(t.name)); th.onclick = () => select(t.name); head.append(th);
  });
  head.append(el("th", null, "씬 (섹션)"));
  const thead = el("thead"); thead.append(head); tbl.append(thead);
  const tb = el("tbody");
  secs.forEach((s, si) => {
    const tr = el("tr"); tr.append(el("td", null, String(si + 1)));
    const a = s.start_bar * 4, b = (s.start_bar + s.bars) * 4;
    info.tracks.forEach((t, ti) => {
      const has = full.get(t.name + "|" + s.start_bar);
      const td = el("td", "slot " + (has ? "full" : "empty-slot") + (scenePlaying === si ? " playing" : ""), has ? s.name : "");
      if (has) td.style.background = colorFor(ti, ((song.tracks || {})[t.name] || {}).color);
      td.dataset.tip = has ? `${t.name} · ${s.name} — 클릭: 이 섹션 반복 재생` : "빈 슬롯";
      if (has) td.onclick = () => launchScene(si, t.name);
      tr.append(td);
    });
    const sc = el("td", "scene" + (scenePlaying === si ? " playing" : ""), `${s.name} · ${s.bars}마디`);
    sc.dataset.tip = "씬 띄우기 — 이 섹션의 모든 트랙을 반복 재생";
    sc.onclick = () => launchScene(si);
    tr.append(sc); tb.append(tr);
  });
  tbl.append(tb); box.append(tbl);
}

$("#bpm").onchange = () => call("edit.set", { bpm: parseFloat($("#bpm").value) });
$("#undo").onclick = () => call("edit.undo").then(refresh);
$("#redo").onclick = () => call("edit.redo").then(refresh);

document.addEventListener("keydown", (e) => {
  const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName);
  if (typing) return;
  if (dawKeyDown(e)) return;                                   // 컴퓨터 MIDI 키보드·격자·루프·맵 모드(daw.js)
  // Space: 멈춰 있으면 시작 마커부터, Shift+Space: 멈춘 곳에서 이어서, 재생 중이면 멈춤
  if (e.code === "Space") { e.preventDefault(); (playing ? call("transport.stop").then(poll) : dawPlay(!e.shiftKey)); }
  else if (e.ctrlKey && e.key.toLowerCase() === "z") { e.preventDefault(); call(e.shiftKey ? "edit.redo" : "edit.undo").then(refresh); }
  else if (e.ctrlKey && e.key.toLowerCase() === "y") { e.preventDefault(); call("edit.redo").then(refresh); }
  else if (e.key === "Escape") setTimeSel(null);
  else if (e.key === "Tab") { e.preventDefault(); setView(document.body.classList.contains("session-view") ? "arrange" : "session"); }
  else if (e.key === "F9") { e.preventDefault(); record(); }
  else if (e.ctrlKey && e.key.toLowerCase() === "t") { e.preventDefault(); addTrack(); }
  else if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "r") { e.preventDefault(); exportAudio(); }
  else if ($("#piano").classList.contains("on")) return;               // 피아노롤이 열려 있으면 거기서 처리
  else if ((e.key === "Delete" || e.key === "Backspace") && selClip) { e.preventDefault(); call("clip.remove", { track: selClip.track, clip: selClip.clip }).then(() => { selClip = null; refresh(); }); }
  else if (e.ctrlKey && e.key.toLowerCase() === "d" && selClip) { e.preventDefault(); call("clip.duplicate", { track: selClip.track, clip: selClip.clip }).then(refresh); }
  else if (e.ctrlKey && e.key.toLowerCase() === "e" && selClip) {
    e.preventDefault();
    call("transport.state").then((st) => call("clip.split", { track: selClip.track, clip: selClip.clip, at: st.position })).then(refresh).catch((err) => status(err.message));
  }
});
window.addEventListener("resize", () => { if (info) drawOverview(); });
document.addEventListener("mouseover", (e) => {
  const t = e.target.closest("[title],[data-tip]"); if (!t) return;
  if (t.title) { t.dataset.tip = t.title; t.removeAttribute("title"); }
  status(t.dataset.tip);
});

connect();
