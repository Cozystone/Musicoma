"""가사 — 본인이 가사를 안 주면 Claude 가 콘셉트(thesis·arc)에서 새로 쓴다. 이 모듈은 '맞는지' 검사한다.

쓰는 순서(Claude)
  1 concept.json 의 thesis·arc·motif·not 을 읽는다 — 가사는 그 섹션의 intent 를 말해야 한다
  2 노래(멜로디): 음표 수 = 음절 수. 영어는 'ev- ery' 처럼 하이픈, 한국어는 글자 하나 = 한 음절, '+' = 이어 부르기
     랩: 한 줄 = beats_per_line 박. 88BPM 4박이면 9~13음절이 자연스럽다(템포가 빠르면 줄인다)
  3 각운: 줄 끝(또는 2줄씩) 모음이 맞게. 같은 단어 반복으로 운 맞추기 금지
  4 클리셰 금지 목록(아래) — 꼭 써야 하면 비틀어서
  5 check_song() 으로 검사 → 고쳐서 통과시킨 뒤 짓는다
실존 가수의 가사를 베끼거나 그대로 인용하지 않는다(원작 가사 금지).
"""
import re

CLICHES_EN = ["fire", "desire", "heart of gold", "baby baby", "tonight tonight", "dance the night away",
              "feel alive", "never let go", "in the air", "shine bright", "one more time", "touch the sky"]
CLICHES_KO = ["사랑해 사랑해", "너만을", "영원히 함께", "눈물이 흘러", "가슴이 아파", "별처럼 빛나"]
_HANGUL = re.compile(r"[가-힣]")


def syllables_en(word):
    w = re.sub(r"[^a-z']", "", word.lower())
    if not w:
        return 0
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and not w.endswith(("le", "ee", "ye")) and n > 1:
        n -= 1
    if w.endswith("ed") and not w.endswith(("ted", "ded")) and n > 1:
        n -= 1
    return max(1, n)


def syllables(text, lang=None):
    lang = lang or ("ko" if _HANGUL.search(text) else "en")
    if lang == "ko":
        return len(_HANGUL.findall(text))
    return sum(syllables_en(w) for w in text.replace("-", " ").split() if w != "+")


def tokens_needed(melody_text):
    from .arrange import melody
    notes, _ = melody(melody_text)
    return len(notes)


def _tail_vowels(line, lang):
    if lang == "ko":
        chars = _HANGUL.findall(line)
        if not chars:
            return ""
        c = ord(chars[-1]) - 0xAC00
        return str((c % 588) // 28)                 # 마지막 글자의 중성(모음)
    words = re.findall(r"[a-z']+", line.lower())
    if not words:
        return ""
    w = words[-1].rstrip("'").replace("qu", "kw")
    w = w[0] + re.sub(r"(?<=[^aeiou])y(?=[^aeiou]|$)", "i", w[1:]) if len(w) > 1 else w    # rhyme→rhime
    # 철자 → 소리(대략): 같은 소리 다른 철자를 하나로(repeat/sweet, coast/most, night/bite, soprano/tokyo)
    for a, b in (("igh", "ai"), ("eigh", "ei"), ("ea", "ee"), ("ie", "ee"), ("ei", "ee"), ("oa", "o"), ("ow", "o"),
                 ("oe", "o"), ("ue", "oo"), ("ew", "oo"), ("ou", "ow"), ("ay", "ei"), ("ey", "ee"), ("ph", "f"), ("ck", "k")):
        w = w.replace(a, b)
    if w.endswith("y") and len(w) > 2 and w[-2] not in "aeiou":
        w = w[:-1] + "ee"
    if w.endswith("e") and len(w) > 3 and w[-2] not in "aeiou" and w[-3] in "aeiou":   # 묵음 e: bite→bait 소리
        w = w[:-3] + {"a": "ei", "i": "ai", "o": "o", "u": "oo", "e": "ee"}[w[-3]] + w[-2]
    v = re.findall(r"[aeiou]+[^aeiou]*$", w)
    tail = v[0] if v else w[-2:]
    return re.sub(r"(s|z)$", "", tail)                 # 복수형 s 는 운에서 무시


def check_rap(lines, bpm, beats_per_line=4, lang="en"):
    """랩 줄: 박 대비 음절 밀도 + 2줄씩 각운 + 클리셰."""
    sec = beats_per_line * 60 / bpm
    out = []
    for i, l in enumerate(lines):
        text = l["text"] if isinstance(l, dict) else l
        n = syllables(text, lang)
        rate = n / (l.get("beats", beats_per_line) * 60 / bpm if isinstance(l, dict) else sec)
        prob = []
        if rate > 5.2:
            prob.append(f"너무 빽빽(초당 {rate:.1f}음절 — 줄이거나 2줄로)")
        elif rate < 2.2:
            prob.append(f"너무 성김(초당 {rate:.1f}음절)")
        out.append({"line": text, "syllables": n, "per_sec": round(rate, 1), "problems": prob})
    for i in range(0, len(out) - 1, 2):
        a, b = out[i]["line"], out[i + 1]["line"]
        ta, tb = _tail_vowels(a, lang), _tail_vowels(b, lang)
        nuc = lambda t: re.match(r"[aeiou]*", t).group(0) if lang != "ko" else t
        if ta != tb and nuc(ta) != nuc(tb):                    # 완전운 또는 모음만 같은 반운(랩에선 흔함)
            out[i + 1]["problems"].append(f"앞 줄과 각운 안 맞음('{a.split()[-1]}' / '{b.split()[-1]}')")
        if a.split()[-1].lower().strip(",.!?") == b.split()[-1].lower().strip(",.!?"):
            out[i + 1]["problems"].append("같은 단어로 운 맞춤 — 다른 단어로")
    return out


def check_sung(lyrics, melody_text, lang=None):
    """노래: 토큰 수 = 음표 수(한국어는 글자, 영어는 하이픈 음절 + '+')."""
    lang = lang or ("ko" if _HANGUL.search(lyrics) else "en")
    if lang == "ko":
        n = len(_HANGUL.findall(lyrics)) + lyrics.split().count("+")
    else:
        n = len(lyrics.split())
    need = tokens_needed(melody_text)
    prob = [] if n == need else [f"음절 토큰 {n}개 ≠ 음표 {need}개"]
    if lang == "en":
        for w in lyrics.split():
            if w not in ("+",) and not w.endswith("-") and syllables_en(w) >= 2:
                prob.append(f"'{w}' 는 {syllables_en(w)}음절 — 음표가 여러 개면 하이픈으로 나누기(예 'ci- ty')")
                break
    return {"tokens": n, "notes": need, "problems": prob}


def cliches(text):
    low = text.lower()
    return [c for c in CLICHES_EN + CLICHES_KO if c in low]


def check_song(spec):
    """설계서 안의 모든 rap·vocal 파트 가사 검사. 반환: 문제 목록(빈 목록 = 통과)."""
    issues = []
    for p in spec.get("parts", []):
        if "rap" in p:
            r = p["rap"]
            for row in check_rap(r["lines"], spec["bpm"], r.get("beats_per_line", 4), r.get("lang", "en")):
                issues += [f"{p['track']} 랩 '{row['line'][:30]}…': {x}" for x in row["problems"]]
            joined = " ".join(l["text"] if isinstance(l, dict) else l for l in r["lines"])
            issues += [f"{p['track']} 클리셰 '{c}'" for c in cliches(joined)]
        if "vocal" in p:
            v = p["vocal"]
            res = check_sung(v["lyrics"], v["melody"], v.get("lang"))
            issues += [f"{p['track']} 노래: {x}" for x in res["problems"]]
            issues += [f"{p['track']} 클리셰 '{c}'" for c in cliches(v["lyrics"])]
    return issues
