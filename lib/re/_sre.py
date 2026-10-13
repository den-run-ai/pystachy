# Pystachy's re: the matching engine of CPython 3.13's _sre (Modules/_sre/sre_lib.h and sre.c),
# ported to the subset. It runs the code that re's compiler (__init__.py, as CPython's
# _compiler.py) makes of a pattern, over a string's code points (State.s), with CPython's
# explicit stack of match contexts: a nested match (DO_JUMP) pushes a context and resumes the
# code after it once that context returns (the jump labels, here the K_* steps of sre_match).
# Positions are indices into State.s; __init__.py turns them into the str's own indices.
from . import _unicode
from ._constants import *

# ---- the characters, as sre.c tests them

# lazily decoded tables of _unicode.py: the boundaries of ALNUM, DECIMAL, SPACE, LINEBREAK, IDSTART
# and IDCONTINUE (each range a start and an end past it), and the code points LOWER and UPPER map
# and their maps
_ranges: list[list[int]] = []
_mapkeys: list[list[int]] = []
_mapvals: list[list[int]] = []


def _decode() -> None:
    for text in [_unicode.ALNUM, _unicode.DECIMAL, _unicode.SPACE, _unicode.LINEBREAK, _unicode.IDSTART, _unicode.IDCONTINUE]:
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
    keys = _mapkeys[t]
    lo = 0
    hi = len(keys)
    while lo < hi:
        mid = (lo + hi) // 2
        if keys[mid] < ch:
            lo = mid + 1
        else:
            hi = mid
    if lo < len(keys) and keys[lo] == ch:
        return _mapvals[t][lo]
    return ch


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


class State:
    # SRE_STATE over the code points s: start and end bound the match (pos and endpos), ptr is
    # where the last match ended, and mark the group bounds (-1 for none) up to lastmark
    def __init__(self, s: list[int], start: int, end: int, groups: int) -> None:
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
        self.offs: list[int] = []  # (re's: the index in the str of each of s's code points, [] if they are theirs)
        # (not _sre's: the contexts of the matches of this state, kept for reuse: those below top are
        # in use, by sre_match() and the calls nested in it through sre_count(), the others free)
        self.ctxs: list[Ctx] = []
        self.top = 0
        # Pattern's lazily built ASCII class tables, shared by its states. Empty until _state
        # attaches them; direct engine callers retain charset()'s bytecode evaluation.
        self.charset_offsets: list[int] = []
        self.charset_ascii: list[int] = []

    def reset(self) -> None:
        # state_reset
        self.lastmark = -1
        self.lastindex = -1
        self.repeat = None
        self.data = []


def _charset_table(state: State, code: list[int], i: int) -> int:
    start = len(state.charset_ascii)
    for c in range(128):
        state.charset_ascii.append(int(charset(code, i, c)))
    state.charset_offsets[i] = start
    return start


def _charset(state: State, code: list[int], i: int, ch: int) -> bool:
    # The caller applies an IN_IGNORE/IN_UNI_IGNORE's folding before arriving here. Each code
    # position therefore has one fixed set, including scoped flags, independent of the string.
    # Keep CPython's bytecode untouched and non-ASCII characters on its original evaluator.
    if ch >= 128 or len(state.charset_offsets) == 0:
        return charset(code, i, ch)
    start = state.charset_offsets[i]
    if start < 0:
        start = _charset_table(state, code, i)
    return state.charset_ascii[start + ch] != 0


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


def _mark_push(state: State, lastmark: int) -> None:
    for i in range(lastmark + 1):
        state.data.append(state.mark[i])


def _mark_pop(state: State, lastmark: int, discard: bool) -> None:
    n = lastmark + 1
    if n == 0:
        return
    base = len(state.data) - n
    for i in range(n):
        state.mark[i] = state.data[base + i]
    if discard:
        _drop(state, n)


def _drop(state: State, n: int) -> None:
    for _ in range(n):
        state.data.pop()


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


def sre_count(state: State, code: list[int], p: int, maxcount: int) -> int:
    # SRE(count): how many times the single-character item at code[p] matches from state.ptr, at
    # most maxcount
    s = state.s
    ptr = state.ptr
    end = state.end
    if maxcount < end - ptr and maxcount != MAXREPEAT:
        end = ptr + maxcount
    op = code[p]
    if op == IN:
        while ptr < end and _charset(state, code, p + 2, s[ptr]):
            ptr += 1
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


def sre_at(state: State, ptr: int, at: int) -> bool:
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


def sre_match(state: State, code: list[int], start: int, toplevel: bool) -> int:
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
                if code[tail] == LITERAL:
                    # the tail starts with a literal: skip the positions where it cannot match
                    ctx.chr = code[tail + 1]
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
                op = code[pattern + 1]
                if (op == REPEAT_ONE or op == MIN_REPEAT_ONE or op == POSSESSIVE_REPEAT_ONE) \
                        and _repeated(code, pattern + 1) >= 0 and not _first(state, code, pattern + 5, ptr):
                    # (not _sre's: an alternative that begins with a character repeated at least
                    # once cannot match where that character is not; the opcode is tested here, as
                    # the alternatives inside a lazy repeat's tail are tried at each character)
                    pattern += code[pattern]
                    continue
                state.ptr = ptr
                nextp = pattern + 1
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
            while ctx.count >= code[pattern + 1] and (ptr >= end or s[ptr] != ctx.chr):
                ptr -= 1
                ctx.count -= 1
            if ctx.count < code[pattern + 1]:
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


def sre_search(state: State, code: list[int]) -> int:
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
            status = sre_match(state, code, pattern + 2 * prefix_skip, False)
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
                    status = sre_match(state, code, pattern + 2 * prefix_skip, False)
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
    if charset_at >= 0:
        # a character from a known set first
        end = state.end
        state.must_advance = False
        while True:
            while ptr < end and not _charset(state, code, charset_at, s[ptr]):
                ptr += 1
            if ptr >= end:
                return 0
            state.start = ptr
            state.ptr = ptr
            status = sre_match(state, code, pattern, False)
            if status != 0:
                break
            ptr += 1
            state.lastmark = -1
            state.lastindex = -1
    elif _at_line_start(code, pattern):
        # (not in _sre: a pattern that begins with ^ of MULTILINE, after marks, which match
        # anywhere, can match only where a line begins, as sre_at() says: at the string's start or
        # after a \n, not at pos; the matcher is entered there alone, which the general case below
        # does at every position, each match failing at once elsewhere)
        if ptr == 0 or s[ptr - 1] == 10:
            state.start = ptr
            state.ptr = ptr
            status = sre_match(state, code, pattern, True)
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
            status = sre_match(state, code, pattern, False)
    elif _repeated(code, _after_marks(code, pattern)) >= 0:
        # (not _sre's: a pattern that begins with a character repeated at least once, after
        # groups' marks, can match only where that character is: the matcher is entered there
        # alone, which the general case below does at every position)
        item = _repeated(code, _after_marks(code, pattern))
        first = ptr  # (where must_advance applies, as in the general case)
        while True:
            while ptr < end and not _first(state, code, item, ptr):
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
            status = sre_match(state, code, pattern, ptr == first)
            state.must_advance = False
            if status != 0:
                return status
            ptr += 1
    else:
        # the general case
        state.start = ptr
        state.ptr = ptr
        status = sre_match(state, code, pattern, True)
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
            status = sre_match(state, code, pattern, False)
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
    # where the item is, a LITERAL or an IN, if the code at p is a REPEAT_ONE, MIN_REPEAT_ONE or
    # POSSESSIVE_REPEAT_ONE of it, at least once (<op> <skip> <min> <max> item), else -1
    op = code[p]
    if (op == REPEAT_ONE or op == MIN_REPEAT_ONE or op == POSSESSIVE_REPEAT_ONE) and code[p + 2] >= 1:
        if code[p + 4] == LITERAL or code[p + 4] == IN:
            return p + 4
    return -1


def _first(state: State, code: list[int], item: int, ptr: int) -> bool:
    # whether the character at ptr matches the LITERAL or IN at item
    if ptr >= state.end:
        return False
    if code[item] == LITERAL:
        return state.s[ptr] == code[item + 1]
    return _charset(state, code, item + 2, state.s[ptr])
