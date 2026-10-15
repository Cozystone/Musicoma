"""Musicoma Core 렌더 계획(render plan) 내보내기 — 지금 엔진에 열린 곡(또는 이름/경로로 연 곡)을
Tracktion 없이 musicoma-core.exe 가 렌더할 수 있는 독립 JSON 으로 만든다.

    from musicoma.core_export import export_plan, save_plan
    plan = export_plan()                         # 지금 열린 곡
    plan = export_plan(project="musicoma-005-kr-hook")   # edit.load 후 내보내기(엔진의 열린 곡이 바뀜!)
    save_plan(plan, "scratch/core/x/plan.json")

엔진에는 읽기 명령만 쓴다(edit.info · clip.list · clip.notes · clip.controllers · device.params).
project/path 를 주면 edit.load 를 한다. 오디오 클립 세부(파일·오프셋·게인·페이드·리버스)와
LPF 모드처럼 명령으로 안 나오는 값은 저장된 .tracktionedit(XML)에서 읽는다 → 저장 안 된 변경은 빠질 수 있다.

──────────────────────────────── 스키마 (version 1) ────────────────────────────────
{
  "format": "musicoma-render-plan", "version": 1,
  "source": {"edit": <.tracktionedit 경로>, "exported": "YYYY-MM-DD HH:MM:SS"},
  "bpm": 92.0, "time_sig": "4/4",
  "tempo": [{"beat": 0, "bpm": 92.0}],          # C1 은 첫 템포만 사용(템포 변화 미지원)
  "length_beats": 16.0,
  "render": {"start_beat": 0, "end_beat": 16.0, "tail_sec": 2.0, "sample_rate": 48000},
  "master": {"volume_db": -3.0, "chain": [<device>...]},
  "tracks": [{
      "index": 0, "name": "Piano", "volume_db": -6.0, "pan": -0.3,   # pan -1..1
      "mute": false, "solo": false,
      "chain": [<device>...],          # 엔진의 디바이스 순서 그대로(믹서 제외). 볼륨/팬은 체인 뒤.
      "midi_clips": [{"index": 0, "name": "MIDI", "start_beat": 0, "end_beat": 16, "mute": false,
                      "notes": [{"pitch": 60, "start": 0.0, "length": 1.0, "velocity": 100}],   # 박, 클립 기준
                      "cc":    [{"cc": 64, "beat": 0.0, "value": 127}],                       # 1 모드휠, 11 익스프레션, 64 서스테인
                      "bend":  [{"beat": 0.0, "value": 0.0}]}],                               # -1..1
      "audio_clips": [{"index": 1, "name": "...", "file": "D:/...wav", "start_beat": 0, "end_beat": 8,
                       "start_sec": 0.0, "length_sec": 5.2, "offset_sec": 0.0, "gain_db": 0.0, "pan": 0.0,
                       "fade_in_sec": 0.0, "fade_out_sec": 0.0, "reverse": false, "mute": false}]
  }]
}
<device> 공통: {"kind": ..., "name": 엔진 표시 이름, "enabled": true, "params": {id: 값}, "texts": {id: 표시 문자열}}
  kind = "sfz"        + "sfz": 경로, "volume_db"               (C1 지원: 자체 샘플러)
         "vst3"       + "plugin": 이름, "supported": false     (C2 에서 VST3 호스팅)
         "builtin_synth" (4osc/sampler)  supported false
         "lowpass"    + "frequency", "mode" ("lowpass"|"highpass")         (C1 지원)
         "compressor" + "threshold_db", "ratio", "attack_ms", "release_ms", "output_db"  (C1 지원)
         "eq"         + params(4밴드 원값)      (C1 통과 + 경고)
         "reverb" / "delay" / "chorus" / "phaser" / "pitchshift"  (C1 통과 + 경고)
         "send"       + "bus", "level_db"        (체인 위치에서 버스로 보냄 = 프리페이더)
         "return"     + "bus"                    (그 위치에 버스 합을 더함)
         "unknown"    + "type"
────────────────────────────────────────────────────────────────────────────────────
"""
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from .engine import connect

ROOT = Path(__file__).resolve().parent.parent
FORMAT = "musicoma-render-plan"
VERSION = 1

_DB = re.compile(r"([-+]?\d+(?:\.\d+)?)\s*dB", re.I)


def _db_from_text(text, fallback=0.0):
    if text is None:
        return fallback
    if "-inf" in str(text).lower():
        return -150.0
    m = _DB.search(str(text))
    return float(m.group(1)) if m else fallback


# ---------------------------------------------------------------------------- XML (.tracktionedit)
def _read_xml(path):
    try:
        t = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    t = re.sub(r"\b(\w+):(\w+)=", r"\1_\2=", t)     # base64:layout 같은 접두사 속성
    try:
        return ET.fromstring(t)
    except ET.ParseError:
        return None


def _xml_tracks(root):
    """오디오 트랙(TRACK 요소)만 순서대로 → [{plugins: [...], clips: [...]}]"""
    out = []
    if root is None:
        return out
    for tr in root.findall("TRACK"):
        plugins = [p for p in tr.findall("PLUGIN") if p.get("type") not in ("volume", "level")]
        clips = [c for c in tr if c.tag in ("MIDICLIP", "AUDIOCLIP", "WAVECLIP", "STEPCLIP", "EDITCLIP")]
        out.append({"name": tr.get("name"), "plugins": plugins, "clips": clips})
    return out


def _f(el, key, default=0.0):
    try:
        return float(el.get(key, default))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------- 디바이스
_FX_KIND = {"4bandEq": "eq", "reverb": "reverb", "delay": "delay", "chorus": "chorus", "phaser": "phaser",
            "pitchShifter": "pitchshift", "pitchshift": "pitchshift", "lowpass": "lowpass", "compressor": "compressor"}


def _device(e, track_ref, d, xml_plugin):
    t = d.get("type", "")
    out = {"name": d.get("name"), "type": t, "enabled": bool(d.get("enabled", True))}
    try:
        ps = e.call("device.params", {"track": track_ref, "device": d["device"]})["params"]
    except Exception:  # noqa: BLE001
        ps = []
    out["params"] = {p["id"]: p["value"] for p in ps}
    out["texts"] = {p["id"]: p.get("text") for p in ps}
    texts = out["texts"]
    vals = out["params"]

    if t == "musicomaSfz":
        out.update(kind="sfz", sfz=d.get("sfz"), volume_db=float(vals.get("volume", 0.0)), supported=True)
    elif t == "auxsend":
        m = re.search(r"#(\d+)", d.get("name") or "")
        bus = int(m.group(1)) - 1 if m else int(_f(xml_plugin, "busNum", 0)) if xml_plugin is not None else 0
        out.update(kind="send", bus=bus, level_db=_db_from_text(texts.get("send level"), 0.0))
    elif t == "auxreturn":
        m = re.search(r"#(\d+)", d.get("name") or "")
        bus = int(m.group(1)) - 1 if m else int(_f(xml_plugin, "busNum", 0)) if xml_plugin is not None else 0
        out.update(kind="return", bus=bus)
    elif t == "compressor":
        thr = float(vals.get("threshold", 1.0))
        ratio_raw = float(vals.get("ratio", 1.0)) or 1.0
        out.update(kind="compressor", supported=True,
                   threshold_db=_db_from_text(texts.get("threshold"), 20 * __import__("math").log10(max(thr, 1e-6))),
                   ratio=1.0 / ratio_raw, attack_ms=float(vals.get("attack", 100.0)),
                   release_ms=float(vals.get("release", 100.0)),
                   output_db=_db_from_text(texts.get("output gain"), float(vals.get("output gain", 0.0))))
    elif t == "lowpass":
        mode = (xml_plugin.get("mode") if xml_plugin is not None else None) or "lowpass"
        out.update(kind="lowpass", supported=True, frequency=float(vals.get("frequency", 4000.0)),
                   mode="highpass" if "high" in mode.lower() else "lowpass")
    elif t in _FX_KIND:
        out.update(kind=_FX_KIND[t], supported=False)
    elif t in ("4osc", "sampler"):
        out.update(kind="builtin_synth", supported=False)
    elif t.lower() in ("vst3", "vst", "external") or (xml_plugin is not None and xml_plugin.get("type") == "vst"):
        out.update(kind="vst3", plugin=d.get("name"), supported=False)
    else:
        out.update(kind="unknown", supported=False)
    return out


# ---------------------------------------------------------------------------- 클립
def _audio_clip(c_info, xml_clip, bpm):
    spb = 60.0 / bpm
    out = {"index": c_info["clip"], "name": c_info.get("name"), "start_beat": c_info["start"],
           "end_beat": c_info["end"], "start_sec": c_info["start"] * spb,
           "length_sec": (c_info["end"] - c_info["start"]) * spb}
    if xml_clip is None:
        out["error"] = "no XML for audio clip (save the edit first)"
        return out
    out.update(file=xml_clip.get("source"), offset_sec=_f(xml_clip, "offset"), gain_db=_f(xml_clip, "gain"),
               pan=_f(xml_clip, "pan"), fade_in_sec=_f(xml_clip, "fadeIn"), fade_out_sec=_f(xml_clip, "fadeOut"),
               reverse=xml_clip.get("isReversed", "0") in ("1", "true"),
               mute=xml_clip.get("mute", "0") in ("1", "true"))
    if xml_clip.get("start") is not None:
        out["start_sec"] = _f(xml_clip, "start")
        out["length_sec"] = _f(xml_clip, "length")
    return out


def _midi_clip(e, track_ref, c, xml_clip):
    notes = e.call("clip.notes", {"track": track_ref, "clip": c["clip"]})
    try:
        ctl = e.call("clip.controllers", {"track": track_ref, "clip": c["clip"]})
    except Exception:  # noqa: BLE001
        ctl = {"cc": [], "bend": []}
    mute = xml_clip is not None and xml_clip.get("mute", "0") in ("1", "true")
    return {"index": c["clip"], "name": c.get("name"), "start_beat": c["start"], "end_beat": c["end"], "mute": mute,
            "notes": notes, "cc": ctl.get("cc", []), "bend": ctl.get("bend", [])}


# ---------------------------------------------------------------------------- 공개 함수
def _resolve_edit(project=None, path=None):
    if path:
        return Path(path)
    p = Path(project)
    if p.suffix == ".tracktionedit":
        return p
    return ROOT / "projects" / project / f"{project}.tracktionedit"


def export_plan(e=None, project=None, path=None, start_beat=None, end_beat=None, tail=2.0, sample_rate=48000):
    """지금 열린 곡(또는 project/path 를 열어서) → 렌더 계획 dict."""
    e = e or connect("core-export")
    if project or path:
        f = _resolve_edit(project, path)
        if not f.exists():
            raise FileNotFoundError(f)
        e.call("edit.load", {"path": str(f)})
    info = e.call("edit.info")
    bpm = float(info["bpm"])
    xml_tracks = _xml_tracks(_read_xml(info.get("path", "")))
    warnings = []

    tracks = []
    for ti, t in enumerate(info["tracks"]):
        xt = xml_tracks[ti] if ti < len(xml_tracks) and xml_tracks[ti]["name"] == t["name"] else None
        if xt is None and xml_tracks:
            warnings.append(f"track {t['name']}: saved XML does not match (audio clip details may be missing)")
        chain = []
        for di, d in enumerate(t.get("devices", [])):
            xp = xt["plugins"][di] if xt and di < len(xt["plugins"]) else None
            chain.append(_device(e, ti, d, xp))
        midi, audio = [], []
        for c in t.get("clips", []):
            xc = xt["clips"][c["clip"]] if xt and c["clip"] < len(xt["clips"]) else None
            if c.get("type") == "midi":
                midi.append(_midi_clip(e, ti, c, xc))
            else:
                audio.append(_audio_clip(c, xc, bpm))
        tracks.append({"index": ti, "name": t["name"], "volume_db": float(t.get("volume_db", 0.0)),
                       "pan": float(t.get("pan", 0.0)), "mute": bool(t.get("mute")), "solo": bool(t.get("solo")),
                       "chain": chain, "midi_clips": midi, "audio_clips": audio})

    master = info.get("master", {})
    master_chain = [_device(e, "master", d, None) for d in master.get("devices", [])]
    length = float(info.get("length_beats", 0.0))
    plan = {
        "format": FORMAT, "version": VERSION,
        "source": {"edit": info.get("path"), "exported": time.strftime("%Y-%m-%d %H:%M:%S")},
        "bpm": bpm, "time_sig": info.get("time_sig", "4/4"), "tempo": [{"beat": 0, "bpm": bpm}],
        "length_beats": length,
        "render": {"start_beat": 0.0 if start_beat is None else start_beat,
                   "end_beat": length if end_beat is None else end_beat, "tail_sec": tail, "sample_rate": sample_rate},
        "master": {"volume_db": float(master.get("volume_db", 0.0)), "chain": master_chain},
        "tracks": tracks,
    }
    if warnings:
        plan["warnings"] = warnings
    return plan


def save_plan(plan, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def summary(plan):
    """사람이 읽는 요약: 트랙별 악기·클립 수·C1 지원 여부."""
    rows = []
    for t in plan["tracks"]:
        inst = next((d for d in t["chain"] if d.get("kind") in ("sfz", "vst3", "builtin_synth")), None)
        unsupported = [d.get("kind") for d in t["chain"] if d.get("supported") is False]
        rows.append({"track": t["name"], "instrument": (inst or {}).get("sfz") or (inst or {}).get("plugin"),
                     "midi_clips": len(t["midi_clips"]), "audio_clips": len(t["audio_clips"]),
                     "unsupported": unsupported})
    return rows


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if not args:
        print("usage: python -m musicoma.core_export <out.json> [project|edit-path]")
        raise SystemExit(2)
    src = args[1] if len(args) > 1 else None
    kw = {"path": src} if src and src.endswith(".tracktionedit") else ({"project": src} if src else {})
    p = export_plan(**kw)
    print(save_plan(p, args[0]))
    for r in summary(p):
        print(r)
