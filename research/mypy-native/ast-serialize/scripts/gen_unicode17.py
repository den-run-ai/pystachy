"""Generate lib/ast_serialize/_unicode.py from Unicode 17.0's DerivedCoreProperties.txt (the
version of the unicode-ident crate the extension's lexer uses): XID_Start and XID_Continue above
ASCII."""
import sys

path, out_path = sys.argv[1], sys.argv[2]
props = {"XID_Start": set(), "XID_Continue": set()}
for line in open(path, encoding="utf-8"):
    line = line.split("#", 1)[0].strip()
    if not line:
        continue
    fields = [x.strip() for x in line.split(";")]
    cps, prop = fields[0], fields[1]
    if prop not in props:
        continue
    if ".." in cps:
        a, b = cps.split("..")
        rng = range(int(a, 16), int(b, 16) + 1)
    else:
        rng = range(int(cps, 16), int(cps, 16) + 1)
    props[prop].update(cp for cp in rng if cp >= 0x80)


def ranges(s):
    out = []
    for cp in sorted(s):
        if out and out[-1][1] == cp - 1:
            out[-1][1] = cp
        else:
            out.append([cp, cp])
    return out


def base36(n):
    d = "0123456789abcdefghijklmnopqrstuvwxyz"
    s = ""
    while True:
        s = d[n % 36] + s
        n //= 36
        if n == 0:
            return s


def enc(rs):
    parts = []
    prev = 0x7F
    for a, b in rs:
        parts.append(f"{base36(a - prev)}.{base36(b - a)}")
        prev = b
    return " ".join(parts)


def wrap(s, width=96):
    lines = []
    while len(s) > width:
        cut = s.rfind(" ", 0, width)
        lines.append(s[:cut + 1])
        s = s[cut + 1:]
    lines.append(s)
    return lines


src = open(out_path).read()
head = '''"""XID_Start and XID_Continue above ASCII, for the lexer's identifiers: Unicode 17.0's, as the
unicode-ident crate (1.0.22) that the extension's lexer uses. Generated from
DerivedCoreProperties-17.0.0.txt (SHA-256 24c7fed1195c482faaefd5c1e7eb821c5ee1fb6de07ecdbaa64b56a99da22c08)
by listing the ranges of each property: each "gap.length" pair, in base 36, starts a range that
many code points past the previous range's end (0x7f first).
"""

'''
body = []
for name, prop in (("_START", "XID_Start"), ("_CONTINUE", "XID_Continue")):
    body.append(f"{name}_TEXT = (\n")
    for line in wrap(enc(ranges(props[prop]))):
        body.append(f'    "{line}"\n')
    body.append(")\n\n")
rest = src[src.index("_start: list[int] = []"):]
open(out_path, "w").write(head + "".join(body) + rest)
print(len(ranges(props["XID_Start"])), len(ranges(props["XID_Continue"])))
