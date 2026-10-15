"""Song — Claude 가 곡을 다루는 기본 단위.

엔진 명령(트랙·디바이스·클립) 위에 '역할' 과 '섹션' 과 '기록' 을 얹는다.
곡마다 projects/<name>/song.json 에 메타가 남아 다음 대화에서도 이어 작업할 수 있다.

    s = Song.new("seoul-night", bpm=88, key="Eb major", style="chipmunk-soul")
    d = s.track("Drums", "drums_vintage", role="drums")
    d.fx("compressor", {"threshold": -18, "ratio": 4, "attack": 20})
    d.midi(notes, start=0, length=16)
    s.section("verse", 4, 16)
    s.render()                      # → wav + ears 리포트 + png
"""
import json
import shutil
import time
from pathlib import Path

from . import ears as ears_mod
from .engine import connect
from .knowledge import resolve_sound, style as load_style
from .master import master

ROOT = Path(__file__).resolve().parent.parent


class Track:
    def __init__(self, song, name):
        self.song = song
        self.name = name

    @property
    def e(self):
        return self.song.e

    def info(self):
        return next(t for t in self.e.call("edit.info")["tracks"] if t["name"] == self.name)

    def fx(self, device, params=None, **kw):
        """이펙트/디바이스 추가. params 는 {이름|id: 값|'텍스트'}."""
        d = self.e.call("device.add", {"track": self.name, "device": device, **kw})
        if params:
            self.e.call("device.set", {"track": self.name, "device": d["device"], "params": params})
        return d["device"]

    def set(self, device, params=None, **kw):
        return self.e.call("device.set", {"track": self.name, "device": device, "params": params or {}, **kw})

    def params(self, device, filter=None):
        return self.e.call("device.params", {"track": self.name, "device": device, **({"filter": filter} if filter else {})})

    def send(self, bus, level_db=-12.0):
        return self.e.call("device.add", {"track": self.name, "device": "send", "bus": bus, "level_db": level_db})

    def mix(self, **kw):
        """volume_db / pan / mute / solo"""
        return self.e.call("track.set", {"track": self.name, **kw})

    def midi(self, notes, start=0.0, length=None, name="MIDI", cc=None, bend=None):
        if length is None:
            end = max((n["start"] + n["length"] for n in notes), default=4)
            length = max(4, -(-end // 4) * 4)
        return self.e.call("clip.add_midi", {"track": self.name, "start": start, "length": length, "name": name,
                                             "notes": notes, **({"cc": cc} if cc else {}), **({"bend": bend} if bend else {})})

    def audio(self, path, start=0.0, **kw):
        return self.e.call("clip.add_audio", {"track": self.name, "path": str(path), "start": start, **kw})

    def automate(self, device, param, points, clear=True):
        return self.e.call("automation.set", {"track": self.name, "device": device, "param": param,
                                              "points": points, "clear": clear})

    def clips(self):
        return self.e.call("clip.list", {"track": self.name})

    def clear(self):
        for c in reversed(self.clips()):
            self.e.call("clip.remove", {"track": self.name, "clip": c["clip"]})

    def preset(self, role, key):
        """음색 프리셋 적용: 악기·이펙트를 갈고(센드는 유지) 연주 설정을 기록한다."""
        from .knowledge import presets as load_presets
        pr = load_presets()[role][key]
        info = self.info()
        for d in reversed(info["devices"]):
            if d["type"] not in ("auxsend", "auxreturn"):
                self.e.call("device.remove", {"track": self.name, "device": d["device"]})
        r = resolve_sound(pr["sound"])
        add = {"track": self.name, "device": r["device"], "index": 0, **({"sfz": r["sfz"]} if "sfz" in r else {})}
        dev = self.e.call("device.add", add)
        if "patch" in r:
            self.e.call("device.load_file", {"track": self.name, "device": dev["device"], "path": r["patch"]})
        for fx in pr.get("fx", []):
            self.fx(fx["device"], fx.get("params"))
        meta = self.song.meta.setdefault("tracks", {}).setdefault(self.name, {})
        meta.update({"sound": pr["sound"], "preset": f"{role}/{key}", "perform": pr.get("perform")})
        self.song.save()
        return {"track": self.name, "preset": pr["name"], "sound": pr["sound"], "perform": pr.get("perform")}

    def show(self, device=0):
        """플러그인 창을 띄워 사람이 직접 만지게."""
        return self.e.call("device.show", {"track": self.name, "device": device})


class Song:
    def __init__(self, name, e=None):
        self.name = name
        self.e = e or connect("claude")
        self.dir = ROOT / "projects" / name
        self.meta_path = self.dir / "song.json"
        self.meta = json.loads(self.meta_path.read_text(encoding="utf-8")) if self.meta_path.exists() else {}

    # ---------------------------------------------------------------- 만들기/열기
    @classmethod
    def new(cls, name, bpm=90, key=None, style=None, time_sig="4/4", brief=""):
        s = cls(name)
        s.e.call("edit.new", {"name": name, "bpm": bpm, "time_sig": time_sig})
        s.meta = {"name": name, "bpm": bpm, "key": key, "style": style, "time_sig": time_sig, "brief": brief,
                  "created": time.strftime("%Y-%m-%d %H:%M"), "tracks": {}, "sections": [], "sources": [],
                  "history": [], "versions": []}
        s.save()
        return s

    @classmethod
    def open(cls, name):
        s = cls(name)
        f = s.dir / f"{name}.tracktionedit"
        if not f.exists():
            raise FileNotFoundError(f)
        s.e.call("edit.load", {"path": str(f)})
        return s

    def save(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.meta_path.write_text(json.dumps(self.meta, ensure_ascii=False, indent=1), encoding="utf-8")
        try:
            self.e.call("edit.save")
        except Exception:
            pass

    def log(self, request, did):
        """사용자 요청과 그에 대해 한 일을 남긴다(미세조정의 맥락 = 다음 판단 근거)."""
        self.meta.setdefault("history", []).append({"t": time.strftime("%m-%d %H:%M"), "request": request, "did": did})
        self.save()

    @property
    def style_card(self):
        try:
            return load_style(self.meta["style"]) if self.meta.get("style") else None
        except FileNotFoundError:          # 카드가 없는 장르 이름(예: 'soul')이면 카드 없이 진행
            return None

    @property
    def bpm(self):
        return self.meta["bpm"]

    def bars(self, n):
        return n * 4  # 4/4 가정: 마디 → 박

    # ---------------------------------------------------------------- 트랙
    def track(self, name, sound=None, role=None, volume_db=None, pan=None):
        """트랙 하나 + 악기. sound 는 역할 이름(piano_grand, rhodes, bass_sub...) / 'Keys/EP 2' / sfz 경로 / VST 이름."""
        names = [t["name"] for t in self.e.call("edit.info")["tracks"]]
        if name not in names:
            self.e.call("track.add", {"name": name})
        t = Track(self, name)
        if sound:
            r = resolve_sound(sound)
            add = {"track": name, "device": r["device"]}
            if "sfz" in r:
                add["sfz"] = r["sfz"]
            self.e.call("device.add", add)
            if "patch" in r:
                self.e.call("device.load_file", {"track": name, "device": 0, "path": r["patch"]})
        if volume_db is not None or pan is not None:
            t.mix(**{k: v for k, v in (("volume_db", volume_db), ("pan", pan)) if v is not None})
        self.meta.setdefault("tracks", {})[name] = {"sound": sound, "role": role}
        self.save()
        return t

    def __getitem__(self, name):
        return Track(self, name)

    def bus(self, name, device="Dragonfly Hall Reverb", bus=0, params=None, volume_db=0.0):
        """리턴 버스(공유 리버브 등). 보내는 쪽은 track.send(bus, dB)."""
        t = self.track(name, role=f"return bus {bus}")
        self.e.call("device.add", {"track": name, "device": "return", "bus": bus})
        if device:
            t.fx(device, params)
        t.mix(volume_db=volume_db)
        self.meta["tracks"][name]["bus"] = bus
        self.save()
        return t

    def master_fx(self, device, params=None):
        d = self.e.call("device.add", {"track": "master", "device": device})
        if params:
            self.e.call("device.set", {"track": "master", "device": d["device"], "params": params})
        return d["device"]

    # ---------------------------------------------------------------- 구조
    def section(self, name, start_bar, bars):
        secs = [s for s in self.meta.get("sections", []) if s["name"] != name or s["start_bar"] != start_bar]
        secs.append({"name": name, "start_bar": start_bar, "bars": bars})
        self.meta["sections"] = sorted(secs, key=lambda s: s["start_bar"])
        self.save()

    def where(self, section_name, occurrence=0):
        """섹션 이름 → (시작 박, 길이 박)"""
        hits = [s for s in self.meta.get("sections", []) if s["name"] == section_name]
        s = hits[occurrence]
        return s["start_bar"] * 4, s["bars"] * 4

    # ---------------------------------------------------------------- 결과
    def render(self, lufs=None, start=None, end=None, tail=2.5, png=True, ref=None, label=None):
        if lufs is None and self.style_card:
            lufs = self.style_card.get("mix", {}).get("target_lufs")
        params = {"tail": tail}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        out_dir = self.dir / "renders"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%m%d-%H%M%S")
        params["path"] = str(out_dir / f"{self.name}_{label or stamp}.wav")
        r = self.e.call("render", params)
        raw = r["path"]
        if lufs is not None:
            m = master(raw, lufs=lufs, glue=True)
            Path(raw).unlink()
            Path(m["path"]).rename(raw)
        report, audio, sr = ears_mod.analyze(r["path"])
        if png:
            p = str(Path(r["path"]).with_suffix(".png"))
            refrep = ears_mod.analyze(ref)[0] if ref else None
            ears_mod.draw(report, audio, sr, p, refrep)
            report["png"] = p
        if ref:
            report["vs_reference"] = ears_mod.compare(report, ears_mod.analyze(ref)[0])
        report["render_ms"] = r.get("render_ms")
        return report

    def render_stems(self, start=None, end=None):
        """트랙마다 따로 렌더해 음량·대역을 잰다 → 어느 트랙이 어느 대역을 차지하는지(믹스 판단용)."""
        info = self.e.call("edit.info")
        out_dir = self.dir / ".work/stems"          # 측정용 트랙별 렌더 — 중간 파일
        out_dir.mkdir(parents=True, exist_ok=True)
        for old in out_dir.glob("*.wav"):
            try:
                old.unlink()
            except OSError:
                pass
        stamp = time.strftime("%H%M%S")
        rows = []
        for t in info["tracks"]:
            if t["mute"]:
                continue
            params = {"tracks": [t["name"]], "tail": 1.5, "path": str(out_dir / f"{t['name']}_{stamp}.wav")}
            if start is not None:
                params["start"] = start
            if end is not None:
                params["end"] = end
            try:
                r = self.e.call("render", params)
            except Exception as ex:          # 소리 없는 트랙(리턴 버스 단독 등)
                rows.append({"track": t["name"], "error": str(ex)[:80]})
                continue
            rep, _, _ = ears_mod.analyze(r["path"])
            rows.append({"track": t["name"], "lufs": rep["loudness"]["lufs_integrated"],
                         "peak": rep["loudness"]["sample_peak_dbfs"], "bands_db": rep["bands_db"],
                         "width": rep["stereo"]["width_side_to_mid_db"]})
        return rows

    def balance(self, targets=None, reference="drums", max_move_db=12.0, passes=3, tolerance_lu=0.7):
        """여러 번 재고 고친다 — 트랙 볼륨이 컴프레서 앞에 있으면 올린 만큼 안 올라가서(10-15 kanye 랩이 묻힌 원인),
        한 번에 맞추면 오차가 남는다. 매번 다시 렌더해 측정, 모두 tolerance 안이면 멈춘다."""
        all_moves, res = [], None
        for i in range(passes):
            res = self._balance_once(targets, reference, max_move_db, tolerance_lu)
            all_moves += [{**m, "pass": i + 1} for m in res["moves"]]
            if not res["moves"]:
                break
        return {"reference": res["reference"] if res else reference, "moves": all_moves}

    def _balance_once(self, targets=None, reference="drums", max_move_db=12.0, tolerance_lu=0.5):
        """역할별 음량 비율 맞추기. targets = {트랙이름 또는 역할 키워드: 기준 대비 LU}.

        기준 트랙(reference) = 0. 예: {"drums": 0, "sample": -2, "bass": -3, "keys": -7}
        장르 카드 mix.balance_lu 가 있으면 그걸 쓴다. 바꾼 양을 돌려준다.
        """
        if targets is None:
            targets = (self.style_card or {}).get("mix", {}).get("balance_lu")
        if not targets:
            raise ValueError("no balance targets (style card mix.balance_lu)")
        rows = {r["track"]: r for r in self.render_stems() if r.get("lufs") is not None}
        tracks_meta = self.meta.get("tracks", {})

        def target_for(name):
            key = name.lower()
            role = (tracks_meta.get(name, {}).get("role") or "").lower()
            for k, v in targets.items():
                if k.lower() == key or k.lower() in key or k.lower() in role:
                    return v
            return None

        ref_name = next((n for n in rows if target_for(n) == 0 and reference.lower() in n.lower()), None) \
            or next((n for n in rows if target_for(n) == 0), None)
        if ref_name is None:
            raise ValueError("reference track not found among rendered stems")
        ref_lufs = rows[ref_name]["lufs"]
        info = {t["name"]: t for t in self.e.call("edit.info")["tracks"]}
        moves = []
        for name, r in rows.items():
            tgt = target_for(name)
            if tgt is None or name == ref_name:
                continue
            delta = max(-max_move_db, min(max_move_db, (ref_lufs + tgt) - r["lufs"]))
            if abs(delta) < tolerance_lu:
                continue
            want = round(info[name].get("volume_db", 0) + delta, 1)
            new_db = min(want, 6.0)                    # 트랙 페이더 최대 +6dB — 넘치는 만큼은 오디오 클립 게인으로
            self.e.call("track.set", {"track": name, "volume_db": new_db})
            extra = round(want - new_db, 1)
            if extra > 0.05:
                for c in self.e.call("clip.list", {"track": name}):
                    if c.get("type") == "audio":
                        self.e.call("clip.set", {"track": name, "clip": c["clip"],
                                                 "gain_db": round(c.get("gain_db", 0) + extra, 1)})
            moves.append({"track": name, "was_lu": round(r["lufs"] - ref_lufs, 1), "target_lu": tgt,
                          "volume_db": new_db, "moved_db": round(delta, 1)})
        self.save()
        return {"reference": ref_name, "moves": moves}

    def snapshot(self, label, note=""):
        """지금 상태를 버전으로 고정(.tracktionedit 복사 + 렌더)."""
        self.save()
        vdir = self.dir / "versions"
        vdir.mkdir(exist_ok=True)
        src = self.dir / f"{self.name}.tracktionedit"
        dst = vdir / f"{label}.tracktionedit"
        shutil.copy2(src, dst)
        rep = self.render(label=label)
        self.meta.setdefault("versions", []).append({"label": label, "note": note, "edit": str(dst),
                                                     "render": rep["file"], "t": time.strftime("%m-%d %H:%M")})
        self.save()
        return rep

    def summary(self):
        info = self.e.call("edit.info")
        return {"meta": {k: self.meta.get(k) for k in ("name", "bpm", "key", "style", "brief", "sections")},
                "tracks": [{"name": t["name"], "role": self.meta.get("tracks", {}).get(t["name"], {}).get("role"),
                            "volume_db": round(t.get("volume_db", 0), 1), "pan": round(t.get("pan", 0), 2),
                            "mute": t["mute"], "devices": [d["name"] for d in t["devices"]],
                            "clips": len(t["clips"])} for t in info["tracks"]],
                "length_beats": info["length_beats"],
                "recent_history": self.meta.get("history", [])[-5:]}
