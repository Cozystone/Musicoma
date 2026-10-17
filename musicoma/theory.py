"""화성 — 코드 이름·로마 숫자 → 노트, 보이싱, 보이스 리딩.

chord("Ebmaj9")            -> [63, 67, 70, 74, 77]  (근음 옥타브 4)
roman("ii7", key="Eb")     -> "Fm7"
progression("IVmaj7 iii7 vi7 V7/vi", key="C") -> 코드 이름들
voice(chords, style="rhodes", low=48, high=76) -> 보이스 리딩된 노트 묶음
"""
import re

NOTE_INDEX = {"C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4, "F": 5, "F#": 6, "GB": 6,
              "G": 7, "G#": 8, "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11, "CB": 11, "E#": 5, "FB": 4, "B#": 0}
NAMES_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
NAMES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# 코드 품질 → 근음 기준 반음 간격
QUALITIES = {
    "": [0, 4, 7], "maj": [0, 4, 7], "M": [0, 4, 7], "m": [0, 3, 7], "min": [0, 3, 7], "-": [0, 3, 7],
    "dim": [0, 3, 6], "aug": [0, 4, 8], "+": [0, 4, 8], "sus2": [0, 2, 7], "sus4": [0, 5, 7], "sus": [0, 5, 7],
    "5": [0, 7], "6": [0, 4, 7, 9], "m6": [0, 3, 7, 9], "69": [0, 4, 7, 9, 14],
    "7": [0, 4, 7, 10], "maj7": [0, 4, 7, 11], "M7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "-7": [0, 3, 7, 10],
    "mmaj7": [0, 3, 7, 11], "m7b5": [0, 3, 6, 10], "ø": [0, 3, 6, 10], "dim7": [0, 3, 6, 9], "7sus4": [0, 5, 7, 10],
    "9": [0, 4, 7, 10, 14], "maj9": [0, 4, 7, 11, 14], "m9": [0, 3, 7, 10, 14], "add9": [0, 4, 7, 14],
    "madd9": [0, 3, 7, 14], "11": [0, 4, 7, 10, 14, 17], "m11": [0, 3, 7, 10, 14, 17], "maj7#11": [0, 4, 7, 11, 18],
    "13": [0, 4, 7, 10, 14, 21], "maj13": [0, 4, 7, 11, 14, 21], "m13": [0, 3, 7, 10, 14, 21],
    "7b9": [0, 4, 7, 10, 13], "7#9": [0, 4, 7, 10, 15], "7#5": [0, 4, 8, 10], "7b13": [0, 4, 7, 10, 20],
    "9sus4": [0, 5, 7, 10, 14], "13sus4": [0, 5, 7, 10, 14, 21], "11sus4": [0, 5, 7, 10, 14, 17], "6/9": [0, 4, 7, 9, 14],
}

SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10], "dorian": [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10], "phrygian": [0, 1, 3, 5, 7, 8, 10], "lydian": [0, 2, 4, 6, 7, 9, 11],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11], "pentatonic": [0, 2, 4, 7, 9], "minor_pentatonic": [0, 3, 5, 7, 10],
    "blues": [0, 3, 5, 6, 7, 10],
}

_CHORD_RE = re.compile(r"^([A-Ga-g])([#b]?)(.*?)(?:/([A-Ga-g][#b]?))?$")
_ROMAN_RE = re.compile(r"^([b#]?)(VII|VI|V|IV|III|II|I|vii|vi|v|iv|iii|ii|i)(°|ø|\+)?(.*?)(?:/(.+))?$")
_ROMAN_DEG = {"I": 0, "II": 1, "III": 2, "IV": 3, "V": 4, "VI": 5, "VII": 6}


def pc(name):
    """음이름 → 0..11 ('Eb', 'F#', 'bb' 모두)"""
    n = name.strip().replace("♭", "b").replace("♯", "#")
    letter, acc = n[0].upper(), n[1:2]
    return (NOTE_INDEX[letter] + (1 if acc == "#" else -1 if acc == "b" else 0)) % 12


def note_name(midi, flats=True):
    names = NAMES_FLAT if flats else NAMES_SHARP
    return f"{names[midi % 12]}{midi // 12 - 1}"


def parse_chord(name):
    """'Ebmaj9/G' -> (root_pc, intervals, bass_pc|None)"""
    m = _CHORD_RE.match(name.strip())
    if not m:
        raise ValueError(f"cannot parse chord '{name}'")
    root = pc(m.group(1) + m.group(2))
    qual = m.group(3).replace("Δ", "maj7").replace("min", "m") if m.group(3) not in QUALITIES else m.group(3)
    if qual not in QUALITIES:
        raise ValueError(f"unknown chord quality '{m.group(3)}' in '{name}' (known: {sorted(QUALITIES)})")
    bass = pc(m.group(4)) if m.group(4) else None
    return root, QUALITIES[qual], bass


def chord(name, octave=4):
    """근음 위치 기본형 노트 (MIDI)."""
    root, ivs, bass = parse_chord(name)
    base = 12 * (octave + 1) + root
    notes = [base + i for i in ivs]
    if bass is not None:
        b = 12 * octave + bass
        while b >= notes[0]:
            b -= 12
        notes = [b] + notes
    return notes


def roman(numeral, key="C", mode="major"):
    """로마 숫자 → 코드 이름. 대문자=장, 소문자=단. 'V7/vi' 같은 부속화음 지원."""
    numeral = numeral.strip()
    if "/" in numeral and not numeral.split("/")[1][:1].isdigit():
        head, target = numeral.split("/", 1)
        if _ROMAN_RE.match(target):
            tgt_name = roman(target, key, mode)
            tgt_root = NAMES_FLAT[parse_chord(tgt_name)[0]]
            return roman(head, tgt_root, "major")
    m = _ROMAN_RE.match(numeral)
    if not m:
        raise ValueError(f"cannot parse roman numeral '{numeral}'")
    acc, rn, sym, ext, _ = m.groups()
    # 단조에서 변화표 없는 III·VI·VII 은 '그 조의' 자연단음계 음 위(D단조 VI = Bb). 'bVI' 처럼 b 를 붙인 표기는
    # 대중음악 관례대로 장음계 기준(같은 Bb) — 둘 다 같은 답이 나오게. (10-15 오케스트라 '화음 안 맞음'의 원인 수정:
    # 예전엔 단조에서도 장음계 기준이라 D단조 i VI III VII 이 Dm B Gb Db 로 나왔다)
    base = SCALES["minor"] if (mode == "minor" and not acc) else SCALES["major"]
    root = (pc(key) + base[_ROMAN_DEG[rn.upper()]] + (-1 if acc == "b" else 1 if acc == "#" else 0)) % 12
    minor = rn.islower()
    ext = ext or ""
    if sym == "°":
        qual = "dim7" if ext == "7" else "dim"
    elif sym == "ø":
        qual = "m7b5"
    elif sym == "+":
        qual = "aug" if not ext else "7#5"
    elif minor:
        qual = "m" + ext if not ext.startswith("maj") else "m" + ext   # i, i7, im9, imaj7 -> mmaj7
        qual = {"mmaj7": "mmaj7", "m": "m"}.get(qual, qual)
    else:
        qual = ext                                                      # I, I7, Imaj7, I9, Isus4
    name = NAMES_FLAT[root] + qual
    parse_chord(name)
    return name


def progression(text, key="C", mode="major"):
    """'ii7 V7 Imaj7' 또는 'Dm7 G7 Cmaj7' 둘 다 받는다. 공백·'|'·',' 구분."""
    out = []
    for tok in re.split(r"[\s|,]+", text.strip()):
        if not tok:
            continue
        out.append(roman(tok, key, mode) if _ROMAN_RE.match(tok) and not _CHORD_RE.match(tok) or tok[:1] in "iIvV" or tok[:2] in ("bV", "bI", "#I", "#i", "bi", "bv")
                   else (parse_chord(tok), tok)[1])
    return out


def scale_notes(key="C", mode="major", low=36, high=96):
    root = pc(key)
    ivs = SCALES[mode]
    return [n for n in range(low, high + 1) if (n - root) % 12 in ivs]


# ---------------------------------------------------------------------------
# 보이싱

VOICING_STYLES = {
    # (근음 제외 여부, 펼침, 범위)
    "piano": dict(drop_root=False, spread=False, low=52, high=79),
    "rhodes": dict(drop_root=True, spread=False, low=53, high=77),     # 근음은 베이스가 맡는다
    "pad": dict(drop_root=False, spread=True, low=48, high=84),
    "stab": dict(drop_root=True, spread=False, low=60, high=84),
    "guitar": dict(drop_root=False, spread=True, low=40, high=76),
}


def _candidates(pcs, low, high):
    return [[n for n in range(low, high + 1) if n % 12 == p] for p in pcs]


def voice(chords, style="piano", low=None, high=None, top_note_target=None):
    if style == "power":                      # 파워코드(10-17 밴드): 근음 + 5도 + 옥타브, 코드 성질 무시(장·단 구분 없이)
        out = []
        for ch in chords:
            r = bass_note(ch, low or 40, high or 52)
            out.append([r, r + 7, r + 12])
        return out
    """보이스 리딩: 이전 보이싱에서 가장 적게 움직이는 자리 배치를 고른다."""
    cfg = VOICING_STYLES.get(style, VOICING_STYLES["piano"])
    low = low or cfg["low"]
    high = high or cfg["high"]
    result, prev = [], None
    for name in chords:
        root, ivs, _ = parse_chord(name)
        pcs = [(root + i) % 12 for i in ivs]
        if cfg["drop_root"] and len(pcs) >= 4:
            pcs = pcs[1:]
        # 5음 이상이면 5음(완전5도)을 먼저 뺀다 — 텐션이 더 중요
        if len(pcs) > 4 and (root + 7) % 12 in pcs:
            pcs.remove((root + 7) % 12)
        best, best_cost = None, None
        start_range = range(low, low + 12)
        for start in start_range:
            v, n = [], start
            for p in pcs:
                while n % 12 != p:
                    n += 1
                v.append(n)
                n += 1
            if cfg["spread"] and len(v) >= 3:
                v[1] += 12 if v[1] + 12 <= high else 0
                v.sort()
            if v[-1] > high:
                continue
            if prev is None:
                cost = abs(sum(v) / len(v) - (low + high) / 2)
                if top_note_target:
                    cost += abs(v[-1] - top_note_target)
            else:
                cost = sum(min(abs(a - b) for b in prev) for a in v) + 0.5 * abs(v[-1] - prev[-1])
            if best_cost is None or cost < best_cost:
                best, best_cost = sorted(v), cost
        if best is None:
            best = sorted(chord(name, 4))
        result.append(best)
        prev = best
    return result


def bass_note(name, low=28, high=48):
    root, _, bass = parse_chord(name)
    target = bass if bass is not None else root
    n = low
    while n % 12 != target:
        n += 1
    return n if n <= high else n - 12


def transpose_chord(name, semitones):
    """'Fmaj7/A' +4 → 'Amaj7/Db'"""
    root, ivs, bass = parse_chord(name)
    m = _CHORD_RE.match(name.strip())
    qual = m.group(3)
    out = NAMES_FLAT[(root + semitones) % 12] + qual
    if bass is not None:
        out += "/" + NAMES_FLAT[(bass + semitones) % 12]
    return out


def transpose_key(key, semitones):
    """'F major' +4 → 'A major'"""
    name, _, mode = key.partition(" ")
    return f"{NAMES_FLAT[(pc(name) + semitones) % 12]} {mode or 'major'}".strip()
