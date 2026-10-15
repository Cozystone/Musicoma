// Musicoma 데스크톱 셸.
// 엔진(:47800)과 UI 서버(:47801/:47802)가 이미 떠 있으면 그대로 쓰고,
// 없으면 띄운 뒤 http://127.0.0.1:47802 를 창으로 연다.
// 종료할 때는 이 셸이 직접 띄운 프로세스만 정리한다.
'use strict';

const { app, BrowserWindow, Menu, shell, dialog } = require('electron');
const { spawn, execFileSync } = require('child_process');
const net = require('net');
const fs = require('fs');
const path = require('path');

const ENGINE_PORT = 47800;
const HTTP_PORT = 47802;
const UI_URL = `http://127.0.0.1:${HTTP_PORT}`;
const DEFAULT_ROOT = 'D:\\0.Musicoma';

const LOG_DIR = path.join(process.env.LOCALAPPDATA || app.getPath('temp'), 'Musicoma', 'logs');
const CONFIG = path.join(app.getPath('appData'), 'Musicoma', 'config.json');

const spawned = []; // { name, child } — 이 셸이 띄운 것만
let splash = null;
let win = null;

function log(msg) {
  try {
    fs.mkdirSync(LOG_DIR, { recursive: true });
    fs.appendFileSync(path.join(LOG_DIR, 'shell.log'), `[${new Date().toISOString()}] ${msg}\n`);
  } catch (_) { /* 로그 실패는 무시 */ }
}

function readRoot() {
  try {
    const cfg = JSON.parse(fs.readFileSync(CONFIG, 'utf8'));
    if (cfg && typeof cfg.root === 'string' && cfg.root.trim()) return cfg.root.trim();
  } catch (_) { /* 없으면 기본값 */ }
  return DEFAULT_ROOT;
}

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

function killSpawned() {
  while (spawned.length) {
    const { name, child } = spawned.pop(); // UI 서버 먼저, 엔진 나중
    if (!child.pid || child.exitCode !== null) continue;
    try {
      execFileSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
      log(`killed ${name} pid=${child.pid}`);
    } catch (e) {
      log(`kill ${name} failed: ${e.message}`);
    }
  }
}

async function ensureServers(root) {
  const engineExe = path.join(root, 'engine', 'build', 'musicoma_engine_artefacts', 'Release', 'musicoma-engine.exe');
  const python = path.join(root, '.venv', 'Scripts', 'python.exe');
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
    if (!fs.existsSync(python)) throw new Error(`Python 가상환경이 없습니다:\n${python}`);
    if (!fs.existsSync(server)) throw new Error(`UI 서버 파일이 없습니다:\n${server}`);
    setStatus('화면 서버 시작 중…');
    const child = launch('ui-server', python, [server], {
      cwd: root,
      env: { PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' },
    });
    if (!(await waitPort(HTTP_PORT, child, 40000))) throw new Error('화면 서버가 시작되지 않았습니다 (logs\\ui-server.log)');
  }
  setStatus('여는 중…');
}

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

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (win) { if (win.isMinimized()) win.restore(); win.focus(); }
  });

  app.whenReady().then(async () => {
    Menu.setApplicationMenu(null);
    const root = readRoot();
    log(`start — root=${root}`);
    await createSplash();
    try {
      await ensureServers(root);
      createMain();
    } catch (e) {
      log(`startup failed: ${e.message}`);
      setStatus(e.message, true);
      await dialog.showMessageBox(splash && !splash.isDestroyed() ? splash : null, {
        type: 'error',
        title: 'Musicoma',
        message: '시작하지 못했습니다',
        detail: `${e.message}\n\n로그: ${LOG_DIR}\n설정: ${CONFIG}`,
      });
      app.quit();
    }
  });

  app.on('window-all-closed', () => app.quit());
  app.on('will-quit', killSpawned);
  process.on('exit', killSpawned);
}
