"""Single-character Unicode 15.1 names for source literals, independent of the host Python."""
# Names-only adaptation of lib/_pystachy_unicodedata.py's CPython-derived decoder;
# see THIRD_PARTY_NOTICES. Reuse its generated data, without the property database,
# runtime Unicode strings or named sequences (which Python literals do not accept).
from lib import _pystachy_unicodedata_names as _n


_JAMO_L = ["G", "GG", "N", "D", "DD", "R", "M", "B", "BB", "S", "SS", "", "J", "JJ", "C", "K", "T", "P", "H"]
_JAMO_V = ["A", "AE", "YA", "YAE", "EO", "E", "YEO", "YE", "O", "WA", "WAE", "OE", "YO", "U", "WEO", "WE", "WI", "YU", "EU",
           "YI", "I"]
_JAMO_T = ["", "G", "GG", "GS", "N", "NJ", "NH", "D", "L", "LG", "LM", "LB", "LS", "LT", "LP", "LH", "M", "B", "BS", "S",
           "SS", "NG", "J", "C", "K", "T", "P", "H"]
_nm: list[int] = []
_name_cp: list[int] = []
_name_at: list[int] = []
_word_start: list[int] = []
_word_end: list[int] = []
_word_order: list[int] = []
_suffix_prefix: list[str] = []
_suffix_ranges: list[list[int]] = []
_cjk: list[int] = []
_tangut: list[int] = []
_aliases: dict[str, int] = {}


def _numbers(text: str) -> list[int]:
    # Base-36 integers, read without allocating a string for each number.
    out: list[int] = []
    v = 0
    digits = False
    for x in text.encode():
        if x == 32:
            if digits:
                out.append(v)
            v = 0
            digits = False
        else:
            v = v * 36 + (x - 48 if x < 58 else x - 87)
            digits = True
    if digits:
        out.append(v)
    return out


def _ranges(text: str, out: list[int]) -> None:
    vs = _numbers(text)
    at = 0
    for i in range(0, len(vs), 2):
        at += vs[i]
        out.append(at)
        at += vs[i + 1]
        out.append(at)


def _in(ranges: list[int], c: int) -> bool:
    lo = 0
    hi = len(ranges)
    while lo < hi:
        mid = (lo + hi) // 2
        if ranges[mid] <= c:
            lo = mid + 1
        else:
            hi = mid
    return lo % 2 == 1


def _decode_names() -> None:
    for v in _numbers(_n.NAMES):
        _nm.append(v)
    at = 0
    i = 0
    while i < len(_nm):
        at += _nm[i]
        _name_cp.append(at)
        _name_at.append(i + 1)
        i += 2 + _nm[i + 1]
    start = 0
    w = _n.WORDS
    for i in range(len(w) + 1):
        if i == len(w) or w[i] == " ":
            _word_start.append(start)
            _word_end.append(i)
            start = i + 1
    for v in _numbers(_n.WORD_ORDER):
        _word_order.append(v)
    for entry in _n.SUFFIXED:
        cut = entry.find(":")
        rs: list[int] = []
        _ranges(entry[cut + 1 :], rs)
        _suffix_prefix.append(entry[:cut])
        _suffix_ranges.append(rs)
    _ranges(_n.CJK, _cjk)
    _ranges(_n.TANGUT, _tangut)
    for entry in _n.ALIASES:
        cut = entry.find(":")
        _aliases[entry[cut + 1 :]] = int(entry[:cut], 16)


def _word(i: int) -> str:
    return _n.WORDS[_word_start[i] : _word_end[i]]


def _word_index(w: str) -> int:
    lo = 0
    hi = len(_word_order)
    while lo < hi:
        mid = (lo + hi) // 2
        if _word(_word_order[mid]) < w:
            lo = mid + 1
        else:
            hi = mid
    return _word_order[lo] if lo < len(_word_order) and _word(_word_order[lo]) == w else -1


def _regular(up: str) -> int:
    ws = [_word_index(w) for w in up.split(" ")]
    for x in ws:
        if x < 0:
            return -1
    n = len(ws)
    for e in range(len(_name_cp)):
        at = _name_at[e]
        if _nm[at] == n and _nm[at + 1] == ws[0]:
            same = True
            for j in range(1, n):
                if _nm[at + 1 + j] != ws[j]:
                    same = False
                    break
            if same:
                return _name_cp[e]
    return -1


def _upper(s: str) -> str:
    return "".join([chr(ord(x) - 32) if "a" <= x <= "z" else x for x in s])


def _jamo(name: str, at: int, column: list[str]) -> list[int]:
    best = -1
    size = -1
    for i in range(len(column)):
        s = column[i]
        if len(s) > size and name[at : at + len(s)] == s:
            best = i
            size = len(s)
    return [best, size if size >= 0 else 0]


def _hex(s: str) -> int:
    if len(s) < 4 or len(s) > 6 or s[0] == "0":
        return -1
    v = 0
    for x in s:
        if "0" <= x <= "9":
            v = v * 16 + ord(x) - 48
        elif "A" <= x <= "F":
            v = v * 16 + ord(x) - 55
        else:
            return -1
    return v if v <= 0x10FFFF else -1


def lookup_name(name: str) -> int:
    # A single code point, including aliases, or -1. No whitespace folding or
    # Unicode case conversion: CPython compares names using ASCII uppercasing.
    if name == "" or len(name) > 256:
        return -1
    for c in name:
        if ord(c) >= 128:
            return -1
    up = _upper(name)
    if up.startswith("HANGUL SYLLABLE "):
        lv = _jamo(up, 16, _JAMO_L)
        vv = _jamo(up, 16 + lv[1], _JAMO_V)
        tv = _jamo(up, 16 + lv[1] + vv[1], _JAMO_T)
        if lv[0] != -1 and vv[0] != -1 and tv[0] != -1 and 16 + lv[1] + vv[1] + tv[1] == len(up):
            return 0xAC00 + (lv[0] * 21 + vv[0]) * 28 + tv[0]
        return -1
    if len(_name_at) == 0:
        _decode_names()
    for prefix, ranges in [("CJK UNIFIED IDEOGRAPH-", _cjk), ("TANGUT IDEOGRAPH-", _tangut)]:
        if up.startswith(prefix):
            v = _hex(up[len(prefix) :])
            return v if v >= 0 and _in(ranges, v) else -1
    for k in range(len(_suffix_prefix)):
        prefix = _suffix_prefix[k] + "-"
        if up.startswith(prefix):
            v = _hex(up[len(prefix) :])
            if v >= 0 and _in(_suffix_ranges[k], v) and f"{v:04X}" == up[len(prefix) :]:
                return v
    if up in _aliases:
        return _aliases[up]
    return _regular(up)
