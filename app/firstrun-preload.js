// 첫 실행 창 ↔ 셸 다리 (sandbox preload: contextBridge + ipcRenderer 만 쓴다)
'use strict';
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('musicoma', {
  info: () => ipcRenderer.invoke('setup:info'),
  start: (opts) => ipcRenderer.send('setup:start', opts),
  skip: (opts) => ipcRenderer.send('setup:skip', opts),
  done: () => ipcRenderer.send('setup:continue'),
  onEvent: (cb) => ipcRenderer.on('setup:event', (_e, ev) => cb(ev)),
});
