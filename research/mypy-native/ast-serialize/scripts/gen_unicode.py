"""Generate lib/ast_serialize/_unicode.py: XID_Start and XID_Continue of the running CPython's
Unicode database (3.13: Unicode 15.1), for code points >= 0x80."""
import sys, unicodedata

def ranges(pred):
    out = []
    start = None
    for cp in range(0x80, 0x110000):
        ok = pred(cp)
        if ok and start is None:
            start = cp
        elif not ok and start is not None:
            out.append((start, cp - 1)); start = None
    if start is not None:
        out.append((start, 0x10FFFF))
    return out

def enc(rs):
    # deltas from the previous range's end, in base 36, "gap.len" pairs separated by spaces
    parts = []
    prev = 0x7F
    for a, b in rs:
        parts.append(f"{base36(a - prev)}.{base36(b - a)}")
        prev = b
    return ' '.join(parts)

def base36(n):
    d = '0123456789abcdefghijklmnopqrstuvwxyz'
    if n == 0: return '0'
    s = ''
    while n:
        s = d[n % 36] + s; n //= 36
    return s

def wrap(s, width=96):
    lines = []
    while len(s) > width:
        cut = s.rfind(' ', 0, width)
        lines.append(s[:cut + 1]); s = s[cut + 1:]
    lines.append(s)
    return lines

xs = ranges(lambda cp: chr(cp).isidentifier())
xc = ranges(lambda cp: ('a' + chr(cp)).isidentifier())
out = ['"""XID_Start and XID_Continue above ASCII, for the lexer\'s identifiers (Ruff uses the\n',
       'unicode-ident crate). Generated from CPython ' + sys.version.split()[0] + "'s Unicode " + unicodedata.unidata_version + ' database by\n',
       'stripping the ranges of str.isidentifier(): each "gap.length" pair, in base 36, starts a range that\n',
       'many code points past the previous range\'s end (0x7f first).\n"""\n\n']
for name, rs in (('_START', xs), ('_CONTINUE', xc)):
    out.append(f'{name}_TEXT = (\n')
    for line in wrap(enc(rs)):
        out.append(f'    "{line}"\n')
    out.append(')\n\n')
out.append('''_start: list[int] = []
_continue: list[int] = []


def _decode(text: str, out: list[int]) -> None:
    # out: the first and last code point of each range, in order
    prev = 0x7F
    for pair in text.split(" "):
        dot = pair.find(".")
        first = prev + int(pair[:dot], 36)
        prev = first + int(pair[dot + 1:], 36)
        out.append(first)
        out.append(prev)


def _in(ranges: list[int], cp: int) -> bool:
    lo = 0
    hi = len(ranges) // 2
    while lo < hi:
        mid = (lo + hi) // 2
        if ranges[2 * mid + 1] < cp:
            lo = mid + 1
        else:
            hi = mid
    return lo < len(ranges) // 2 and ranges[2 * lo] <= cp


def is_xid_start(cp: int) -> bool:
    if len(_start) == 0:
        _decode(_START_TEXT, _start)
    return _in(_start, cp)


def is_xid_continue(cp: int) -> bool:
    if len(_continue) == 0:
        _decode(_CONTINUE_TEXT, _continue)
    return _in(_continue, cp)
''')
open(sys.argv[1], 'w').write(''.join(out))
print(len(xs), len(xc))
