"""Generate/check the runtime's compact Unicode classification and case tables.

Use the CPython pinned by .python-version (Unicode 15.1.0):
    python3 tools/unicode_classification_tables.py --write
    python3 tools/unicode_classification_tables.py --check
The tables are embedded in runtime.c so the runtime cache tracks them with that source.

Classification: each uint32 stores a transition code point in its high 28 bits and the four
flags alpha=1, digit=2, decimal=4, numeric=8 in its low bits. Alnum accepts any flag.

Case (str's upper, lower, title, capitalize, swapcase, casefold, isupper, islower, istitle):
  - unicode_case_flags: each uint32 starts a run at the code point in its high 24 bits; the
    flags upper=1, lower=2, title=4, case-ignorable=8 of the run's even offsets are in bits
    4-7 and those of its odd offsets in bits 0-3 (alternating scripts take one entry);
  - unicode_case_lower/upper/title/fold: pairs of uint32, sorted by code point. The first
    holds a run's first code point (high 21 bits), its count less one (10 bits) and its
    step less one (1 bit); the second the signed distance to each mapped code point, or,
    with bit 30 alone of its top two set, a full mapping to two or three code points:
    bit 16 tells three, and the low 16 bits index unicode_case_pool. A code point in no run
    maps to itself.
Every value comes from the pinned CPython's own str methods, one code point at a time.
"""
import argparse
from pathlib import Path
import sys
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
START = "/* BEGIN GENERATED UNICODE CLASSIFICATION */"
END = "/* END GENERATED UNICODE CLASSIFICATION */"
CASE_START = "/* BEGIN GENERATED UNICODE CASE */"
CASE_END = "/* END GENERATED UNICODE CASE */"
LIMIT = 0x110000
KINDS = ("lower", "upper", "title", "fold")  # (runtime.py's kinds of pys_unicode_case_map)
SIGMA, FINAL_SIGMA = "\u03a3", "\u03c2"
SPECIAL = 1 << 30


def flags(cp):
    if cp < 0 or cp >= 0x110000:
        return 0
    ch = chr(cp)
    return int(ch.isalpha()) | int(ch.isdigit()) * 2 | int(ch.isdecimal()) * 4 | int(ch.isnumeric()) * 8


def case_flags(cp):
    # CPython's Py_UNICODE_ISUPPER, ISLOWER and ISTITLE, and its case-ignorable property, which
    # only str.lower() shows: a capital sigma after a cased letter is final unless a cased letter
    # follows, case-ignorable characters aside (handle_capital_sigma)
    if cp < 0 or cp >= LIMIT:
        return 0
    ch = chr(cp)
    ignorable = ("A" + ch + SIGMA).lower()[-1] == FINAL_SIGMA and (ch + SIGMA).lower()[-1] != FINAL_SIGMA
    return int(ch.isupper()) | int(ch.islower()) * 2 | int(ch.istitle() and not ch.isupper()) * 4 | int(ignorable) * 8


def case_map(cp, kind):
    # CPython's full mapping of one code point (KINDS[kind]): up to three code points of 21
    # bits each, the first lowest. A lone capital sigma lowers to the non-final form.
    if cp < 0 or cp >= LIMIT:
        return cp
    ch = chr(cp)
    mapped = (ch.lower(), ch.upper(), ch.title(), ch.casefold())[kind]
    if not 1 <= len(mapped) <= 3:
        raise RuntimeError(f"U+{cp:04X} maps to {len(mapped)} code points")
    return sum(ord(c) << 21 * i for i, c in enumerate(mapped))


def pinned_version():
    pinned = (ROOT / ".python-version").read_text().strip()
    if sys.implementation.name != "cpython" or sys.version.split()[0] != pinned or unicodedata.unidata_version != "15.1.0":
        raise RuntimeError(f"generate with CPython {pinned}, Unicode 15.1.0")
    return pinned


def utf8_len(cp):
    return 1 if cp < 0x80 else 2 if cp < 0x800 else 3 if cp < 0x10000 else 4


def flag_runs(values):
    # runs whose flags repeat with period two (a uniform run has equal halves)
    entries, cp = [], 0
    while cp < LIMIT:
        even = values[cp]
        odd = values[cp + 1] if cp + 1 < LIMIT else even
        end = cp
        while end < LIMIT and values[end] == (odd if (end - cp) & 1 else even):
            end += 1
        if end - cp == 1:
            odd = even
        entries.append(cp << 8 | even << 4 | odd)
        cp = end
    return entries


def map_runs(kind, pool, index):
    # the runs of one mapping: equal distances at step one or two, and one entry per full mapping
    runs = []  # [first, count, step, value, special]
    for cp in range(LIMIT):
        packed = case_map(cp, kind)
        if packed == cp:
            continue
        if packed >> 21:
            seq = tuple(packed >> 21 * i & 0x1FFFFF for i in range(3 if packed >> 42 else 2))
            if seq not in index:
                index[seq] = len(pool)
                pool.extend(seq)
            runs.append([cp, 1, 1, SPECIAL | (len(seq) - 2) << 16 | index[seq], True])
            continue
        delta = packed - cp
        last = runs[-1] if runs else None
        if last and not last[4] and last[3] == delta and last[1] < 1024:
            first, count, step = last[:3]
            if (count == 1 and cp - first in (1, 2)) or (count > 1 and cp == first + count * step):
                last[1], last[2] = count + 1, cp - first if count == 1 else step
                continue
        runs.append([cp, 1, 1, delta, False])
    table = []
    for first, count, step, value, special in runs:
        if not special and not -(1 << 29) <= value < 1 << 29:
            raise RuntimeError(f"U+{first:04X}: distance {value} does not fit")
        table += [first << 11 | (count - 1) << 1 | (step - 1), value & 0xFFFFFFFF]
    return table


def lookup_flags(entries, cp):
    # runtime.c's pys_unicode_case_flags
    lo, n = 0, len(entries)
    while n > 1:
        half = n >> 1
        if entries[lo + half] >> 8 <= cp:
            lo += half
        n -= half
    entry = entries[lo]
    return (entry if (cp - (entry >> 8)) & 1 else entry >> 4) & 15


def lookup_map(table, pool, cp):
    # runtime.c's pys_unicode_case_map
    lo, n = 0, len(table) // 2
    while n > 1:
        half = n >> 1
        if table[2 * (lo + half)] >> 11 <= cp:
            lo += half
        n -= half
    run, value = table[2 * lo], table[2 * lo + 1]
    offset, step = (cp - (run >> 11)) & (1 << 64) - 1, (run & 1) + 1
    if offset >= ((run >> 1 & 1023) + 1) * step or offset & (step - 1):
        return cp
    if value >> 30 == 1:
        at = value & 0xFFFF
        packed = pool[at] | pool[at + 1] << 21
        return packed | pool[at + 2] << 42 if value >> 16 & 1 else packed
    return cp + (value - (1 << 32) if value >> 31 else value)


def case_tables():
    # (flags, pool, [the four mappings]), each checked against CPython for every code point,
    # with what runtime.py assumes of them. Runs are expanded against CPython's values; this
    # file's copy of runtime.c's lookups reads each code point in or beside a run, and a code
    # point that no run is near must map to itself.
    values = [case_flags(cp) for cp in range(LIMIT)]
    flags = flag_runs(values)
    pool, index, tables = [], {}, []
    for kind in range(len(KINDS)):
        tables.append(map_runs(kind, pool, index))
    if len(pool) > 0xFFFF or max(pool) > 0xFFFF:
        raise RuntimeError("the pool of full mappings does not fit 16 bits")
    starts = [entry >> 8 for entry in flags] + [LIMIT]
    if starts[0] != 0 or starts != sorted(set(starts)):
        raise RuntimeError("case flag runs are not in order from U+0000")
    near = set()
    for i, entry in enumerate(flags):
        first, end, even, odd = starts[i], starts[i + 1], entry >> 4 & 15, entry & 15
        if values[first:end:2] != [even] * len(range(first, end, 2)) or values[first + 1:end:2] != [odd] * len(range(first + 1, end, 2)):
            raise RuntimeError(f"U+{first:04X}: case flags do not survive their encoding")
        near.update((first - 1, first, first + 1))
    for table in tables:
        firsts = [run >> 11 for run in table[::2]]
        if firsts != sorted(set(firsts)):
            raise RuntimeError("mapping runs are not in order")
        for run in table[::2]:
            near.update(range((run >> 11) - 2, (run >> 11) + ((run >> 1 & 1023) + 1) * ((run & 1) + 1) + 2))
    methods = (str.lower, str.upper, str.title, str.casefold)
    for cp in range(LIMIT):
        ch = chr(cp)
        if ((ch + "A").title()[-1] == "a") != (values[cp] & 7 != 0):
            raise RuntimeError(f"U+{cp:04X}: cased is not upper, lower or title")
        if cp not in near:
            if any(method(ch) != ch for method in methods):
                raise RuntimeError(f"U+{cp:04X}: a mapping has no run")
            continue
        if lookup_flags(flags, cp) != values[cp]:
            raise RuntimeError(f"U+{cp:04X}: case flags are not found")
        for kind, table in enumerate(tables):
            packed = case_map(cp, kind)
            if lookup_map(table, pool, cp) != packed:
                raise RuntimeError(f"U+{cp:04X}: {KINDS[kind]} mapping does not survive its encoding")
            if sum(utf8_len(packed >> 21 * i & 0x1FFFFF) for i in range(3) if i == 0 or packed >> 21 * i) > 3 * utf8_len(cp):
                raise RuntimeError(f"U+{cp:04X}: {KINDS[kind]} mapping is more than three times its bytes")
    for cp in range(128):
        # runtime.py maps ASCII itself, and takes the properties of its letters from their ranges
        letter = chr(cp).isascii() and chr(cp).isalpha()
        want = (1 if cp < 97 else 2) if letter else values[cp] & 8
        low, up = (cp | 32, cp & 223) if letter else (cp, cp)
        if values[cp] != want or [case_map(cp, kind) for kind in range(4)] != [low, up, up, low]:
            raise RuntimeError(f"U+{cp:04X}: ASCII case differs from runtime.py's")
    if case_map(ord(SIGMA), 0) != ord(FINAL_SIGMA) + 1:
        raise RuntimeError("a lone capital sigma does not lower to the non-final form")
    return flags, pool, tables


def words(name, kind, entries, per):
    lines = [f"static const {kind} {name}[] = {{"]
    for i in range(0, len(entries), per):
        lines.append("  " + ", ".join(f"0x{x:x}" for x in entries[i:i + per]) + ",")
    return lines + ["};"]


def render_case():
    pinned = pinned_version()
    flags, pool, tables = case_tables()
    lines = [CASE_START, f"/* Generated by tools/unicode_classification_tables.py from CPython {pinned}, Unicode 15.1.0.",
             "   unicode_case_flags: (run's first code point << 8) | flags at even offsets << 4 | flags at odd",
             "   offsets, of upper=1, lower=2, title=4, case-ignorable=8. The mappings: pairs of (first code point",
             "   << 11 | count - 1 << 1 | step - 1) and the distance to the mapped code point, or 1 << 30 |",
             "   three code points? << 16 | index in unicode_case_pool of a full mapping.",
             "   Do not edit: regenerate with --write; --check verifies every code point. */"]
    lines += words("unicode_case_flags", "uint32_t", flags, 12)
    lines += words("unicode_case_pool", "uint16_t", pool, 16)
    for name, table in zip(KINDS, tables):
        lines += words("unicode_case_" + name, "uint32_t", table, 10)
    return "\n".join(lines + [CASE_END])


def render():
    pinned = pinned_version()
    entries, previous = [], -1
    for cp in range(0x110000):
        value = flags(cp)
        if value != previous:
            entries.append(cp * 16 + value)
            previous = value
    lines = [START, f"/* Generated by tools/unicode_classification_tables.py from CPython {pinned}, Unicode 15.1.0.",
             "   Each entry is (transition code point << 4) | alpha/digit/decimal/numeric flags.",
             "   Do not edit: regenerate with --write; --check verifies every code point. */",
             "static const uint32_t unicode_classification[] = {"]
    for i in range(0, len(entries), 12):
        lines.append("  " + ", ".join(f"0x{x:x}" for x in entries[i:i + 12]) + ",")
    return "\n".join(lines + ["};", END])


def block(text, start, end):
    return text[text.index(start):text.index(end) + len(end)] if start in text and end in text else ""


def check():
    text = (ROOT / "runtime.c").read_text()
    if block(text, START, END) != render():
        raise RuntimeError("runtime.c Unicode classification table differs; regenerate with --write")
    if block(text, CASE_START, CASE_END) != render_case():
        raise RuntimeError("runtime.c Unicode case tables differ; regenerate with --write")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write:
        path = ROOT / "runtime.c"
        text = path.read_text()
        generated = render()
        if START in text:
            text = text[:text.index(START)] + generated + text[text.index(END) + len(END):]
        else:
            marker = "/* ---------- tables ---------- */"
            text = text.replace(marker, marker + "\n" + generated, 1)
        generated = render_case()
        if CASE_START in text:
            text = text[:text.index(CASE_START)] + generated + text[text.index(CASE_END) + len(CASE_END):]
        else:
            text = text.replace(END, END + "\n" + generated, 1)
        path.write_text(text)
    else:
        check()
        print("Unicode 15.1.0 classification and case tables match all 1,114,112 code points")


if __name__ == "__main__":
    main()
