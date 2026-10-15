// Musicoma 데스크톱 셸.
// 엔진(:47800)과 UI 서버(:47801/:47802)가 이미 떠 있으면 그대로 쓰고,
// 없으면 띄운 뒤 http://127.0.0.1:47802 를 창으로 연다.
// 종료할 때는 이 셸이 직접 띄운 프로세스만 정리한다.
//
// 루트(코드+데이터 폴더) 결정 순서:
//   ① 환경변수 MUSICOMA_ROOT → ② %APPDATA%\Musicoma\config.json 의 root
//   → ③ 설치 폴더의 resources\musicoma → ④ D:\0.Musicoma
// Python: 루트가 설치 폴더면 번들 런타임(resources\runtime\python, AI 를 깔았으면 <root>\python-ai),
//         외부 루트(개발 체크아웃)면 그 루트의 .venv 가 있으면 그것, 없으면 번들 런타임.
'use strict';

const { app, BrowserWindow, Menu, shell, dialog, ipcMain } = require('electron');
const { spawn, execFileSync, execFile } = require('child_process');
const net = require('net');
const fs = require('fs');
const path = require('path');

const ENGINE_PORT = 47800;
const HTTP_PORT = 47802;
const UI_URL = `http://127.0.0.1:${HTTP_PORT}`;
const DEFAULT_ROOT = 'D:\\0.Musicoma';
const ENGINE_REL = path.join('engine', 'build', 'musicoma_engine_artefacts', 'Release', 'musicoma-engine.exe');

const LOG_DIR = path.join(process.env.LOCALAPPDATA || app.getPath('temp'), 'Musicoma', 'logs');
const CFG_DIR = path.join(app.getPath('appData'), 'Musicoma');
const CONFIG = path.join(CFG_DIR, 'config.json');
const STATE = path.join(CFG_DIR, 'state.json');
// 번들 런타임: 설치판은 resources\runtime, 개발(npm start)은 app\runtime\dist
const RUNTIME_DIR = app.isPackaged ? path.join(process.resourcesPath, 'runtime') : path.join(__dirname, 'runtime', 'dist');
const BUNDLED_ROOT = app.isPackaged ? path.join(process.resourcesPath, 'musicoma') : null;

const spawned = []; // { name, child } — 이 셸이 띄운 것만
let splash = null;
let win = null;
let setupWin = null;
let setupChild = null;
let starting = true; // 첫 실행 창 → 시작 화면 → 메인 창으로 넘어가는 동안은 창이 0개여도 끝내지 않는다

function log(msg) {
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
    fs.appendFileSync(path.join(LOG_DIR, 'shell.log'), `[${new Date().toISOString()}] ${msg}\n`);
  } catch (_) { /* 로그 실패는 무시 */ }
}

function readJson(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch (_) { return null; }
}

function writeJson(file, data) {
  try {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, JSON.stringify(data, null, 2));
  } catch (e) { log(`write ${file} failed: ${e.message}`); }
}

// ───────── 루트 · 파이썬 ─────────
function resolveRoot() {
  const env = (process.env.MUSICOMA_ROOT || '').trim();
  if (env) return { root: env, source: 'env MUSICOMA_ROOT' };
  const cfg = readJson(CONFIG);
  if (cfg && typeof cfg.root === 'string' && cfg.root.trim()) return { root: cfg.root.trim(), source: CONFIG };
  if (BUNDLED_ROOT && fs.existsSync(path.join(BUNDLED_ROOT, 'ui', 'server.py'))) return { root: BUNDLED_ROOT, source: 'installed resources' };
  return { root: DEFAULT_ROOT, source: 'default' };
}

function venvUsable(py) {
  // venv 의 python.exe 는 pyvenv.cfg 의 home(기반 파이썬)이 있어야 돈다
  if (!fs.existsSync(py)) return false;
  try {
    const cfg = fs.readFileSync(path.join(path.dirname(py), '..', 'pyvenv.cfg'), 'utf8');
    const m = cfg.match(/^home\s*=\s*(.+)$/m);
    return !m || fs.existsSync(m[1].trim());
  } catch (_) { return true; }
}

function resolvePython(root) {
  const bundled = path.join(RUNTIME_DIR, 'python', 'python.exe');
  const aiOverlay = path.join(root, 'python-ai', 'Scripts', 'python.exe');
  const devVenv = path.join(root, '.venv', 'Scripts', 'python.exe');
  const isBundledRoot = BUNDLED_ROOT && path.resolve(root) === path.resolve(BUNDLED_ROOT);
  const order = isBundledRoot ? [aiOverlay, bundled, devVenv] : [devVenv, aiOverlay, bundled];
  for (const p of order) if (venvUsable(p)) return { python: p, base: fs.existsSync(bundled) ? bundled : p };
  return { python: null, base: null, tried: order };
}

function uvPath() {
  const p = path.join(RUNTIME_DIR, 'uv.exe');
  return fs.existsSync(p) ? p : null;
}

function childEnv(root) {
  const env = { PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1', MUSICOMA_ROOT: root };
  const uv = uvPath();
  if (uv) env.MUSICOMA_UV = uv;
  if (fs.existsSync(path.join(root, 'setup', 'requirements-ai.txt'))) env.MUSICOMA_BUNDLE = path.join(root, 'setup');
  return env;
}

function ensureWritable(root) {
  const probe = path.join(root, `.write-test-${process.pid}`);
  try { fs.writeFileSync(probe, 'x'); fs.unlinkSync(probe); return true; } catch (_) { return false; }
}

function writeMcpConfig(root, python) {
  // 설치판 루트에만: Claude Code 가 쓰는 .mcp.json 을 번들 파이썬으로 맞춘다(개발 루트의 파일은 건드리지 않음)
  if (!BUNDLED_ROOT || path.resolve(root) !== path.resolve(BUNDLED_ROOT)) return;
  const want = {
    mcpServers: {
      musicoma: {
        command: python.replace(/\\/g, '/'),
        args: ['-m', 'musicoma.mcp_server'],
        cwd: root.replace(/\\/g, '/'),
        env: { PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' },
      },
    },
  };
  const file = path.join(root, '.mcp.json');
  const text = JSON.stringify(want, null, 2);
  try { if (fs.readFileSync(file, 'utf8') === text) return; } catch (_) { /* 없음 */ }
  try { fs.writeFileSync(file, text); log(`wrote ${file}`); } catch (e) { log(`.mcp.json write failed: ${e.message}`); }
}

// ───────── 프로세스 ─────────
function isListening(port) {
  return new Promise((resolve) => {
    const s = net.createConnection({ host: '127.0.0.1', port });
    const done = (ok) => { s.destroy(); resolve(ok); };
    s.setTimeout(500);
    s.once('connect', () => done(true));
    s.once('timeout', () => done(false));
    s.once('error', () => done(false));
  });
}

async function waitPort(port, child, timeoutMs) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    if (await isListening(port)) return true;
    if (child && child.exitCode !== null) return false; // 일찍 죽음
    await new Promise((r) => setTimeout(r, 300));
  }
  return false;
}

function setStatus(text, isError = false) {
  log(`status: ${text}`);
  if (!splash || splash.isDestroyed()) return;
  splash.webContents
    .executeJavaScript(`window.setStatus && window.setStatus(${JSON.stringify(text)}, ${isError})`)
    .catch(() => {});
}

function launch(name, file, args, opts) {
  fs.mkdirSync(LOG_DIR, { recursive: true });
  const out = fs.openSync(path.join(LOG_DIR, `${name}.log`), 'a');
  fs.writeSync(out, `\n===== ${new Date().toISOString()} ${file} ${args.join(' ')}\n`);
  const child = spawn(file, args, {
    cwd: opts.cwd,
    env: { ...process.env, ...(opts.env || {}) },
    stdio: ['ignore', out, out],
    windowsHide: true,
    detached: false,
  });
  fs.closeSync(out);
  child.on('exit', (code) => log(`${name} exited (${code})`));
  child.on('error', (e) => log(`${name} spawn error: ${e.message}`));
  spawned.push({ name, child });
  log(`spawned ${name} pid=${child.pid}`);
  return child;
}

function killTree(name, child) {
  if (!child || !child.pid || child.exitCode !== null) return;
  try {
    execFileSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
    log(`killed ${name} pid=${child.pid}`);
  } catch (e) {
    log(`kill ${name} failed: ${e.message}`);
  }
}

function killSpawned() {
  while (spawned.length) {
    const { name, child } = spawned.pop(); // 나중에 띄운 것부터(UI 서버 → 엔진)
    killTree(name, child);
  }
}

async function ensureServers(root, py) {
  const engineExe = path.join(root, ENGINE_REL);
  const server = path.join(root, 'ui', 'server.py');

  setStatus('엔진 확인 중…');
  if (await isListening(ENGINE_PORT)) {
    log('engine already running — reuse');
  } else {
    if (!fs.existsSync(engineExe)) throw new Error(`엔진 실행 파일이 없습니다:\n${engineExe}`);
    setStatus('엔진 시작 중…');
    const child = launch('engine', engineExe, ['--port', String(ENGINE_PORT), '--root', root], {
      cwd: path.dirname(engineExe),
    });
    if (!(await waitPort(ENGINE_PORT, child, 30000))) throw new Error('엔진이 시작되지 않았습니다 (logs\\engine.log)');
  }

  setStatus('화면 서버 확인 중…');
  if (await isListening(HTTP_PORT)) {
    log('ui server already running — reuse');
  } else {
    if (!py.python) throw new Error(`Python 을 찾지 못했습니다:\n${(py.tried || []).join('\n')}`);
    if (!fs.existsSync(server)) throw new Error(`UI 서버 파일이 없습니다:\n${server}`);
    setStatus('화면 서버 시작 중…');
    const child = launch('ui-server', py.python, [server], { cwd: root, env: childEnv(root) });
    if (!(await waitPort(HTTP_PORT, child, 40000))) throw new Error('화면 서버가 시작되지 않았습니다 (logs\\ui-server.log)');
  }
  setStatus('여는 중…');
}

// ───────── 첫 실행: 음원·AI 모듈 ─────────
function needsSetup(root) {
  // sounds/sfz 가 없거나 비었으면 당연히, 기본 팩 일부만 있으면(받다가 끊김) 이어받기를 권한다
  const sfz = path.join(root, 'sounds', 'sfz');
  let empty = true;
  try {
    empty = !fs.readdirSync(sfz, { withFileTypes: true }).some((d) => d.isDirectory() && !d.name.startsWith('.'));
  } catch (_) { /* 없음 */ }
  if (empty) return true;
  const m = readJson(path.join(root, 'musicoma', 'setup_manifest.json'));
  if (!m) return false;
  return m.sounds.some((s) => s.pack === 'core' && (s.markers || []).some((k) => !fs.existsSync(path.join(root, s.dest, k))));
}

function setupInfo(root) {
  const m = readJson(path.join(root, 'musicoma', 'setup_manifest.json'));
  if (!m) return null;
  const core = m.sounds.filter((s) => s.pack === 'core');
  const sum = (a, k) => a.reduce((t, s) => t + (s[k] || 0), 0);
  const ai = m.ai || { runtime: {}, venvs: [] };
  const aiMb = (ai.runtime.approx_disk_mb || 0) + sum(ai.venvs || [], 'approx_disk_mb');
  return {
    root,
    coreDownloadGB: +(sum(core, 'size') / 1e9).toFixed(1),
    coreDiskGB: +(sum(core, 'unpacked_mb') / 1024).toFixed(1),
    coreCount: core.length,
    aiDiskGB: Math.round(aiMb / 1024),
    hasUv: !!uvPath(),
  };
}

function hasNvidia() {
  return new Promise((resolve) => {
    execFile('nvidia-smi', ['-L'], { windowsHide: true, timeout: 5000 }, (err, out) => {
      resolve(!err && /GPU \d+:/.test(out || ''));
    });
  });
}

function runFirstRun(root, py) {
  return new Promise(async (resolve) => {
    const info = setupInfo(root);
    if (!info) { log('setup manifest missing — skip first-run'); resolve('nomanifest'); return; }
    info.nvidia = await hasNvidia();
    let finished = false;
    const finish = (result) => {
      if (finished) return;
      finished = true;
      ipcMain.removeHandler('setup:info');
      ipcMain.removeAllListeners('setup:start');
      ipcMain.removeAllListeners('setup:skip');
      ipcMain.removeAllListeners('setup:continue');
      if (setupChild) { killTree('setup', setupChild); setupChild = null; }
      if (setupWin && !setupWin.isDestroyed()) setupWin.close();
      setupWin = null;
      resolve(result);
    };

    ipcMain.handle('setup:info', () => info);
    ipcMain.on('setup:skip', (_e, opts) => {
      if (opts && opts.dontAsk) writeJson(STATE, { ...(readJson(STATE) || {}), skipSetup: true });
      log('first-run skipped');
      finish('skipped');
    });
    ipcMain.on('setup:continue', () => finish('done'));
    ipcMain.on('setup:start', (_e, opts) => {
      if (setupChild) return;
      const args = ['-m', 'musicoma.setup_assets', '--root', root];
      if (opts && opts.sounds) args.push('--sounds', 'core');
      if (opts && opts.ai) args.push('--ai', '--python', py.base || py.python);
      log(`setup: ${py.python} ${args.join(' ')}`);
      fs.mkdirSync(LOG_DIR, { recursive: true });
      const logFile = fs.createWriteStream(path.join(LOG_DIR, 'setup.log'), { flags: 'a' });
      logFile.write(`\n===== ${new Date().toISOString()} ${args.join(' ')}\n`);
      setupChild = spawn(py.python, args, { cwd: root, env: { ...process.env, ...childEnv(root) }, windowsHide: true });
      spawned.push({ name: 'setup', child: setupChild });
      let buf = '';
      const send = (ev) => { if (setupWin && !setupWin.isDestroyed()) setupWin.webContents.send('setup:event', ev); };
      setupChild.stdout.on('data', (d) => {
        buf += d.toString('utf8');
        let i;
        while ((i = buf.indexOf('\n')) >= 0) {
          const line = buf.slice(0, i).trim();
          buf = buf.slice(i + 1);
          if (!line) continue;
          logFile.write(line + '\n');
          try { send(JSON.parse(line)); } catch (_) { send({ event: 'log', text: line }); }
        }
      });
      setupChild.stderr.on('data', (d) => { const t = d.toString('utf8'); logFile.write(t); send({ event: 'log', text: t.trim().slice(-300) }); });
      setupChild.on('exit', (code) => {
        logFile.end(`===== exit ${code}\n`);
        log(`setup exited (${code})`);
        setupChild = null;
        send({ event: 'exit', code });
      });
    });

    setupWin = new BrowserWindow({
      width: 620,
      height: 520,
      resizable: false,
      center: true,
      show: false,
      backgroundColor: '#1e1e1e',
      title: 'Musicoma — 처음 설정',
      autoHideMenuBar: true,
      icon: path.join(__dirname, 'build', 'icon.ico'),
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
        preload: path.join(__dirname, 'firstrun-preload.js'),
      },
    });
    setupWin.loadFile(path.join(__dirname, 'firstrun.html'));
    setupWin.once('ready-to-show', () => setupWin.show());
    setupWin.on('closed', () => finish(setupChild ? 'closed' : 'skipped')); // 창을 닫으면 중단(다음에 이어받기)
  });
}

// ───────── 창 ─────────
function createSplash() {
  splash = new BrowserWindow({
    width: 420,
    height: 220,
    frame: false,
    resizable: false,
    movable: true,
    center: true,
    show: false,
    backgroundColor: '#1e1e1e',
    title: 'Musicoma',
    icon: path.join(__dirname, 'build', 'icon.ico'),
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  splash.loadFile(path.join(__dirname, 'splash.html'));
  splash.once('ready-to-show', () => splash.show());
  return new Promise((resolve) => splash.webContents.once('did-finish-load', resolve));
}

function createMain() {
  win = new BrowserWindow({
    width: 1600,
    height: 1000,
    show: false,
    backgroundColor: '#1e1e1e',
    title: 'Musicoma',
    autoHideMenuBar: true,
    icon: path.join(__dirname, 'build', 'icon.ico'),
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.on('page-title-updated', (e) => e.preventDefault()); // 제목은 항상 Musicoma
  // 외부 링크는 기본 브라우저로
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(UI_URL)) { shell.openExternal(url); return { action: 'deny' }; }
    return { action: 'allow' };
  });
  win.once('ready-to-show', () => {
    win.show();
    if (splash && !splash.isDestroyed()) splash.close();
    splash = null;
  });
  win.on('closed', () => { win = null; });
  win.loadURL(UI_URL);
}

async function fail(message) {
  log(`startup failed: ${message}`);
  setStatus(message, true);
  await dialog.showMessageBox(splash && !splash.isDestroyed() ? splash : null, {
    type: 'error',
    title: 'Musicoma',
    message: '시작하지 못했습니다',
    detail: `${message}\n\n로그: ${LOG_DIR}\n설정: ${CONFIG}`,
  });
  app.quit();
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    const w = win || setupWin;
    if (w) { if (w.isMinimized()) w.restore(); w.focus(); }
  });

  app.whenReady().then(async () => {
    Menu.setApplicationMenu(null);
    const { root, source } = resolveRoot();
    const py = resolvePython(root);
    log(`start — root=${root} (${source}) python=${py.python} runtime=${RUNTIME_DIR} packaged=${app.isPackaged}`);

    if (!fs.existsSync(root)) { await createSplash(); return fail(`루트 폴더가 없습니다:\n${root}`); }
    if (!ensureWritable(root)) {
      await createSplash();
      return fail(`루트 폴더에 쓸 수 없습니다:\n${root}\n\n쓰기 가능한 위치에 다시 설치하거나 config.json 의 root 를 바꾸세요.`);
    }
    if (py.python) writeMcpConfig(root, py.python);

    // 첫 실행: 음원이 없으면 받을지 묻는다(엔진·서버가 이미 떠 있으면 묻지 않음 — 쓰는 중)
    const state = readJson(STATE) || {};
    const busy = (await isListening(ENGINE_PORT)) && (await isListening(HTTP_PORT));
    if (!busy && py.python && !state.skipSetup && needsSetup(root)) {
      const r = await runFirstRun(root, py);
      log(`first-run result: ${r}`);
      if (r === 'closed') { starting = false; app.quit(); return; }
    }

    await createSplash();
    try {
      await ensureServers(root, resolvePython(root)); // AI 를 방금 깔았으면 python-ai 로 바뀜
      createMain();
      starting = false;
    } catch (e) {
      starting = false;
      await fail(e.message);
    }
  });

  app.on('window-all-closed', () => {
    if (starting) return;
    app.quit();
  });
  app.on('will-quit', killSpawned);
  process.on('exit', killSpawned);
}
