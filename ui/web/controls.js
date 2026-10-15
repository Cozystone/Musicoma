// Musicoma 컨트롤 — 캔버스로 직접 그리는 페이더·노브·미터. 기본 슬라이더 안 씀.
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const DPR = () => window.devicePixelRatio || 1;

function setupCanvas(cv, w, h) {
  const r = DPR();
  cv.width = Math.round(w * r); cv.height = Math.round(h * r);
  cv.style.width = w + "px"; cv.style.height = h + "px";
  const g = cv.getContext("2d");
  g.setTransform(r, 0, 0, r, 0, 0);
  return g;
}

// dB ↔ 페이더 위치(0..1): 상단 +6dB, 0dB 가 약 76% 지점, 아래로 갈수록 촘촘한 곡선
const FADER_MAX = 6, FADER_MIN = -70;
function dbToPos(db) {
  if (db <= FADER_MIN) return 0;
  const x = (db - FADER_MIN) / (FADER_MAX - FADER_MIN);
  return Math.pow(x, 2.2);
}
function posToDb(p) {
  if (p <= 0.0005) return -Infinity;
  return FADER_MIN + Math.pow(p, 1 / 2.2) * (FADER_MAX - FADER_MIN);
}

/** 볼륨 페이더 + 스테레오 미터 (한 캔버스). onChange(db) */
class Fader {
  constructor(db, onChange, { w = 46, h = 118 } = {}) {
    this.db = db; this.onChange = onChange; this.w = w; this.h = h;
    this.levels = [-100, -100]; this.peaks = [-100, -100]; this.peakAt = [0, 0];
    this.el = document.createElement("canvas");
    this.el.className = "fader";
    this.g = setupCanvas(this.el, w, h);
    this.el.dataset.tip = "볼륨 — 위아래로 끌기 · Shift 미세 · 더블클릭 0 dB";
    let y0 = 0, p0 = 0;
    this.el.onpointerdown = (e) => {
      this.el.setPointerCapture(e.pointerId);
      y0 = e.clientY; p0 = dbToPos(this.db);
      this.el.onpointermove = (ev) => {
        const k = ev.shiftKey ? 0.15 : 1;
        const p = Math.min(1, Math.max(0, p0 + ((y0 - ev.clientY) / (this.h - 16)) * k));
        this.set(posToDb(p), true);
      };
      this.el.onpointerup = () => { this.el.onpointermove = null; };
    };
    this.el.ondblclick = () => this.set(0, true);
    this.el.onwheel = (e) => { e.preventDefault(); this.set((isFinite(this.db) ? this.db : -70) + (e.deltaY < 0 ? 0.5 : -0.5), true); };
    this.draw();
  }
  set(db, notify) {
    this.db = Math.min(FADER_MAX, db);
    this.draw();
    if (notify) this.onChange(isFinite(this.db) ? Math.round(this.db * 10) / 10 : -100);
  }
  meter(lr) {
    const now = performance.now();
    for (let i = 0; i < 2; i++) {
      const v = lr ? lr[i] : -100;
      this.levels[i] = Math.max(v, this.levels[i] - 1.6);          // 부드럽게 떨어지기
      if (v >= this.peaks[i] || now - this.peakAt[i] > 1200) { this.peaks[i] = v; this.peakAt[i] = now; }
    }
    this.draw();
  }
  draw() {
    const g = this.g, w = this.w, h = this.h, top = 6, bot = h - 6, H = bot - top;
    g.clearRect(0, 0, w, h);
    // 눈금
    g.font = "8px Segoe UI"; g.fillStyle = css("--faint"); g.textAlign = "right";
    for (const d of [6, 0, -6, -12, -24, -48]) {
      const y = bot - dbToPos(d) * H;
      g.fillRect(14, Math.round(y), 3, 1);
      g.fillText(d > 0 ? "+" + d : String(d), 13, y + 3);
    }
    // 미터 두 줄
    const mx = 20, mw = 4;
    for (let i = 0; i < 2; i++) {
      const x = mx + i * (mw + 1);
      g.fillStyle = css("--meter"); g.fillRect(x, top, mw, H);
      const lv = this.levels[i];
      if (lv > -70) {
        const y = bot - dbToPos(Math.min(lv, FADER_MAX)) * H;
        const grad = g.createLinearGradient(0, bot, 0, top);
        grad.addColorStop(0, "#3fbf5a"); grad.addColorStop(dbToPos(-6), "#a8d34a");
        grad.addColorStop(dbToPos(0), "#e6a31a"); grad.addColorStop(1, "#d6413a");
        g.fillStyle = grad; g.fillRect(x, y, mw, bot - y);
      }
      const pk = this.peaks[i];
      if (pk > -70) { g.fillStyle = pk > 0 ? "#d6413a" : css("--text"); g.fillRect(x, bot - dbToPos(Math.min(pk, FADER_MAX)) * H, mw, 1); }
    }
    // 레일 + 손잡이
    const rx = 36;
    g.fillStyle = css("--edge"); g.fillRect(rx - 1, top, 2, H);
    const ty = bot - dbToPos(isFinite(this.db) ? this.db : -100) * H;
    g.fillStyle = css("--panel-hi"); g.fillRect(rx - 7, ty - 5, 14, 10);
    g.strokeStyle = css("--edge"); g.lineWidth = 1; g.strokeRect(rx - 6.5, ty - 4.5, 13, 9);
    g.fillStyle = css("--text"); g.fillRect(rx - 5, ty - 0.5, 10, 1);
  }
}

/** 회전 노브. range [min,max], onChange(value), fmt(value)->text */
class Knob {
  constructor(value, { min = 0, max = 1, size = 28, center = null, fmt = (v) => v.toFixed(2), onChange, tip = "" }) {
    Object.assign(this, { value, min, max, size, center, fmt, onChange, init: value });
    this.el = document.createElement("canvas");
    this.el.className = "knob-c";
    this.g = setupCanvas(this.el, size, size);
    this.el.dataset.tip = (tip ? tip + " — " : "") + "위아래로 끌기 · Shift 미세 · 더블클릭 기본값";
    let y0 = 0, v0 = 0;
    this.el.onpointerdown = (e) => {
      this.el.setPointerCapture(e.pointerId); y0 = e.clientY; v0 = this.value;
      this.el.onpointermove = (ev) => {
        const span = this.max - this.min;
        this.set(v0 + ((y0 - ev.clientY) / (ev.shiftKey ? 600 : 140)) * span, true);
      };
      this.el.onpointerup = () => { this.el.onpointermove = null; };
    };
    this.el.ondblclick = () => this.set(this.init, true);
    this.draw();
  }
  set(v, notify) {
    this.value = Math.min(this.max, Math.max(this.min, v));
    this.draw();
    if (notify && this.onChange) this.onChange(this.value);
  }
  draw() {
    const g = this.g, s = this.size, c = s / 2, r = s / 2 - 3;
    g.clearRect(0, 0, s, s);
    const a0 = Math.PI * 0.75, a1 = Math.PI * 2.25, t = (this.value - this.min) / (this.max - this.min || 1);
    const a = a0 + (a1 - a0) * t;
    const ac = this.center == null ? a0 : a0 + (a1 - a0) * ((this.center - this.min) / (this.max - this.min));
    g.lineWidth = 3; g.lineCap = "butt";
    g.strokeStyle = css("--line"); g.beginPath(); g.arc(c, c, r, a0, a1); g.stroke();
    g.strokeStyle = css("--accent"); g.beginPath(); g.arc(c, c, r, Math.min(ac, a), Math.max(ac, a)); g.stroke();
    g.fillStyle = css("--panel-hi"); g.beginPath(); g.arc(c, c, r - 3.5, 0, Math.PI * 2); g.fill();
    g.strokeStyle = css("--edge"); g.lineWidth = 1; g.stroke();
    g.strokeStyle = css("--text"); g.lineWidth = 1.5;
    g.beginPath(); g.moveTo(c + Math.cos(a) * 2, c + Math.sin(a) * 2); g.lineTo(c + Math.cos(a) * (r - 4), c + Math.sin(a) * (r - 4)); g.stroke();
  }
}
