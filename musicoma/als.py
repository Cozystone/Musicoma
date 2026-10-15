"""Ableton Live 세트(.als) → Musicoma 곡. 본인이 만든 프로젝트를 Musicoma 로 옮기는 용도(호환).

.als = gzip 으로 감싼 XML. 읽는 것: 템포·박자, 로케이터(→섹션), 트랙 이름·색·볼륨·팬·뮤트, 센드,
MIDI 클립(노트·루프), 오디오 클립(샘플·오프셋·워프), 디바이스.

Ableton 고유 악기(Drift·Operator·Wavetable…)는 Musicoma 에서 돌 수 없다 → 트랙 이름/역할로 고른 Surge 패치.
샘플 악기(Simpler·Sampler·드럼 랙)는 들어 있는 샘플로 SFZ 를 만들어 원래 소리를 살린다.
이펙트는 비슷한 내장 디바이스로(EQ8→eq, Compressor→compressor, Reverb→send 버스 …), 못 옮긴 것은 보고에 남긴다.
"""
import gzip
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from . import crate
from .song import Song

ROOT = Path(__file__).resolve().parent.parent

SYNTHS = {"Drift", "Operator", "UltraAnalog", "InstrumentVector", "Wavetable", "Meld", "Tension", "Collision",
          "LoungeLizard", "StringStudio", "Electric", "InstrumentMeld", "Poli", "Bass"}
SAMPLERS = {"OriginalSimpler", "MultiSampler", "Simpler", "Sampler"}
FX_MAP = {"Eq8": "eq", "FilterEQ3": "eq", "ChannelEq": "eq", "Compressor2": "compressor", "GlueCompressor": "compressor",
          "Limiter": "compressor", "AutoFilter": "lowpass", "AutoFilter2": "lowpass", "Chorus2": "chorus",
          "Phaser": "phaser", "PhaserNew": "phaser", "Delay": "delay", "PingPongDelay": "delay"}

ROLE_PATCH = [  # 트랙 이름에 들어 있으면 → 소리
    (r"bass|sub|808", "bass_sub"), (r"pad|ambient|atmos|drone|swell", "pad_warm"),
    (r"key|piano|rhodes|ep\b|organ", "rhodes"), (r"brass|horn", "brass_synth"), (r"string", "strings_violins"),
    (r"pluck|arp|bell|mallet", "pluck"), (r"lead|melod|synth|hook", "lead"), (r"choir|vox|vocal", "pad_choir"),
]


def _v(e, path, default=None):
    n = e.find(path)
    return n.get("Value") if n is not None else default


def _f(e, path, default=0.0):
    v = _v(e, path)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def load(path):
    raw = gzip.open(path).read()
    return ET.fromstring(raw)


def _db(lin):
    return round(20 * math.log10(max(float(lin), 1e-6)), 2)


def _sample_path(fileref, als_dir):
    p = _v(fileref, "Path")
    if p and Path(p).exists():
        return p
    rel = _v(fileref, "RelativePath")
    if rel:
        cand = Path(als_dir) / rel
        if cand.exists():
            return str(cand)
    return p


def _role_sound(name):
    for pat, sound in ROLE_PATCH:
        if re.search(pat, name, re.I):
            return sound
    return "rhodes"


def _instrument(track, als_dir, out_dir):
    """트랙의 첫 악기 → ('sfz', path) | ('surge', role) | (None, None), 메모"""
    devs = track.find("DeviceChain/DeviceChain/Devices")
    if devs is None:
        return None, None, []
    notes = []
    for d in devs:
        tag = d.tag
        if tag in SAMPLERS:
            refs = d.findall(".//SampleRef/FileRef")
            paths = [_sample_path(r, als_dir) for r in refs]
            paths = [p for p in paths if p and Path(p).exists()]
            if paths:
                sfz = out_dir / f"{_safe(track)}.sfz"
                root_key = int(_f(d, ".//RootKey", 60)) if d.find(".//RootKey") is not None else 60
                crate.make_instrument(paths[0], sfz, root_note=root_key)
                return "sfz", str(sfz), [f"{tag} → SFZ ({Path(paths[0]).name})"]
        if tag == "DrumGroupDevice":
            pads = []
            for branch in d.findall(".//DrumBranch"):
                key = branch.find(".//ReceivingNote")
                ref = branch.find(".//SampleRef/FileRef")
                if key is None or ref is None:
                    continue
                p = _sample_path(ref, als_dir)
                if p and Path(p).exists():
                    # Ableton 드럼랙의 ReceivingNote 는 128-노트 번호
                    pads.append((128 - int(key.get("Value")), p))
            if pads:
                sfz = out_dir / f"{_safe(track)}_kit.sfz"
                lines = ["<global>", "loop_mode=one_shot", "ampeg_release=0.05"]
                for note, p in sorted(pads):
                    lines += ["<region>", f"sample={Path(p).as_posix()}", f"key={note}"]
                sfz.write_text("\n".join(lines) + "\n", encoding="utf-8")
                return "sfz", str(sfz), [f"Drum Rack → SFZ kit ({len(pads)} pads)"]
        if tag in SYNTHS:
            return "surge", _role_sound(_name(track)), [f"{tag} → Surge '{_role_sound(_name(track))}' (Ableton 고유 신스는 대체)"]
        if tag == "InstrumentGroupDevice":
            inner = d.find(".//Devices")
            if inner is not None and len(inner):
                notes.append("Instrument Rack: 첫 체인의 악기 기준")
                fake = ET.Element("T")
                dc = ET.SubElement(ET.SubElement(fake, "DeviceChain"), "DeviceChain")
                dc.append(inner)
                fake.append(track.find("Name"))
                k, v, n = _instrument(fake, als_dir, out_dir)
                if k:
                    return k, v, notes + n
        if tag == "PluginDevice":
            name = _v(d, ".//PluginDesc//PlugName") or _v(d, ".//PluginDesc//Name") or "plugin"
            return "vst", name, [f"VST {name}"]
    return None, None, notes


def _effects(track):
    out, skipped = [], []
    devs = track.find("DeviceChain/DeviceChain/Devices")
    if devs is None:
        return out, skipped
    for d in devs:
        if d.tag in FX_MAP:
            out.append(FX_MAP[d.tag])
        elif d.tag not in SAMPLERS | SYNTHS | {"DrumGroupDevice", "InstrumentGroupDevice", "PluginDevice", "MidiPitcher",
                                              "MidiScaleConstrain"}:
            skipped.append(d.tag)
    return out, skipped


def _name(track):
    return _v(track, "Name/EffectiveName") or _v(track, "Name/UserName") or track.tag


def _safe(track):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", _name(track))[:40]


def _midi_notes(clip):
    start, end = _f(clip, "CurrentStart"), _f(clip, "CurrentEnd")
    loop_on = _v(clip, "Loop/LoopOn") == "true"
    ls, le = _f(clip, "Loop/LoopStart"), _f(clip, "Loop/LoopEnd")
    raw = []
    for kt in clip.findall("Notes/KeyTracks/KeyTrack"):
        key = int(_v(kt, "MidiKey"))
        for n in kt.findall("Notes/MidiNoteEvent"):
            if n.get("IsEnabled", "true") == "false":
                continue
            raw.append((float(n.get("Time")), float(n.get("Duration")), int(float(n.get("Velocity"))), key))
    length = end - start
    notes = []
    if loop_on and le > ls:
        span = le - ls
        k = 0
        while k * span < length:
            for t, d, v, p in raw:
                if ls <= t < le:
                    at = (t - ls) + k * span
                    if at < length:
                        notes.append({"pitch": p, "start": round(max(0, at), 5), "length": round(min(d, length - at), 5), "velocity": v})
            k += 1
    else:
        for t, d, v, p in raw:
            at = t - ls
            if 0 <= at < length:
                notes.append({"pitch": p, "start": round(at, 5), "length": round(min(d, length - at), 5), "velocity": v})
    return start, length, notes


def import_als(path, name=None, log=print):
    path = Path(path)
    root = load(path)
    ls = root.find("LiveSet")
    tempo = _f(ls, "MainTrack/DeviceChain/Mixer/Tempo/Manual", 120.0) or 120.0
    num = _v(ls, ".//MainTrack//TimeSignature//Numerator") or "4"
    name = name or re.sub(r"[^a-z0-9-]+", "-", path.stem.lower()).strip("-")
    out_dir = ROOT / "projects" / name / "imported"
    out_dir.mkdir(parents=True, exist_ok=True)
    s = Song.new(name, bpm=tempo, brief=f"imported from {path.name}")
    report = {"source": str(path), "tempo": tempo, "tracks": [], "skipped_effects": {}, "notes": []}

    # 로케이터 → 섹션 (박 → 마디)
    locs = sorted(((_f(l, "Time"), _v(l, "Name")) for l in ls.findall("Locators/Locators/Locator")))
    for i, (t, nm) in enumerate(locs):
        nxt = locs[i + 1][0] if i + 1 < len(locs) else None
        bars = int(round(((nxt or t + 32) - t) / 4))
        s.section(re.sub(r"\s+", "-", (nm or f"loc{i}").lower()), int(t // 4), max(1, bars))

    # 리턴 트랙 → 버스 (리버브·딜레이 성격만 옮김)
    returns = [t for t in ls.find("Tracks") if t.tag == "ReturnTrack"]
    for bi, rt in enumerate(returns):
        devs = [d.tag for d in rt.find("DeviceChain/DeviceChain/Devices")]
        dev = "Dragonfly Hall Reverb" if any("Reverb" in d or "Hybrid" in d for d in devs) else \
              ("delay" if any("Delay" in d or "Echo" in d for d in devs) else "Dragonfly Room Reverb")
        s.bus(f"Return {chr(65 + bi)}", dev, bus=bi, volume_db=_db(_f(rt, "DeviceChain/Mixer/Volume/Manual", 1.0)))

    for tr in ls.find("Tracks"):
        if tr.tag not in ("MidiTrack", "AudioTrack"):
            continue
        tname = _name(tr)
        mix = tr.find("DeviceChain/Mixer")
        vol = _db(_f(mix, "Volume/Manual", 1.0))
        pan = _f(mix, "Pan/Manual", 0.0)
        muted = _v(mix, "Speaker/Manual") == "false"
        row = {"track": tname, "type": tr.tag, "volume_db": vol, "pan": pan, "color": int(_f(tr, "Color", 0))}
        if tr.tag == "MidiTrack":
            kind, val, notes = _instrument(tr, path.parent, out_dir)
            row["instrument"] = notes
            sound = val if kind in ("sfz", "surge") else None
            t = s.track(tname, sound, role=f"imported {tr.tag}", volume_db=vol, pan=pan)
            if kind == "vst":
                try:
                    s.e.call("device.add", {"track": tname, "device": val})
                except Exception as ex:
                    row["instrument"].append(f"VST 못 찾음: {ex}")
            n_notes = 0
            for c in tr.findall("DeviceChain/MainSequencer/ClipTimeable/ArrangerAutomation/Events/MidiClip"):
                start, length, notes_ = _midi_notes(c)
                if length <= 0:
                    continue
                s.e.call("clip.add_midi", {"track": tname, "start": start, "length": length,
                                           "name": _v(c, "Name") or "clip", "notes": notes_})
                n_notes += len(notes_)
            row["notes"] = n_notes
        else:
            t = s.track(tname, None, role=f"imported {tr.tag}", volume_db=vol, pan=pan)
            n_clips = 0
            for c in tr.findall("DeviceChain/MainSequencer/Sample/ArrangerAutomation/Events/AudioClip"):
                f = _sample_path(c.find("SampleRef/FileRef"), path.parent)
                if not f or not Path(f).exists():
                    report["notes"].append(f"{tname}: 샘플 없음 {f}")
                    continue
                start, end = _f(c, "CurrentStart"), _f(c, "CurrentEnd")
                warped = _v(c, "IsWarped") == "true"
                src = f
                marks = [(float(w.get("SecTime")), float(w.get("BeatTime"))) for w in c.findall("WarpMarkers/WarpMarker")]
                if warped and len(marks) >= 2 and marks[-1][1] > marks[0][1]:
                    # 워프: 소스 초/박 비율 → 이 곡 템포로 늘이기(음정 유지)
                    sec_per_beat_src = (marks[-1][0] - marks[0][0]) / (marks[-1][1] - marks[0][1])
                    rate = (60.0 / tempo) / sec_per_beat_src
                    if abs(rate - 1) > 0.002:
                        src = crate.stretch(f, rate=1 / rate, out=out_dir / f"{_safe(tr)}_{n_clips}_warp.wav")
                    offset = _f(c, "Loop/LoopStart") * (60.0 / tempo)
                else:
                    offset = _f(c, "Loop/LoopStart")
                semis = _f(c, "PitchCoarse")
                if semis:
                    src = crate.stretch(src, rate=1.0, semitones=semis, out=out_dir / f"{_safe(tr)}_{n_clips}_pitch.wav")
                s.e.call("clip.add_audio", {"track": tname, "path": str(src), "start": start, "length": end - start,
                                            "offset": max(0.0, offset), "gain_db": _db(_f(c, "SampleVolume", 1.0)),
                                            "name": _v(c, "Name") or Path(f).stem})
                n_clips += 1
            row["audio_clips"] = n_clips
        fx, skipped = _effects(tr)
        for fx_name in fx:
            try:
                t.fx(fx_name)
            except Exception:
                skipped.append(fx_name)
        for i, send in enumerate(mix.findall("Sends/TrackSendHolder")):
            lvl = _f(send, "Send/Manual", 0.0)
            if lvl > 0.001 and i < len(returns):
                t.send(i, _db(lvl))
        if muted:
            t.mix(mute=True)
        s.meta["tracks"][tname]["color"] = row["color"]
        row["effects"] = fx
        if skipped:
            report["skipped_effects"][tname] = skipped
        report["tracks"].append(row)
        log(f"{tname}: {row}")
    s.meta["imported_from"] = str(path)
    s.save()
    return s, report
