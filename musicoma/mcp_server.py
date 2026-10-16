"""Musicoma MCP 서버 — Claude Code 가 음악을 만들고 고치는 도구 묶음.

등록: D:/0.Musicoma/.mcp.json (프로젝트 범위). 실행: .venv/Scripts/python -m musicoma.mcp_server
"""
import json
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from musicoma import crate as crate_mod, groove, knowledge, theory, transcribe as tr  # noqa: E402
from musicoma.engine import connect  # noqa: E402
from musicoma.song import Song  # noqa: E402

mcp = FastMCP("musicoma", instructions=(
    "Musicoma: a DAW Claude drives. Workflow: understand the request → knowledge_style (genre card) → "
    "source (compose & bounce a record via build_spec, or the user's file in sounds/inbox; NEVER AI-generated audio) → crate ops → build tracks with engine/compose → "
    "render (ears report + png; Read the png) → fix → song_log. For fine-tuning phrases use knowledge_tweak first. "
    "Positions are in beats (4/4: bar n starts at beat 4n). Never download copyrighted recordings; generate sources."))

_engine = None


def E():
    global _engine
    if _engine is None:
        _engine = connect("claude-mcp")
    try:
        _engine.call("ping")
    except Exception:
        _engine = connect("claude-mcp")
    return _engine


def _song(name):
    """이름으로 곡을 잡는다. 엔진에 다른 곡이 열려 있으면 이 곡을 연다."""
    e = E()
    from musicoma.layout import edit_file
    path = edit_file(name)
    current = e.call("ping").get("edit", "")
    if path.exists() and Path(current or ".").resolve() != path.resolve():
        e.call("edit.load", {"path": str(path)})
    return Song(name, e)


def _j(x):
    return json.loads(json.dumps(x, ensure_ascii=False, default=lambda o: float(o) if hasattr(o, "__float__") else str(o)))


# ----------------------------------------------------------------------------- 엔진
@mcp.tool()
def engine(method: str, params: dict | None = None) -> dict:
    """Raw engine command (full control). Call method='help' for the complete list.
    Main: edit.new/load/save/info/set/undo/redo, track.add/remove/set, device.available/add/remove/params/set/
    show/load_file/programs/program/preset_save/preset_load, clip.add_midi/add_audio/list/notes/set_notes/set/remove/
    import_midi, automation.set, transport.play/stop/state, render. Tracks by index or name; 'master' for master chain.
    MIDI notes: [{pitch, start, length, velocity}] in beats, note start relative to clip start."""
    return _j(E().call(method, params or {}))


# ----------------------------------------------------------------------------- 지식
@mcp.tool()
def knowledge_style(query: str) -> dict:
    """Find genre/style cards from natural language (Korean or English), e.g. '올드칸예 스타일에 시티팝 샘플링'.
    Returns matching card ids (best first) and the full YAML of the top matches: tempo, swing, drum patterns,
    harmony, sounds, sample treatment, arrangement, mix targets (balance_lu, target_lufs), don'ts."""
    ids = knowledge.find_style(query)
    return {"matches": ids, "cards": {i: knowledge.style(i) for i in ids[:3]},
            "all_styles": list(knowledge.styles().keys())}


@mcp.tool()
def knowledge_tweak(phrase: str) -> dict:
    """Map a fine-tuning request ('킥 좀 더 펀치있게', '더 따뜻하게', '스네어 뒤로') to concrete moves from the
    tweak lexicon. Apply ONE axis, small step, then render and report before/after numbers."""
    hits = knowledge.find_tweak(phrase)
    return {"matches": hits, "note": "no lexicon match — ask one clarifying question (sound/timing/harmony/arrangement)"
            if not hits else "apply smallest step first"}


@mcp.tool()
def knowledge_sounds() -> dict:
    """Catalog of available sounds by role (sfz instruments, Surge XT patches, effects) and how to load them.
    Song tracks accept these role names directly (e.g. 'rhodes', 'bass_sub', 'piano_grand', 'strings_violins')."""
    return knowledge.sounds()


# ----------------------------------------------------------------------------- 곡
@mcp.tool()
def song_new(name: str, bpm: float = 90, key: str = "", style: str = "", brief: str = "") -> dict:
    """Create a new song project (projects/<name>/). style = card id from knowledge_style."""
    s = Song.new(name, bpm=bpm, key=key or None, style=style or None, brief=brief)
    return s.summary()


@mcp.tool()
def song_status(name: str) -> dict:
    """Song summary: meta (bpm/key/style/sections), tracks (role, volume, devices, clips), recent request history,
    versions. Use at the start of any follow-up request to regain context."""
    s = _song(name)
    out = s.summary()
    out["versions"] = s.meta.get("versions", [])
    return _j(out)


@mcp.tool()
def song_track(name: str, track: str, sound: str = "", role: str = "", volume_db: float | None = None,
               pan: float | None = None) -> dict:
    """Add (or get) a track with an instrument. sound: role name from knowledge_sounds ('rhodes', 'bass_sub',
    'drums_acoustic_basic', ...), a Surge patch like 'Keys/EP 2', an .sfz path, or a VST3 name."""
    s = _song(name)
    s.track(track, sound or None, role=role or None, volume_db=volume_db, pan=pan)
    return _j(next(t for t in s.summary()["tracks"] if t["name"] == track))


@mcp.tool()
def presets_list(role: str = "") -> dict:
    """Tone presets by role (piano, keys, bass, drums, strings, pad, brass, lead, guitar, pluck): instrument + fx chain +
    performance settings. Use preset_apply to switch a track's tone in one step."""
    from musicoma.knowledge import presets
    p = presets()
    return {r: {k: v["name"] for k, v in d.items()} for r, d in p.items() if not role or r == role}


@mcp.tool()
def preset_apply(name: str, track: str, role: str, preset: str) -> dict:
    """Switch a track's tone: replaces instrument and insert effects (keeps sends), records perform settings.
    Performance (perform role/feel) takes effect on the next build_spec of the song."""
    return _j(_song(name)[track].preset(role, preset))


@mcp.tool()
def song_section(name: str, section: str, start_bar: int, bars: int) -> dict:
    """Mark a section (intro/verse/hook/bridge/outro...). Lets requests like '후렴만' resolve to beats."""
    s = _song(name)
    s.section(section, start_bar, bars)
    return {"sections": s.meta["sections"]}


@mcp.tool()
def render(name: str, lufs: float | None = None, label: str = "", start_beat: float | None = None,
           end_beat: float | None = None, reference: str = "", fmt: str = "mp3") -> dict:
    """Render + master to target LUFS (default from style card) + ears report (loudness, true peak, 6 bands,
    stereo, issues like dead air/clipping, tempo/key estimate) + spectrogram PNG. Read the PNG to 'see' it.
    reference: path to a reference wav for band/LUFS comparison.
    fmt: "mp3" (default, 320k, for listening/sharing) or "wav" (only when the render will be re-sampled/processed)."""
    s = _song(name)
    rep = s.render(lufs=lufs, label=label or None, start=start_beat, end=end_beat, ref=reference or None, fmt=fmt)
    return _j(rep)


@mcp.tool()
def render_stems(name: str) -> list:
    """Render each track alone and measure LUFS + band energy → see which track owns which band (mix decisions)."""
    return _j(_song(name).render_stems())


@mcp.tool()
def balance(name: str, targets: dict | None = None) -> dict:
    """Set track volumes so each role sits at its target loudness relative to the reference (drums=0).
    targets like {"drums":0,"sample":-1.5,"bass":-2.5}; default = style card mix.balance_lu."""
    return _j(_song(name).balance(targets))


@mcp.tool()
def snapshot(name: str, label: str, note: str = "") -> dict:
    """Freeze current state as a version (edit copy + render). Use when the user says 'this is good'."""
    return _j(_song(name).snapshot(label, note))


@mcp.tool()
def song_log(name: str, request: str, did: str) -> dict:
    """Record the user's request and what you changed (keeps context for future fine-tuning)."""
    s = _song(name)
    s.log(request, did)
    return {"history_len": len(s.meta["history"])}


@mcp.tool()
def show_device(name: str, track: str, device: int = 0) -> dict:
    """Open a plugin's own window on the user's screen for hands-on tweaking (hybrid control)."""
    _song(name)
    return E().call("device.show", {"track": track, "device": device})


# ----------------------------------------------------------------------------- 작곡 도우미
@mcp.tool()
def compose(op: str, args: dict) -> dict:
    """Music helpers that return MIDI notes (beats). ops:
    - progression {text, key, mode}: 'ii7 V7 Imaj7' or chord names → chord names (supports V7/vi, bVII, i)
    - voice {chords, style: piano|rhodes|pad|stab|guitar} → voicings (voice-led)
    - chord_notes {voicings|chords+style, durations, rhythm?[[off,len,velmul]], velocity, strum} → notes
    - drums {pattern{kick,snare,hat,...: 'x..o-X..'}, bars, swing, swing_unit, humanize_ms, humanize_vel, bpm,
             start, kit?} → notes  (16 steps/bar; X accent x normal - soft o ghost)
    - bass {roots|chords, durations, pattern?[[off,len,semi]], velocity} → notes
    - scale {key, mode, low, high} → midi notes
    - chord {name, octave} → midi notes
    - perform {notes, role: piano|keys|bass|drums|strings|pad|brass|lead|guitar|pluck, bpm, feel: straight|laid_back|pushed|loose|tight,
               intensity 0..1} → {notes, cc, bend} — turns score into a human performance (pedal, rolls, dynamics arcs,
               micro-timing, expression swells, slides). Pass cc/bend to engine clip.add_midi with the notes.
    If args has 'song' and 'track', the notes are also written as a clip (args 'start', 'length', 'clip_name')."""
    a = dict(args)
    if op == "progression":
        res = theory.progression(a["text"], a.get("key", "C"), a.get("mode", "major"))
    elif op == "voice":
        res = theory.voice(a["chords"], a.get("style", "piano"))
    elif op == "chord_notes":
        v = a.get("voicings") or theory.voice(a["chords"], a.get("style", "piano"))
        res = groove.chord_notes(v, a.get("durations", 4), start=a.get("start_offset", 0.0),
                                 velocity=a.get("velocity", 82), strum=a.get("strum", 0.0),
                                 rhythm=[tuple(r) for r in a["rhythm"]] if a.get("rhythm") else None)
    elif op == "drums":
        res = groove.pattern_notes(a["pattern"], bars=a.get("bars", 1), swing=a.get("swing", 0.5),
                                   swing_unit=a.get("swing_unit", 16), humanize_ms=a.get("humanize_ms", 0),
                                   humanize_vel=a.get("humanize_vel", 0), bpm=a.get("bpm", 90),
                                   kit=a.get("kit"), start=a.get("start_offset", 0.0), seed=a.get("seed", 0))
    elif op == "bass":
        roots = a.get("roots") or [theory.bass_note(c) for c in a["chords"]]
        res = groove.bass_line(roots, a.get("durations", 4), start=a.get("start_offset", 0.0),
                               pattern=[tuple(p) for p in a["pattern"]] if a.get("pattern") else None,
                               velocity=a.get("velocity", 100))
    elif op == "scale":
        res = theory.scale_notes(a.get("key", "C"), a.get("mode", "major"), a.get("low", 48), a.get("high", 84))
    elif op == "chord":
        res = theory.chord(a["name"], a.get("octave", 4))
    elif op == "perform":
        from musicoma import perform as perform_mod
        res = perform_mod.perform(a["notes"], role=a.get("role", "piano"), bpm=a.get("bpm", 90), feel=a.get("feel", "straight"),
                                  intensity=a.get("intensity", 0.7), seed=a.get("seed", 1))
    else:
        raise ValueError(f"unknown op {op}")
    out = {"result": res}
    if a.get("song") and a.get("track") and isinstance(res, list) and res and isinstance(res[0], dict):
        s = _song(a["song"])
        out["clip"] = s[a["track"]].midi(res, start=a.get("start", 0.0), length=a.get("length"),
                                         name=a.get("clip_name", op))
    return _j(out)


# ----------------------------------------------------------------------------- 소스 · 크레이트
@mcp.tool()
def crate(op: str, args: dict) -> dict:
    """Sample tools (each writes new wavs under sounds/crate/, never touches the original). ops:
    analyze {path} → bpm, key, beats, bars | separate {path} → stems vocals/drums/bass/other |
    best_bars {path, bars} → loudest-steady region | loop_region {path, start, end, bars, target_bpm} (varispeed fit) |
    loop {path, bars, bar_index?, target_bpm?} | varispeed {path, semitones|ratio} (chipmunk: pitch+speed) |
    stretch {path, rate|target_bpm+source_bpm, semitones} (keeps pitch / keeps time) | cut {path, start, end} |
    chop {path, mode: onsets|beats|even, n, min_len, max_len} | make_kit {chops, out_sfz, base_note=36} (pads) |
    make_instrument {path, out_sfz, root_note} (one-shot across keyboard) | age {path, preset: vinyl|dusty|tape|radio} |
    mix_files {paths, out, gains_db?}"""
    fn = {"analyze": crate_mod.analyze, "separate": crate_mod.separate, "best_bars": crate_mod.best_bars,
          "loop_region": crate_mod.loop_region, "loop": crate_mod.loop, "varispeed": crate_mod.varispeed,
          "stretch": crate_mod.stretch, "cut": crate_mod.cut, "chop": crate_mod.chop, "make_kit": crate_mod.make_kit,
          "make_instrument": crate_mod.make_instrument, "age": crate_mod.age, "mix_files": crate_mod.mix_files}[op]
    return {"result": _j(fn(**args))}


@mcp.tool()
def transcribe(op: str, path: str, bpm: float, beats_per_chord: int = 2, bass_path: str = "") -> dict:
    """Extract music from audio so new parts fit the sample. op: bass (pYIN → MIDI notes on 8th grid) |
    chords (chroma template matching, bass-assisted) → chord names per beats_per_chord."""
    if op == "bass":
        return {"notes": tr.bass_notes(path, bpm)}
    ch = tr.chords(path, bpm, beats_per_chord=beats_per_chord, bass_path=bass_path or None)
    return {"chords": ch, "simplified": tr.simplify(ch)}


@mcp.tool()
def import_file(path: str, song: str = "", track: str = "", start_beat: float = 0.0) -> dict:
    """Bring in anything the user/agent has: audio (wav/mp3/flac/aiff/ogg/m4a), video (mp4/mov/mkv/webm → audio),
    MIDI (.mid), a folder of stems, or an Ableton .als. Converts to 48k wav, measures bpm/key; with `song` it is added
    as a track. Only for material the user owns or has rights to — never download copyrighted recordings."""
    from musicoma import importer
    return _j(importer.import_any(path, song=_song(song) if song else None, track=track or None, start_beat=start_beat))


@mcp.tool()
def reverse_song(path: str, name: str) -> dict:
    """Reverse-engineer a finished track (audio or video the user owns/has rights to) into an editable Musicoma project:
    stem separation → tempo/key → drums/bass/chords/melody transcribed to MIDI and re-played by Musicoma instruments,
    original stems kept as muted reference tracks. Approximate skeleton, not a perfect copy."""
    from musicoma import importer
    log = []
    s = importer.reverse(path, name, log=log.append)
    return _j({"steps": log, "song": s.summary()})


# ----------------------------------------------------------------------------- 레시피
@mcp.tool()
def voice_list() -> dict:
    """Prepared singer voices (sounds/voices). Only the user's own or consented voices may be added."""
    from musicoma import voice
    return {"voices": voice.voices()}


@mcp.tool()
def voice_add(name: str, wav: str, language: str = "English", vocal_sep: bool = False) -> dict:
    """Prepare a singer from a 10-30s singing sample (the user's own or consented voice ONLY — refuse celebrity
    or third-party cloning). vocal_sep=True if the sample has accompaniment."""
    from musicoma import voice
    return voice.add_voice(name, wav, language, vocal_sep)


@mcp.tool()
def sing(voice: str, lyrics: str, bpm: float, melody: str, out: str = "", language: str = "English",
         seed: int = 0, humanize: dict | None = None) -> dict:
    """Have a prepared voice sing Musicoma's melody (notation 'E4:1 G4:.5 r:1 ...') with lyrics (one token per note:
    split multi-note words into syllables with hyphens 'ev- ery ci- ty' (best intelligibility on fast notes),
    '+' = hold previous syllable over the next note; rests take no token). Uses score mode (clearest lyrics). Languages: English/Mandarin/Cantonese.
    humanize: {vibrato_cents, vibrato_hz, vibrato_delay, glide_ms, scoop_cents, fall_cents, drift_cents}.
    Returns a 48k wav. In a spec, use a part {"track": "Vox", "in": [...], "vocal": {voice, melody, lyrics}}."""
    from musicoma import voice as v
    return {"wav": v.sing(voice, lyrics, bpm, melody=melody, out=out or None, language=language, seed=seed,
                          humanize=humanize)}


@mcp.tool()
def voice_design(description: str, seed: int | None = None, name: str = "", lang: str = "en",
                 sample_text: str = "", singer: bool = False) -> dict:
    """GENERATE a brand-new voice from a text description (VoxCPM2 Voice Design, Apache-2.0) — no picking from a
    library. e.g. 'A husky middle-aged man, deep gravelly baritone, confident hip-hop rapper'. Same description+seed =
    same person; change only the seed for another person with the same vibe. NEVER describe or name a real person.
    singer=True also prepares it for sing() (melodic singing). Returns the voice name for rap()/sing()/parts."""
    from musicoma import voice_design as vd, voice
    v = vd.design(description, seed=seed, name=name or None, lang=lang, sample_text=sample_text or None)
    out = {"voice": v, **vd.info(v), "sample": str(vd.VOICES / v / "design.wav")}
    if singer:
        out["singer"] = voice.add_voice_aligned(v, vd.VOICES / v / "design.wav")
    return out


@mcp.tool()
def rap(voice: str, lines: list, bpm: float, out: str, beats_per_line: float = 4,
        style: str = "confident rhythmic hip-hop rap delivery", lock: float = 0.75, seed: int = 0) -> dict:
    """Rap lyric lines with a generated voice, word onsets snapped to the 16th grid (lock 0..1: 1 = machine-tight,
    0.6-0.8 = human). lines: strings or {text, beats}. Output wav starts at beat 0 of the first line.
    In a spec: part {"track": "Rap", "in": ["verse"], "rap": {voice, lines, beats_per_line, style, lock, seed}}."""
    from musicoma import voice_design as vd
    p, rep = vd.rap(voice, lines, bpm, out, beats_per_line=beats_per_line, style=style, lock=lock, seed=seed)
    return {"wav": p, "lines": rep}


@mcp.tool()
def voice_character(path: str, out: str, description: str = "", pitch_st: float | None = None,
                    formant: float | None = None, breath: float | None = None, rasp: float | None = None,
                    brightness: float | None = None, vibrato: float | None = None, age: float | None = None) -> dict:
    """Fine-tune the feel of an existing vocal take without changing who it is (WORLD vocoder knobs).
    description words (husky/raspy/deep/bright/dark/breathy/young/middle-aged...) set defaults; explicit knobs override."""
    from musicoma import voice_character as vc
    over = {k: v for k, v in dict(pitch_st=pitch_st, formant=formant, breath=breath, rasp=rasp, brightness=brightness,
                                  vibrato=vibrato, age=age).items() if v is not None}
    p, k = vc.character(path, out, description, **over)
    return {"wav": p, "knobs": k}


@mcp.tool()
def sing_svc(voice: str, lyrics: str, bpm: float, melody: str, out: str, lang: str = "ko", takes: int = 3,
             seed: int = 0) -> dict:
    """Sing via the clear-speech → note-aligned guide → SoulX-SVC path. Use for Korean (and other non-English) lyrics:
    one note = one syllable (Korean: one Hangul char per note; '+' holds the previous syllable). Sings `takes` takes
    and keeps the one speech recognition hears most clearly (scores saved in <out>.json). English: prefer sing()."""
    from musicoma import sing_svc as sv
    import json as _json
    p = sv.sing_svc(voice, lyrics, bpm, melody=melody, out=out, lang=lang, takes=takes, seed=seed)
    meta = _json.loads(Path(p).with_suffix(".json").read_text(encoding="utf-8"))
    return {"wav": p, "chosen": meta["chosen"], "takes": [{k: t[k] for k in ("take", "error", "heard")} for t in meta["takes"]]}


@mcp.tool()
def hum_listen(path: str, bpm: float, key: str = "C major", mode: str = "auto") -> dict:
    """Understand something the user hummed/sang/beatboxed ("동딩띵!") — even if sloppy. Returns notes snapped to the
    song's grid (keeps a little human feel) and key/scale (melody mode) or kick/snare/hat (drums mode, auto-detected).
    Show the user what you heard (note names/rhythm) before placing. Recordings from the UI mic land in sounds/inbox/hum_*."""
    from musicoma import hum, theory
    r = hum.listen(path, bpm, key, mode)
    r["heard_names"] = [theory.note_name(n["pitch"]) for n in r["notes"]] if r["mode"] == "melody" else         [{36: "kick", 38: "snare", 42: "hat"}.get(n["pitch"], n["pitch"]) for n in r["notes"]]
    return r


@mcp.tool()
def vocal_takes(state: str) -> list:
    """Section-by-section vocal 'recording' of a song (like a real singer: verse, hook... each its own clip + kept
    alternative takes). state = the vocal json (e.g. projects/<song>/vocals/rap_lego.json). Shows chosen seed and
    alternatives per section with lyric error rate (wer), voice similarity, key fit."""
    from musicoma import lego
    return lego.takes_list(_abs(state))


@mcp.tool()
def vocal_retake(state: str, section: str, takes: int = 6, lyrics: str = "") -> dict:
    """Re-record ONE section ("NG on hook2 — sing it again", optionally with new lyrics) in the same voice.
    Other sections stay untouched. Old takes are kept; vocal_use_take to go back. Rebuild the song after (build_spec)."""
    from musicoma import lego
    return lego.retake(_abs(state), section, takes=takes, lyrics=lyrics or None, log=lambda m: None)


@mcp.tool()
def vocal_use_take(state: str, section: str, seed: int) -> dict:
    """Swap a section to another kept take (no generation). Rebuild the song after."""
    from musicoma import lego
    return lego.use_take(_abs(state), section, seed)


def _abs(p):
    from pathlib import Path
    from musicoma import arrange
    q = Path(p)
    return str(q if q.is_absolute() else Path(arrange.ROOT) / q)


@mcp.tool()
def hum_understand(path: str, bpm: float, key: str = "C major", lang: str = "ko") -> dict:
    """A voice note that MIXES speech and humming/beatbox ("이 리듬으로 1분 20초에 네 번 넣어줘 — 투두투두…").
    Returns said (the spoken instruction), music (each hummed part as hum_listen results + its clip path) and place
    (at/repeat parsed from the speech). Melodies are transposed as a whole into the song key (shape kept).
    Act on the instruction, then hum_place each music clip."""
    from musicoma import hum
    return hum.understand(path, bpm, key, lang)


@mcp.tool()
def hum_place(song: str, path: str, at: str = "0", repeat: int = 1, track: str = "Hum", sound: str = "",
              key: str = "", mode: str = "auto") -> dict:
    """Put a hummed idea into the song: at = '1:20' (min:sec) / '80s' / 'bar 33' (snapped to the bar), repeated `repeat`
    times on `track` with `sound` (e.g. 'dexed:city_bell', 'rhodes', 'flute', a drum kit). Becomes an editable MIDI clip."""
    from musicoma import hum
    s = _song(song)
    r = hum.listen(path, s.bpm, key or s.meta.get("key") or "C major", mode)
    return hum.place(s, r, track=track, at=at, repeat=repeat, sound=sound or None)


@mcp.tool()
def references(genre: str) -> dict:
    """STEP 0 of every new song: existing reference songs for the genre — form, tempo, key, harmony, devices to learn,
    with sources (knowledge/references/<genre>.yaml) + any of the user's own songs measured by the analyzer
    (scratch/refs) + genre human-priors (timing/form numbers). If no card exists or it is thin, WebSearch 3-5 canonical
    songs (tempo/key/structure/arrangement from chord sites, wikis, reviews — never download audio), write a new card,
    then cite them in concept.references. Learn forms/devices only; never copy melodies or lyrics."""
    import yaml
    from musicoma import corpus
    base = Path(__file__).resolve().parent / "knowledge" / "references"
    card = None
    for f in base.glob("*.yaml"):
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        if genre.lower().replace(" ", "-") in (f.stem, d.get("genre", "")):
            card = d
    g = {"city-pop": "citypop", "hip-hop": "hiphop", "boom-bap": "hiphop", "chipmunk-soul": "hiphop"}.get(genre, genre)
    return {"card": card, "measured_priors": corpus.priors(g), "note": None if card else "카드 없음 — WebSearch 로 대표곡 3~5개를 조사해 knowledge/references/<genre>.yaml 로 저장"}


@mcp.tool()
def concept(song: str, data: dict | None = None) -> dict:
    """STEP 1 of every new song (before any notes): the concept doc — thesis, arc[{section,intent,energy}],
    motif{melody,why}, collision[2-3 distant materials], constraints, events[{section,at,length,type: stop|filter}],
    not[...]. data=None returns a template + the user's reference principles + their taste notes (TASTE/LOG).
    Every later decision (sounds, form, lyrics) must trace back to this doc."""
    from musicoma import concept as c
    if data is None:
        return {"template": c.template(), "taste": c.taste_context()}
    return c.save(song, data)


@mcp.tool()
def motif_develop(motif: str, ops: list | None = None, key: str = "C major", bars: int = 4,
                  plan: str = "statement answer", chords: list | None = None) -> dict:
    """Develop the concept's motif instead of repeating it. ops: up:n down:n chrom:n octave:n invert retro augment:f
    diminish:f displace:b fragment:n tail:n sequence:s,k rhythm:a,b,... ; plan: phrase shape from statement answer
    question sequence climb fragment. chords=[[start,end,'Am7'],...] snaps strong-beat notes to chord tones.
    Returns melody notation for a spec 'melody' part (padded to bars*4 beats)."""
    from musicoma import motif as m
    return {"melody": m.section_melody(motif, ops or [], [tuple(c) for c in chords] if chords else None, key, bars, plan)}


@mcp.tool()
def critique(song: str = "", spec: dict | None = None) -> dict:
    """The anti-slop pass — run after writing a spec and after every build. Numbers: exact 4-bar repetition,
    section contrast, melody notes off the chord on strong beats, motif presence/variation, 'events', plus lyric
    checks (syllables vs notes/bars, rhyme, cliches). Then answer the qualitative questions yourself and fix
    the spec until issues are resolved."""
    from musicoma import critic, lyrics
    if spec is None:
        r = critic.critique_project(song)
        import json as _j
        spec = _j.loads((critic.arrange.ROOT / "projects" / song / "spec.json").read_text(encoding="utf-8"))
    else:
        from musicoma import concept as c
        r = critic.critique(spec, c.load(spec.get("name", song)))
    r["lyrics"] = lyrics.check_song(spec)
    return {"report": critic.format_report(r), "issues": r["issues"] + r["lyrics"], "score": r["score"]}


@mcp.tool()
def tidy(project: str = "", dry_run: bool = False) -> dict:
    """Keep files readable: move intermediate files (per-line rap takes, guides, SVC takes, SoulX work, measurement
    stems, logs) of a song folder into projects/<song>/.work/ and refresh projects/<song>/README.md. Never deletes.
    project='' tidies every song. Put experiments/tests under scratch/ (musicoma.layout.scratch()), not in projects/."""
    from musicoma import layout
    names = [project] if project else [p.name for p in layout.PROJECTS.iterdir() if p.is_dir()]
    return {n: layout.tidy(n, dry_run=dry_run) for n in names}


@mcp.tool()
def build_spec(spec: dict, render: bool = True, label: str = "") -> dict:
    """Build a whole song from an arrangement spec (any genre) — see musicoma/arrange.py docstring for the format:
    sections, tracks{sound, role, fx, sends}, buses, master, parts{drums|chords|bass|melody|notes|audio, in:[sections]},
    automation, mix{balance, target_lufs}. Fine-tuning = edit the spec (projects/<name>/spec.json) and rebuild."""
    from musicoma import arrange
    log = []
    s, rep = arrange.build(spec, render=render, label=label or None, log=log.append)
    return _j({"log": log, "report": rep, "song": s.summary()})


@mcp.tool()
def recipe_chipmunk_soul(name: str, bpm: float = 88, semitones: float = 4, key: str = "F major",
                         source_style: str = "city-pop", lead: str = "flute", seed: int = 7, source: str = "",
                         brief: str = "") -> dict:
    """Example recipe (old-Kanye chipmunk soul). No AI audio: composes & records a soul/city-pop 'record' at the
    slower source tempo, ages it, samples its hook (varispeed +semitones), chops the lead, then builds a boom-bap beat
    via arrange specs. source = the user's own audio file (sounds/inbox) to sample instead."""
    from musicoma.recipes import chipmunk_soul as cs
    log = []
    s, notes, rep = cs.build(name, bpm=bpm, semitones=semitones, key=key, source_style=source_style, lead=lead,
                             seed=seed, source=source or None, brief=brief, log=log.append)
    return _j({"steps": log, "notes": notes, "report": rep, "song": s.summary()})


if __name__ == "__main__":
    mcp.run()
