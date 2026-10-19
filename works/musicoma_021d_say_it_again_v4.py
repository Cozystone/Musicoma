"""musicoma-021 「Say It Again」 v4 — 줄마다 부름 창(2마디) + 대답 창(2마디)을 박에 고정.

v3 측정: 한 구간에 4줄을 줘도 lego 는 줄 사이를 0.4~1.8박만 쉰다(빈자리 1.25박↑ 거의 없음) — lego 는 구간을 채운다.
v4: 줄 하나 = lego 구간 하나(2마디). 각 줄은 비트를 듣고 한 번에 부른 것이라 TTS 줄 붙이기와 다르다. 그 뒤 2마디 = 밴드의 대답.

v3 원래 설명: — 애프터워드: 빈자리는 가사로 만든다.

v1·v2 교훈: 절에 8줄을 주면 lego 가 쉬지 않고 이어 부른다(빈자리 0~2곳) → 대답할 곳이 없다. 줄을 잘라 다시 놓으면(v2) 끊긴 소리.
v3: 절마다 4줄만(16마디) → lego 가 한 호흡으로 부르되 줄 사이가 자연히 빈다. 그 빈자리에만 그 줄의 억양(×3 과장)을 악기가 대답.
랩은 손대지 않는다(자르거나 옮기지 않음). 훅은 한 테이크를 세 번.
    python works/musicoma_021c_say_it_again_v3.py
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from musicoma import arrange, lego, master
from musicoma_020_escape_velocity import mix, RAP_REF
import musicoma_021_say_it_again as W
from musicoma_021b_say_it_again_edit import phrase_lines, syllable_answer

VERSE1 = ["Dad calls on Sundays at nine, asks about the weather",
          "I say it's fine, he says good, that's the whole call",
          "He used to sing in the car, now he says drive safe",
          "I hear the TV behind him, a game that nobody's winning"]
VERSE2 = ["I wanted to say I'm tired, I said the rent went up",
          "He wanted to say he's lonely, he said the dog's getting old",
          "Two men reading the weather to each other every week",
          "There's a song under the small talk we both forgot the words to"]
HOOK = ["Say it again", "Without the words"]

if __name__ == "__main__":
    log = lambda m: print(m, flush=True)
    d = W.ROOT / "projects" / W.NAME
    secs, b = {}, 0
    for n, k in W.FORM:
        secs[n] = b * 4; b += k
    spec = W.band_spec()
    s, rep = arrange.build(spec, label="band0", fmt="wav", log=lambda m: None)
    beat = rep["file"]; guide = lego.render_guide(spec)
    cap = ("old school hip hop, male rapper, tired and tender, talking more than rapping, clear words, on the beat, "
           "no singing, dry close mic")
    sections = []
    for sec, lines in (("verse1", VERSE1), ("verse2", VERSE2)):
        for k, line in enumerate(lines):
            a = secs[sec] + k * 16                                            # 4마디마다 한 줄: 부름 2마디 + 대답 2마디
            sections.append({"name": f"{sec}_{k}", "start": round(a * W.SPB, 3), "end": round((a + 8) * W.SPB, 3), "tag": "Verse", "lyrics": line, "key": W.KEY})
    for k, line in enumerate(HOOK):
        a = secs["hook1"] + k * 16
        sections.append({"name": f"hook1_{k}", "start": round(a * W.SPB, 3), "end": round((a + 6) * W.SPB, 3), "tag": "Chorus", "lyrics": line, "key": W.KEY})
    out = d / "vocals" / "rap4"
    import os
    if os.environ.get("REUSE") and out.with_suffix(".json").exists():           # 이미 녹음한 것 그대로(NG 구간만 retake 한 뒤 다시 짓기)
        for sec_name in (os.environ.get("RETAKE") or "").split(","):
            if sec_name:
                lego.retake(str(out.with_suffix(".json")), sec_name, takes=8, enough=2, log=log)
    else:
        _, rp = lego.vocal_track(beat, sections, W.BPM, W.KEY, cap, out, takes=6, enough=2, guide_wav=guide, pass_wer=0.3, min_key_fit=0.0, lang="en", reference=str(RAP_REF), log=log)
        log("[rap] " + " · ".join(f"{r['section']} {r['wer']}" for r in rp))
    st = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    sr = 48000
    vox = np.zeros((int((b * 4) * W.SPB * sr) + sr * 4, 2), np.float32)
    def put(f, at):
        v, _ = sf.read(f, dtype="float32", always_2d=True)
        if v.shape[1] == 1: v = np.repeat(v, 2, 1)
        i = int(at * sr); n = min(len(v), len(vox) - i); vox[i:i + n] += v[:n]
    ep, v1_answers = [], []
    for x in st["sections"]:
        sec, k = x["name"].rsplit("_", 1); k = int(k)
        y, _ = sf.read(x["file"], dtype="float32", always_2d=True)
        mono = y.mean(1)
        from musicoma.vocal_align import _chunks
        ch = _chunks(mono, sr, gap=0.2, min_len=0.08, floor_db=-38)
        end_s = ch[-1][1] if ch else len(mono) / sr
        hook = sec == "hook1"
        ans = syllable_answer(mono[:int(end_s * sr)], sr, 69 if hook else 57, 88 if hook else 76)
        if sec == "verse1":
            v1_answers.append(ans)
        targets = ["hook1", "hook2", "hook3"] if hook else [sec]
        line_beat = k * 16
        end_rel = (x["place_s"] + end_s) / W.SPB - secs[sec]
        start_rel = max(line_beat + 4, round((end_rel + .5) * 2) / 2)
        room = line_beat + 15.5 - start_rel
        if ans:
            span = ans[-1]["start"] + ans[-1]["length"]
            sc = min(1.0, room / max(.5, span))
            notes = [{**n, "start": round(n["start"] * sc * 4) / 4, "length": max(.25, round(n["length"] * sc * 4) / 4)} for n in ans]
            trk = "Bell" if hook else "Sax"
            for tgt in targets:
                ep.append({"track": trk, "in": [tgt], "offset": start_rel, "notes": notes})
                if hook:
                    ep.append({"track": "Sax", "in": [tgt], "offset": start_rel, "notes": [{**n, "pitch": n["pitch"] - 12, "velocity": 78} for n in notes]})
        for tgt in targets:
            put(x["file"], x["place_s"] + (secs[tgt] - secs[sec]) * W.SPB)
    t = 0.0; br = []
    for ans in v1_answers:
        br += [{**n, "start": round(t + n["start"], 2)} for n in ans]; t += 8
    br = [n for n in br if n["start"] < 31.5]
    ep += [{"track": "Sax", "in": ["bridge"], "notes": br}, {"track": "Violin", "in": ["bridge"], "notes": [{**n, "pitch": n["pitch"] - 12} for n in br]}]
    log(f"[echo] 대답 파트 {len(ep)}")
    vw = d / "vocals" / "vox_v4.wav"; sf.write(str(vw), vox, sr, subtype="FLOAT")
    s2, rep2 = arrange.build(W.band_spec(ep), label="band4", fmt="wav", log=lambda m: None)
    mixed = d / "mix_v4.wav"; mix(rep2["file"], [vw], mixed)
    m = master.master(str(mixed), lufs=-11.0, ceiling=-1.0, glue=True, out=str(d / "renders" / f"{W.NAME}_{os.environ.get('LABEL', 'v4')}.wav"))
    mp3 = Path(m["path"]).with_suffix(".mp3")
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", m["path"], "-b:a", "320k", str(mp3)], check=True)
    log(json.dumps({"file": str(mp3), "lufs": m["lufs"], "true_peak": m["true_peak"]}, ensure_ascii=False))
