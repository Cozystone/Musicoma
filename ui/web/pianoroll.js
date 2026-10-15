// 피아노롤 — 노트 직접 편집. 클릭=그리기(빈 곳) · 끌기=이동 · 오른쪽 끝 끌기=길이 · 더블클릭/Del=삭제
// Shift+끌기=여러 개 선택 · 아래 벨로시티 줄에서 세기 조절 · Ctrl+휠=가로 확대 · 바뀌면 자동 저장
class PianoRoll {
  constructor(host, { onSave }) {
    this.host = host; this.onSave = onSave;
    this.notes = []; this.sel = new Set(); this.len = 16; this.grid = 0.25;
    this.ppb = 48; this.rowH = 10; this.lo = 24; this.hi = 108; this.velH = 46; this.keysW = 44;
    host.innerHTML = "";
    this.bar = document.createElement("div"); this.bar.className = "pr-bar";
    this.bar.innerHTML = `<span class="pr-title"></span>
      <label>격자 <select class="pr-grid"><option value="1">1/4</option><option value="0.5">1/8</option>
      <option value="0.25" selected>1/16</option><option value="0.125">1/32</option><option value="0">끔</option></select></label>
      <button class="pr-q" data-tip="선택한 노트(없으면 전체)를 격자에 맞춤">퀀타이즈</button>
      <button class="pr-close" data-icon="close" data-tip="피아노롤 닫기"></button>`;
    this.wrap = document.createElement("div"); this.wrap.className = "pr-wrap";
    this.cv = document.createElement("canvas"); this.cv.className = "pr-canvas";
    this.wrap.append(this.cv);
    host.append(this.bar, this.wrap);
    hydrateIcons(this.bar);
    this.bar.querySelector(".pr-grid").onchange = (e) => { this.grid = parseFloat(e.target.value); this.draw(); };
    this.bar.querySelector(".pr-q").onclick = () => this.quantize();
    this.bar.querySelector(".pr-close").onclick = () => this.onClose && this.onClose();
    this.bind();
    new ResizeObserver(() => this.draw()).observe(this.wrap);
  }

  load(title, notes, lengthBeats) {
    this.bar.querySelector(".pr-title").textContent = title;
    this.notes = notes.map((n, i) => ({ ...n, id: i }));
    this.len = lengthBeats; this.sel.clear();
    const ps = notes.map((n) => n.pitch);
    const mid = ps.length ? (Math.min(...ps) + Math.max(...ps)) / 2 : 60;
    this.draw();
    this.wrap.scrollTop = Math.max(0, (this.hi - mid) * this.rowH - this.wrap.clientHeight / 2 + 20);
  }

  get W() { return this.keysW + this.len * this.ppb + 40; }
  get Hn() { return (this.hi - this.lo + 1) * this.rowH; }
  yOf(p) { return (this.hi - p) * this.rowH; }
  pAt(y) { return this.hi - Math.floor(y / this.rowH); }
  xOf(b) { return this.keysW + b * this.ppb; }
  bAt(x) { return (x - this.keysW) / this.ppb; }
  snap(b) { return this.grid ? Math.round(b / this.grid) * this.grid : b; }
  snapDown(b) { return this.grid ? Math.floor(b / this.grid) * this.grid : b; }

  draw() {
    const W = this.W, H = this.Hn + this.velH;
    const g = setupCanvas(this.cv, W, H);
    const black = [1, 3, 6, 8, 10];
    // 줄 배경
    for (let p = this.lo; p <= this.hi; p++) {
      const y = this.yOf(p);
      g.fillStyle = black.includes(p % 12) ? css("--lane-alt") : css("--lane");
      g.fillRect(this.keysW, y, W, this.rowH);
      if (p % 12 === 0) { g.fillStyle = css("--line"); g.fillRect(this.keysW, y + this.rowH - 1, W, 1); }
    }
    // 세로 격자
    for (let b = 0; b <= this.len; b += this.grid || 0.25) {
      const x = Math.round(this.xOf(b));
      g.fillStyle = b % 4 === 0 ? css("--edge") : b % 1 === 0 ? css("--line") : css("--line-soft");
      g.fillRect(x, 0, 1, this.Hn);
    }
    // 건반
    for (let p = this.lo; p <= this.hi; p++) {
      const y = this.yOf(p), isB = black.includes(p % 12);
      g.fillStyle = isB ? "#2a2a2a" : "#e8e8e8";
      g.fillRect(0, y, isB ? this.keysW * 0.62 : this.keysW, this.rowH - (isB ? 0 : 0.5));
      if (p % 12 === 0) { g.fillStyle = "#333"; g.font = "8px Segoe UI"; g.fillText("C" + (p / 12 - 1), this.keysW - 16, y + this.rowH - 2); }
    }
    g.fillStyle = css("--edge"); g.fillRect(this.keysW - 1, 0, 1, H);
    // 노트
    for (const n of this.notes) {
      const x = this.xOf(n.start), y = this.yOf(n.pitch), w = Math.max(3, n.length * this.ppb - 1);
      const sel = this.sel.has(n.id);
      const v = n.velocity / 127;
      g.fillStyle = sel ? css("--accent") : `hsl(205 ${30 + v * 40}% ${72 - v * 30}%)`;
      g.fillRect(x, y + 1, w, this.rowH - 2);
      g.strokeStyle = css("--edge"); g.lineWidth = 1; g.strokeRect(x + 0.5, y + 1.5, w - 1, this.rowH - 3);
    }
    // 벨로시티 줄
    const vy = this.Hn;
    g.fillStyle = css("--panel"); g.fillRect(0, vy, W, this.velH);
    g.fillStyle = css("--edge"); g.fillRect(0, vy, W, 1);
    g.fillStyle = css("--dim"); g.font = "9px Segoe UI"; g.fillText("세기", 6, vy + 14);
    for (const n of this.notes) {
      const x = this.xOf(n.start), h = (n.velocity / 127) * (this.velH - 8);
      g.fillStyle = this.sel.has(n.id) ? css("--accent") : css("--text");
      g.fillRect(x, vy + this.velH - 2 - h, 2, h);
      g.fillRect(x - 1, vy + this.velH - 2 - h, 4, 2);
    }
  }

  hit(x, y) {
    for (let i = this.notes.length - 1; i >= 0; i--) {
      const n = this.notes[i], nx = this.xOf(n.start), ny = this.yOf(n.pitch), w = Math.max(3, n.length * this.ppb);
      if (x >= nx && x <= nx + w && y >= ny && y < ny + this.rowH) return { n, edge: x > nx + w - 5 };
    }
    return null;
  }

  bind() {
    const cv = this.cv;
    const pos = (e) => { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    cv.onpointerdown = (e) => {
      const [x, y] = pos(e);
      cv.setPointerCapture(e.pointerId);
      if (y > this.Hn) return this.velDrag(e, x);
      if (x < this.keysW) return;
      const h = this.hit(x, y);
      if (!h) {
        // 빈 곳: 새 노트(격자 한 칸, 직전 길이 기억)
        const n = { pitch: this.pAt(y), start: Math.max(0, this.snapDown(this.bAt(x))), length: this.lastLen || this.grid || 0.25,
                    velocity: this.lastVel || 100, id: Date.now() };
        this.notes.push(n); this.sel = new Set([n.id]);
        this.draw(); this.changed();
        return this.drag(e, n, false, x, y);
      }
      if (e.shiftKey) { this.sel.has(h.n.id) ? this.sel.delete(h.n.id) : this.sel.add(h.n.id); }
      else if (!this.sel.has(h.n.id)) this.sel = new Set([h.n.id]);
      this.draw();
      this.drag(e, h.n, h.edge, x, y);
    };
    cv.ondblclick = (e) => {
      const [x, y] = pos(e); const h = this.hit(x, y);
      if (h) { this.notes = this.notes.filter((n) => n !== h.n); this.sel.delete(h.n.id); this.draw(); this.changed(); }
    };
    this.wrap.addEventListener("wheel", (e) => {
      if (!e.ctrlKey) return;
      e.preventDefault();
      this.ppb = Math.min(240, Math.max(8, this.ppb * (e.deltaY < 0 ? 1.2 : 0.83)));
      this.draw();
    }, { passive: false });
    this.keyHandler = (e) => {
      if (!this.host.offsetParent || ["INPUT", "TEXTAREA"].includes(e.target.tagName)) return;
      if ((e.key === "Delete" || e.key === "Backspace") && this.sel.size) {
        this.notes = this.notes.filter((n) => !this.sel.has(n.id)); this.sel.clear(); this.draw(); this.changed(); e.preventDefault();
      }
      if (e.ctrlKey && e.key.toLowerCase() === "a") { this.sel = new Set(this.notes.map((n) => n.id)); this.draw(); e.preventDefault(); }
      if (["ArrowUp", "ArrowDown"].includes(e.key) && this.sel.size) {
        const d = (e.key === "ArrowUp" ? 1 : -1) * (e.shiftKey ? 12 : 1);
        for (const n of this.notes) if (this.sel.has(n.id)) n.pitch = Math.min(127, Math.max(0, n.pitch + d));
        this.draw(); this.changed(); e.preventDefault();
      }
    };
    document.addEventListener("keydown", this.keyHandler);
  }

  drag(e, n, edge, x0, y0) {
    const moving = this.notes.filter((m) => this.sel.has(m.id));
    const orig = moving.map((m) => ({ m, s: m.start, p: m.pitch, l: m.length }));
    this.cv.onpointermove = (ev) => {
      const r = this.cv.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
      const db = (x - x0) / this.ppb, dp = Math.round((y0 - y) / this.rowH);
      for (const o of orig) {
        if (edge) { o.m.length = Math.max(this.grid || 0.05, this.snap(o.l + db) || this.grid || 0.05); this.lastLen = o.m.length; }
        else { o.m.start = Math.max(0, this.snap(o.s + db)); o.m.pitch = Math.min(127, Math.max(0, o.p + dp)); }
      }
      this.draw();
    };
    this.cv.onpointerup = () => { this.cv.onpointermove = null; this.changed(); };
  }

  velDrag(e, x0) {
    const targets = this.sel.size ? this.notes.filter((n) => this.sel.has(n.id)) : null;
    const apply = (ev) => {
      const r = this.cv.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top - this.Hn;
      const v = Math.round(Math.min(127, Math.max(1, (1 - (y - 2) / (this.velH - 8)) * 127)));
      const list = targets || this.notes.filter((n) => Math.abs(this.xOf(n.start) - x) < 4);
      for (const n of list) n.velocity = v;
      this.lastVel = v;
      this.draw();
    };
    apply(e);
    this.cv.onpointermove = apply;
    this.cv.onpointerup = () => { this.cv.onpointermove = null; this.changed(); };
  }

  quantize() {
    const list = this.sel.size ? this.notes.filter((n) => this.sel.has(n.id)) : this.notes;
    const q = this.grid || 0.25;
    for (const n of list) n.start = Math.round(n.start / q) * q;
    this.draw(); this.changed();
  }

  changed() {
    clearTimeout(this._t);
    this._t = setTimeout(() => this.onSave(this.notes.map(({ pitch, start, length, velocity }) =>
      ({ pitch, start: Math.round(start * 1e4) / 1e4, length: Math.round(length * 1e4) / 1e4, velocity }))), 250);
  }

  dispose() { document.removeEventListener("keydown", this.keyHandler); }
}
