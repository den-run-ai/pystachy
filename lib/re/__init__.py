# Pystachy's re: CPython 3.13's re module (Lib/re/__init__.py, _parser.py, _compiler.py and the
# _sre engine of Modules/_sre), ported to the subset. The parser and the compiler make the
# code CPython's do, and _sre.py runs it as CPython's engine does, so a pattern matches,
# splits and substitutes as in CPython, with CPython's errors and their messages.
#
# A str holds UTF-8 in Pystachy: a pattern is read and a string matched character by character
# (their code points), and every position (pos, endpos, a match's spans, an error's pos) is an
# index into the str, as slicing and find() count them. For ASCII text that is CPython's.
from . import _sre
from ._constants import *

__all__ = ["match", "fullmatch", "search", "sub", "subn", "split", "findall", "finditer", "compile", "purge",
           "escape", "error", "Pattern", "Match", "A", "I", "L", "M", "S", "X", "U", "ASCII", "IGNORECASE",
           "LOCALE", "MULTILINE", "DOTALL", "VERBOSE", "UNICODE", "NOFLAG", "PatternError"]
__version__ = "2.2.1"

# the flags (CPython's are RegexFlag members; these are their int values)
NOFLAG = 0
ASCII = A = SRE_FLAG_ASCII  # assume ascii "locale"
IGNORECASE = I = SRE_FLAG_IGNORECASE  # ignore case
LOCALE = L = SRE_FLAG_LOCALE  # assume current 8-bit locale
UNICODE = U = SRE_FLAG_UNICODE  # assume unicode "locale"
MULTILINE = M = SRE_FLAG_MULTILINE  # make anchors look for newline
DOTALL = S = SRE_FLAG_DOTALL  # make dot match newline
VERBOSE = X = SRE_FLAG_VERBOSE  # ignore whitespace and comments
DEBUG = SRE_FLAG_DEBUG  # dump pattern after compilation

_MAXSIZE = 9223372036854775807  # sys.maxsize
_UTF8 = len("é") == 2  # (a str holds UTF-8, as in Pystachy; else code points, as in CPython)


class error(Exception):
    # re.error. In CPython 3.13 it is PatternError itself (error = PatternError); here PatternError,
    # which the module raises, derives from it, so that both catch it
    def __init__(self, msg: str, pattern: str | None = None, pos: int | None = None) -> None:
        self.msg = msg
        self.pattern = pattern
        self.pos = pos
        self.lineno: int | None = None
        self.colno: int | None = None
        if pattern is not None and pos is not None:
            msg = "%s at position %d" % (msg, pos)
            self.lineno = pattern.count("\n", 0, pos) + 1
            self.colno = pos - pattern.rfind("\n", 0, pos)
            if "\n" in pattern:
                msg = "%s (line %d, column %d)" % (msg, pattern.count("\n", 0, pos) + 1, pos - pattern.rfind("\n", 0, pos))
        super().__init__(msg)


class PatternError(error):
    """Exception raised for invalid regular expressions."""


def _chr(c: int) -> str:
    # the str of code point c (chr() of a Pystachy str below 256 is a byte; this is its UTF-8)
    return "%c" % c


def _charat(s: str, i: int) -> str:
    # the character that begins at index i of s: in Pystachy, its UTF-8 bytes
    c = s[i]
    if not _UTF8:
        return c
    b = ord(c)
    if b < 0xC0:
        return c
    n = 2 if b < 0xE0 else 3 if b < 0xF0 else 4
    return s[i : i + n]


# ---- the strings a pattern matches, as the code points the engine reads, with their indices

_last = ""
_last_codes: list[int] = []
_last_offs: list[int] = []  # (the index in the str of each code point, and its length; [] for ASCII)
_decoded = 0  # the code points decoded so far (tests/deviations/lib_re_decoding.py counts them)


def _codes(string: str) -> list[int]:
    # string's code points, decoded once for the string matched last (as parsy matches one string
    # at many positions); _offs then has the index of each in the str, or is [] if those are theirs.
    # An operation keeps what it gets (its State's s and offs): what a function it calls matches,
    # which decodes another string, is no reason to decode its own again
    global _last, _last_codes, _last_offs, _decoded
    if string is _last and len(string) == len(_last):
        return _last_codes
    codes: list[int] = []
    offs: list[int] = []
    if not _UTF8:
        for c in string:
            codes.append(ord(c))
    else:
        n = len(string)
        bs = [ord(c) for c in string]
        ascii = True
        for b in bs:
            if b >= 128:
                ascii = False
                break
        if ascii:
            codes = bs
        else:
            i = 0
            while i < n:
                b = bs[i]
                k = 1
                cp = b
                if b >= 0xC2 and b < 0xF5:
                    k = 2 if b < 0xE0 else 3 if b < 0xF0 else 4
                    cp = b & (0x1F if k == 2 else 0x0F if k == 3 else 0x07)
                    if i + k > n:
                        k = 1
                    else:
                        for j in range(1, k):
                            if bs[i + j] & 0xC0 != 0x80:
                                k = 1
                                break
                            cp = (cp << 6) | (bs[i + j] & 0x3F)
                    if k == 1:
                        cp = b  # (not UTF-8: the byte as it is)
                offs.append(i)
                codes.append(cp)
                i += k
            offs.append(n)
    _last = string
    _last_codes = codes
    _last_offs = offs
    _decoded += len(codes)
    return codes


def _to_char(offs: list[int], pos: int) -> int:
    # the code point at index pos of the str (or the next one, inside a character's bytes)
    if len(offs) == 0:
        return pos
    lo = 0
    hi = len(offs) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if offs[mid] < pos:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _to_char_floor(offs: list[int], pos: int) -> int:
    # the code point at index pos of the str, or the one whose bytes pos is inside
    i = _to_char(offs, pos)
    if len(offs) != 0 and offs[i] > pos:
        i -= 1
    return i


def _to_index(offs: list[int], i: int) -> int:
    # the index in the str of code point i
    if len(offs) == 0 or i < 0:
        return i
    return offs[i]


# ---- the parser (CPython's _parser.py)

SPECIAL_CHARS = ".\\[{()*+?^$|"
REPEAT_CHARS = "*+?{"
DIGITS = "0123456789"
OCTDIGITS = "01234567"
HEXDIGITS = "0123456789abcdefABCDEF"
ASCIILETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
WHITESPACE = " \t\n\r\v\f"

ESCAPES = {"\\a": 7, "\\b": 8, "\\f": 12, "\\n": 10, "\\r": 13, "\\t": 9, "\\v": 11, "\\\\": 92}
# \A \b \B \Z are (AT, code), the others (IN, [(CATEGORY, code)])
CATEGORIES = {"\\A": (AT, AT_BEGINNING_STRING), "\\b": (AT, AT_BOUNDARY), "\\B": (AT, AT_NON_BOUNDARY),
              "\\d": (IN, CATEGORY_DIGIT), "\\D": (IN, CATEGORY_NOT_DIGIT), "\\s": (IN, CATEGORY_SPACE),
              "\\S": (IN, CATEGORY_NOT_SPACE), "\\w": (IN, CATEGORY_WORD), "\\W": (IN, CATEGORY_NOT_WORD),
              "\\Z": (AT, AT_END_STRING)}
FLAGS = {"i": SRE_FLAG_IGNORECASE, "L": SRE_FLAG_LOCALE, "m": SRE_FLAG_MULTILINE, "s": SRE_FLAG_DOTALL,
         "x": SRE_FLAG_VERBOSE, "a": SRE_FLAG_ASCII, "u": SRE_FLAG_UNICODE}
TYPE_FLAGS = SRE_FLAG_ASCII | SRE_FLAG_LOCALE | SRE_FLAG_UNICODE
GLOBAL_FLAGS = SRE_FLAG_DEBUG
MAXWIDTH = 9223372036854775807  # (CPython's is 1 << 64: any width past MAXCODE and MAXREPEAT)
MAXCODE = 4294967295


class Item:
    # one (op, av) of a SubPattern: av's parts are fields, by op. LITERAL, NOT_LITERAL: arg, the
    # code point; AT, CATEGORY: arg, the code; GROUPREF: arg, the group; RANGE: arg and arg2, the
    # bounds; MIN_REPEAT, MAX_REPEAT, POSSESSIVE_REPEAT: arg and arg2 (min, max) and sub;
    # SUBPATTERN: arg (the group, -1 for none), arg2 and arg3 (add and del flags) and sub; ASSERT,
    # ASSERT_NOT: arg (1 ahead, -1 behind) and sub; ATOMIC_GROUP: sub; GROUPREF_EXISTS: arg, sub
    # and sub2 (or None); IN: items; BRANCH: subs; CHARSET, BIGCHARSET (the compiler's): codes
    def __init__(self, op: int, arg: int) -> None:
        self.op = op
        self.arg = arg
        self.arg2 = 0
        self.arg3 = 0
        self.sub: SubPattern | None = None
        self.sub2: SubPattern | None = None
        self.items: list[Item] = []
        self.subs: list[SubPattern] = []
        self.codes: list[int] = []


def _item(op: int, arg: int, sub: "SubPattern | None") -> Item:
    it = Item(op, arg)
    it.sub = sub
    return it


def _in(items: list[Item]) -> Item:
    it = Item(IN, 0)
    it.items = items
    return it


def _range(lo: int, hi: int) -> Item:
    it = Item(RANGE, lo)
    it.arg2 = hi
    return it


def _repeat(op: int, lo: int, hi: int, sub: "SubPattern") -> Item:
    it = Item(op, lo)
    it.arg2 = hi
    it.sub = sub
    return it


def _sub(p: Item) -> "SubPattern":
    s = p.sub
    if s is None:
        raise AssertionError("no subpattern")
    return s


def _same(a: Item, b: Item) -> bool:
    # a == b of CPython's (op, av) tuples: equal values, but the same SubPattern objects
    if a.op != b.op or a.arg != b.arg or a.arg2 != b.arg2 or a.arg3 != b.arg3 or a.sub is not b.sub or a.sub2 is not b.sub2:
        return False
    if len(a.items) != len(b.items) or len(a.subs) != len(b.subs):
        return False
    for i in range(len(a.items)):
        if not _same(a.items[i], b.items[i]):
            return False
    for i in range(len(a.subs)):
        if a.subs[i] is not b.subs[i]:
            return False
    return True


def _uniq(items: list[Item]) -> list[Item]:
    # the set's members once each, in order (list(dict.fromkeys(items)))
    seen: dict[tuple[int, int, int], bool] = {}
    out: list[Item] = []
    for it in items:
        key = (it.op, it.arg, it.arg2)
        if key not in seen:
            seen[key] = True
            out.append(it)
    return out


class State:
    # keeps track of state for parsing
    def __init__(self) -> None:
        self.flags = 0
        self.groupdict: dict[str, int] = {}
        self.gwidths: list[tuple[int, int]] = [(0, 0)]  # (group 0)
        self.gclosed: list[bool] = [False]
        self.lookbehindgroups = -1  # (-1: None)
        self.grouprefpos: dict[int, int] = {}

    def groups(self) -> int:
        return len(self.gclosed)

    def opengroup(self, name: str | None) -> int:
        gid = self.groups()
        self.gwidths.append((0, 0))
        self.gclosed.append(False)
        if self.groups() > MAXGROUPS:
            raise PatternError("too many groups")
        if name is not None:
            if name in self.groupdict:
                raise PatternError("redefinition of group name %s as group %d; was group %d" % (repr(name), gid, self.groupdict[name]))
            self.groupdict[name] = gid
        return gid

    def closegroup(self, gid: int, p: "SubPattern") -> None:
        self.gwidths[gid] = p.getwidth()
        self.gclosed[gid] = True

    def checkgroup(self, gid: int) -> bool:
        return gid < self.groups() and self.gclosed[gid]

    def checklookbehindgroup(self, gid: int, source: "Tokenizer") -> None:
        if self.lookbehindgroups >= 0:
            if not self.checkgroup(gid):
                raise source.error("cannot refer to an open group", 0)
            if gid >= self.lookbehindgroups:
                raise source.error("cannot refer to group defined in the same lookbehind subpattern", 0)


def _add(a: int, b: int) -> int:
    return MAXWIDTH if a >= MAXWIDTH - b else a + b


def _mul(a: int, b: int) -> int:
    return 0 if a == 0 or b == 0 else MAXWIDTH if a >= MAXWIDTH // b else a * b


class SubPattern:
    # a subpattern, in intermediate form
    def __init__(self, state: State) -> None:
        self.state = state
        self.data: list[Item] = []
        self.width = (-1, -1)

    def getwidth(self) -> tuple[int, int]:
        # determine the width (min, max) for this subpattern
        if self.width[0] >= 0:
            return self.width
        lo = 0
        hi = 0
        for it in self.data:
            op = it.op
            if op == BRANCH:
                i = MAXWIDTH
                j = 0
                for alt in it.subs:
                    w = alt.getwidth()
                    i = min(i, w[0])
                    j = max(j, w[1])
                lo = _add(lo, i)
                hi = _add(hi, j)
            elif op == ATOMIC_GROUP or op == SUBPATTERN:
                w = _sub(it).getwidth()
                lo = _add(lo, w[0])
                hi = _add(hi, w[1])
            elif op == MIN_REPEAT or op == MAX_REPEAT or op == POSSESSIVE_REPEAT:
                w = _sub(it).getwidth()
                lo = _add(lo, _mul(w[0], it.arg))
                if it.arg2 == MAXREPEAT and w[1] != 0:
                    hi = MAXWIDTH
                else:
                    hi = _add(hi, _mul(w[1], it.arg2))
            elif op == ANY or op == RANGE or op == IN or op == LITERAL or op == NOT_LITERAL or op == CATEGORY:
                lo = _add(lo, 1)
                hi = _add(hi, 1)
            elif op == GROUPREF:
                w = self.state.gwidths[it.arg]
                lo = _add(lo, w[0])
                hi = _add(hi, w[1])
            elif op == GROUPREF_EXISTS:
                w = _sub(it).getwidth()
                i = w[0]
                j = w[1]
                no = it.sub2
                if no is not None:
                    w2 = no.getwidth()
                    i = min(i, w2[0])
                    j = max(j, w2[1])
                else:
                    i = 0
                lo = _add(lo, i)
                hi = _add(hi, j)
            elif op == SUCCESS:
                break
        self.width = (min(lo, MAXWIDTH), min(hi, MAXWIDTH))
        return self.width


class Tokenizer:
    def __init__(self, string: str) -> None:
        self.string = string
        self.index = 0
        self.next: str | None = None
        self.advance()

    def advance(self) -> None:
        index = self.index
        if index >= len(self.string):
            self.next = None
            return
        char = _charat(self.string, index)
        index += len(char)
        if char == "\\":
            if index >= len(self.string):
                raise PatternError("bad escape (end of pattern)", self.string, len(self.string) - 1)
            c2 = _charat(self.string, index)
            char += c2
            index += len(c2)
        self.index = index
        self.next = char

    def match(self, char: str) -> bool:
        if char == self.next:
            self.advance()
            return True
        return False

    def get(self) -> str | None:
        this = self.next
        self.advance()
        return this

    def getwhile(self, n: int, charset: str) -> str:
        result = ""
        for _ in range(n):
            c = self.next
            if c is None or c not in charset:
                break
            result += c
            self.advance()
        return result

    def getuntil(self, terminator: str, name: str) -> str:
        result = ""
        while True:
            c = self.next
            self.advance()
            if c is None:
                if result == "":
                    raise self.error("missing " + name, 0)
                raise self.error("missing %s, unterminated name" % terminator, len(result))
            if c == terminator:
                if result == "":
                    raise self.error("missing " + name, 1)
                break
            result += c
        return result

    def tell(self) -> int:
        n = self.next
        return self.index - (len(n) if n is not None else 0)

    def seek(self, index: int) -> None:
        self.index = index
        self.advance()

    def error(self, msg: str, offset: int) -> PatternError:
        return PatternError(msg, self.string, self.tell() - offset)

    def checkgroupname(self, name: str, offset: int) -> None:
        if not _isidentifier(name):
            raise self.error("bad character in group name %s" % repr(name), len(name) + offset)


def _isidentifier(name: str) -> bool:
    # str.isidentifier()
    codes = _codes_of(name)
    if len(codes) == 0:
        return False
    for i in range(len(codes)):
        if not (_sre.uni_isidstart(codes[i]) if i == 0 else _sre.uni_isidcontinue(codes[i])):
            return False
    return True


def _codes_of(s: str) -> list[int]:
    # s's code points, without the cache of the strings matched
    out: list[int] = []
    i = 0
    while i < len(s):
        c = _charat(s, i)
        out.append(ord(c))
        i += len(c)
    return out


def _int_digits(s: str) -> str:
    # ASCII digits s as int() reads them, without their leading zeros (which a 64-bit int could not
    # parse past 19 digits, as CPython's int does)
    d = s.lstrip("0")
    return d if d != "" else "0"


def _isdecimal(s: str) -> bool:
    # s.isdecimal() and s.isascii()
    if s == "":
        return False
    for c in s:
        if c < "0" or c > "9":
            return False
    return True


def _class_escape(source: Tokenizer, escape: str) -> Item:
    # handle escape code inside character class
    if escape in ESCAPES:
        return Item(LITERAL, ESCAPES[escape])
    if escape in CATEGORIES and CATEGORIES[escape][0] == IN:
        return _in([Item(CATEGORY, CATEGORIES[escape][1])])
    c = escape[1:2]
    if c == "x":
        # hexadecimal escape (exactly two digits)
        escape += source.getwhile(2, HEXDIGITS)
        if len(escape) != 4:
            raise source.error("incomplete escape %s" % escape, len(escape))
        return Item(LITERAL, int(escape[2:], 16))
    elif c == "u":
        # unicode escape (exactly four digits)
        escape += source.getwhile(4, HEXDIGITS)
        if len(escape) != 6:
            raise source.error("incomplete escape %s" % escape, len(escape))
        return Item(LITERAL, int(escape[2:], 16))
    elif c == "U":
        # unicode escape (exactly eight digits)
        escape += source.getwhile(8, HEXDIGITS)
        if len(escape) != 10:
            raise source.error("incomplete escape %s" % escape, len(escape))
        cp = int(escape[2:], 16)
        if cp > 0x10FFFF:
            raise source.error("bad escape %s" % escape, len(escape))
        return Item(LITERAL, cp)
    elif c == "N":
        # named unicode escape e.g. \N{EM DASH} (CPython looks the name up in unicodedata)
        if not source.match("{"):
            raise source.error("missing {", 0)
        charname = source.getuntil("}", "character name")
        # (Pystachy has no table of the names: rejected as a pattern error, at compile())
        raise source.error("\\N{%s} is not supported: Pystachy's re has no table of the Unicode character names" % charname, len(charname) + len("\\N{}"))
    elif c != "" and c in OCTDIGITS:
        # octal escape (up to three digits)
        escape += source.getwhile(2, OCTDIGITS)
        cp = int(escape[1:], 8)
        if cp > 0o377:
            raise source.error("octal escape value %s outside of range 0-0o377" % escape, len(escape))
        return Item(LITERAL, cp)
    elif c != "" and c in DIGITS:
        raise source.error("bad escape %s" % escape, len(escape))
    if len(_codes_of(escape)) == 2:
        if c in ASCIILETTERS:
            raise source.error("bad escape %s" % escape, len(escape))
        return Item(LITERAL, ord(escape[1:]))
    raise source.error("bad escape %s" % escape, len(escape))


def _escape(source: Tokenizer, escape: str, state: State) -> Item:
    # handle escape code in expression
    if escape in CATEGORIES:
        cat = CATEGORIES[escape]
        return Item(AT, cat[1]) if cat[0] == AT else _in([Item(CATEGORY, cat[1])])
    if escape in ESCAPES:
        return Item(LITERAL, ESCAPES[escape])
    c = escape[1:2]
    if c == "x":
        # hexadecimal escape
        escape += source.getwhile(2, HEXDIGITS)
        if len(escape) != 4:
            raise source.error("incomplete escape %s" % escape, len(escape))
        return Item(LITERAL, int(escape[2:], 16))
    elif c == "u":
        escape += source.getwhile(4, HEXDIGITS)
        if len(escape) != 6:
            raise source.error("incomplete escape %s" % escape, len(escape))
        return Item(LITERAL, int(escape[2:], 16))
    elif c == "U":
        escape += source.getwhile(8, HEXDIGITS)
        if len(escape) != 10:
            raise source.error("incomplete escape %s" % escape, len(escape))
        cp = int(escape[2:], 16)
        if cp > 0x10FFFF:
            raise source.error("bad escape %s" % escape, len(escape))
        return Item(LITERAL, cp)
    elif c == "N":
        if not source.match("{"):
            raise source.error("missing {", 0)
        charname = source.getuntil("}", "character name")
        # (Pystachy has no table of the names: rejected as a pattern error, at compile())
        raise source.error("\\N{%s} is not supported: Pystachy's re has no table of the Unicode character names" % charname, len(charname) + len("\\N{}"))
    elif c == "0":
        # octal escape
        escape += source.getwhile(2, OCTDIGITS)
        return Item(LITERAL, int(escape[1:], 8))
    elif c != "" and c in DIGITS:
        # octal escape *or* decimal group reference (sigh)
        nx = source.next
        if nx is not None and nx in DIGITS:
            escape += nx
            source.advance()
            nx = source.next
            if escape[1] in OCTDIGITS and escape[2] in OCTDIGITS and nx is not None and nx in OCTDIGITS:
                # got three octal digits; this is an octal escape
                escape += nx
                source.advance()
                cp = int(escape[1:], 8)
                if cp > 0o377:
                    raise source.error("octal escape value %s outside of range 0-0o377" % escape, len(escape))
                return Item(LITERAL, cp)
        # not an octal escape, so this is a group reference
        group = int(escape[1:])
        if group < state.groups():
            if not state.checkgroup(group):
                raise source.error("cannot refer to an open group", len(escape))
            state.checklookbehindgroup(group, source)
            return Item(GROUPREF, group)
        raise source.error("invalid group reference %d" % group, len(escape) - 1)
    if len(_codes_of(escape)) == 2:
        if c in ASCIILETTERS:
            raise source.error("bad escape %s" % escape, len(escape))
        return Item(LITERAL, ord(escape[1:]))
    raise source.error("bad escape %s" % escape, len(escape))


def _parse_sub(source: Tokenizer, state: State, verbose: bool, nested: int) -> SubPattern:
    # parse an alternation: a|b|c
    items: list[SubPattern] = []
    while True:
        items.append(_parse(source, state, verbose, nested + 1, nested == 0 and len(items) == 0))
        if not source.match("|"):
            break
        if nested == 0:
            verbose = state.flags & SRE_FLAG_VERBOSE != 0
    if len(items) == 1:
        return items[0]
    subpattern = SubPattern(state)
    # check if all items share a common prefix
    while True:
        prefix: Item | None = None
        common = True
        for item in items:
            if len(item.data) == 0:
                common = False
                break
            if prefix is None:
                prefix = item.data[0]
            elif not _same(item.data[0], prefix):
                common = False
                break
        if not common or prefix is None:
            break
        # all subitems start with a common "prefix": move it out of the branch
        for item in items:
            item.data.pop(0)
        subpattern.data.append(prefix)
    # check if the branch can be replaced by a character set
    cset: list[Item] = []
    asset = True
    for item in items:
        if len(item.data) != 1:
            asset = False
            break
        it = item.data[0]
        if it.op == LITERAL:
            cset.append(it)
        elif it.op == IN and it.items[0].op != NEGATE:
            for x in it.items:
                cset.append(x)
        else:
            asset = False
            break
    if asset:
        # (the compiler may optimize this even more)
        subpattern.data.append(_in(_uniq(cset)))
        return subpattern
    br = Item(BRANCH, 0)
    br.subs = items
    subpattern.data.append(br)
    return subpattern


def _parse(source: Tokenizer, state: State, verbose: bool, nested: int, first: bool) -> SubPattern:
    # parse a simple pattern
    subpattern = SubPattern(state)
    while True:
        this = source.next
        if this is None:
            break  # end of pattern
        if this == "|" or this == ")":
            break  # end of subpattern
        source.advance()
        if verbose:
            # skip whitespace and comments
            if this in WHITESPACE:
                continue
            if this == "#":
                while True:
                    c = source.get()
                    if c is None or c == "\n":
                        break
                continue
        if this[0] == "\\":
            subpattern.data.append(_escape(source, this, state))
        elif this not in SPECIAL_CHARS:
            subpattern.data.append(Item(LITERAL, ord(this)))
        elif this == "[":
            here = source.tell() - 1
            # character set
            cset: list[Item] = []
            negate = source.match("^")
            # check remaining characters
            while True:
                c = source.get()
                if c is None:
                    raise source.error("unterminated character set", source.tell() - here)
                if c == "]" and len(cset) > 0:
                    break
                code1: Item
                if c[0] == "\\":
                    code1 = _class_escape(source, c)
                else:
                    code1 = Item(LITERAL, ord(c))
                if source.match("-"):
                    # potential range
                    that = source.get()
                    if that is None:
                        raise source.error("unterminated character set", source.tell() - here)
                    if that == "]":
                        if code1.op == IN:
                            code1 = code1.items[0]
                        cset.append(code1)
                        cset.append(Item(LITERAL, 45))
                        break
                    code2: Item
                    if that[0] == "\\":
                        code2 = _class_escape(source, that)
                    else:
                        code2 = Item(LITERAL, ord(that))
                    if code1.op != LITERAL or code2.op != LITERAL:
                        raise source.error("bad character range %s-%s" % (c, that), len(c) + 1 + len(that))
                    lo = code1.arg
                    hi = code2.arg
                    if hi < lo:
                        raise source.error("bad character range %s-%s" % (c, that), len(c) + 1 + len(that))
                    cset.append(_range(lo, hi))
                else:
                    if code1.op == IN:
                        code1 = code1.items[0]
                    cset.append(code1)
            cset = _uniq(cset)
            if len(cset) == 1 and cset[0].op == LITERAL:
                # optimization
                if negate:
                    subpattern.data.append(Item(NOT_LITERAL, cset[0].arg))
                else:
                    subpattern.data.append(cset[0])
            else:
                if negate:
                    cset.insert(0, Item(NEGATE, 0))
                # (charmap optimization can't be added here because global flags still are not known)
                subpattern.data.append(_in(cset))
        elif this in REPEAT_CHARS:
            # repeat previous item
            here = source.tell()
            lo = 0
            hi = 0
            if this == "?":
                lo = 0
                hi = 1
            elif this == "*":
                lo = 0
                hi = MAXREPEAT
            elif this == "+":
                lo = 1
                hi = MAXREPEAT
            else:
                if source.next == "}":
                    subpattern.data.append(Item(LITERAL, ord(this)))
                    continue
                lo = 0
                hi = MAXREPEAT
                los = ""
                his = ""
                nx = source.next
                while nx is not None and nx in DIGITS:
                    los += nx
                    source.advance()
                    nx = source.next
                if source.match(","):
                    nx = source.next
                    while nx is not None and nx in DIGITS:
                        his += nx
                        source.advance()
                        nx = source.next
                else:
                    his = los
                if not source.match("}"):
                    subpattern.data.append(Item(LITERAL, ord(this)))
                    source.seek(here)
                    continue
                if los != "":
                    los = _int_digits(los)
                    if len(los) > 10 or int(los) >= MAXREPEAT:
                        raise OverflowError("the repetition number is too large")
                    lo = int(los)
                if his != "":
                    his = _int_digits(his)
                    if len(his) > 10 or int(his) >= MAXREPEAT:
                        raise OverflowError("the repetition number is too large")
                    hi = int(his)
                    if hi < lo:
                        raise source.error("min repeat greater than max repeat", source.tell() - here)
            # figure out which item to repeat
            if len(subpattern.data) == 0 or subpattern.data[-1].op == AT:
                raise source.error("nothing to repeat", source.tell() - here + len(this))
            last = subpattern.data[-1]
            if last.op == MIN_REPEAT or last.op == MAX_REPEAT or last.op == POSSESSIVE_REPEAT:
                raise source.error("multiple repeat", source.tell() - here + len(this))
            item = SubPattern(state)
            item.data.append(last)
            if last.op == SUBPATTERN and last.arg < 0 and last.arg2 == 0 and last.arg3 == 0:
                item = _sub(last)
            if source.match("?"):
                # Non-Greedy Match
                subpattern.data[-1] = _repeat(MIN_REPEAT, lo, hi, item)
            elif source.match("+"):
                # Possessive Match (Always Greedy)
                subpattern.data[-1] = _repeat(POSSESSIVE_REPEAT, lo, hi, item)
            else:
                # Greedy Match
                subpattern.data[-1] = _repeat(MAX_REPEAT, lo, hi, item)
        elif this == ".":
            subpattern.data.append(Item(ANY, 0))
        elif this == "(":
            start = source.tell() - 1
            capture = True
            atomic = False
            name: str | None = None
            add_flags = 0
            del_flags = 0
            if source.match("?"):
                # options
                char = source.get()
                if char is None:
                    raise source.error("unexpected end of pattern", 0)
                if char == "P":
                    # python extensions
                    if source.match("<"):
                        # named group: skip forward to end of name
                        gname = source.getuntil(">", "group name")
                        source.checkgroupname(gname, 1)
                        name = gname
                    elif source.match("="):
                        # named backreference
                        gname = source.getuntil(")", "group name")
                        source.checkgroupname(gname, 1)
                        if gname not in state.groupdict:
                            raise source.error("unknown group name %s" % repr(gname), len(gname) + 1)
                        gid = state.groupdict[gname]
                        if not state.checkgroup(gid):
                            raise source.error("cannot refer to an open group", len(gname) + 1)
                        state.checklookbehindgroup(gid, source)
                        subpattern.data.append(Item(GROUPREF, gid))
                        continue
                    else:
                        c = source.get()
                        if c is None:
                            raise source.error("unexpected end of pattern", 0)
                        raise source.error("unknown extension ?P" + c, len(c) + 2)
                elif char == ":":
                    # non-capturing group
                    capture = False
                elif char == "#":
                    # comment
                    while True:
                        if source.next is None:
                            raise source.error("missing ), unterminated comment", source.tell() - start)
                        if source.get() == ")":
                            break
                    continue
                elif char == "=" or char == "!" or char == "<":
                    # lookahead assertions
                    dir = 1
                    lookbehindgroups = -1
                    if char == "<":
                        c = source.get()
                        if c is None:
                            raise source.error("unexpected end of pattern", 0)
                        if c != "=" and c != "!":
                            raise source.error("unknown extension ?<" + c, len(c) + 2)
                        char = c
                        dir = -1  # lookbehind
                        lookbehindgroups = state.lookbehindgroups
                        if lookbehindgroups < 0:
                            state.lookbehindgroups = state.groups()
                    p = _parse_sub(source, state, verbose, nested + 1)
                    if dir < 0:
                        if lookbehindgroups < 0:
                            state.lookbehindgroups = -1
                    if not source.match(")"):
                        raise source.error("missing ), unterminated subpattern", source.tell() - start)
                    if char == "=":
                        subpattern.data.append(_item(ASSERT, dir, p))
                    elif len(p.data) > 0:
                        subpattern.data.append(_item(ASSERT_NOT, dir, p))
                    else:
                        subpattern.data.append(Item(FAILURE, 0))
                    continue
                elif char == "(":
                    # conditional backreference group
                    condname = source.getuntil(")", "group name")
                    condgroup = 0
                    if not _isdecimal(condname):
                        source.checkgroupname(condname, 1)
                        if condname not in state.groupdict:
                            raise source.error("unknown group name %s" % repr(condname), len(condname) + 1)
                        condgroup = state.groupdict[condname]
                    else:
                        digits = _int_digits(condname)
                        if len(digits) > 18:
                            raise source.error("invalid group reference %s" % digits, len(condname) + 1)
                        condgroup = int(digits)
                        if condgroup == 0:
                            raise source.error("bad group number", len(condname) + 1)
                        if condgroup >= MAXGROUPS:
                            raise source.error("invalid group reference %d" % condgroup, len(condname) + 1)
                        if condgroup not in state.grouprefpos:
                            state.grouprefpos[condgroup] = source.tell() - len(condname) - 1
                    state.checklookbehindgroup(condgroup, source)
                    item_yes = _parse(source, state, verbose, nested + 1, False)
                    item_no: SubPattern | None = None
                    if source.match("|"):
                        item_no = _parse(source, state, verbose, nested + 1, False)
                        if source.next == "|":
                            raise source.error("conditional backref with more than two branches", 0)
                    if not source.match(")"):
                        raise source.error("missing ), unterminated subpattern", source.tell() - start)
                    it = _item(GROUPREF_EXISTS, condgroup, item_yes)
                    it.sub2 = item_no
                    subpattern.data.append(it)
                    continue
                elif char == ">":
                    # non-capturing, atomic group
                    capture = False
                    atomic = True
                elif char in FLAGS or char == "-":
                    # flags
                    fl = _parse_flags(source, state, char)
                    if fl[0] < 0:  # global flags
                        if not first or len(subpattern.data) > 0:
                            raise source.error("global flags not at the start of the expression", source.tell() - start)
                        verbose = state.flags & SRE_FLAG_VERBOSE != 0
                        continue
                    add_flags = fl[0]
                    del_flags = fl[1]
                    capture = False
                else:
                    raise source.error("unknown extension ?" + char, len(char) + 1)
            # parse group contents
            group = -1
            if capture:
                try:
                    group = state.opengroup(name)
                except PatternError as err:
                    raise source.error(err.msg, len(name) + 1 if name is not None else 1) from None
            sub_verbose = (verbose or add_flags & SRE_FLAG_VERBOSE != 0) and del_flags & SRE_FLAG_VERBOSE == 0
            p = _parse_sub(source, state, sub_verbose, nested + 1)
            if not source.match(")"):
                raise source.error("missing ), unterminated subpattern", source.tell() - start)
            if group >= 0:
                state.closegroup(group, p)
            if atomic:
                subpattern.data.append(_item(ATOMIC_GROUP, 0, p))
            else:
                it = _item(SUBPATTERN, group, p)
                it.arg2 = add_flags
                it.arg3 = del_flags
                subpattern.data.append(it)
        elif this == "^":
            subpattern.data.append(Item(AT, AT_BEGINNING))
        elif this == "$":
            subpattern.data.append(Item(AT, AT_END))
        else:
            raise AssertionError("unsupported special character %s" % repr(this))
    # unpack non-capturing groups
    i = len(subpattern.data) - 1
    while i >= 0:
        it = subpattern.data[i]
        if it.op == SUBPATTERN and it.arg < 0 and it.arg2 == 0 and it.arg3 == 0:
            inner = _sub(it).data
            data: list[Item] = []
            for j in range(i):
                data.append(subpattern.data[j])
            for x in inner:
                data.append(x)
            for j in range(i + 1, len(subpattern.data)):
                data.append(subpattern.data[j])
            subpattern.data = data
        i -= 1
    return subpattern


def _parse_flags(source: Tokenizer, state: State, char: str) -> tuple[int, int]:
    # (add_flags, del_flags) of a group's flags; (-1, 0) where they are global
    add_flags = 0
    del_flags = 0
    if char != "-":
        while True:
            flag = FLAGS[char]
            if char == "L":
                raise source.error("bad inline flags: cannot use 'L' flag with a str pattern", 0)
            add_flags |= flag
            if flag & TYPE_FLAGS != 0 and add_flags & TYPE_FLAGS != flag:
                raise source.error("bad inline flags: flags 'a', 'u' and 'L' are incompatible", 0)
            nx = source.get()
            if nx is None:
                raise source.error("missing -, : or )", 0)
            char = nx
            if char == ")" or char == "-" or char == ":":
                break
            if char not in FLAGS:
                msg = "unknown flag" if _isalpha(char) else "missing -, : or )"
                raise source.error(msg, len(char))
    if char == ")":
        state.flags |= add_flags
        return (-1, 0)
    if add_flags & GLOBAL_FLAGS != 0:
        raise source.error("bad inline flags: cannot turn on global flag", 1)
    if char == "-":
        nx = source.get()
        if nx is None:
            raise source.error("missing flag", 0)
        char = nx
        if char not in FLAGS:
            msg = "unknown flag" if _isalpha(char) else "missing flag"
            raise source.error(msg, len(char))
        while True:
            flag = FLAGS[char]
            if flag & TYPE_FLAGS != 0:
                raise source.error("bad inline flags: cannot turn off flags 'a', 'u' and 'L'", 0)
            del_flags |= flag
            nx = source.get()
            if nx is None:
                raise source.error("missing :", 0)
            char = nx
            if char == ":":
                break
            if char not in FLAGS:
                msg = "unknown flag" if _isalpha(char) else "missing :"
                raise source.error(msg, len(char))
    if del_flags & GLOBAL_FLAGS != 0:
        raise source.error("bad inline flags: cannot turn off global flag", 1)
    if add_flags & del_flags != 0:
        raise source.error("bad inline flags: flag turned on and off", 1)
    return (add_flags, del_flags)


def _isalpha(c: str) -> bool:
    # str.isalpha() of a token (False for an escape's two characters). Past ASCII, a character an
    # identifier may begin with stands for a letter: the two differ for 263 rare code points,
    # where the message of a bad inline flag differs from CPython's
    codes = _codes_of(c)
    if len(codes) != 1:
        return False
    cp = codes[0]
    if cp < 128:
        return (65 <= cp and cp <= 90) or (97 <= cp and cp <= 122)
    return _sre.uni_isidstart(cp)


def fix_flags(src: str, flags: int) -> int:
    # check and fix flags for a str pattern
    if flags & SRE_FLAG_LOCALE != 0:
        raise ValueError("cannot use LOCALE flag with a str pattern")
    if flags & SRE_FLAG_ASCII == 0:
        flags |= SRE_FLAG_UNICODE
    elif flags & SRE_FLAG_UNICODE != 0:
        raise ValueError("ASCII and UNICODE flags are incompatible")
    return flags


def parse(string: str, flags: int) -> SubPattern:
    # parse 're' pattern into a SubPattern of Items
    source = Tokenizer(string)
    state = State()
    state.flags = flags
    p = _parse_sub(source, state, flags & SRE_FLAG_VERBOSE != 0, 0)
    p.state.flags = fix_flags(string, p.state.flags)
    if source.next is not None:
        raise source.error("unbalanced parenthesis", 0)
    for g in p.state.grouprefpos:
        if g >= p.state.groups():
            raise PatternError("invalid group reference %d" % g, string, p.state.grouprefpos[g])
    return p


class Template:
    # a replacement string, compiled (parse_template, _sre.template): literals[0], then each
    # group's text and the literal after it
    def __init__(self) -> None:
        self.literals: list[str] = []
        self.groups: list[int] = []

    def expand(self, m: "Match") -> str:
        # expand_template: the literals, with each group's text (none for a group that did not match)
        out = [self.literals[0]]
        for i in range(len(self.groups)):
            index = self.groups[i]
            if index > m.re.groups:
                raise IndexError("no such group")
            g = m._get(index)
            if g is not None:
                out.append(g)
            out.append(self.literals[i + 1])
        return "".join(out)


def parse_template(source: str, pattern: "Pattern") -> Template:
    # parse 're' replacement string into list of literals and group references
    s = Tokenizer(source)
    result = Template()
    literal: list[str] = []
    while True:
        this = s.get()
        if this is None:
            break  # end of replacement string
        if this[0] == "\\":
            # group
            c = this[1:]
            if c == "g":
                if not s.match("<"):
                    raise s.error("missing <", 0)
                name = s.getuntil(">", "group name")
                index = 0
                if not _isdecimal(name):
                    s.checkgroupname(name, 1)
                    if name not in pattern.groupindex:
                        raise IndexError("unknown group name %s" % repr(name))
                    index = pattern.groupindex[name]
                else:
                    digits = _int_digits(name)
                    if len(digits) > 18:
                        raise s.error("invalid group reference %s" % digits, len(name) + 1)
                    index = int(digits)
                    if index >= MAXGROUPS:
                        raise s.error("invalid group reference %d" % index, len(name) + 1)
                if index > pattern.groups:
                    raise s.error("invalid group reference %d" % index, len(name) + 1)
                result.literals.append("".join(literal))
                literal = []
                result.groups.append(index)
            elif c == "0":
                nx = s.next
                if nx is not None and nx in OCTDIGITS:
                    this += nx
                    s.advance()
                    nx = s.next
                    if nx is not None and nx in OCTDIGITS:
                        this += nx
                        s.advance()
                literal.append(_chr(int(this[1:], 8) & 0xFF))
            elif c in DIGITS:
                isoctal = False
                nx = s.next
                if nx is not None and nx in DIGITS:
                    this += nx
                    s.advance()
                    nx = s.next
                    if c in OCTDIGITS and this[2] in OCTDIGITS and nx is not None and nx in OCTDIGITS:
                        this += nx
                        s.advance()
                        isoctal = True
                        cp = int(this[1:], 8)
                        if cp > 0o377:
                            raise s.error("octal escape value %s outside of range 0-0o377" % this, len(this))
                        literal.append(_chr(cp))
                if not isoctal:
                    index = int(this[1:])
                    if index > pattern.groups:
                        raise s.error("invalid group reference %d" % index, len(this) - 1)
                    result.literals.append("".join(literal))
                    literal = []
                    result.groups.append(index)
            else:
                if this in ESCAPES:
                    this = _chr(ESCAPES[this])
                elif c in ASCIILETTERS:
                    raise s.error("bad escape %s" % this, len(this))
                literal.append(this)
        else:
            literal.append(this)
    result.literals.append("".join(literal))
    return result


# ---- the compiler (CPython's _compiler.py)

_EXTRA: dict[int, list[int]] = {}  # (re._casefix._EXTRA_CASES, decoded when a pattern first ignores case)


def _fixes() -> dict[int, list[int]]:
    if len(_EXTRA) == 0:
        from . import _unicode

        for w in _unicode.EXTRA_CASES.split():
            colon = w.find(":")
            _EXTRA[int(w[:colon], 36)] = [int(x, 36) for x in w[colon + 1 :].split(",")]
    return _EXTRA


class _Case:
    # how a pattern ignores case, if it does: iscased and tolower of _sre, and the extra cases
    def __init__(self, flags: int) -> None:
        self.on: bool = flags & SRE_FLAG_IGNORECASE != 0 and flags & SRE_FLAG_LOCALE == 0
        self.uni: bool = flags & SRE_FLAG_UNICODE != 0

    def iscased(self, ch: int) -> bool:
        return _sre.unicode_iscased(ch) if self.uni else _sre.ascii_iscased(ch)

    def tolower(self, ch: int) -> int:
        return _sre.lower_unicode(ch) if self.uni else _sre.lower_ascii(ch)

    def fixes(self, ch: int) -> list[int]:
        # the other characters that ignore case to the same as lowercase ch (unicode only)
        if not self.uni:
            return []
        f = _fixes()
        return f[ch] if ch in f else []


def _combine_flags(flags: int, add_flags: int, del_flags: int) -> int:
    if add_flags & TYPE_FLAGS != 0:
        flags &= ~TYPE_FLAGS
    return (flags | add_flags) & ~del_flags


def _compile_code(code: list[int], pattern: list[Item], flags: int) -> None:
    # internal: compile a (sub)pattern
    case = _Case(flags)
    for it in pattern:
        op = it.op
        if op == LITERAL or op == NOT_LITERAL:
            av = it.arg
            if flags & SRE_FLAG_IGNORECASE == 0:
                code.append(op)
                code.append(av)
            elif flags & SRE_FLAG_LOCALE != 0:
                code.append(LITERAL_LOC_IGNORE if op == LITERAL else NOT_LITERAL_LOC_IGNORE)
                code.append(av)
            elif not case.iscased(av):
                code.append(op)
                code.append(av)
            else:
                lo = case.tolower(av)
                fx = case.fixes(lo)
                if not case.uni:  # ascii
                    code.append(LITERAL_IGNORE if op == LITERAL else NOT_LITERAL_IGNORE)
                    code.append(lo)
                elif len(fx) == 0:
                    code.append(LITERAL_UNI_IGNORE if op == LITERAL else NOT_LITERAL_UNI_IGNORE)
                    code.append(lo)
                else:
                    code.append(IN_UNI_IGNORE)
                    skip = len(code)
                    code.append(0)
                    if op == NOT_LITERAL:
                        code.append(NEGATE)
                    code.append(LITERAL)
                    code.append(lo)
                    for k in fx:
                        code.append(LITERAL)
                        code.append(k)
                    code.append(FAILURE)
                    code[skip] = len(code) - skip
        elif op == IN:
            opt = _optimize_charset(it.items, case)
            if flags & SRE_FLAG_IGNORECASE != 0 and flags & SRE_FLAG_LOCALE != 0:
                code.append(IN_LOC_IGNORE)
            elif not opt.hascased:
                code.append(IN)
            elif not case.uni:  # ascii
                code.append(IN_IGNORE)
            else:
                code.append(IN_UNI_IGNORE)
            skip = len(code)
            code.append(0)
            _compile_charset(opt.items, flags, code)
            code[skip] = len(code) - skip
        elif op == ANY:
            code.append(ANY_ALL if flags & SRE_FLAG_DOTALL != 0 else ANY)
        elif op == MIN_REPEAT or op == MAX_REPEAT or op == POSSESSIVE_REPEAT:
            sub = _sub(it)
            if _simple(sub):
                code.append(MIN_REPEAT_ONE if op == MIN_REPEAT else REPEAT_ONE if op == MAX_REPEAT else POSSESSIVE_REPEAT_ONE)
                skip = len(code)
                code.append(0)
                code.append(it.arg)
                code.append(it.arg2)
                _compile_code(code, sub.data, flags)
                code.append(SUCCESS)
                code[skip] = len(code) - skip
            else:
                code.append(POSSESSIVE_REPEAT if op == POSSESSIVE_REPEAT else REPEAT)
                skip = len(code)
                code.append(0)
                code.append(it.arg)
                code.append(it.arg2)
                _compile_code(code, sub.data, flags)
                code[skip] = len(code) - skip
                code.append(MIN_UNTIL if op == MIN_REPEAT else MAX_UNTIL if op == MAX_REPEAT else SUCCESS)
        elif op == SUBPATTERN:
            group = it.arg
            if group > 0:
                code.append(MARK)
                code.append((group - 1) * 2)
            _compile_code(code, _sub(it).data, _combine_flags(flags, it.arg2, it.arg3))
            if group > 0:
                code.append(MARK)
                code.append((group - 1) * 2 + 1)
        elif op == ATOMIC_GROUP:
            # an ATOMIC_GROUP op, its pattern and a SUCCESS that ends the repeats in it
            code.append(ATOMIC_GROUP)
            skip = len(code)
            code.append(0)
            _compile_code(code, _sub(it).data, flags)
            code.append(SUCCESS)
            code[skip] = len(code) - skip
        elif op == SUCCESS or op == FAILURE:
            code.append(op)
        elif op == ASSERT or op == ASSERT_NOT:
            code.append(op)
            skip = len(code)
            code.append(0)
            sub = _sub(it)
            if it.arg >= 0:
                code.append(0)  # look ahead
            else:
                w = sub.getwidth()
                if w[0] > MAXCODE:
                    raise PatternError("looks too much behind")
                if w[0] != w[1]:
                    raise PatternError("look-behind requires fixed-width pattern")
                code.append(w[0])  # look behind
            _compile_code(code, sub.data, flags)
            code.append(SUCCESS)
            code[skip] = len(code) - skip
        elif op == AT:
            code.append(op)
            av = it.arg
            if flags & SRE_FLAG_MULTILINE != 0:
                av = AT_BEGINNING_LINE if av == AT_BEGINNING else AT_END_LINE if av == AT_END else av
            if flags & SRE_FLAG_LOCALE != 0:
                av = AT_LOC_BOUNDARY if av == AT_BOUNDARY else AT_LOC_NON_BOUNDARY if av == AT_NON_BOUNDARY else av
            elif flags & SRE_FLAG_UNICODE != 0:
                av = AT_UNI_BOUNDARY if av == AT_BOUNDARY else AT_UNI_NON_BOUNDARY if av == AT_NON_BOUNDARY else av
            code.append(av)
        elif op == BRANCH:
            code.append(op)
            tails: list[int] = []
            for alt in it.subs:
                skip = len(code)
                code.append(0)
                _compile_code(code, alt.data, flags)
                code.append(JUMP)
                tails.append(len(code))
                code.append(0)
                code[skip] = len(code) - skip
            code.append(FAILURE)  # end of branch
            for tail in tails:
                code[tail] = len(code) - tail
        elif op == CATEGORY:
            code.append(op)
            code.append(_category(it.arg, flags))
        elif op == GROUPREF:
            if flags & SRE_FLAG_IGNORECASE == 0:
                code.append(op)
            elif flags & SRE_FLAG_LOCALE != 0:
                code.append(GROUPREF_LOC_IGNORE)
            elif not case.uni:  # ascii
                code.append(GROUPREF_IGNORE)
            else:
                code.append(GROUPREF_UNI_IGNORE)
            code.append(it.arg - 1)
        elif op == GROUPREF_EXISTS:
            code.append(op)
            code.append(it.arg - 1)
            skipyes = len(code)
            code.append(0)
            _compile_code(code, _sub(it).data, flags)
            no = it.sub2
            if no is not None and len(no.data) > 0:
                code.append(JUMP)
                skipno = len(code)
                code.append(0)
                code[skipyes] = len(code) - skipyes + 1
                _compile_code(code, no.data, flags)
                code[skipno] = len(code) - skipno
            else:
                code[skipyes] = len(code) - skipyes + 1
        else:
            raise PatternError("internal: unsupported operand type %s" % OPNAMES[op])


def _category(av: int, flags: int) -> int:
    # CH_LOCALE and CH_UNICODE
    if flags & SRE_FLAG_LOCALE != 0:
        return CATEGORY_LOC_WORD if av == CATEGORY_WORD else CATEGORY_LOC_NOT_WORD if av == CATEGORY_NOT_WORD else av
    if flags & SRE_FLAG_UNICODE != 0:
        return av + CATEGORY_UNI_DIGIT if av <= CATEGORY_NOT_LINEBREAK else av
    return av


def _compile_charset(charset: list[Item], flags: int, code: list[int]) -> None:
    # compile charset subprogram
    for it in charset:
        op = it.op
        code.append(op)
        if op == NEGATE:
            pass
        elif op == LITERAL:
            code.append(it.arg)
        elif op == RANGE or op == RANGE_UNI_IGNORE:
            code.append(it.arg)
            code.append(it.arg2)
        elif op == CHARSET or op == BIGCHARSET:
            for w in it.codes:
                code.append(w)
        elif op == CATEGORY:
            code.append(_category(it.arg, flags))
        else:
            raise PatternError("internal: unsupported set operator %s" % OPNAMES[op])
    code.append(FAILURE)


class _Charset:
    # _optimize_charset's result: the set's items and whether case matters in it
    def __init__(self, items: list[Item], hascased: bool) -> None:
        self.items = items
        self.hascased = hascased


def _setbits(charmap: list[int], ks: list[int]) -> bool:
    # set charmap[k] for each k, in order, until one is past it (CPython's IndexError): False then
    for k in ks:
        if k >= len(charmap):
            return False
        charmap[k] = 1
    return True


def _optimize_charset(charset: list[Item], case: _Case) -> _Charset:
    # internal: optimize character set (case.on: IGNORECASE and not LOCALE, CPython's fixup)
    out: list[Item] = []
    tail: list[Item] = []
    charmap = [0] * 256
    hascased = False
    for it in charset:
        op = it.op
        av = it.arg
        while True:
            fits = True
            if op == LITERAL:
                if case.on:
                    av = case.tolower(av)
                    fits = _setbits(charmap, [av])
                    if fits:
                        fits = _setbits(charmap, case.fixes(av))
                    if fits and not hascased and case.iscased(av):
                        hascased = True
                else:
                    fits = _setbits(charmap, [av])
            elif op == RANGE:
                if case.on:
                    for i in range(it.arg, it.arg2 + 1):
                        lo = case.tolower(i)
                        if not _setbits(charmap, [lo]) or not _setbits(charmap, case.fixes(lo)):
                            fits = False
                            break
                    if fits and not hascased:
                        for i in range(it.arg, it.arg2 + 1):
                            if case.iscased(i):
                                hascased = True
                                break
                else:
                    if it.arg2 >= len(charmap):
                        # (CPython sets the bits below the map's size first)
                        for i in range(it.arg, len(charmap)):
                            charmap[i] = 1
                        fits = False
                    else:
                        for i in range(it.arg, it.arg2 + 1):
                            charmap[i] = 1
            elif op == NEGATE:
                out.append(it)
            else:
                tail.append(it)
            if fits:
                break
            if len(charmap) == 256:
                # character set contains non-UCS1 character codes
                for _ in range(0xFF00):
                    charmap.append(0)
                continue
            # character set contains non-BMP character codes: for a range, all BMP characters
            # in it are already set
            t = Item(op, av)
            t.arg2 = it.arg2
            if case.on:
                if op == RANGE:
                    if case.uni:  # not ASCII
                        t.op = RANGE_UNI_IGNORE
                    hascased = True
                elif not hascased and case.iscased(av):
                    hascased = True
            tail.append(t)
            break
    # compress character map
    runs: list[tuple[int, int]] = []
    many = False
    q = 0
    n = len(charmap)
    while True:
        p = q
        while p < n and charmap[p] == 0:
            p += 1
        if p >= n:
            break
        if len(runs) >= 2:
            many = True
            break
        q = p
        while q < n and charmap[q] != 0:
            q += 1
        if q >= n:
            runs.append((p, n))
            break
        runs.append((p, q))
    if not many:
        # use literal/range
        for r in runs:
            if r[1] - r[0] == 1:
                out.append(Item(LITERAL, r[0]))
            else:
                out.append(_range(r[0], r[1] - 1))
        for t in tail:
            out.append(t)
        # if the case was changed or new representation is more compact
        if hascased or len(out) < len(charset):
            return _Charset(out, hascased)
        # else original character set is good enough
        return _Charset(charset, hascased)
    # use bitmap
    if n == 256:
        cs = Item(CHARSET, 0)
        cs.codes = _mk_bitmap(charmap, 0, 256)
        out.append(cs)
        for t in tail:
            out.append(t)
        return _Charset(out, hascased)
    # a big charset: the map sliced into chunks of 256 characters, each different chunk numbered
    # once; a word of how many, the 256 chunk numbers (as bytes), and the chunks' bitmaps
    comps: dict[str, int] = {}
    mapping: list[int] = []
    block = 0
    chunks: list[int] = []
    for i in range(0, 65536, 256):
        key = "".join(["1" if charmap[j] != 0 else "0" for j in range(i, i + 256)])
        if key in comps:
            mapping.append(comps[key])
        else:
            comps[key] = block
            mapping.append(block)
            block += 1
            for j in range(i, i + 256):
                chunks.append(charmap[j])
    data = [block]
    for w in range(64):
        data.append(mapping[4 * w] | (mapping[4 * w + 1] << 8) | (mapping[4 * w + 2] << 16) | (mapping[4 * w + 3] << 24))
    for w in _mk_bitmap(chunks, 0, len(chunks)):
        data.append(w)
    big = Item(BIGCHARSET, 0)
    big.codes = data
    out.append(big)
    for t in tail:
        out.append(t)
    return _Charset(out, hascased)


def _mk_bitmap(bits: list[int], start: int, end: int) -> list[int]:
    # the 0/1 values as 32-bit words, bit i of word j the value j * 32 + i
    out: list[int] = []
    for j in range(start, end, 32):
        v = 0
        for i in range(32):
            if bits[j + i] != 0:
                v |= 1 << i
        out.append(v)
    return out


def _simple(p: SubPattern) -> bool:
    # check if this subpattern is a "simple" operator
    if len(p.data) != 1:
        return False
    it = p.data[0]
    if it.op == SUBPATTERN:
        return it.arg < 0 and _simple(_sub(it))
    return it.op == LITERAL or it.op == NOT_LITERAL or it.op == ANY or it.op == IN


def _generate_overlap_table(prefix: list[int]) -> list[int]:
    # for each index i of the prefix, the length of its longest proper prefix that ends at i
    table = [0] * len(prefix)
    for i in range(1, len(prefix)):
        idx = table[i - 1]
        while True:
            if prefix[i] == prefix[idx]:
                table[i] = idx + 1
                break
            if idx == 0:
                table[i] = 0
                break
            idx = table[idx - 1]
    return table


class _Prefix:
    def __init__(self) -> None:
        self.prefix: list[int] = []
        self.skip = -1  # (-1: None)
        self.got_all = False


def _get_literal_prefix(pattern: SubPattern, flags: int) -> _Prefix:
    # look for literal prefix
    r = _Prefix()
    case = _Case(flags)
    ignore = flags & SRE_FLAG_IGNORECASE != 0
    for it in pattern.data:
        if it.op == LITERAL:
            if ignore and case.iscased(it.arg):
                return r
            r.prefix.append(it.arg)
        elif it.op == SUBPATTERN:
            flags1 = _combine_flags(flags, it.arg2, it.arg3)
            if flags1 & SRE_FLAG_IGNORECASE != 0 and flags1 & SRE_FLAG_LOCALE != 0:
                return r
            r1 = _get_literal_prefix(_sub(it), flags1)
            if r.skip < 0:
                if it.arg >= 0:
                    r.skip = len(r.prefix)
                elif r1.skip >= 0:
                    r.skip = len(r.prefix) + r1.skip
            for x in r1.prefix:
                r.prefix.append(x)
            if not r1.got_all:
                return r
        else:
            return r
    r.got_all = True
    return r


def _get_charset_prefix(pattern: SubPattern, flags: int) -> list[Item] | None:
    while True:
        if len(pattern.data) == 0:
            return None
        it = pattern.data[0]
        if it.op != SUBPATTERN:
            break
        pattern = _sub(it)
        flags = _combine_flags(flags, it.arg2, it.arg3)
        if flags & SRE_FLAG_IGNORECASE != 0 and flags & SRE_FLAG_LOCALE != 0:
            return None
    ignore = flags & SRE_FLAG_IGNORECASE != 0
    case = _Case(flags)
    it = pattern.data[0]
    if it.op == LITERAL:
        if ignore and case.iscased(it.arg):
            return None
        return [it]
    elif it.op == BRANCH:
        charset: list[Item] = []
        for p in it.subs:
            if len(p.data) == 0:
                return None
            x = p.data[0]
            if x.op == LITERAL and not (ignore and case.iscased(x.arg)):
                charset.append(x)
            else:
                return None
        return charset
    elif it.op == IN:
        if ignore:
            for x in it.items:
                if x.op == LITERAL:
                    if case.iscased(x.arg):
                        return None
                elif x.op == RANGE:
                    if x.arg2 > 0xFFFF:
                        return None
                    for c in range(x.arg, x.arg2 + 1):
                        if case.iscased(c):
                            return None
        return it.items
    return None


def _compile_info(code: list[int], pattern: SubPattern, flags: int) -> None:
    # internal: compile an info block: the min and max width, and an optional literal prefix or
    # a character map
    w = pattern.getwidth()
    lo = w[0]
    hi = w[1]
    if hi > MAXCODE:
        hi = MAXCODE
    if lo == 0:
        for x in [INFO, 4, 0, lo, hi]:
            code.append(x)
        return
    # look for a literal prefix
    prefix: list[int] = []
    prefix_skip = -1
    got_all = False
    charset: list[Item] | None = None
    if not (flags & SRE_FLAG_IGNORECASE != 0 and flags & SRE_FLAG_LOCALE != 0):
        r = _get_literal_prefix(pattern, flags)
        prefix = r.prefix
        prefix_skip = r.skip
        got_all = r.got_all
        # if no prefix, look for charset prefix
        if len(prefix) == 0:
            charset = _get_charset_prefix(pattern, flags)
    # add an info block
    code.append(INFO)
    skip = len(code)
    code.append(0)
    # literal flag
    mask = 0
    if len(prefix) > 0:
        mask = SRE_INFO_PREFIX
        if prefix_skip < 0 and got_all:
            mask = mask | SRE_INFO_LITERAL
    elif charset is not None and len(charset) > 0:
        mask = mask | SRE_INFO_CHARSET
    code.append(mask)
    # pattern length
    if lo < MAXCODE:
        code.append(lo)
    else:
        code.append(MAXCODE)
        prefix = prefix[:MAXCODE]
    code.append(hi)
    # add literal prefix
    if len(prefix) > 0:
        code.append(len(prefix))  # length
        if prefix_skip < 0:
            prefix_skip = len(prefix)
        code.append(prefix_skip)  # skip
        for x in prefix:
            code.append(x)
        # generate overlap table
        for x in _generate_overlap_table(prefix):
            code.append(x)
    elif charset is not None and len(charset) > 0:
        opt = _optimize_charset(charset, _Case(0))
        _compile_charset(opt.items, flags, code)
    code[skip] = len(code) - skip


def _code(p: SubPattern, flags: int) -> list[int]:
    flags = p.state.flags | flags
    code: list[int] = []
    # compile info block
    _compile_info(code, p, flags)
    # compile the pattern
    _compile_code(code, p.data, flags)
    code.append(SUCCESS)
    return code


# ---- Pattern and Match (_sre's objects)


class Pattern:
    """Compiled regular expression object."""

    def __init__(self, pattern: str, flags: int, code: list[int], groups: int, groupindex: dict[str, int]) -> None:
        self.pattern = pattern
        self.flags = flags
        self.groups = groups
        self.groupindex = groupindex
        self._code = code
        # Classes are evaluated for ASCII only on first use. Their lifetime is this Pattern's,
        # so purge() or cache eviction can release them with the pattern. Integer offsets into
        # the flattened tables keep the warm lookup on the compiler's inline list[int] reads.
        self._charset_offsets = [-1] * len(code)
        self._charset_ascii: list[int] = []
        self._indexgroup: list[str | None] = [None] * (groups + 1)
        for k in groupindex:
            self._indexgroup[groupindex[k]] = k

    def _state(self, string: str, pos: int, endpos: int) -> _sre.State:
        # state_init: pos and endpos clamped to the string, then made code point indices; where one
        # is inside a character's bytes, the match starts after that character, or ends before it.
        # The state's pos and endpos keep them as the caller gave them, for the match objects
        n = len(string)
        pos = 0 if pos < 0 else n if pos > n else pos
        endpos = 0 if endpos < 0 else n if endpos > n else endpos
        codes = _codes(string)
        offs = _last_offs
        st = _sre.State(codes, _to_char(offs, pos), _to_char_floor(offs, endpos), self.groups)
        st.charset_offsets = self._charset_offsets
        st.charset_ascii = self._charset_ascii
        st.offs = offs
        st.pos = pos
        st.endpos = endpos
        return st

    def _new_match(self, string: str, st: _sre.State) -> "Match":
        # pattern_new_match: the match's bounds and its groups', as indices into the str
        offs = st.offs
        mark = [_to_index(offs, st.start), _to_index(offs, st.ptr)]
        j = 0
        for _ in range(self.groups):
            if j + 1 <= st.lastmark and st.mark[j] >= 0 and st.mark[j + 1] >= 0:
                mark.append(_to_index(offs, st.mark[j]))
                mark.append(_to_index(offs, st.mark[j + 1]))
            else:
                mark.append(-1)
                mark.append(-1)
            j += 2
        return Match(self, string, mark, st.pos, st.endpos, st.lastindex)

    def match(self, string: str, pos: int = 0, endpos: int = _MAXSIZE) -> "Match | None":
        """Matches zero or more characters at the beginning of the string."""
        st = self._state(string, pos, endpos)
        st.ptr = st.start
        if _sre.sre_match(st, self._code, 0, True) == 0:
            return None
        return self._new_match(string, st)

    def fullmatch(self, string: str, pos: int = 0, endpos: int = _MAXSIZE) -> "Match | None":
        """Matches against all of the string."""
        st = self._state(string, pos, endpos)
        st.ptr = st.start
        st.match_all = True
        if _sre.sre_match(st, self._code, 0, True) == 0:
            return None
        return self._new_match(string, st)

    def search(self, string: str, pos: int = 0, endpos: int = _MAXSIZE) -> "Match | None":
        """Scan through string looking for a match, and return a corresponding match object instance.

        Return None if no position in the string matches."""
        st = self._state(string, pos, endpos)
        if _sre.sre_search(st, self._code) == 0:
            return None
        return self._new_match(string, st)

    def findall(self, string: str, pos: int = 0, endpos: int = _MAXSIZE) -> list[str]:
        """Return a list of all non-overlapping matches of pattern in string."""
        if self.groups > 1:
            # (the list of tuples CPython gives has no type Pystachy can give it: their length is
            # the pattern's group count)
            raise NotImplementedError("re.findall() of a pattern with %d groups returns tuples of that many items, which Pystachy does not have: use finditer() and m.group(1, 2, ...)" % self.groups)
        st = self._state(string, pos, endpos)
        offs = st.offs
        out: list[str] = []
        while st.start <= st.end:
            st.reset()
            st.ptr = st.start
            if _sre.sre_search(st, self._code) == 0:
                break
            if self.groups == 0:
                out.append(string[_to_index(offs, st.start) : _to_index(offs, st.ptr)])
            elif st.lastmark < 1 or st.mark[0] < 0 or st.mark[1] < 0:
                out.append("")
            else:
                out.append(string[_to_index(offs, st.mark[0]) : _to_index(offs, st.mark[1])])
            st.must_advance = st.ptr == st.start
            st.start = st.ptr
        return out

    def finditer(self, string: str, pos: int = 0, endpos: int = _MAXSIZE) -> "list[Match]":
        """Return an iterator over all non-overlapping matches for the RE pattern in string.

        For each match, the iterator returns a match object."""
        # (a list of them: Pystachy has no iterator of matches made as the loop asks)
        st = self._state(string, pos, endpos)
        out: list[Match] = []
        while True:
            st.reset()
            st.ptr = st.start
            if _sre.sre_search(st, self._code) == 0:
                break
            out.append(self._new_match(string, st))
            st.must_advance = st.ptr == st.start
            st.start = st.ptr
        return out

    def split(self, string: str, maxsplit: int = 0) -> list[str]:
        """Split string by the occurrences of pattern."""
        st = self._state(string, 0, _MAXSIZE)
        offs = st.offs
        out: list[str] = []
        n = 0
        last = st.start
        while maxsplit == 0 or n < maxsplit:
            st.reset()
            st.ptr = st.start
            if _sre.sre_search(st, self._code) == 0:
                break
            # the segment before this match
            out.append(string[_to_index(offs, last) : _to_index(offs, st.start)])
            # the groups (if any)
            for i in range(self.groups):
                j = 2 * i
                if j >= st.lastmark or st.mark[j] < 0 or st.mark[j + 1] < 0:
                    raise NotImplementedError("re.split() of a pattern whose group %d did not take part in the match gives None, which the list[str] Pystachy returns cannot hold" % (i + 1))
                out.append(string[_to_index(offs, st.mark[j]) : _to_index(offs, st.mark[j + 1])])
            n += 1
            st.must_advance = st.ptr == st.start
            last = st.ptr
            st.start = st.ptr
        # the segment after the last match (even if empty)
        out.append(string[_to_index(offs, last) : st.endpos])
        return out

    def sub(self, repl, string: str, count: int = 0) -> str:
        """Return the string obtained by replacing the leftmost non-overlapping occurrences of pattern in string by the replacement repl."""
        return self._subx(repl, string, count)[0]

    def subn(self, repl, string: str, count: int = 0) -> tuple[str, int]:
        """Return the tuple (new_string, number_of_subs_made) found by replacing the leftmost non-overlapping occurrences of pattern with the replacement repl."""
        return self._subx(repl, string, count)

    def _subx(self, repl, string: str, count: int) -> tuple[str, int]:
        # pattern_subx: repl a str (a literal one is used as it is, else a template) or a function
        # of the match
        literal = ""
        template = Template()
        if isinstance(repl, str):
            if "\\" not in repl:
                literal = repl
            else:
                template = _compile_template(self, repl)
                if len(template.groups) == 0:
                    literal = template.literals[0]
                    template = Template()
        st = self._state(string, 0, _MAXSIZE)
        offs = st.offs
        out: list[str] = []
        n = 0
        i = 0
        while count == 0 or n < count:
            st.reset()
            st.ptr = st.start
            if _sre.sre_search(st, self._code) == 0:
                break
            b = _to_index(offs, st.start)
            e = _to_index(offs, st.ptr)
            if i < b:
                # the segment before this match
                out.append(string[i:b])
            if isinstance(repl, str):
                if len(template.literals) == 0:
                    out.append(literal)
                else:
                    out.append(template.expand(self._new_match(string, st)))
            else:
                out.append(repl(self._new_match(string, st)))
            i = e
            n += 1
            st.must_advance = st.ptr == st.start
            st.start = st.ptr
        # the segment after the last match
        end = st.endpos
        if i < end:
            out.append(string[i:end])
        return ("".join(out), n)

    def __repr__(self) -> str:
        names = ["re.IGNORECASE", "re.LOCALE", "re.MULTILINE", "re.DOTALL", "re.UNICODE", "re.VERBOSE", "re.DEBUG", "re.ASCII"]
        values = [SRE_FLAG_IGNORECASE, SRE_FLAG_LOCALE, SRE_FLAG_MULTILINE, SRE_FLAG_DOTALL, SRE_FLAG_UNICODE, SRE_FLAG_VERBOSE, SRE_FLAG_DEBUG, SRE_FLAG_ASCII]
        flags = self.flags
        # (re.UNICODE is left out for a str pattern)
        if flags & (SRE_FLAG_LOCALE | SRE_FLAG_UNICODE | SRE_FLAG_ASCII) == SRE_FLAG_UNICODE:
            flags &= ~SRE_FLAG_UNICODE
        items: list[str] = []
        for i in range(len(names)):
            if flags & values[i] != 0:
                items.append(names[i])
                flags &= ~values[i]
        if flags != 0:
            items.append("0x%x" % flags)
        r = _cut(repr(self.pattern), 200)
        if len(items) > 0:
            return "re.compile(%s, %s)" % (r, "|".join(items))
        return "re.compile(%s)" % r

    def __eq__(self, other) -> bool:
        if not isinstance(other, Pattern):
            return False
        return self is other or (self.flags == other.flags and self._code == other._code and self.pattern == other.pattern)

    def __hash__(self) -> int:
        # (CPython's also mixes in a hash of the code's bytes; equal patterns hash alike either way)
        return hash(self.pattern) ^ self.flags ^ len(self._code)


def _cut(s: str, n: int) -> str:
    # %.<n>R: the first n characters of s
    if not _UTF8:
        return s[:n]
    i = 0
    k = 0
    while i < len(s) and k < n:
        i += len(_charat(s, i))
        k += 1
    return s[:i]


class Match:
    """The result of re.match() and re.search().
    Match objects always have a boolean value of True."""

    def __init__(self, pattern: Pattern, string: str, mark: list[int], pos: int, endpos: int, lastindex: int) -> None:
        self.re = pattern
        self.string = string
        self._mark = mark
        self.pos = pos
        self.endpos = endpos
        self.lastindex: int | None = lastindex if lastindex >= 0 else None
        self.lastgroup: str | None = pattern._indexgroup[lastindex] if 0 <= lastindex and lastindex <= pattern.groups else None

    def _index(self, g) -> int:
        # match_getindex: a group's number, or its name's
        i = -1
        if isinstance(g, str):
            if g in self.re.groupindex:
                i = self.re.groupindex[g]
        elif isinstance(g, bool) or isinstance(g, int):
            i = int(g)
        else:
            raise IndexError("no such group")
        if i < 0 or i > self.re.groups:
            raise IndexError("no such group")
        return i

    def _get(self, g, default: str | None = None) -> str | None:
        i = self._index(g)
        if self._mark[2 * i] < 0:
            return default
        return self.string[self._mark[2 * i] : self._mark[2 * i + 1]]

    def group(self, *args):
        """group([group1, ...]) -> str or tuple.
        Return subgroup(s) of the match by indices or names.
        For 0 returns the entire match."""
        if len(args) == 0:
            return self._get(0)
        if len(args) == 1:
            return self._get(args[0])
        if len(args) == 2:
            return (self._get(args[0]), self._get(args[1]))
        if len(args) == 3:
            return (self._get(args[0]), self._get(args[1]), self._get(args[2]))
        if len(args) == 4:
            return (self._get(args[0]), self._get(args[1]), self._get(args[2]), self._get(args[3]))
        if len(args) == 5:
            return (self._get(args[0]), self._get(args[1]), self._get(args[2]), self._get(args[3]), self._get(args[4]))
        raise NotImplementedError("Match.group() of more than 5 groups")

    def __getitem__(self, g):
        return self._get(g)

    def groups(self, default: str | None = None) -> tuple[str | None, ...]:
        """Return a tuple containing all the subgroups of the match, from 1."""
        # (its length is the pattern's group count, which no Pystachy tuple type has: an error
        # where it is called)
        return tuple([self._get(i, default) for i in range(1, self.re.groups + 1)])

    def groupdict(self, default: str | None = None) -> dict[str, str | None]:
        """Return a dictionary containing all the named subgroups of the match, keyed by the subgroup name."""
        out: dict[str, str | None] = {}
        for k in self.re.groupindex:
            out[k] = self._get(k, default)
        return out

    def start(self, group=0) -> int:
        """Return index of the start of the substring matched by group."""
        return self._mark[2 * self._index(group)]

    def end(self, group=0) -> int:
        """Return index of the end of the substring matched by group."""
        return self._mark[2 * self._index(group) + 1]

    def span(self, group=0) -> tuple[int, int]:
        """For match object m, return the 2-tuple (m.start(group), m.end(group))."""
        i = self._index(group)
        return (self._mark[2 * i], self._mark[2 * i + 1])

    def expand(self, template: str) -> str:
        """Return the string obtained by doing backslash substitution on the string template, as done by the sub() method."""
        return _compile_template(self.re, template).expand(self)

    def __repr__(self) -> str:
        g0 = self._get(0)
        return "<re.Match object; span=(%d, %d), match=%s>" % (self._mark[0], self._mark[1], _cut(repr(g0), 50))


# ---- the module's functions

_cache: dict[tuple[str, int], Pattern] = {}
_MAXCACHE = 512
_tcache: dict[tuple[str, str], Template] = {}


def _compile(pattern, flags: int) -> Pattern:
    # internal: compile pattern (a Pattern is itself, without flags)
    if isinstance(pattern, Pattern):
        if flags != 0:
            raise ValueError("cannot process flags argument with a compiled pattern")
        return pattern
    if not isinstance(pattern, str):
        raise TypeError("first argument must be string or compiled pattern")
    key = (pattern, flags)
    if key in _cache:
        return _cache[key]
    p = parse(pattern, flags)
    code = _code(p, flags)
    compiled = Pattern(pattern, flags | p.state.flags, code, p.state.groups() - 1, p.state.groupdict)
    if flags & SRE_FLAG_DEBUG != 0:
        return compiled
    if len(_cache) >= _MAXCACHE:
        # drop the oldest item (the first key)
        oldest = key
        for k in _cache:
            oldest = k
            break
        del _cache[oldest]
    _cache[key] = compiled
    return compiled


def _compile_template(pattern: Pattern, repl: str) -> Template:
    # internal: compile replacement pattern
    key = (pattern.pattern + "\x00" + str(pattern.flags), repl)
    if key in _tcache:
        return _tcache[key]
    t = parse_template(repl, pattern)
    if len(_tcache) >= _MAXCACHE:
        oldest = key
        for k in _tcache:
            oldest = k
            break
        del _tcache[oldest]
    _tcache[key] = t
    return t


def match(pattern, string: str, flags: int = 0) -> Match | None:
    """Try to apply the pattern at the start of the string, returning
    a Match object, or None if no match was found."""
    return _compile(pattern, flags).match(string)


def fullmatch(pattern, string: str, flags: int = 0) -> Match | None:
    """Try to apply the pattern to all of the string, returning
    a Match object, or None if no match was found."""
    return _compile(pattern, flags).fullmatch(string)


def search(pattern, string: str, flags: int = 0) -> Match | None:
    """Scan through string looking for a match to the pattern, returning
    a Match object, or None if no match was found."""
    return _compile(pattern, flags).search(string)


def sub(pattern, repl, string: str, count: int = 0, flags: int = 0) -> str:
    """Return the string obtained by replacing the leftmost
    non-overlapping occurrences of the pattern in string by the
    replacement repl."""
    return _compile(pattern, flags).sub(repl, string, count)


def subn(pattern, repl, string: str, count: int = 0, flags: int = 0) -> tuple[str, int]:
    """Return a 2-tuple containing (new_string, number)."""
    return _compile(pattern, flags).subn(repl, string, count)


def split(pattern, string: str, maxsplit: int = 0, flags: int = 0) -> list[str]:
    """Split the source string by the occurrences of the pattern,
    returning a list containing the resulting substrings."""
    return _compile(pattern, flags).split(string, maxsplit)


def findall(pattern, string: str, flags: int = 0) -> list[str]:
    """Return a list of all non-overlapping matches in the string."""
    return _compile(pattern, flags).findall(string)


def finditer(pattern, string: str, flags: int = 0) -> list[Match]:
    """Return an iterator over all non-overlapping matches in the
    string.  For each match, the iterator returns a Match object."""
    return _compile(pattern, flags).finditer(string)


def compile(pattern, flags: int = 0) -> Pattern:
    "Compile a regular expression pattern, returning a Pattern object."
    return _compile(pattern, flags)


def purge() -> None:
    "Clear the regular expression caches"
    _cache.clear()
    _tcache.clear()


def escape(pattern: str) -> str:
    """
    Escape special characters in a string.
    """
    out: list[str] = []
    for c in pattern:
        if c in "()[]{}?*+-|^$\\.&~# \t\n\r\v\f":
            out.append("\\")
        out.append(c)
    return "".join(out)
