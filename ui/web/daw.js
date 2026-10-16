// Musicoma — Ableton 식 편집 손맛(10-17). app.js 다음에 읽힌다(app.js 의 전역을 쓴다).
//   시작 마커(Insert Marker) · 눈금자 스크럽 · 루프 막대 · 격자(Ctrl+1/2/4) · 따라가기(Ctrl+Shift+F)
//   컴퓨터 MIDI 키보드(M: A~; = 흰·검은 건반, Z/X 옥타브, C/V 세기) · MIDI 맵 모드(Ctrl+M) · 양자화(Ctrl+U)
//   MIDI 입력 표시등 · 루프 켜기(Ctrl+L = 선택 구간으로) · Home = 처음으로
'use strict';

let startMarker = 0;                         // 멈춘 상태에서 Space/재생을 누르면 여기서 시작(Ableton 의 Insert Marker)
let follow = store.get("follow", "1") !== "0";
const loopSt = { a: 0, b: 0, on: false, dragging: false };
let lastNoteSeq = null, lastCcSeq = null;
let mapPending = null;                       // MIDI 맵: 고른 파라미터 — 다음에 움직인 컨트롤러가 여기에 붙는다
let mapList = [];

// ───────── 격자 ─────────
function gridLabel() {
  const u = snapUnit();
  return u >= 4 ? `${u / 4}마디` : u >= 1 ? `1/${4 / u}` : `1/${Math.round(4 / u)}`;
}
function gridKey(e) {
  if (!e.ctrlKey || e.shiftKey || e.altKey) return false;
  if (e.key === "1") { gridShift = Math.max(-4, gridShift - 1); }          // 촘촘히
  else if (e.key === "2") { gridShift = Math.min(4, gridShift + 1); }      // 넓게
  else if (e.key === "4") { snapOn = !snapOn; }
  else return false;
  e.preventDefault();
  store.set("gridShift", gridShift); store.set("snapOn", snapOn ? "1" : "0");
  drawArrange();
  status(snapOn ? `격자 ${gridLabel()} (Ctrl+1 촘촘히 · Ctrl+2 넓게 · Ctrl+4 끄기)` : "격자 끔 — 자유롭게 놓입니다 (Ctrl+4 켜기)");
  return true;
}

// ───────── 재생 위치 · 시작 마커 ─────────
function setPlayheadUI(pos) {
  const ph = $("#playhead"); ph.style.display = "block"; ph.style.left = pos * pxPerBeat + "px";
  $("#pos").textContent = fmtPos(pos);
}
function drawMarker() {
  const ruler = $("#ruler");
  let m = ruler.querySelector(".marker");
  if (!m) { m = el("div", "marker"); m.dataset.tip = "시작 마커 — 멈춘 상태에서 Space 를 누르면 여기서 재생(Shift+Space: 멈춘 곳에서 이어서)"; ruler.append(m); }
  m.style.left = startMarker * pxPerBeat + "px";
}
let locBusy = false, locNext = null;
async function dawLocate(b, moveMarker = !playing) {
  b = Math.max(0, b);
  if (moveMarker) { startMarker = b; drawMarker(); }
  setPlayheadUI(b);
  if (locBusy) { locNext = b; return; }
  locBusy = true;
  try { await call("transport.locate", { beat: b }); }
  catch (e) { status(e.message); }
  finally {
    locBusy = false;
    if (locNext != null) { const q = locNext; locNext = null; dawLocate(q, false); }
  }
}
function dawPlay(fromMarker = true) {
  return call("transport.play", fromMarker ? { from: startMarker } : {}).then(startPoll);
}
const rulerBeat = (cx, free) => Math.max(0, snapB((cx - $("#ruler").getBoundingClientRect().left) / pxPerBeat, free));

// ───────── 루프 막대 ─────────
function defaultLoop() {
  if (timeSel) return [timeSel.a, timeSel.b];
  const s = (song.sections || []).find((x) => x.start_bar * 4 <= startMarker && (x.start_bar + x.bars) * 4 > startMarker) || (song.sections || [])[0];
  if (s) return [s.start_bar * 4, (s.start_bar + s.bars) * 4];
  const a = Math.floor(startMarker / 4) * 4;
  return [a, a + 16];
}
async function setLoop(on, range) {
  if (range) { loopSt.a = range[0]; loopSt.b = range[1]; }
  if (on && !(loopSt.b > loopSt.a)) [loopSt.a, loopSt.b] = defaultLoop();
  loopSt.on = on;
  $("#loop").classList.toggle("on", on);
  await call("transport.loop", { start: loopSt.a, end: loopSt.b, enabled: on });
  drawLoopBrace();
  status(on ? `루프 ${barOf(loopSt.a)}–${barOf(loopSt.b - 0.001)}마디 (막대 끌기: 옮기기 · 양 끝: 길이 · 클릭: 끄기)` : "루프 끔");
}
function drawLoopBrace() {
  const ruler = $("#ruler");
  ruler.querySelector(".loopbrace")?.remove();
  if (!(loopSt.b > loopSt.a)) return;
  const lb = el("div", "loopbrace" + (loopSt.on ? " on" : ""));
  const L = el("div", "lb-h l"), R = el("div", "lb-h r");
  lb.append(L, R);
  lb.style.left = loopSt.a * pxPerBeat + "px"; lb.style.width = Math.max(4, (loopSt.b - loopSt.a) * pxPerBeat) + "px";
  lb.dataset.tip = "루프 구간 — 끌기: 옮기기 · 양 끝: 길이 · 클릭: 루프 켜기/끄기 · Ctrl+L: 선택 구간으로 루프";
  lb.onpointerdown = (e) => {
    if (e.button !== 0) return;
    e.stopPropagation(); e.preventDefault();
    const mode = e.target === L ? "l" : e.target === R ? "r" : "m", x0 = e.clientX, a0 = loopSt.a, b0 = loopSt.b;
    let moved = false;
    loopSt.dragging = true;
    lb.setPointerCapture(e.pointerId);
    lb.onpointermove = (ev) => {
      if (!moved && Math.abs(ev.clientX - x0) < 3) return;
      moved = true;
      const d = (ev.clientX - x0) / pxPerBeat, free = ev.altKey || ev.shiftKey;
      if (mode === "m") { const na = Math.max(0, snapB(a0 + d, free)); loopSt.a = na; loopSt.b = na + (b0 - a0); }
      else if (mode === "l") loopSt.a = Math.min(b0 - (free ? 0.0625 : snapUnit()), Math.max(0, snapB(a0 + d, free)));
      else loopSt.b = Math.max(a0 + (free ? 0.0625 : snapUnit()), snapB(b0 + d, free));
      lb.style.left = loopSt.a * pxPerBeat + "px"; lb.style.width = (loopSt.b - loopSt.a) * pxPerBeat + "px";
      status(`루프 ${barOf(loopSt.a)}마디 ${((loopSt.a % 4) + 1).toFixed(2)}박 – ${barOf(loopSt.b - 0.001)}마디 (Shift/Alt: 격자 무시)`);
    };
    lb.onpointerup = () => {
      lb.onpointermove = null; loopSt.dragging = false;
      if (moved) call("transport.loop", { start: loopSt.a, end: loopSt.b });
      else setLoop(!loopSt.on);
    };
  };
  ruler.append(lb);
}

// ───────── 눈금자 · 격자선 (drawArrange 끝에서 부른다) ─────────
function dawDecorate() {
  const ruler = $("#ruler"), lanes = $("#lanes");
  ruler.onpointerdown = (e) => {
    if (e.button !== 0 || e.target.closest(".sec,.loopbrace")) return;
    e.preventDefault();
    ruler.setPointerCapture(e.pointerId);
    dawLocate(rulerBeat(e.clientX, e.altKey || e.shiftKey));
    ruler.onpointermove = (ev) => dawLocate(rulerBeat(ev.clientX, ev.altKey || ev.shiftKey));
    ruler.onpointerup = () => { ruler.onpointermove = null; };
  };
  ruler.ondblclick = (e) => {
    if (e.target.closest(".sec,.loopbrace")) return;
    startMarker = rulerBeat(e.clientX, e.altKey || e.shiftKey); drawMarker(); dawPlay();
  };
  ruler.dataset.tip = "클릭·끌기: 재생 위치(멈춰 있으면 시작 마커도) · 더블클릭: 거기서 재생 · Shift/Alt: 격자 무시";
  // 격자선: 마디(진하게) + 현재 격자 단위
  const unit = snapUnit() * pxPerBeat, bar = 4 * pxPerBeat;
  lanes.style.setProperty("--gridimg", snapOn && unit >= 4
    ? "linear-gradient(to right, var(--grid-bar) 1px, transparent 1px), linear-gradient(to right, var(--grid-unit) 1px, transparent 1px)"
    : "linear-gradient(to right, var(--grid-bar) 1px, transparent 1px)");
  lanes.style.setProperty("--gridsize", snapOn && unit >= 4 ? `${bar}px 100%, ${unit}px 100%` : `${bar}px 100%`);
  $("#grid").textContent = snapOn ? gridLabel() : "격자 끔";
  drawMarker(); drawLoopBrace();
}

// ───────── 상태 받기(재생 중 50ms, 멈춰 있을 때 300ms) ─────────
function dawOnState(st) {
  if (!loopSt.dragging) {
    const changed = loopSt.a !== st.loop[0] || loopSt.b !== st.loop[1] || loopSt.on !== st.looping;
    loopSt.a = st.loop[0]; loopSt.b = st.loop[1]; loopSt.on = st.looping;
    $("#loop").classList.toggle("on", st.looping);
    if (changed) drawLoopBrace();
  }
  if (st.playing && follow) {                 // 따라가기: 화면 오른쪽 끝을 넘으면 한 화면 넘김(Ableton 처럼)
    const wrap = $("#lanes-wrap"), x = st.position * pxPerBeat;
    if (x > wrap.scrollLeft + wrap.clientWidth - 30 || x < wrap.scrollLeft) wrap.scrollLeft = Math.max(0, x - 40);
  }
  const led = $("#midiled");
  if (led) {
    const n = st.note_seq ?? 0, c = st.midi_last?.seq ?? 0;
    if ((lastNoteSeq != null && n !== lastNoteSeq) || (lastCcSeq != null && c !== lastCcSeq)) {
      led.classList.add("on"); clearTimeout(led._t); led._t = setTimeout(() => led.classList.remove("on"), 120);
    }
    led.dataset.tip = `MIDI 입력 ${st.midi_inputs || 0}개 연결 — 깜빡이면 신호가 들어오는 중` + (st.midi_last?.cc >= 0 ? ` · 마지막 CC ${st.midi_last.cc} = ${st.midi_last.value}` : "");
    led.classList.toggle("none", !st.midi_inputs);
  }
  if (mapPending && lastCcSeq != null && st.midi_last && st.midi_last.seq !== lastCcSeq && st.midi_last.cc >= 0) {
    const p = mapPending; mapPending = null;
    call("midi.map", { cc: st.midi_last.cc, track: p.track, device: p.device, param: p.param })
      .then((r) => { status(`CC ${r.cc} → ${r.track} · ${r.param} 연결됨 (Ctrl+M 으로 맵 모드 끝내기)`); drawDetail(); })
      .catch((e) => status("연결 실패: " + e.message));
  }
  lastNoteSeq = st.note_seq ?? 0; lastCcSeq = st.midi_last?.seq ?? 0;
}
setInterval(() => {
  if (pollTimer || !info || !ws || ws.readyState !== 1) return;
  call("transport.state").then(dawOnState).catch(() => {});
  if ($("#mixer").classList.contains("on") && (kbOn || kbHeld.size))     // 멈춰 있어도 건반 연주 미터
    call("meters").then((m) => { for (const [name, f] of faders) f.meter(m.tracks[name]); masterFader && masterFader.meter(m.master); }).catch(() => {});
}, 300);

// ───────── 컴퓨터 MIDI 키보드 (Ableton: M) ─────────
const KB = { KeyA: 0, KeyW: 1, KeyS: 2, KeyE: 3, KeyD: 4, KeyF: 5, KeyT: 6, KeyG: 7, KeyY: 8, KeyH: 9, KeyU: 10, KeyJ: 11,
             KeyK: 12, KeyO: 13, KeyL: 14, KeyP: 15, Semicolon: 16, Quote: 17 };
let kbOn = store.get("kbOn", "0") === "1", kbOct = parseInt(store.get("kbOct", "3")), kbVel = parseInt(store.get("kbVel", "100"));
const kbHeld = new Map();
const noteName = (n) => ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][n % 12] + (Math.floor(n / 12) - 1);
function drawKb() {
  const b = $("#kbd");
  b.classList.toggle("on", kbOn);
  b.textContent = kbOn ? `⌨ ${noteName(12 * (kbOct + 1))} · ${kbVel}` : "⌨";
  b.dataset.tip = "컴퓨터 MIDI 키보드 (M) — A W S E D F T G Y H U J K O L P ; ' = 건반, Z/X 옥타브, C/V 세기. 고른 트랙(또는 녹음 대기 트랙)이 연주됩니다";
}
function kbAllOff() {
  if (!kbHeld.size) return;
  call("midi.inject", { messages: [...kbHeld.values()].map((n) => [0x80, n, 0]) });
  kbHeld.clear();
}
function dawKeyDown(e) {
  if (gridKey(e)) return true;
  if (e.code === "KeyM" && e.ctrlKey && !e.shiftKey) { e.preventDefault(); toggleMapMode(); return true; }
  if (e.code === "KeyM" && !e.ctrlKey && !e.altKey && !e.metaKey) {
    kbOn = !kbOn; store.set("kbOn", kbOn ? "1" : "0"); if (!kbOn) kbAllOff(); drawKb();
    status(kbOn ? `컴퓨터 MIDI 키보드 켬 — '${selected || "선택한 트랙"}' 이(가) 연주됩니다` : "컴퓨터 MIDI 키보드 끔");
    return true;
  }
  if (e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === "l") { e.preventDefault(); setLoop(true, timeSel ? [timeSel.a, timeSel.b] : null); return true; }
  if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "f") {
    e.preventDefault(); follow = !follow; store.set("follow", follow ? "1" : "0"); status(follow ? "따라가기 켬" : "따라가기 끔"); return true;
  }
  if (e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === "u" && selClip) { e.preventDefault(); quantizeClip(); return true; }
  if (e.key === "Home") { e.preventDefault(); dawLocate(0, true); return true; }
  if (!kbOn || e.ctrlKey || e.altKey || e.metaKey) return false;
  if (e.code in KB) {
    e.preventDefault();
    if (e.repeat || kbHeld.has(e.code)) return true;
    const n = Math.min(127, 12 * (kbOct + 1) + KB[e.code]);
    kbHeld.set(e.code, n);
    call("midi.inject", { messages: [[0x90, n, kbVel]] });
    status(`${noteName(n)} · 세기 ${kbVel}`);
    return true;
  }
  if (e.code === "KeyZ" || e.code === "KeyX") { kbAllOff(); kbOct = Math.max(-1, Math.min(8, kbOct + (e.code === "KeyX" ? 1 : -1))); store.set("kbOct", kbOct); drawKb(); return true; }
  if (e.code === "KeyC" || e.code === "KeyV") { kbVel = Math.max(1, Math.min(127, kbVel + (e.code === "KeyV" ? 20 : -20))); store.set("kbVel", kbVel); drawKb(); return true; }
  return false;
}
document.addEventListener("keyup", (e) => {
  const n = kbHeld.get(e.code);
  if (n == null) return;
  kbHeld.delete(e.code);
  call("midi.inject", { messages: [[0x80, n, 0]] });
});
window.addEventListener("blur", kbAllOff);

// ───────── MIDI 맵 모드 (Ableton: Ctrl+M) ─────────
function toggleMapMode() {
  const on = !document.body.classList.contains("map-mode");
  document.body.classList.toggle("map-mode", on);
  mapPending = null;
  if (on && !$("#devices").classList.contains("on")) showTab("devices");
  status(on ? "MIDI 맵 모드 — 디바이스의 노브를 누르고 컨트롤러를 움직이면 연결됩니다. 연결된 노브는 오른쪽 클릭으로 해제 (Ctrl+M 끝)" : "MIDI 맵 모드 끝");
}
$("#devices").addEventListener("pointerdown", (e) => {
  if (!document.body.classList.contains("map-mode")) return;
  const k = e.target.closest(".knob[data-param]"); if (!k) return;
  e.preventDefault(); e.stopPropagation();
  if (e.button === 2) {
    const cc = k.dataset.cc;
    if (cc) call("midi.unmap", { cc: Number(cc) }).then(() => { status(`CC ${cc} 연결 해제`); drawDetail(); });
    return;
  }
  document.querySelectorAll(".knob.map-wait").forEach((x) => x.classList.remove("map-wait"));
  k.classList.add("map-wait");
  mapPending = { track: k.dataset.track, device: Number(k.dataset.device), param: k.dataset.param };
  status(`'${k.dataset.name}' — 이제 컨트롤러 노브·페이더를 움직이세요`);
}, true);
$("#devices").addEventListener("contextmenu", (e) => { if (document.body.classList.contains("map-mode")) e.preventDefault(); });
// drawDetail 이 그린 노브에 연결 표시
async function dawMarkMaps() {
  try { mapList = await call("midi.maps"); } catch { mapList = []; }
  document.querySelectorAll("#devices .knob[data-param]").forEach((k) => {
    const m = mapList.find((x) => x.track === k.dataset.track && x.slot === Number(k.dataset.device) && x.param === k.dataset.param);
    k.classList.toggle("mapped", !!m);
    if (m) { k.dataset.cc = m.cc; k.dataset.tip = `${k.dataset.name} — CC ${m.cc} 에 연결됨`; } else delete k.dataset.cc;
  });
}

// ───────── 양자화 (Ableton: Ctrl+U) ─────────
async function quantizeClip() {
  if (!selClip || selClip.type !== "midi") { status("MIDI 클립을 고른 뒤 Ctrl+U"); return; }
  const notes = await call("clip.notes", { track: selClip.track, clip: selClip.clip });
  // 양자화 단위: 기본 1/16. 격자를 그보다 촘촘히 두었을 때만 그 격자(축소해 둔 1마디 격자로 드럼을 뭉개지 않게)
  const u = Math.min(0.25, snapOn ? snapUnit() : 0.25), c0 = selClip.start;
  const q = notes.map((n) => ({ ...n, start: Math.max(0, Math.round((c0 + n.start) / u) * u - c0) }));
  await call("clip.set_notes", { track: selClip.track, clip: selClip.clip, notes: q, replace: true });
  status(`양자화: 노트 ${q.length}개를 1/${Math.round(4 / u)} 격자에 맞춤 (Ctrl+Z 되돌리기)`);
  refresh();
}

drawKb();
$("#kbd").onclick = () => dawKeyDown({ code: "KeyM", ctrlKey: false, altKey: false, metaKey: false, preventDefault() {} });
$("#grid").onclick = () => gridKey({ ctrlKey: true, shiftKey: false, altKey: false, key: "4", preventDefault() {} });
