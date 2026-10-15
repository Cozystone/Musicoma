// Musicoma 아이콘 — 직접 그린 16px 선 아이콘(1.5px 획). 남의 아이콘 세트 사용 안 함.
const ICONS = {
  play: '<path d="M5 3.5v9l7-4.5z" fill="currentColor" stroke="none"/>',
  stop: '<rect x="4" y="4" width="8" height="8" fill="currentColor" stroke="none"/>',
  record: '<circle cx="8" cy="8" r="4" fill="currentColor" stroke="none"/>',
  loop: '<path d="M3 7.5V6.5a2 2 0 0 1 2-2h7M10.5 2.5l2 2-2 2M13 8.5v1a2 2 0 0 1-2 2H4M5.5 13.5l-2-2 2-2"/>',
  metro: '<path d="M6 2.5h4l2.5 11h-9zM8 10l3.5-6.5M5 10.5h6"/>',
  undo: '<path d="M5.5 4L2.5 7l3 3M2.5 7H10a3.5 3.5 0 0 1 0 7H7"/>',
  redo: '<path d="M10.5 4l3 3-3 3M13.5 7H6a3.5 3.5 0 0 0 0 7h3"/>',
  zoomin: '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14M5 7h4M7 5v4"/>',
  zoomout: '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14M5 7h4"/>',
  fit: '<path d="M2.5 5.5v-3h3M10.5 2.5h3v3M13.5 10.5v3h-3M5.5 13.5h-3v-3"/>',
  height: '<path d="M8 2.5v11M5.5 5L8 2.5 10.5 5M5.5 11L8 13.5 10.5 11"/>',
  browser: '<rect x="2.5" y="2.5" width="11" height="11"/><path d="M6.5 2.5v11"/>',
  spark: '<path d="M8 2l1.4 3.6L13 7l-3.6 1.4L8 12l-1.4-3.6L3 7l3.6-1.4z" fill="currentColor" stroke="none"/><path d="M13 11.5l.5 1.3 1.3.5-1.3.5-.5 1.3-.5-1.3-1.3-.5 1.3-.5z" fill="currentColor" stroke="none"/>',
  theme: '<circle cx="8" cy="8" r="5.5"/><path d="M8 2.5v11" /><path d="M8 2.5a5.5 5.5 0 0 1 0 11z" fill="currentColor" stroke="none"/>',
  power: '<path d="M8 2.5v5M5 4.5a4.5 4.5 0 1 0 6 0"/>',
  open: '<rect x="2.5" y="4.5" width="9" height="9"/><path d="M8 2.5h5.5V8M13.5 2.5L7.5 8.5"/>',
  close: '<path d="M4 4l8 8M12 4l-8 8"/>',
  plus: '<path d="M8 3v10M3 8h10"/>',
  speaker: '<path d="M3 6h2.5L9 3v10L5.5 10H3z" fill="currentColor" stroke="none"/><path d="M11 5.5a3.5 3.5 0 0 1 0 5"/>',
  midi: '<rect x="2.5" y="3.5" width="11" height="9"/><path d="M5.5 3.5v5M8 3.5v5M10.5 3.5v5"/>',
  wave: '<path d="M2 8h1.5M4.5 5v6M7 3v10M9.5 5.5v5M12 7v2M14 8h0"/>',
  pencil: '<path d="M3 13l1-3.5 6.5-6.5 2.5 2.5L6.5 12z M9.5 4l2.5 2.5"/>',
  select: '<path d="M4 2.5l8 5.5-3.5 1 2 4-1.5.7-2-4L4 12z" fill="currentColor" stroke="none"/>',
  duplicate: '<rect x="2.5" y="5.5" width="8" height="8"/><path d="M5.5 5.5v-3h8v8h-3"/>',
  scissors: '<circle cx="4.5" cy="11.5" r="2"/><circle cx="11.5" cy="11.5" r="2"/><path d="M5.8 10L12 2.5M10.2 10L4 2.5"/>',
  trash: '<path d="M3 4.5h10M6 4.5V3h4v1.5M4.5 4.5l.8 9h5.4l.8-9"/>',
  piano: '<rect x="2.5" y="2.5" width="11" height="11"/><path d="M2.5 9.5h11M5.5 2.5v7M8 2.5v7M10.5 2.5v7"/>',
  mixer: '<path d="M4 2.5v11M8 2.5v11M12 2.5v11"/><rect x="2.5" y="8" width="3" height="2" fill="currentColor"/><rect x="6.5" y="5" width="3" height="2" fill="currentColor"/><rect x="10.5" y="10" width="3" height="2" fill="currentColor"/>',
  device: '<rect x="2.5" y="3.5" width="11" height="9"/><circle cx="6" cy="8" r="1.8"/><circle cx="10.5" cy="8" r="1.8"/>',
  ear: '<path d="M5 6a3 3 0 0 1 6 0c0 2-2 2.5-2 4.5a1.8 1.8 0 0 1-3.5.5M7 6.5a1 1 0 0 1 2 0"/>',
  send: '<path d="M2.5 8l11-5-4 11-2-4.5z"/>',
  export: '<path d="M8 10V2.5M5 5.5L8 2.5l3 3M3 9.5v4h10v-4"/>',
  settings: '<circle cx="8" cy="8" r="2"/><path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M3.4 12.6l1.4-1.4M11.2 4.8l1.4-1.4"/>',
  mic: '<rect x="6" y="2.5" width="4" height="7" rx="2"/><path d="M4 8a4 4 0 0 0 8 0M8 12v2"/>',
  arm: '<circle cx="8" cy="8" r="4.2"/>',
  chevron: '<path d="M6 4l4 4-4 4"/>',
};

function icon(name, size = 14) {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 16 16");
  s.setAttribute("width", size); s.setAttribute("height", size);
  s.setAttribute("fill", "none"); s.setAttribute("stroke", "currentColor");
  s.setAttribute("stroke-width", "1.5"); s.setAttribute("stroke-linecap", "square");
  s.classList.add("ico");
  s.innerHTML = ICONS[name] || "";
  return s;
}

// data-icon="이름" 을 가진 버튼에 아이콘을 채운다(텍스트는 그대로 옆에)
function hydrateIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((b) => {
    if (b.querySelector("svg.ico")) return;
    b.prepend(icon(b.dataset.icon, parseInt(b.dataset.iconSize || "14")));
  });
}
