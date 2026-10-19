"""musicoma-021 「Say It Again」 v3 — 애프터워드: 빈자리는 가사로 만든다.

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
           "one line then a long pause, lots of space, no singing, dry close mic")
    sections = [{"name": n, "start": round(secs[n] * W.SPB, 3), "end": round((secs[n] + 64) * W.SPB, 3), "tag": "Verse", "lyrics": "\n".join(L), "key": W.KEY}
                for n, L in (("verse1", VERSE1), ("verse2", VERSE2))]
    sections.append({"name": "hook1", "start": round(secs["hook1"] * W.SPB, 3), "end": round((secs["hook1"] + 32) * W.SPB, 3), "tag": "Chorus",
                     "lyrics": "\n".join(HOOK + HOOK), "key": W.KEY})
    out = d / "vocals" / "rap3"
    _, rp = lego.vocal_track(beat, sections, W.BPM, W.KEY, cap, out, takes=10, guide_wav=guide, pass_wer=0.3, min_key_fit=0.0, lang="en", reference=str(RAP_REF), log=log)
    log("[rap] " + " · ".join(f"{r['section']} 오류율 {r['wer']}" for r in rp))
    st = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    by = {x["name"]: x for x in st["sections"]}
    sr = 48000
    ep, gaps_report = [], {}
    plan = (("verse1", 4, "Sax", 57, 76, ["verse1"]), ("verse2", 4, "Sax", 57, 76, ["verse2"]), ("hook1", 4, "Bell", 69, 88, ["hook1", "hook2", "hook3"]))
    v1_answers = []
    for name, n_lines, trk, lo, hi, targets in plan:
        sec = by[name]
        y, s2 = sf.read(sec["file"], dtype="float32", always_2d=True); assert s2 == sr
        mono = y.mean(1)
        lines = phrase_lines(mono, sr, n_lines)
        rows = []
        for k, (a, e) in enumerate(lines):
            ans = syllable_answer(mono[int(a * sr):int(e * sr)], sr, lo, hi)
            sec_end = (secs[name] + (32 if name == "hook1" else 64)) * W.SPB - sec["place_s"]       # 파일 기준 구간 끝(초)
            nxt = lines[k + 1][0] if k + 1 < len(lines) else sec_end
            gap_b = (nxt - e) / W.SPB
            rows.append(round(gap_b, 1))
            if name == "verse1":
                v1_answers.append(ans)
            if gap_b < 1.25 or not ans:
                continue
            # 곡 박 위치(구간 시작 기준): 말 끝 + 반박
            end_abs_b = (sec["place_s"] + e) / W.SPB
            start_rel = round((end_abs_b - secs[name] + .5) * 2) / 2
            room = gap_b - .75
            span = ans[-1]["start"] + ans[-1]["length"]
            sc = min(1.0, room / max(.5, span))
            notes = [{**x, "start": round(x["start"] * sc * 4) / 4, "length": max(.25, round(x["length"] * sc * 4) / 4)} for x in ans]
            for tgt in targets:
                ep.append({"track": trk, "in": [tgt], "offset": start_rel, "notes": notes})
                if trk == "Bell":
                    ep.append({"track": "Sax", "in": [tgt], "offset": start_rel, "notes": [{**x, "pitch": x["pitch"] - 12, "velocity": 78} for x in notes]})
        gaps_report[name] = rows
    # 브리지: 밴드 혼자 1절을 '랩'
    t = 0.0; br = []
    for ans in v1_answers:
        br += [{**x, "start": round(t + x["start"], 2)} for x in ans]
        t += (ans[-1]["start"] + ans[-1]["length"] + 2.0) if ans else 6
    br = [x for x in br if x["start"] < 31.5]
    ep += [{"track": "Sax", "in": ["bridge"], "notes": br}, {"track": "Violin", "in": ["bridge"], "notes": [{**x, "pitch": x["pitch"] - 12} for x in br]}]
    log(f"[echo] 줄 뒤 빈자리(박) {gaps_report} → 대답 파트 {len(ep)}")
    # 보컬: 그대로(절은 lego 자리, 훅은 한 테이크를 세 번)
    vox = np.zeros((int((b * 4) * W.SPB * sr) + sr * 4, 2), np.float32)
    def put(f, at):
        v, _ = sf.read(f, dtype="float32", always_2d=True)
        if v.shape[1] == 1: v = np.repeat(v, 2, 1)
        i = int(at * sr); n = min(len(v), len(vox) - i); vox[i:i + n] += v[:n]
    put(by["verse1"]["file"], by["verse1"]["place_s"]); put(by["verse2"]["file"], by["verse2"]["place_s"])
    for sec in ("hook1", "hook2", "hook3"):
        put(by["hook1"]["file"], by["hook1"]["place_s"] + (secs[sec] - secs["hook1"]) * W.SPB)
    vw = d / "vocals" / "vox_v3.wav"; sf.write(str(vw), vox, sr, subtype="FLOAT")
    s2, rep2 = arrange.build(W.band_spec(ep), label="band3", fmt="wav", log=lambda m: None)
    mixed = d / "mix_v3.wav"; mix(rep2["file"], [vw], mixed)
    m = master.master(str(mixed), lufs=-11.0, ceiling=-1.0, glue=True, out=str(d / "renders" / f"{W.NAME}_v3.wav"))
    mp3 = Path(m["path"]).with_suffix(".mp3")
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", m["path"], "-b:a", "320k", str(mp3)], check=True)
    log(json.dumps({"file": str(mp3), "lufs": m["lufs"], "true_peak": m["true_peak"]}, ensure_ascii=False))
