# Pystachy's re: the matching engine of CPython 3.13's _sre (Modules/_sre/sre_lib.h and sre.c),
# ported to the subset. It runs the code that re's compiler (__init__.py, as CPython's
# _compiler.py) makes of a pattern, over a string's code points (State.s: the str's own bytes
# where each byte is a code point, as sre.c reads a 1-byte string, else a list of them), with CPython's
# explicit stack of match contexts: a nested match (DO_JUMP) pushes a context and resumes the
# code after it once that context returns (the jump labels, here the K_* steps of sre_match).
# Positions are indices into State.s; __init__.py turns them into the str's own indices.
from typing import Generic, TypeVar

import _pystachy_re_specialized

from . import _unicode
from ._constants import *

# the subject's representation (State.s): a str's own bytes where each is a code point (a bytes),
# else its code points (a list[int]); each function over a State is compiled for both
_S = TypeVar("_S")

# ---- the characters, as sre.c tests them

# lazily decoded tables of _unicode.py: the boundaries of ALNUM, DECIMAL, SPACE, LINEBREAK, IDSTART
# and IDCONTINUE plus their alphabetic classification delta (each range a start and an end past
# it), and the code points LOWER and UPPER map and their maps
_ranges: list[list[int]] = []
_mapkeys: list[list[int]] = []
_mapvals: list[list[int]] = []
# (not sre.c's: _mapped()'s recent results, a code point and its map in each of 256 slots for each
# table, by the code point's low byte; case-insensitive text uses few code points again and again)
_mapmemo: list[int] = []


def _decode() -> None:
    for text in [_unicode.ALNUM, _unicode.DECIMAL, _unicode.SPACE, _unicode.LINEBREAK, _unicode.IDSTART,
                 _unicode.IDCONTINUE, _unicode.ALPHA_IDSTART_DELTA]:
        bounds: list[int] = []
        at = 0
        for w in text.split():
            at += int(w, 36)
            bounds.append(at)
        _ranges.append(bounds)
    for text in [_unicode.LOWER, _unicode.UPPER]:
        keys: list[int] = []
        vals: list[int] = []
        at = 0
        for w in text.split():
            up = w.find(":")
            cut = up if up >= 0 else w.find("-")
            at += int(w[:cut], 36)
            keys.append(at)
            vals.append(at + int(w[cut + 1 :], 36) if up >= 0 else at - int(w[cut + 1 :], 36))
        _mapkeys.append(keys)
        _mapvals.append(vals)
    for _ in range(2 * 256 * 2):
        _mapmemo.append(-1)


def _inranges(t: int, ch: int) -> bool:
    # is ch in table t's ranges: an odd count of boundaries at or below it
    if len(_ranges) == 0:
        _decode()
    bounds = _ranges[t]
    lo = 0
    hi = len(bounds)
    while lo < hi:
        mid = (lo + hi) // 2
        if bounds[mid] <= ch:
            lo = mid + 1
        else:
            hi = mid
    return lo % 2 == 1


def _mapped(t: int, ch: int) -> int:
    if len(_ranges) == 0:
        _decode()
    slot = (t * 256 + (ch & 255)) * 2
    if _mapmemo[slot] == ch:
        return _mapmemo[slot + 1]
    keys = _mapkeys[t]
    lo = 0
    hi = len(keys)
    while lo < hi:
        mid = (lo + hi) // 2
        if keys[mid] < ch:
            lo = mid + 1
        else:
            hi = mid
    m = _mapvals[t][lo] if lo < len(keys) and keys[lo] == ch else ch
    _mapmemo[slot] = ch
    _mapmemo[slot + 1] = m
    return m


def ascii_isalnum(ch: int) -> bool:
    return (48 <= ch and ch <= 57) or (65 <= ch and ch <= 90) or (97 <= ch and ch <= 122)


def lower_ascii(ch: int) -> int:
    return ch + 32 if 65 <= ch and ch <= 90 else ch


def upper_ascii(ch: int) -> int:
    return ch - 32 if 97 <= ch and ch <= 122 else ch


def lower_unicode(ch: int) -> int:
    # Py_UNICODE_TOLOWER
    if ch < 128:
        return lower_ascii(ch)
    return _mapped(0, ch)


def upper_unicode(ch: int) -> int:
    # Py_UNICODE_TOUPPER (a character with a special casing: the first of its full uppercase)
    if ch < 128:
        return upper_ascii(ch)
    return _mapped(1, ch)


def uni_isalnum(ch: int) -> bool:
    if ch < 128:
        return ascii_isalnum(ch)
    return _inranges(0, ch)


def uni_isdecimal(ch: int) -> bool:
    if ch < 128:
        return 48 <= ch and ch <= 57
    return _inranges(1, ch)


def uni_isspace(ch: int) -> bool:
    if ch < 128:
        return (9 <= ch and ch <= 13) or (28 <= ch and ch <= 32)
    return _inranges(2, ch)


def uni_islinebreak(ch: int) -> bool:
    if ch < 128:
        return (10 <= ch and ch <= 13) or (28 <= ch and ch <= 30)
    return _inranges(3, ch)


def uni_isidstart(ch: int) -> bool:
    # str.isidentifier() of the character alone (the parser's test of a group name, not _sre's)
    if ch < 128:
        return (65 <= ch and ch <= 90) or (97 <= ch and ch <= 122) or ch == 95
    return _inranges(4, ch)


def uni_isidcontinue(ch: int) -> bool:
    # a character an identifier may go on with
    if ch < 128:
        return ascii_isalnum(ch) or ch == 95
    return _inranges(5, ch)


def uni_isalpha(ch: int) -> bool:
    # str.isalpha(): some identifier starts are not letters, and some letters cannot start names
    if ch < 128:
        return (65 <= ch and ch <= 90) or (97 <= ch and ch <= 122)
    return uni_isidstart(ch) != _inranges(6, ch)


def ascii_iscased(ch: int) -> bool:
    return ch < 128 and ((65 <= ch and ch <= 90) or (97 <= ch and ch <= 122))


def unicode_iscased(ch: int) -> bool:
    return ch != lower_unicode(ch) or ch != upper_unicode(ch)


def is_word(ch: int) -> bool:
    # SRE_IS_WORD: ASCII
    return ch <= 122 and (ascii_isalnum(ch) or ch == 95)


def uni_is_word(ch: int) -> bool:
    return uni_isalnum(ch) or ch == 95


def category(cat: int, ch: int) -> bool:
    # sre_category (LOCALE's apply to bytes patterns only, which this re does not have: as the "C"
    # locale's)
    if cat == CATEGORY_DIGIT:
        return 48 <= ch and ch <= 57
    if cat == CATEGORY_NOT_DIGIT:
        return not (48 <= ch and ch <= 57)
    if cat == CATEGORY_SPACE:
        return (9 <= ch and ch <= 13) or ch == 32
    if cat == CATEGORY_NOT_SPACE:
        return not ((9 <= ch and ch <= 13) or ch == 32)
    if cat == CATEGORY_WORD or cat == CATEGORY_LOC_WORD:
        return is_word(ch)
    if cat == CATEGORY_NOT_WORD or cat == CATEGORY_LOC_NOT_WORD:
        return not is_word(ch)
    if cat == CATEGORY_LINEBREAK:
        return ch == 10
    if cat == CATEGORY_NOT_LINEBREAK:
        return ch != 10
    if cat == CATEGORY_UNI_DIGIT:
        return uni_isdecimal(ch)
    if cat == CATEGORY_UNI_NOT_DIGIT:
        return not uni_isdecimal(ch)
    if cat == CATEGORY_UNI_SPACE:
        return uni_isspace(ch)
    if cat == CATEGORY_UNI_NOT_SPACE:
        return not uni_isspace(ch)
    if cat == CATEGORY_UNI_WORD:
        return uni_is_word(ch)
    if cat == CATEGORY_UNI_NOT_WORD:
        return not uni_is_word(ch)
    if cat == CATEGORY_UNI_LINEBREAK:
        return uni_islinebreak(ch)
    if cat == CATEGORY_UNI_NOT_LINEBREAK:
        return not uni_islinebreak(ch)
    return False


def charset(code: list[int], i: int, ch: int) -> bool:
    # SRE(charset): is ch a member of the set at code[i]
    ok = True
    while True:
        op = code[i]
        i += 1
        if op == FAILURE:
            return not ok
        if op == LITERAL:
            if ch == code[i]:
                return ok
            i += 1
        elif op == CATEGORY:
            if category(code[i], ch):
                return ok
            i += 1
        elif op == CHARSET:
            # <CHARSET> <bitmap of 256 bits, in 8 words>
            if ch < 256 and (code[i + (ch >> 5)] >> (ch & 31)) & 1 != 0:
                return ok
            i += 8
        elif op == RANGE:
            if code[i] <= ch and ch <= code[i + 1]:
                return ok
            i += 2
        elif op == RANGE_UNI_IGNORE:
            # (ch is lower cased already)
            if code[i] <= ch and ch <= code[i + 1]:
                return ok
            uch = upper_unicode(ch)
            if code[i] <= uch and uch <= code[i + 1]:
                return ok
            i += 2
        elif op == NEGATE:
            ok = not ok
        elif op == BIGCHARSET:
            # <BIGCHARSET> <blockcount> <256 block indices, as bytes in 64 words> <blocks>
            count = code[i]
            i += 1
            block = -1
            if ch < 65536:
                hi = ch >> 8
                block = (code[i + (hi >> 2)] >> ((hi & 3) * 8)) & 255
            i += 64
            if block >= 0 and (code[i + ((block * 256 + (ch & 255)) >> 5)] >> (ch & 31)) & 1 != 0:
                return ok
            i += count * 8
        else:
            return False


# ---- the state of one match or search, and its contexts


class Repeat:
    # SRE_REPEAT: a REPEAT's (or POSSESSIVE_REPEAT's) count so far, the code position of its
    # operands (-1 for a possessive repeat's), and where its last iteration began
    def __init__(self, pattern: int, prev: "Repeat | None") -> None:
        self.count = -1
        self.pattern = pattern
        self.prev = prev
        self.last_ptr = -1


class State(Generic[_S]):
    # SRE_STATE over the code points s: start and end bound the match (pos and endpos), ptr is
    # where the last match ended, and mark the group bounds (-1 for none) up to lastmark. offs and
    # the tables are re's (see __init__.py's _state)
    def __init__(self, s: _S, start: int, end: int, groups: int, offs: list[int], charset_offsets: list[int],
                 charset_ascii: list[int], prefilter: list[int]) -> None:
        self.s = s
        self.start = start
        self.end = end
        self.pos = start  # (pos and endpos as re's caller gave them: re's _state sets them)
        self.endpos = end
        self.ptr = start
        self.mark = [-1] * (2 * groups)
        self.lastmark = -1
        self.lastindex = -1
        self.repeat: Repeat | None = None
        self.match_all = False
        self.must_advance = False
        self.data: list[int] = []  # the data stack: saved marks and last_ptr values
        self.offs = offs  # (re's: the index in the str of each of s's code points, [] if they are theirs)
        # (not _sre's: the contexts of the matches of this state, kept for reuse: those below top are
        # in use, by sre_match() and the calls nested in it through sre_count(), the others free)
        self.ctxs: list[Ctx] = []
        self.top = 0
        # Pattern's lazily built class tables, shared by its states (see _charset_table)
        self.charset_offsets = charset_offsets
        self.charset_ascii = charset_ascii
        # (not _sre's) the Pattern's lazily found filter of the general search case: see _prefilter
        self.prefilter = prefilter
        # (not _sre's) the matcher generated for the Pattern, which a search runs (_attempt), or -1
        self.fast = -1

    def reset(self) -> None:
        # state_reset (a data stack that the last match left empty is kept, not made again)
        self.lastmark = -1
        self.lastindex = -1
        self.repeat = None
        if len(self.data) != 0:
            self.data = []


# What a set's table says of the code points from 128 (its entry at 128): HIGH_IN, those from
# its entry at 129 to its entry at 130 are members; HIGH_OUT, all others are; HIGH_EVAL, charset()
# decides. An empty range makes HIGH_IN none and HIGH_OUT all of them. A HIGH_EVAL table goes on
# with a memo of charset()'s recent answers: HIGH_MEMO slots of a code point and whether it is a
# member, by its low bits
HIGH_IN = 0
HIGH_OUT = 1
HIGH_EVAL = 2
HIGH_MEMO = 64
MAXCHAR = 4294967295  # (past every code point: the end of a range of all those from 128)


def _charset_table(state: State[_S], code: list[int], i: int) -> int:
    # The set at code[i]'s table, where it begins in state.charset_ascii: whether each ASCII
    # character is a member, then what the set says of the others (HIGH_*). The caller applies an
    # IN_IGNORE/IN_UNI_IGNORE's folding first, so each code position has one fixed set, including
    # scoped flags, independent of the string. CPython's bytecode stays as it is
    start = len(state.charset_ascii)
    for c in range(128):
        state.charset_ascii.append(int(charset(code, i, c)))
    high = _charset_high(code, i)
    for x in high:
        state.charset_ascii.append(x)
    if high[0] == HIGH_EVAL:
        for _ in range(HIGH_MEMO):
            state.charset_ascii.append(-1)
            state.charset_ascii.append(0)
    state.charset_offsets[i] = start
    return start


def _charset_memo(state: State[_S], code: list[int], i: int, t: int, ch: int) -> bool:
    # charset() of a code point from 128 for a HIGH_EVAL set whose table begins at t, through its memo
    table = state.charset_ascii
    slot = t + 131 + (ch & (HIGH_MEMO - 1)) * 2
    if table[slot] == ch:
        return table[slot + 1] != 0
    member = charset(code, i, ch)
    table[slot] = ch
    table[slot + 1] = int(member)
    return member


def _charset_high(code: list[int], i: int) -> list[int]:
    # [HIGH_IN or HIGH_OUT, lo, hi] when the members from 128 of the set at code[i] are the
    # code points of one range (maybe empty), which a leading NEGATE turns inside out; else
    # [HIGH_EVAL, 0, 0]: a BIGCHARSET, a Unicode category or case-insensitive range, members in
    # two ranges or more, or a NEGATE elsewhere (which charset()'s order of items makes matter)
    lo = 1  # (the members from 128 so far: an empty range)
    hi = 0
    mode = HIGH_IN
    if code[i] == NEGATE:
        mode = HIGH_OUT
        i += 1
    while code[i] != FAILURE:
        op = code[i]
        a = 1  # (this item's members from 128: a range, empty unless they are found)
        b = 0
        if op == LITERAL:
            if code[i + 1] >= 128:
                a = code[i + 1]
                b = a
            i += 2
        elif op == RANGE:
            if code[i + 2] >= 128:
                a = code[i + 1] if code[i + 1] >= 128 else 128
                b = code[i + 2]
            i += 3
        elif op == CHARSET:
            # the bitmap's words 4 to 7 (128 to 255): one run of set bits at most
            for c in range(128, 256):
                if (code[i + 1 + (c >> 5)] >> (c & 31)) & 1 != 0:
                    if a > b:
                        a = c
                        b = c
                    elif c == b + 1:
                        b = c
                    else:
                        return [HIGH_EVAL, 0, 0]
            i += 9
        elif op == CATEGORY:
            # the categories that test ASCII alone match all code points from 128 or none
            cat = code[i + 1]
            if cat == CATEGORY_NOT_DIGIT or cat == CATEGORY_NOT_SPACE or cat == CATEGORY_NOT_WORD \
                    or cat == CATEGORY_LOC_NOT_WORD or cat == CATEGORY_NOT_LINEBREAK:
                a = 128
                b = MAXCHAR
            elif not (cat == CATEGORY_DIGIT or cat == CATEGORY_SPACE or cat == CATEGORY_WORD
                      or cat == CATEGORY_LOC_WORD or cat == CATEGORY_LINEBREAK):
                return [HIGH_EVAL, 0, 0]
            i += 2
        else:
            return [HIGH_EVAL, 0, 0]
        if a <= b:
            if lo > hi:
                lo = a
                hi = b
            elif a <= hi + 1 and lo <= b + 1:
                # (overlapping or adjacent: one range still)
                lo = a if a < lo else lo
                hi = b if b > hi else hi
            else:
                return [HIGH_EVAL, 0, 0]
    return [mode, lo, hi]


def _table(state: State[_S], code: list[int], i: int) -> int:
    # where the set at code[i]'s table begins in state.charset_ascii (made at its first use), or -1
    # for a state without tables
    if len(state.charset_offsets) == 0:
        return -1
    t = state.charset_offsets[i]
    if t < 0:
        t = _charset_table(state, code, i)
    return t


def _charset(state: State[_S], code: list[int], i: int, ch: int) -> bool:
    # charset() through the set's table (see _charset_table)
    if len(state.charset_offsets) == 0:
        return charset(code, i, ch)
    start = state.charset_offsets[i]
    if start < 0:
        start = _charset_table(state, code, i)
    table = state.charset_ascii
    if ch < 128:
        return table[start + ch] != 0
    mode = table[start + 128]
    if mode == HIGH_EVAL:
        return _charset_memo(state, code, i, start, ch)
    return (table[start + 129] <= ch and ch <= table[start + 130]) == (mode == HIGH_IN)


def _span(state: State[_S], code: list[int], i: int, fold: int, ptr: int, end: int, inside: bool) -> int:
    # The end of the characters from ptr (to end at most) whose membership in the set at code[i]
    # is inside: sre_count's run of an IN, IN_IGNORE (fold 1) or IN_UNI_IGNORE (fold 2), whose
    # folding applies first, or a search's skip to the first member. (Not _sre's: its loops call
    # SRE(charset) for each character.) The set's table is found once for the whole span, and its
    # ASCII characters are decided here, in loops that call nothing, folded as lower_ascii() and
    # lower_unicode() fold them; _span_rest() goes on from a character from 128
    s = state.s
    t = _table(state, code, i)
    if t >= 0:
        table = state.charset_ascii
        if fold == 0:
            if inside:
                while ptr < end:
                    ch = s[ptr]
                    if ch >= 128:
                        break
                    if table[t + ch] == 0:
                        return ptr
                    ptr += 1
            else:
                while ptr < end:
                    ch = s[ptr]
                    if ch >= 128:
                        break
                    if table[t + ch] != 0:
                        return ptr
                    ptr += 1
        elif inside:
            while ptr < end:
                ch = s[ptr]
                if ch >= 128:
                    break
                if table[t + (ch + 32 if 65 <= ch and ch <= 90 else ch)] == 0:
                    return ptr
                ptr += 1
        else:
            while ptr < end:
                ch = s[ptr]
                if ch >= 128:
                    break
                if table[t + (ch + 32 if 65 <= ch and ch <= 90 else ch)] != 0:
                    return ptr
                ptr += 1
        if ptr >= end:
            return ptr
    return _span_rest(state, code, i, t, fold, ptr, end, inside)


def _span_rest(state: State[_S], code: list[int], i: int, t: int, fold: int, ptr: int, end: int, inside: bool) -> int:
    # _span() from a character from 128 on, or from ptr for a state without tables (t < 0): each
    # character decided by the set's table where it can be, ASCII or one range from 128 (or none,
    # or all), else by charset() through the table's memo
    s = state.s
    if t < 0:
        while ptr < end:
            ch = s[ptr]
            if fold == 1:
                ch = lower_ascii(ch)
            elif fold == 2:
                ch = lower_unicode(ch)
            if charset(code, i, ch) != inside:
                break
            ptr += 1
        return ptr
    table = state.charset_ascii
    mode = table[t + 128]
    lo = table[t + 129]
    hi = table[t + 130]
    while ptr < end:
        ch = s[ptr]
        if ch < 128:
            if fold != 0 and 65 <= ch and ch <= 90:
                ch += 32
        elif fold == 2:
            ch = _mapped(0, ch)  # (which may map it to ASCII)
        if ch < 128:
            member = table[t + ch] != 0
        elif mode == HIGH_EVAL:
            slot = t + 131 + (ch & (HIGH_MEMO - 1)) * 2
            member = table[slot + 1] != 0 if table[slot] == ch else _charset_memo(state, code, i, t, ch)
        else:
            member = (lo <= ch and ch <= hi) == (mode == HIGH_IN)
        if member != inside:
            break
        ptr += 1
    return ptr


class Ctx:
    # SRE(match_context): what a context keeps across a nested match it waits for
    def __init__(self, pattern: int, toplevel: bool, jump: int) -> None:
        self.count = 0
        self.chr = 0
        self.rep: Repeat | None = None
        self.lastmark = -1
        self.lastindex = -1
        self.pattern = pattern
        self.ptr = 0
        self.toplevel = toplevel
        self.jump = jump

    def reuse(self, pattern: int, toplevel: bool, jump: int) -> None:
        # a free context, set as a new one is
        self.count = 0
        self.chr = 0
        self.rep = None
        self.lastmark = -1
        self.lastindex = -1
        self.pattern = pattern
        self.ptr = 0
        self.toplevel = toplevel
        self.jump = jump


def _mark_push(state: State[_S], lastmark: int) -> None:
    data = state.data
    mark = state.mark
    for i in range(lastmark + 1):
        data.append(mark[i])


def _mark_pop(state: State[_S], lastmark: int, discard: bool) -> None:
    n = lastmark + 1
    if n == 0:
        return
    data = state.data
    mark = state.mark
    base = len(data) - n
    for i in range(n):
        mark[i] = data[base + i]
    if discard:
        _drop(state, n)


def _drop(state: State[_S], n: int) -> None:
    # the last n items of the data stack (one deletion, not n pops; none for n = 0, which would
    # detach an empty stack's array)
    if n > 0:
        del state.data[len(state.data) - n:]


def _rep(ctx: Ctx) -> Repeat:
    r = ctx.rep
    if r is None:
        raise RuntimeError("internal error in regular expression engine")
    return r


# the jumps: which code a context resumes when the one it pushed returns
JUMP_NONE = 0
JUMP_MAX_UNTIL_1 = 1
JUMP_MAX_UNTIL_2 = 2
JUMP_MAX_UNTIL_3 = 3
JUMP_MIN_UNTIL_1 = 4
JUMP_MIN_UNTIL_2 = 5
JUMP_MIN_UNTIL_3 = 6
JUMP_REPEAT = 7
JUMP_REPEAT_ONE_1 = 8
JUMP_REPEAT_ONE_2 = 9
JUMP_MIN_REPEAT_ONE = 10
JUMP_BRANCH = 11
JUMP_ASSERT = 12
JUMP_ASSERT_NOT = 13
JUMP_POSS_REPEAT_1 = 14
JUMP_POSS_REPEAT_2 = 15
JUMP_ATOMIC_GROUP = 16

# the steps of sre_match's loop: the C code's labels, and the tops of the loops that a nested
# match interrupts
K_ENTRANCE = 0
K_DISPATCH = 1
K_EXIT = 2
K_RESUME = 3
K_BRANCH = 4
K_REPEAT_ONE_LITERAL = 5
K_REPEAT_ONE = 6
K_MIN_REPEAT_ONE = 7
K_MAX_UNTIL_TAIL = 8
K_POSS_MIN = 9
K_POSS_MAX = 10
K_POSS_DONE = 11


def sre_count(state: State[_S], code: list[int], p: int, maxcount: int) -> int:
    # SRE(count): how many times the single-character item at code[p] matches from state.ptr, at
    # most maxcount
    s = state.s
    ptr = state.ptr
    end = state.end
    if maxcount < end - ptr and maxcount != MAXREPEAT:
        end = ptr + maxcount
    op = code[p]
    if op == IN:
        ptr = _span(state, code, p + 2, 0, ptr, end, True)
    elif op == IN_IGNORE:
        ptr = _span(state, code, p + 2, 1, ptr, end, True)
    elif op == IN_UNI_IGNORE:
        ptr = _span(state, code, p + 2, 2, ptr, end, True)
    elif op == ANY:
        while ptr < end and s[ptr] != 10:
            ptr += 1
    elif op == ANY_ALL:
        ptr = end
    elif op == LITERAL:
        c = code[p + 1]
        while ptr < end and s[ptr] == c:
            ptr += 1
    elif op == LITERAL_IGNORE:
        c = code[p + 1]
        while ptr < end and lower_ascii(s[ptr]) == c:
            ptr += 1
    elif op == LITERAL_UNI_IGNORE:
        c = code[p + 1]
        while ptr < end and lower_unicode(s[ptr]) == c:
            ptr += 1
    elif op == NOT_LITERAL:
        c = code[p + 1]
        while ptr < end and s[ptr] != c:
            ptr += 1
    elif op == NOT_LITERAL_IGNORE:
        c = code[p + 1]
        while ptr < end and lower_ascii(s[ptr]) != c:
            ptr += 1
    elif op == NOT_LITERAL_UNI_IGNORE:
        c = code[p + 1]
        while ptr < end and lower_unicode(s[ptr]) != c:
            ptr += 1
    else:
        # a repeated single character pattern
        while state.ptr < end:
            if sre_match(state, code, p, False) == 0:
                break
        return state.ptr - ptr
    return ptr - state.ptr


def sre_at(state: State[_S], ptr: int, at: int) -> bool:
    # SRE(at): is ptr at the position at stands for (the string begins at 0: lookbehind and \b see
    # past pos)
    s = state.s
    end = state.end
    if at == AT_BEGINNING or at == AT_BEGINNING_STRING:
        return ptr == 0
    if at == AT_BEGINNING_LINE:
        return ptr == 0 or s[ptr - 1] == 10
    if at == AT_END:
        return (end - ptr == 1 and s[ptr] == 10) or ptr == end
    if at == AT_END_LINE:
        # (past endpos, where pos is: CPython reads the character there, or the NUL after the string)
        return ptr == end or (ptr < len(s) and s[ptr] == 10)
    if at == AT_END_STRING:
        return ptr == end
    if end == 0:
        return False
    if at == AT_BOUNDARY or at == AT_NON_BOUNDARY or at == AT_LOC_BOUNDARY or at == AT_LOC_NON_BOUNDARY:
        thatp = ptr > 0 and is_word(s[ptr - 1])
        thisp = ptr < end and is_word(s[ptr])
        return thisp != thatp if at == AT_BOUNDARY or at == AT_LOC_BOUNDARY else thisp == thatp
    if at == AT_UNI_BOUNDARY or at == AT_UNI_NON_BOUNDARY:
        thatp = ptr > 0 and uni_is_word(s[ptr - 1])
        thisp = ptr < end and uni_is_word(s[ptr])
        return thisp != thatp if at == AT_UNI_BOUNDARY else thisp == thatp
    return False


def sre_match(state: State[_S], code: list[int], start: int, toplevel: bool) -> int:
    # SRE(match): 1 if the code at code[start] matches at state.ptr (then state.ptr is where the
    # match ends, and state.mark its groups), else 0
    s = state.s
    end = state.end
    # (not _sre's: the contexts are the state's, kept for reuse: this call's are ctxs[base], its
    # first, to ctxs[base + depth], the current one, and a nested match takes the next one, so that
    # contexts are made as deep as the matcher goes, not one for each match and nested match; a call
    # nested in sre_count() takes those above, from state.top, and gives them back when it returns)
    ctxs = state.ctxs
    base = state.top
    depth = 0
    if base < len(ctxs):
        ctx = ctxs[base]
        ctx.reuse(start, toplevel, JUMP_NONE)
    else:
        ctx = Ctx(start, toplevel, JUMP_NONE)
        ctxs.append(ctx)
    state.top = base + 1
    pattern = start
    ptr = 0
    ret = 0
    jump = JUMP_NONE
    k = K_ENTRANCE
    nextp = 0  # (a nested match: its code, its jump and whether it is at the top level)
    nextj = 0
    nextt = False
    while True:
        if k == K_ENTRANCE:
            ptr = state.ptr
            if code[pattern] == INFO:
                # <INFO> <1=skip> <2=flags> <3=min> ...
                if code[pattern + 3] != 0 and end - ptr < code[pattern + 3]:
                    ret = 0
                    k = K_EXIT
                    continue
                pattern += code[pattern + 1] + 1
            k = K_DISPATCH
        if k == K_DISPATCH:
            op = code[pattern]
            pattern += 1
            if op == LITERAL:
                if ptr >= end or s[ptr] != code[pattern]:
                    ret = 0
                    k = K_EXIT
                    continue
                pattern += 1
                ptr += 1
            elif op == IN:
                if ptr >= end or not _charset(state, code, pattern + 1, s[ptr]):
                    ret = 0
                    k = K_EXIT
                    continue
                pattern += code[pattern]
                ptr += 1
            elif op == MARK:
                i = code[pattern]
                if i & 1 == 1:
                    state.lastindex = i // 2 + 1
                if i > state.lastmark:
                    # (the marks between the last one and i are not set)
                    j = state.lastmark + 1
                    while j < i:
                        state.mark[j] = -1
                        j += 1
                    state.lastmark = i
                state.mark[i] = ptr
                pattern += 1
            elif op == SUCCESS:
                if ctx.toplevel and ((state.match_all and ptr != state.end) or (state.must_advance and ptr == state.start)):
                    ret = 0
                    k = K_EXIT
                    continue
                state.ptr = ptr
                ret = 1
                k = K_EXIT
            elif op == NOT_LITERAL:
                if ptr >= end or s[ptr] == code[pattern]:
                    ret = 0
                    k = K_EXIT
                    continue
                pattern += 1
                ptr += 1
            elif op == AT:
                if not sre_at(state, ptr, code[pattern]):
                    ret = 0
                    k = K_EXIT
                    continue
                pattern += 1
            elif op == CATEGORY:
                if ptr >= end or not category(code[pattern], s[ptr]):
                    ret = 0
                    k = K_EXIT
                    continue
                pattern += 1
                ptr += 1
            elif op == ANY:
                if ptr >= end or s[ptr] == 10:
                    ret = 0
                    k = K_EXIT
                    continue
                ptr += 1
            elif op == ANY_ALL:
                if ptr >= end:
                    ret = 0
                    k = K_EXIT
                    continue
                ptr += 1
            elif op == LITERAL_IGNORE or op == LITERAL_UNI_IGNORE:
                if ptr >= end or (lower_ascii(s[ptr]) if op == LITERAL_IGNORE else lower_unicode(s[ptr])) != code[pattern]:
                    ret = 0
                    k = K_EXIT
                    continue
                pattern += 1
                ptr += 1
            elif op == NOT_LITERAL_IGNORE or op == NOT_LITERAL_UNI_IGNORE:
                if ptr >= end or (lower_ascii(s[ptr]) if op == NOT_LITERAL_IGNORE else lower_unicode(s[ptr])) == code[pattern]:
                    ret = 0
                    k = K_EXIT
                    continue
                pattern += 1
                ptr += 1
            elif op == IN_IGNORE or op == IN_UNI_IGNORE:
                if ptr >= end or not _charset(state, code, pattern + 1, lower_ascii(s[ptr]) if op == IN_IGNORE else lower_unicode(s[ptr])):
                    ret = 0
                    k = K_EXIT
                    continue
                pattern += code[pattern]
                ptr += 1
            elif op == JUMP or op == INFO:
                # <JUMP> <offset>
                pattern += code[pattern]
            elif op == BRANCH:
                # <BRANCH> <0=skip> code <JUMP> ... <NULL>
                ctx.lastmark = state.lastmark
                ctx.lastindex = state.lastindex
                if state.repeat is not None:
                    _mark_push(state, ctx.lastmark)
                k = K_BRANCH
            elif op == REPEAT_ONE:
                # <REPEAT_ONE> <skip> <1=min> <2=max> item <SUCCESS> tail: a single character
                # repeated as often as it matches, then given back one at a time
                if code[pattern + 1] > end - ptr:
                    ret = 0
                    k = K_EXIT
                    continue
                state.ptr = ptr
                ctx.count = sre_count(state, code, pattern + 3, code[pattern + 2])
                ptr += ctx.count
                if ctx.count < code[pattern + 1]:
                    ret = 0
                    k = K_EXIT
                    continue
                tail = pattern + code[pattern]
                if code[tail] == SUCCESS and ptr == state.end and not (ctx.toplevel and state.must_advance and ptr == state.start):
                    # the tail is empty: done
                    state.ptr = ptr
                    ret = 1
                    k = K_EXIT
                    continue
                ctx.lastmark = state.lastmark
                ctx.lastindex = state.lastindex
                if state.repeat is not None:
                    _mark_push(state, ctx.lastmark)
                # (not _sre's: also after group marks past lastmark, which a tail that fails leaves
                # where no group sees them, as it left them past lastmark)
                lit = tail
                while code[lit] == MARK and code[lit + 1] > state.lastmark:
                    lit += 2
                if code[lit] == LITERAL:
                    # the tail starts with a literal: skip the positions where it cannot match
                    ctx.chr = code[lit + 1]
                    k = K_REPEAT_ONE_LITERAL
                else:
                    k = K_REPEAT_ONE
            elif op == MIN_REPEAT_ONE:
                # <MIN_REPEAT_ONE> <skip> <1=min> <2=max> item <SUCCESS> tail
                if code[pattern + 1] > end - ptr:
                    ret = 0
                    k = K_EXIT
                    continue
                state.ptr = ptr
                if code[pattern + 1] == 0:
                    ctx.count = 0
                else:
                    # count up to the minimum
                    n = sre_count(state, code, pattern + 3, code[pattern + 1])
                    if n < code[pattern + 1]:
                        ret = 0
                        k = K_EXIT
                        continue
                    ctx.count = n
                    ptr += ctx.count
                if code[pattern + code[pattern]] == SUCCESS and not (ctx.toplevel and ((state.match_all and ptr != state.end) or (state.must_advance and ptr == state.start))):
                    state.ptr = ptr
                    ret = 1
                    k = K_EXIT
                    continue
                ctx.lastmark = state.lastmark
                ctx.lastindex = state.lastindex
                if state.repeat is not None:
                    _mark_push(state, ctx.lastmark)
                k = K_MIN_REPEAT_ONE
            elif op == POSSESSIVE_REPEAT_ONE:
                # <POSSESSIVE_REPEAT_ONE> <skip> <1=min> <2=max> item <SUCCESS> tail: as
                # REPEAT_ONE, but nothing is given back
                if ptr + code[pattern + 1] > end:
                    ret = 0
                    k = K_EXIT
                    continue
                state.ptr = ptr
                ctx.count = sre_count(state, code, pattern + 3, code[pattern + 2])
                ptr += ctx.count
                if ctx.count < code[pattern + 1]:
                    ret = 0
                    k = K_EXIT
                    continue
                pattern += code[pattern]
                if code[pattern] == SUCCESS and ptr == state.end and not (ctx.toplevel and state.must_advance and ptr == state.start):
                    state.ptr = ptr
                    ret = 1
                    k = K_EXIT
                    continue
            elif op == REPEAT:
                # <REPEAT> <skip> <1=min> <2=max> <3=repeat_index> item <UNTIL> tail: the UNTIL
                # does the work, in a new repeat context
                ctx.rep = Repeat(pattern, state.repeat)
                state.repeat = ctx.rep
                state.ptr = ptr
                nextp = pattern + code[pattern]
                nextj = JUMP_REPEAT
                nextt = ctx.toplevel
            elif op == MAX_UNTIL:
                # maximizing repeat: <REPEAT> <skip> <1=min> <2=max> item <MAX_UNTIL> tail
                ctx.rep = state.repeat
                rep = _rep(ctx)
                state.ptr = ptr
                ctx.count = rep.count + 1
                if ctx.count < code[rep.pattern + 1]:
                    # not enough matches
                    rep.count = ctx.count
                    nextp = rep.pattern + 3
                    nextj = JUMP_MAX_UNTIL_1
                    nextt = ctx.toplevel
                elif (ctx.count < code[rep.pattern + 2] or code[rep.pattern + 2] == MAXREPEAT) and state.ptr != rep.last_ptr:
                    # enough matches, but another one if it can
                    rep.count = ctx.count
                    ctx.lastmark = state.lastmark
                    ctx.lastindex = state.lastindex
                    _mark_push(state, ctx.lastmark)
                    state.data.append(rep.last_ptr)  # (zero-width match protection)
                    rep.last_ptr = state.ptr
                    nextp = rep.pattern + 3
                    nextj = JUMP_MAX_UNTIL_2
                    nextt = ctx.toplevel
                else:
                    k = K_MAX_UNTIL_TAIL
            elif op == MIN_UNTIL:
                # minimizing repeat: <REPEAT> <skip> <1=min> <2=max> item <MIN_UNTIL> tail
                ctx.rep = state.repeat
                rep = _rep(ctx)
                state.ptr = ptr
                ctx.count = rep.count + 1
                if ctx.count < code[rep.pattern + 1]:
                    rep.count = ctx.count
                    nextp = rep.pattern + 3
                    nextj = JUMP_MIN_UNTIL_1
                    nextt = ctx.toplevel
                else:
                    # see if the tail matches
                    state.repeat = rep.prev
                    ctx.lastmark = state.lastmark
                    ctx.lastindex = state.lastindex
                    if state.repeat is not None:
                        _mark_push(state, ctx.lastmark)
                    nextp = pattern
                    nextj = JUMP_MIN_UNTIL_2
                    nextt = ctx.toplevel
            elif op == POSSESSIVE_REPEAT:
                # <POSSESSIVE_REPEAT> <skip> <1=min> <2=max> pattern <SUCCESS> tail
                state.ptr = ptr
                ctx.rep = Repeat(-1, state.repeat)
                state.repeat = ctx.rep
                ctx.count = 0
                k = K_POSS_MIN
            elif op == ATOMIC_GROUP:
                # <ATOMIC_GROUP> <skip> pattern <SUCCESS> tail
                state.ptr = ptr
                nextp = pattern + 1
                nextj = JUMP_ATOMIC_GROUP
                nextt = False
            elif op == GROUPREF or op == GROUPREF_IGNORE or op == GROUPREF_UNI_IGNORE:
                groupref = code[pattern] * 2
                if groupref >= state.lastmark:
                    ret = 0
                    k = K_EXIT
                    continue
                p = state.mark[groupref]
                e = state.mark[groupref + 1]
                if p < 0 or e < 0 or e < p:
                    ret = 0
                    k = K_EXIT
                    continue
                same = True
                while p < e:
                    if ptr >= end:
                        same = False
                        break
                    if op == GROUPREF:
                        same = s[ptr] == s[p]
                    elif op == GROUPREF_IGNORE:
                        same = lower_ascii(s[ptr]) == lower_ascii(s[p])
                    else:
                        same = lower_unicode(s[ptr]) == lower_unicode(s[p])
                    if not same:
                        break
                    p += 1
                    ptr += 1
                if not same:
                    ret = 0
                    k = K_EXIT
                    continue
                pattern += 1
            elif op == GROUPREF_EXISTS:
                # <GROUPREF_EXISTS> <group> <skip> codeyes <JUMP> codeno ...
                groupref = code[pattern] * 2
                if groupref >= state.lastmark:
                    pattern += code[pattern + 1]
                    continue
                p = state.mark[groupref]
                e = state.mark[groupref + 1]
                if p < 0 or e < 0 or e < p:
                    pattern += code[pattern + 1]
                    continue
                pattern += 2
            elif op == ASSERT:
                # <ASSERT> <skip> <back> <pattern>
                if ptr < code[pattern + 1]:
                    ret = 0
                    k = K_EXIT
                    continue
                state.ptr = ptr - code[pattern + 1]
                nextp = pattern + 2
                nextj = JUMP_ASSERT
                nextt = False
            elif op == ASSERT_NOT:
                # <ASSERT_NOT> <skip> <back> <pattern>
                if ptr >= code[pattern + 1]:
                    state.ptr = ptr - code[pattern + 1]
                    ctx.lastmark = state.lastmark
                    ctx.lastindex = state.lastindex
                    if state.repeat is not None:
                        _mark_push(state, ctx.lastmark)
                    nextp = pattern + 2
                    nextj = JUMP_ASSERT_NOT
                    nextt = False
                else:
                    pattern += code[pattern]
            elif op == FAILURE:
                ret = 0
                k = K_EXIT
                continue
            else:
                # (the LOCALE opcodes, of bytes patterns, and the set members)
                raise RuntimeError("internal error in regular expression engine")
        elif k == K_EXIT:
            ctx.rep = None  # (a free context refers to no repeat)
            if depth == 0:
                state.top = base
                return ret
            jump = ctx.jump
            depth -= 1
            state.top = base + depth + 1
            ctx = ctxs[base + depth]
            pattern = ctx.pattern
            ptr = ctx.ptr
            k = K_RESUME
            continue
        elif k == K_RESUME:
            k = K_DISPATCH
            if jump == JUMP_BRANCH:
                if ret != 0:
                    if state.repeat is not None:
                        _drop(state, ctx.lastmark + 1)
                    k = K_EXIT
                    continue
                if state.repeat is not None:
                    _mark_pop(state, ctx.lastmark, False)
                state.lastmark = ctx.lastmark
                state.lastindex = ctx.lastindex
                pattern += code[pattern]
                k = K_BRANCH
            elif jump == JUMP_REPEAT_ONE_1 or jump == JUMP_REPEAT_ONE_2 or jump == JUMP_MIN_REPEAT_ONE:
                if ret != 0:
                    if state.repeat is not None:
                        _drop(state, ctx.lastmark + 1)
                    k = K_EXIT
                    continue
                if state.repeat is not None:
                    _mark_pop(state, ctx.lastmark, False)
                state.lastmark = ctx.lastmark
                state.lastindex = ctx.lastindex
                if jump == JUMP_MIN_REPEAT_ONE:
                    state.ptr = ptr
                    if sre_count(state, code, pattern + 3, 1) == 0:
                        if state.repeat is not None:
                            _drop(state, ctx.lastmark + 1)
                        ret = 0
                        k = K_EXIT
                        continue
                    ptr += 1
                    ctx.count += 1
                    k = K_MIN_REPEAT_ONE
                else:
                    ptr -= 1
                    ctx.count -= 1
                    k = K_REPEAT_ONE_LITERAL if jump == JUMP_REPEAT_ONE_1 else K_REPEAT_ONE
            elif jump == JUMP_REPEAT:
                state.repeat = _rep(ctx).prev
                k = K_EXIT  # (with ret as the nested match left it)
                continue
            elif jump == JUMP_MAX_UNTIL_1 or jump == JUMP_MIN_UNTIL_1:
                if ret != 0:
                    k = K_EXIT
                    continue
                _rep(ctx).count = ctx.count - 1
                state.ptr = ptr
                k = K_EXIT
                continue
            elif jump == JUMP_MAX_UNTIL_2:
                rep = _rep(ctx)
                rep.last_ptr = state.data.pop()
                if ret != 0:
                    _drop(state, ctx.lastmark + 1)
                    k = K_EXIT
                    continue
                _mark_pop(state, ctx.lastmark, True)
                state.lastmark = ctx.lastmark
                state.lastindex = ctx.lastindex
                rep.count = ctx.count - 1
                state.ptr = ptr
                k = K_MAX_UNTIL_TAIL
            elif jump == JUMP_MAX_UNTIL_3:
                state.repeat = ctx.rep
                if ret != 0:
                    k = K_EXIT
                    continue
                state.ptr = ptr
                k = K_EXIT
                continue
            elif jump == JUMP_MIN_UNTIL_2:
                rep = _rep(ctx)
                tail_repeat = state.repeat
                state.repeat = rep
                if ret != 0:
                    if tail_repeat is not None:
                        _drop(state, ctx.lastmark + 1)
                    k = K_EXIT
                    continue
                if tail_repeat is not None:
                    _mark_pop(state, ctx.lastmark, True)
                state.lastmark = ctx.lastmark
                state.lastindex = ctx.lastindex
                state.ptr = ptr
                if (ctx.count >= code[rep.pattern + 2] and code[rep.pattern + 2] != MAXREPEAT) or state.ptr == rep.last_ptr:
                    ret = 0
                    k = K_EXIT
                    continue
                rep.count = ctx.count
                state.data.append(rep.last_ptr)  # (zero-width match protection)
                rep.last_ptr = state.ptr
                nextp = rep.pattern + 3
                nextj = JUMP_MIN_UNTIL_3
                nextt = ctx.toplevel
            elif jump == JUMP_MIN_UNTIL_3:
                rep = _rep(ctx)
                rep.last_ptr = state.data.pop()
                if ret != 0:
                    k = K_EXIT
                    continue
                rep.count = ctx.count - 1
                state.ptr = ptr
                k = K_EXIT
                continue
            elif jump == JUMP_POSS_REPEAT_1:
                if ret != 0:
                    ctx.count += 1
                    k = K_POSS_MIN
                else:
                    state.ptr = ptr
                    state.repeat = _rep(ctx).prev
                    k = K_EXIT
                    continue
            elif jump == JUMP_POSS_REPEAT_2:
                if ret != 0:
                    _drop(state, ctx.lastmark + 1)
                    ctx.count += 1
                    k = K_POSS_MAX
                else:
                    _mark_pop(state, ctx.lastmark, True)
                    state.lastmark = ctx.lastmark
                    state.lastindex = ctx.lastindex
                    state.ptr = ptr
                    k = K_POSS_DONE
            elif jump == JUMP_ATOMIC_GROUP:
                if ret == 0:
                    state.ptr = ptr
                    k = K_EXIT
                    continue
                pattern += code[pattern]
                ptr = state.ptr
            elif jump == JUMP_ASSERT:
                if ret == 0:
                    k = K_EXIT
                    continue
                pattern += code[pattern]
            elif jump == JUMP_ASSERT_NOT:
                if ret != 0:
                    if state.repeat is not None:
                        _drop(state, ctx.lastmark + 1)
                    ret = 0
                    k = K_EXIT
                    continue
                if state.repeat is not None:
                    _mark_pop(state, ctx.lastmark, True)
                state.lastmark = ctx.lastmark
                state.lastindex = ctx.lastindex
                pattern += code[pattern]
        elif k == K_BRANCH:
            # the next alternative: <skip> code <JUMP>, a skip of 0 ends them
            k = K_DISPATCH
            while code[pattern] != 0:
                if code[pattern + 1] == LITERAL and (ptr >= end or s[ptr] != code[pattern + 2]):
                    pattern += code[pattern]
                    continue
                if code[pattern + 1] == IN and (ptr >= end or not _charset(state, code, pattern + 3, s[ptr])):
                    pattern += code[pattern]
                    continue
                # (not _sre's, which tests only the first literal or class here: the alternative's
                # next literals and classes are tested too, which change nothing but the position,
                # and its nested match begins after them, at q and at; never at an INFO, which is
                # only at code[0])
                q = pattern + 1
                at = ptr
                if code[q] == LITERAL or code[q] == IN:
                    q += 2 if code[q] == LITERAL else code[q + 1] + 1
                    at += 1
                    while at < end and ((code[q] == LITERAL and s[at] == code[q + 1])
                                        or (code[q] == IN and _charset(state, code, q + 2, s[at]))):
                        q += 2 if code[q] == LITERAL else code[q + 1] + 1
                        at += 1
                    if code[q] == LITERAL or code[q] == IN:
                        pattern += code[pattern]
                        continue
                op = code[q]
                if op == REPEAT_ONE or op == MIN_REPEAT_ONE or op == POSSESSIVE_REPEAT_ONE:
                    item = _repeated(code, q)
                    if item >= 0:
                        plain = code[item] == LITERAL or code[item] == IN
                        if not (_first(state, code, item, at) if plain else _first_ignore(state, code, item, at)):
                            # A mandatory first character rejects impossible alternatives. Keep
                            # the existing single-character-repeat gate and its capture behavior.
                            pattern += code[pattern]
                            continue
                state.ptr = at
                nextp = q
                nextj = JUMP_BRANCH
                nextt = ctx.toplevel
                break
            if nextj == 0:
                if state.repeat is not None:
                    _drop(state, ctx.lastmark + 1)
                ret = 0
                k = K_EXIT
                continue
        elif k == K_REPEAT_ONE_LITERAL:
            k = K_DISPATCH
            n = ctx.count  # (in locals, for the loop)
            least = code[pattern + 1]
            c = ctx.chr
            while n >= least and (ptr >= end or s[ptr] != c):
                ptr -= 1
                n -= 1
            ctx.count = n
            if n < least:
                if state.repeat is not None:
                    _drop(state, ctx.lastmark + 1)
                ret = 0
                k = K_EXIT
                continue
            state.ptr = ptr
            nextp = pattern + code[pattern]
            nextj = JUMP_REPEAT_ONE_1
            nextt = ctx.toplevel
        elif k == K_REPEAT_ONE:
            k = K_DISPATCH
            if ctx.count < code[pattern + 1]:
                if state.repeat is not None:
                    _drop(state, ctx.lastmark + 1)
                ret = 0
                k = K_EXIT
                continue
            state.ptr = ptr
            nextp = pattern + code[pattern]
            nextj = JUMP_REPEAT_ONE_2
            nextt = ctx.toplevel
        elif k == K_MIN_REPEAT_ONE:
            k = K_DISPATCH
            if code[pattern + 2] != MAXREPEAT and ctx.count > code[pattern + 2]:
                if state.repeat is not None:
                    _drop(state, ctx.lastmark + 1)
                ret = 0
                k = K_EXIT
                continue
            state.ptr = ptr
            nextp = pattern + code[pattern]
            nextj = JUMP_MIN_REPEAT_ONE
            nextt = ctx.toplevel
        elif k == K_MAX_UNTIL_TAIL:
            # no more items here: the tail must match
            k = K_DISPATCH
            state.repeat = _rep(ctx).prev
            nextp = pattern
            nextj = JUMP_MAX_UNTIL_3
            nextt = ctx.toplevel
        elif k == K_POSS_MIN:
            k = K_DISPATCH
            if ctx.count < code[pattern + 1]:
                nextp = pattern + 3
                nextj = JUMP_POSS_REPEAT_1
                nextt = False
            else:
                ptr = -1  # (so that the loop is entered: no iteration began here)
                k = K_POSS_MAX
                continue
        elif k == K_POSS_MAX:
            k = K_DISPATCH
            if (ctx.count < code[pattern + 2] or code[pattern + 2] == MAXREPEAT) and state.ptr != ptr:
                ctx.lastmark = state.lastmark
                ctx.lastindex = state.lastindex
                _mark_push(state, ctx.lastmark)
                ptr = state.ptr  # (zero-width match protection)
                nextp = pattern + 3
                nextj = JUMP_POSS_REPEAT_2
                nextt = False
            else:
                k = K_POSS_DONE
                continue
        elif k == K_POSS_DONE:
            state.repeat = _rep(ctx).prev
            pattern += code[pattern] + 1
            ptr = state.ptr
            k = K_DISPATCH
            continue
        if nextj != 0:
            # DO_JUMP: this context waits for a nested one, which begins at nextp
            ctx.pattern = pattern
            ctx.ptr = ptr
            depth += 1
            if base + depth < len(ctxs):
                ctx = ctxs[base + depth]
                ctx.reuse(nextp, nextt, nextj)
            else:
                ctx = Ctx(nextp, nextt, nextj)
                ctxs.append(ctx)
            state.top = base + depth + 1
            pattern = nextp
            nextj = 0
            k = K_ENTRANCE


def _attempt(state: State[_S], code: list[int], pattern: int, toplevel: bool) -> int:
    # (not _sre's) sre_match() where a search tries state.start: by the matcher a program's build of
    # _pystachy_re_specialized has for the pattern (tools/re_specialize.py), from the code's start
    # (a skipped prefix matches again), where the state has one; where it declines (group repeats
    # nested too deep), the state is as the search left it, and sre_match() runs
    if state.fast >= 0:
        ptr = state.ptr
        r = _pystachy_re_specialized.attempt(state.fast, state, toplevel)
        if r >= 0:
            return r
        state.ptr = ptr
        state.lastmark = -1
        state.lastindex = -1
        if len(state.data) != 0:
            state.data = []
    return sre_match(state, code, pattern, toplevel)


def sre_search(state: State[_S], code: list[int]) -> int:
    # SRE(search): the first position from state.start where the code matches (state.start and
    # state.ptr then bound the match), or 0
    s = state.s
    ptr = state.start
    end = state.end
    status = 0
    prefix_len = 0
    prefix_skip = 0
    prefix = 0
    overlap = 0
    charset_at = -1
    flags = 0
    pattern = 0
    if ptr > end:
        return 0
    if code[0] == INFO:
        # <INFO> <1=skip> <2=flags> <3=min> <4=max> <5=prefix info>
        flags = code[2]
        if code[3] != 0 and end - ptr < code[3]:
            return 0
        if code[3] > 1:
            # (leave at least one character, so the literal search works)
            end -= code[3] - 1
            if end <= ptr:
                end = ptr
        if flags & SRE_INFO_PREFIX != 0:
            # <length> <skip> <prefix data> <overlap data>
            prefix_len = code[5]
            prefix_skip = code[6]
            prefix = 7
            overlap = prefix + prefix_len - 1
        elif flags & SRE_INFO_CHARSET != 0:
            charset_at = 5
        pattern = 1 + code[1]
    if prefix_len == 1:
        # a literal character first
        c = code[prefix]
        end = state.end
        state.must_advance = False
        while ptr < end:
            while s[ptr] != c:
                ptr += 1
                if ptr >= end:
                    return 0
            state.start = ptr
            state.ptr = ptr + prefix_skip
            if flags & SRE_INFO_LITERAL != 0:
                return 1  # (that is all of it)
            status = _attempt(state, code, pattern + 2 * prefix_skip, False)
            if status != 0:
                return status
            ptr += 1
            state.lastmark = -1
            state.lastindex = -1
        return 0
    if prefix_len > 1:
        # a known prefix first: skip ahead by its overlap table
        end = state.end
        if prefix_len > end - ptr:
            return 0
        while ptr < end:
            c = code[prefix]
            while True:
                ptr += 1
                if s[ptr - 1] == c:
                    break
                if ptr >= end:
                    return 0
            if ptr >= end:
                return 0
            i = 1
            state.must_advance = False
            while True:
                if s[ptr] == code[prefix + i]:
                    i += 1
                    if i != prefix_len:
                        ptr += 1
                        if ptr >= end:
                            return 0
                        continue
                    # a potential match
                    state.start = ptr - (prefix_len - 1)
                    state.ptr = ptr - (prefix_len - prefix_skip - 1)
                    if flags & SRE_INFO_LITERAL != 0:
                        return 1
                    status = _attempt(state, code, pattern + 2 * prefix_skip, False)
                    if status != 0:
                        return status
                    # close, but no match: try again
                    ptr += 1
                    if ptr >= end:
                        return 0
                    state.lastmark = -1
                    state.lastindex = -1
                i = code[overlap + i]
                if i == 0:
                    break
        return 0
    pf = _prefilter(state, code, pattern)
    if pf[0] == PF_BRANCH and pf[2] != 0:
        # (not _sre's: the alternatives' first literals and classes, found by their bit-parallel
        # filter, where the search below would test them at each position)
        return _branch_search(state, code, pattern, pf, ptr, state.end if charset_at >= 0 else end, charset_at >= 0)
    if charset_at >= 0:
        # a character from a known set first
        end = state.end
        state.must_advance = False
        b = pf[1] if pf[0] == PF_BRANCH else -1
        t = _table(state, code, charset_at)
        table = state.charset_ascii
        while True:
            # (not _sre's loop of SRE(charset) calls: the set's ASCII nonmembers are skipped here, by
            # its table, found once for the search; _span() decides the other characters)
            if t >= 0:
                while ptr < end:
                    ch = s[ptr]
                    if ch >= 128 or table[t + ch] != 0:
                        break
                    ptr += 1
            if ptr < end and (t < 0 or s[ptr] >= 128):
                ptr = _span(state, code, charset_at, 0, ptr, end, False)
            if ptr >= end:
                return 0
            if b >= 0 and not _branch_starts(state, code, b, ptr):
                # (not _sre's: the set has the alternatives' first characters, but no alternative's
                # leading literals and classes all match here)
                ptr += 1
                state.lastmark = -1
                state.lastindex = -1
                continue
            state.start = ptr
            state.ptr = ptr
            status = _attempt(state, code, pattern, False)
            if status != 0:
                break
            ptr += 1
            state.lastmark = -1
            state.lastindex = -1
    elif pf[0] == PF_LINE:
        # (not in _sre: a pattern that begins with ^ of MULTILINE, after marks, which match
        # anywhere, can match only where a line begins, as sre_at() says: at the string's start or
        # after a \n, not at pos; the matcher is entered there alone, which the general case below
        # does at every position, each match failing at once elsewhere)
        if ptr == 0 or s[ptr - 1] == 10:
            state.start = ptr
            state.ptr = ptr
            status = _attempt(state, code, pattern, True)
        state.must_advance = False
        while status == 0:
            while ptr < end and s[ptr] != 10:
                ptr += 1
            if ptr >= end:
                # (where the general case's last position leaves them)
                state.start = end
                state.ptr = end
                return 0
            ptr += 1
            state.lastmark = -1
            state.lastindex = -1
            state.start = ptr
            state.ptr = ptr
            status = _attempt(state, code, pattern, False)
    elif pf[0] == PF_REPEATED:
        # (not _sre's: a pattern that begins with a character repeated at least once, after
        # groups' marks, can match only where that character is: the matcher is entered there
        # alone, which the general case below does at every position)
        item = pf[1]
        first = ptr  # (where must_advance applies, as in the general case)
        while True:
            ptr = _first_span(state, code, item, ptr, end)
            if ptr >= end:
                # (where the general case's last position leaves them)
                state.must_advance = False
                state.start = end
                state.ptr = end
                return 0
            state.lastmark = -1
            state.lastindex = -1
            state.start = ptr
            state.ptr = ptr
            status = _attempt(state, code, pattern, ptr == first)
            state.must_advance = False
            if status != 0:
                return status
            ptr += 1
    elif pf[0] == PF_BRANCH:
        # (not _sre's: a pattern that begins with alternatives, after groups' marks, each beginning
        # with a literal or a class, can match only where all the leading literals and classes of
        # one of them match: the matcher is entered there alone, which the general case below does
        # at every position)
        b = pf[1]
        first = ptr  # (where must_advance applies, as in the general case)
        while True:
            while ptr < end and not _branch_starts(state, code, b, ptr):
                ptr += 1
            if ptr >= end:
                # (where the general case's last position leaves them)
                state.must_advance = False
                state.start = end
                state.ptr = end
                return 0
            state.lastmark = -1
            state.lastindex = -1
            state.start = ptr
            state.ptr = ptr
            status = _attempt(state, code, pattern, ptr == first)
            state.must_advance = False
            if status != 0:
                return status
            ptr += 1
    elif pf[0] == PF_LITERAL:
        # (not _sre's: every match has the literals from code[at] at an offset from its start from
        # dmin to dmax: the matcher is entered only where they are found, at most once at each
        # position, in order, which the general case below does at every position. Positions
        # before the first literals found from a start's least offset cannot match)
        dmin = pf[1]
        dmax = pf[2]
        at = pf[3]
        n = pf[4]
        first = ptr  # (where must_advance applies, as in the general case)
        last = state.end - n  # (where the literals may begin, at most)
        nxt = ptr  # (the first position neither tried nor ruled out)
        while True:
            q = _literals_find(state, code, at, n, nxt + dmin, last)
            if q < 0:
                break
            ptr = q - dmax if q - dmax > nxt else nxt
            while ptr <= q - dmin:
                state.lastmark = -1
                state.lastindex = -1
                state.start = ptr
                state.ptr = ptr
                status = _attempt(state, code, pattern, ptr == first)
                state.must_advance = False
                if status != 0:
                    return status
                ptr += 1
            nxt = q - dmin + 1
        # (where the general case's last position leaves them)
        state.must_advance = False
        state.start = end
        state.ptr = end
        return 0
    else:
        # the general case
        state.start = ptr
        state.ptr = ptr
        status = _attempt(state, code, pattern, True)
        state.must_advance = False
        if status == 0 and code[pattern] == AT and (code[pattern + 1] == AT_BEGINNING or code[pattern + 1] == AT_BEGINNING_STRING):
            state.start = end
            state.ptr = end
            return 0
        while status == 0 and ptr < end:
            ptr += 1
            state.lastmark = -1
            state.lastindex = -1
            state.start = ptr
            state.ptr = ptr
            status = _attempt(state, code, pattern, False)
    return status


def _at_line_start(code: list[int], p: int) -> bool:
    # whether the code at p begins with AT_BEGINNING_LINE, after MARKs
    return code[_after_marks(code, p)] == AT and code[_after_marks(code, p) + 1] == AT_BEGINNING_LINE


def _after_marks(code: list[int], p: int) -> int:
    # the code after the MARKs at p
    while code[p] == MARK:
        p += 2
    return p


def _repeated(code: list[int], p: int) -> int:
    # where a literal or class (including case-insensitive variants) is, if the code at p is a
    # repeat with a nonzero minimum that begins with it, after any group marks, else -1
    op = code[p]
    if (op == REPEAT_ONE or op == MIN_REPEAT_ONE or op == POSSESSIVE_REPEAT_ONE or op == REPEAT) \
            and code[p + 2] >= 1:
        # Both repeat layouts begin <op> <skip> <min> <max> <body>. Only skip MARKs: an
        # assertion, alternative or optional item may let the body match without this character.
        first = _after_marks(code, p + 4) if op == REPEAT else p + 4
        item = code[first]
        if item == LITERAL or item == IN or item == LITERAL_IGNORE or item == LITERAL_UNI_IGNORE \
                or item == IN_IGNORE or item == IN_UNI_IGNORE:
            return first
    return -1


def _first(state: State[_S], code: list[int], item: int, ptr: int) -> bool:
    # whether the character at ptr matches the LITERAL or IN at item
    if ptr >= state.end:
        return False
    if code[item] == LITERAL:
        return state.s[ptr] == code[item + 1]
    return _charset(state, code, item + 2, state.s[ptr])


def _first_span(state: State[_S], code: list[int], item: int, ptr: int, end: int) -> int:
    # the first position from ptr (end at most) where the literal or class at item (_repeated's)
    # matches, each character tested as _first() or _first_ignore() would
    s = state.s
    op = code[item]
    if op == IN or op == IN_IGNORE or op == IN_UNI_IGNORE:
        return _span(state, code, item + 2, 0 if op == IN else 1 if op == IN_IGNORE else 2, ptr, end, False)
    c = code[item + 1]
    if op == LITERAL:
        while ptr < end and s[ptr] != c:
            ptr += 1
        return ptr
    while ptr < end:
        # (lower_ascii() and, for LITERAL_UNI_IGNORE, lower_unicode() as they would apply)
        ch = s[ptr]
        if ch < 128:
            if 65 <= ch and ch <= 90:
                ch += 32
        elif op == LITERAL_UNI_IGNORE:
            ch = _mapped(0, ch)
        if ch == c:
            break
        ptr += 1
    return ptr


def _first_ignore(state: State[_S], code: list[int], item: int, ptr: int) -> bool:
    # Keep Unicode mapping's live arguments out of the common case-sensitive first-item check.
    if ptr >= state.end:
        return False
    op = code[item]
    ch = state.s[ptr]
    if op == LITERAL_IGNORE or op == IN_IGNORE:
        ch = lower_ascii(ch)
    elif op == LITERAL_UNI_IGNORE or op == IN_UNI_IGNORE:
        ch = lower_unicode(ch)
    if op == LITERAL_IGNORE or op == LITERAL_UNI_IGNORE:
        return ch == code[item + 1]
    return _charset(state, code, item + 2, ch)


# ---- (not _sre's) what a search without a literal prefix may skip by, found once for each Pattern

PF_NONE = 0  # [PF_NONE, 0, 0, 0, 0]: the general case
PF_LINE = 1  # [PF_LINE, 0, 0, 0, 0]: a ^ of MULTILINE begins it (_at_line_start)
PF_REPEATED = 2  # [PF_REPEATED, item, 0, 0, 0]: a repeat of the literal or class at item (_repeated)
PF_BRANCH = 3  # [PF_BRANCH, b, n, starts, ends, masks..., high, memo...]: the BRANCH at code[b] begins it (_branch_starts, _branch_masks)
PF_LITERAL = 4  # [PF_LITERAL, dmin, dmax, at, n]: the literals of _literals_find (_walk's)


def _prefilter(state: State[_S], code: list[int], pattern: int) -> list[int]:
    # state.prefilter (the Pattern's), found at its first search: whether the code at pattern
    # begins, after groups' marks, with a ^ of MULTILINE, a mandatory repeat of a literal or a class,
    # or alternatives that each begin with a literal or a class, or else has literals at a bounded
    # offset from the start of every match, in that order (the charset search applies PF_BRANCH)
    pf = state.prefilter
    if len(pf) == 0:
        b = _after_marks(code, pattern)
        found = [PF_NONE, 0, 0, 0, 0]
        if _at_line_start(code, pattern):
            found = [PF_LINE, 0, 0, 0, 0]
        elif _repeated(code, b) >= 0:
            found = [PF_REPEATED, _repeated(code, b), 0, 0, 0]
        elif code[b] == BRANCH and _branch_runs(code, b):
            found = [PF_BRANCH, b, 0, 0, 0]
            _branch_masks(state, code, b, found)
        elif not (code[pattern] == AT and (code[pattern + 1] == AT_BEGINNING or code[pattern + 1] == AT_BEGINNING_STRING)):
            # (the general case tries a ^ of the whole string, first, once)
            w = _walk(code, pattern, True)
            if w[0] >= 0:
                n = 0
                while code[w[0] + 2 * n] == LITERAL or code[w[0] + 2 * n] == LITERAL_IGNORE \
                        or code[w[0] + 2 * n] == LITERAL_UNI_IGNORE:
                    n += 1
                found = [PF_LITERAL, w[1], w[2], w[0], n]
        for x in found:
            pf.append(x)
    return pf


def _branch_runs(code: list[int], b: int) -> bool:
    # whether each alternative of the BRANCH at code[b] begins with a literal or a class
    alt = b + 1
    while code[alt] != 0:
        if code[alt + 1] != LITERAL and code[alt + 1] != IN:
            return False
        alt += code[alt]
    return True


def _branch_masks(state: State[_S], code: list[int], b: int, found: list[int]) -> None:
    # (not _sre's) PF_BRANCH's bit-parallel filter (Shift-And), where the alternatives' runs of
    # leading literals and classes are of n >= 2 items at least: bits k * n to k * n + n - 1 of a
    # word stand for the first n items of alternative k (at most 62 bits). found[5 + c] has the
    # bits of the items that each ASCII character c matches, found[3] the first item of each
    # alternative and found[4] the last. found[5 + 128] has the items that may match a character
    # from 128 (_branch_wide). Where there are some, HIGH_MEMO slots of such a character and the
    # alternatives' first items it matches follow (_branch_high), then where each item is in code
    # (_branch_test). found[2] stays 0 where there is no filter
    k = 0
    n = 62
    alt = b + 1
    while code[alt] != 0:
        q = alt + 1
        run = 0
        while code[q] == LITERAL or code[q] == IN:
            run += 1
            q += 2 if code[q] == LITERAL else code[q + 1] + 1
        n = run if run < n else n
        k += 1
        alt += code[alt]
    if k == 0:
        return
    if n * k > 62:
        n = 62 // k
    if n < 2:
        return
    starts = 0
    for i in range(k):
        starts |= 1 << (i * n)
    found[2] = n
    found[3] = starts
    found[4] = starts << (n - 1)
    for c in range(128):
        found.append(_branch_bits(state, code, b, n, c))
    items = _branch_positions(code, b, n)
    wide = 0
    for i in range(len(items)):
        if _branch_wide(code, items[i]):
            wide |= 1 << i
    found.append(wide)
    if wide != 0:
        for _ in range(HIGH_MEMO):
            found.append(-1)
            found.append(0)
        for q in items:
            found.append(q)


def _branch_bits(state: State[_S], code: list[int], b: int, n: int, ch: int) -> int:
    # the bits of the first n items of the alternatives of the BRANCH at code[b] that ch matches,
    # as _branch_starts tests them (see _branch_masks)
    bits = 0
    bit = 1
    alt = b + 1
    while code[alt] != 0:
        q = alt + 1
        for _ in range(n):
            if code[q] == LITERAL:
                if ch == code[q + 1]:
                    bits |= bit
                q += 2
            else:
                if _charset(state, code, q + 2, ch):
                    bits |= bit
                q += code[q + 1] + 1
            bit <<= 1
        alt += code[alt]
    return bits


def _branch_positions(code: list[int], b: int, n: int) -> list[int]:
    # where the first n items of each alternative of the BRANCH at code[b] are, in the order of
    # their bits (see _branch_masks)
    items: list[int] = []
    alt = b + 1
    while code[alt] != 0:
        q = alt + 1
        for _ in range(n):
            items.append(q)
            q += 2 if code[q] == LITERAL else code[q + 1] + 1
        alt += code[alt]
    return items


def _branch_wide(code: list[int], q: int) -> bool:
    # whether the literal or class at code[q] may match a character from 128: a literal from 128,
    # or a class with members there (see _charset_high)
    if code[q] == LITERAL:
        return code[q + 1] >= 128
    high = _charset_high(code, q + 2)
    return high[0] != HIGH_IN or high[1] <= high[2]


def _branch_high(state: State[_S], code: list[int], pf: list[int], rest: int, ch: int) -> int:
    # the bits of ch, a character from 128, where some item may match one (see _branch_masks): the
    # alternatives' first items it matches, from HIGH_MEMO slots by its low bits, and those of
    # rest, the next items of the matches under way. A character costs the first items where the
    # memo misses and the next items of its matches, never every item
    slot = 5 + 129 + (ch & (HIGH_MEMO - 1)) * 2
    if pf[slot] != ch:
        pf[slot + 1] = _branch_test(state, code, pf, pf[3] & pf[5 + 128], ch)
        pf[slot] = ch
    if rest == 0:
        return pf[slot + 1]
    return pf[slot + 1] | _branch_test(state, code, pf, rest, ch)


def _branch_test(state: State[_S], code: list[int], pf: list[int], cand: int, ch: int) -> int:
    # the items of cand (bits of the filter) that ch matches, each tested as _branch_starts tests
    # it, where pf says it is (see _branch_masks)
    bits = 0
    at = 5 + 129 + 2 * HIGH_MEMO - 1
    while cand != 0:
        low = cand & -cand
        cand ^= low
        q = pf[at + low.bit_length()]
        if code[q] == LITERAL:
            if code[q + 1] == ch:
                bits |= low
        elif _charset(state, code, q + 2, ch):
            bits |= low
    return bits


def _branch_search(state: State[_S], code: list[int], pattern: int, pf: list[int], ptr: int, end: int, charset: bool) -> int:
    # (not _sre's) the search of a PF_BRANCH pattern that has its bit-parallel filter: d has the bits
    # of the alternatives' items that the characters up to s[j] match in order from an item that
    # begins its alternative's run (Shift-And), so a set last bit means that alternative's first n
    # items match from j - n + 1. Only those positions can satisfy _branch_starts; the matcher is
    # entered at each that does, below end, as the charset search (charset) or PF_BRANCH's loop
    # enters it, with their bounds, flags and resets. A character from 128 that no item may match
    # has no bits; for the others, see _branch_high
    s = state.s
    stop = state.end
    b = pf[1]
    n = pf[2]
    starts = pf[3]
    ends = pf[4]
    wide = pf[5 + 128]
    later = wide & ~starts  # (the items after the first that may match a character from 128)
    first = ptr
    if charset:
        state.must_advance = False
    d = 0
    j = ptr
    while j < stop:
        c = s[j]
        if c < 128:
            d = ((d << 1) | starts) & pf[5 + c]
        elif wide == 0:
            d = 0
        else:
            d = _branch_high(state, code, pf, (d << 1) & later, c)
        if d & ends != 0:
            at = j - n + 1
            if at >= end:
                break
            if _branch_starts(state, code, b, at):
                state.lastmark = -1
                state.lastindex = -1
                state.start = at
                state.ptr = at
                status = _attempt(state, code, pattern, False if charset else at == first)
                if not charset:
                    state.must_advance = False
                if status != 0:
                    return status
        j += 1
    if not charset:
        # (where the general case's last position leaves them)
        state.must_advance = False
        state.start = end
        state.ptr = end
    return 0


def _branch_starts(state: State[_S], code: list[int], b: int, ptr: int) -> bool:
    # whether an alternative of the BRANCH at code[b] may begin at ptr: all its leading literals
    # and classes match there (as K_BRANCH tests them), or it begins with something else
    s = state.s
    end = state.end
    alt = b + 1
    while code[alt] != 0:
        q = alt + 1
        at = ptr
        while True:
            op = code[q]
            if op == LITERAL:
                if at >= end or s[at] != code[q + 1]:
                    break
                q += 2
            elif op == IN:
                if at >= end or not _charset(state, code, q + 2, s[at]):
                    break
                q += code[q + 1] + 1
            else:
                return True
            at += 1
        alt += code[alt]
    return False


def _walk(code: list[int], p: int, find: bool) -> list[int]:
    # [where the items from code[p] end (at the JUMP that ends an alternative, or SUCCESS), the
    # least and the greatest number of characters they match], or with find, [where the first
    # literal (LITERAL, LITERAL_IGNORE or LITERAL_UNI_IGNORE) not in an alternative, an assertion
    # or a repeat is, the least and greatest number before it]; [-1, 0, 0] where an item before is
    # of no such bounded width
    lo = 0
    hi = 0
    while True:
        op = code[p]
        if op == JUMP or op == SUCCESS:
            return [-1, 0, 0] if find else [p, lo, hi]
        if find and (op == LITERAL or op == LITERAL_IGNORE or op == LITERAL_UNI_IGNORE):
            return [p, lo, hi]
        if op == MARK or op == AT:
            p += 2
        elif op == ASSERT or op == ASSERT_NOT:
            p += code[p + 1] + 1
        elif op == LITERAL or op == NOT_LITERAL or op == CATEGORY or op == LITERAL_IGNORE \
                or op == NOT_LITERAL_IGNORE or op == LITERAL_UNI_IGNORE or op == NOT_LITERAL_UNI_IGNORE:
            lo += 1
            hi += 1
            p += 2
        elif op == ANY or op == ANY_ALL:
            lo += 1
            hi += 1
            p += 1
        elif op == IN or op == IN_IGNORE or op == IN_UNI_IGNORE:
            lo += 1
            hi += 1
            p += code[p + 1] + 1
        elif op == REPEAT_ONE or op == MIN_REPEAT_ONE or op == POSSESSIVE_REPEAT_ONE:
            # (of one character: <op> <skip> <min> <max> item <SUCCESS>)
            if code[p + 3] == MAXREPEAT:
                return [-1, 0, 0]
            lo += code[p + 2]
            hi += code[p + 3]
            p += code[p + 1] + 1
        elif op == BRANCH:
            least = -1
            most = 0
            alt = p + 1
            while code[alt] != 0:
                w = _walk(code, alt + 1, False)
                if w[0] < 0:
                    return [-1, 0, 0]
                least = w[1] if least < 0 or w[1] < least else least
                most = w[2] if w[2] > most else most
                alt += code[alt]
            if least < 0:
                return [-1, 0, 0]
            lo += least
            hi += most
            p = alt + 1
        else:
            return [-1, 0, 0]


def _literals_find(state: State[_S], code: list[int], at: int, n: int, q: int, last: int) -> int:
    # the first position from q (last at most) where the n literals from code[at] all match, each
    # as the matcher tests it (lowered as lower_ascii() or lower_unicode() for the _IGNOREs), or -1
    s = state.s
    op = code[at]
    c = code[at + 1]
    while q <= last:
        # the first literal, in a loop of its own
        if op == LITERAL:
            while q <= last and s[q] != c:
                q += 1
        else:
            while q <= last:
                ch = s[q]
                if ch < 128:
                    if 65 <= ch and ch <= 90:
                        ch += 32
                elif op == LITERAL_UNI_IGNORE:
                    ch = _mapped(0, ch)
                if ch == c:
                    break
                q += 1
        if q > last:
            return -1
        j = 1
        while j < n:
            op2 = code[at + 2 * j]
            ch = s[q + j]
            if op2 == LITERAL_IGNORE:
                ch = lower_ascii(ch)
            elif op2 == LITERAL_UNI_IGNORE:
                ch = lower_unicode(ch)
            if ch != code[at + 2 * j + 1]:
                break
            j += 1
        if j == n:
            return q
        q += 1
    return -1
