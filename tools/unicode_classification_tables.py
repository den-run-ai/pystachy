"""Generate/check the runtime's Unicode property and case tables.

Use the CPython pinned by .python-version (Unicode 15.1.0):
    python3 tools/unicode_classification_tables.py --write
    python3 tools/unicode_classification_tables.py --check
The tables are embedded in runtime.c so the runtime cache tracks them with that source.

Each table gives every code point its value without a search. The first 2,048 code points,
which UTF-8 writes in one or two bytes, index a _low array where a table has one. Any code
point takes three loads, of stages that hold one item for each code point, or one byte for
each eight where a code point has one bit (item i's bit cp & 7, with i = cp >> 3):
    stage3[stage2[stage1[i >> A + B] << A | i >> B & (1 << A) - 1] << B | i & (1 << B) - 1]
A stage keeps each distinct block once, the block of zeros first: stage 1 gives 0 where all
the items of an entry are 0. Stage 1 stops after the last block that holds an item other
than 0, so an item from len(stage1) << A + B on is 0.

Properties (unicode_property_low and _1 to _3, with A, B = 4, 3): a byte of alpha=1, digit=2,
decimal=4 and numeric=8. Alnum accepts any of them.

Printable (unicode_printable_low and _1 to _3, with A, B = 4, 4): a bit, for repr(). Every
program links it, so it is apart from the properties and small.

Case (unicode_case_low and _1 to _3, with A, B = 5, 3): record << 3 | upper=1 | lower=2 | title=4, for
str's upper, lower, title, capitalize, swapcase, casefold, isupper, islower and istitle. A
record is four uint32 of unicode_case_records, for the lower, upper, title and casefold
mappings: the signed distance to the mapped code point or, with bit 30 alone of its top two
set, a full mapping to two or three code points: bit 16 tells three, and the low 16 bits
index unicode_case_pool. Record 0 maps a code point to itself.

Case-ignorable (unicode_case_ignorable_1 to _3, with A, B = 5, 3, and no _low array): a bit for
the code points that the context of a capital sigma looks past. Only a capital sigma asks, so
a program whose strs are lowered links these stages and not the properties.
Every value comes from the pinned CPython's own str methods, one code point at a time.
"""
import argparse
import functools
from pathlib import Path
import sys
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
START = "/* BEGIN GENERATED UNICODE CLASSIFICATION */"
END = "/* END GENERATED UNICODE CLASSIFICATION */"
CASE_START = "/* BEGIN GENERATED UNICODE CASE */"
CASE_END = "/* END GENERATED UNICODE CASE */"
LIMIT = 0x110000
LOW = 0x800              # (the code points of one or two UTF-8 bytes: the _low arrays)
PROPERTY_SPLIT = (4, 3)  # (A, B of the module docstring, as runtime.c's unicode_property reads them)
PRINTABLE_SPLIT = (4, 4)  # (runtime.c's printable)
CASE_SPLIT = (5, 3)      # (runtime.c's unicode_case)
IGNORABLE_SPLIT = (5, 3)  # (runtime.c's pys_unicode_case_ignorable)
KINDS = ("lower", "upper", "title", "fold")  # (runtime.py's kinds of pys_unicode_case_map)
SIGMA, FINAL_SIGMA = "\u03a3", "\u03c2"
SPECIAL = 1 << 30


def flags(cp):
    # runtime.c's pys_unicode_flags
    if cp < 0 or cp >= LIMIT:
        return 0
    ch = chr(cp)
    return int(ch.isalpha()) | int(ch.isdigit()) * 2 | int(ch.isdecimal()) * 4 | int(ch.isnumeric()) * 8


def printable(cp):
    # runtime.c's printable: CPython's Py_UNICODE_ISPRINTABLE, by which repr() escapes
    return int(0 <= cp < LIMIT and chr(cp).isprintable())


def case_ignorable(cp):
    # runtime.c's pys_unicode_case_ignorable: CPython's case-ignorable property, which only
    # str.lower() shows. A capital sigma after a cased letter is final unless a cased letter
    # follows, case-ignorable characters aside (handle_capital_sigma)
    if cp < 0 or cp >= LIMIT:
        return 0
    ch = chr(cp)
    return int(("A" + ch + SIGMA).lower()[-1] == FINAL_SIGMA and (ch + SIGMA).lower()[-1] != FINAL_SIGMA)


def case_flags(cp):
    # runtime.c's pys_unicode_case_flags: CPython's Py_UNICODE_ISUPPER, ISLOWER and ISTITLE
    if cp < 0 or cp >= LIMIT:
        return 0
    ch = chr(cp)
    return int(ch.isupper()) | int(ch.islower()) * 2 | int(ch.istitle() and not ch.isupper()) * 4


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


def pack(items, size):
    # (the block of each size items, the distinct blocks one after another: first the block of
    # zeros, which has the number 0 whether or not one is there)
    blocks, index, data = {(0,) * size: 0}, [], [0] * size
    for start in range(0, len(items), size):
        block = tuple(items[start:start + size])
        if block not in blocks:
            blocks[block] = len(blocks)
            data += block
        index.append(blocks[block])
    return index, data


def stages(items, split, low):
    # the first low items, and the three stages of all, cut after the last that is not 0
    a, b = split
    top = (max((i for i, item in enumerate(items) if item), default=0) >> a + b) + 1
    index, stage3 = pack(items[:top << a + b], 1 << b)
    stage1, stage2 = pack(index, 1 << a)
    return items[:low], stage1, stage2, stage3


def bits(values):
    # (a byte for each eight code points, of their one bit each)
    return [sum(values[i + j] << j for j in range(8)) for i in range(0, LIMIT, 8)]


def lookup(table, split, i):
    # runtime.c's unicode_property and unicode_case: item i
    (low, stage1, stage2, stage3), (a, b) = table, split
    if 0 <= i < len(low):
        return low[i]
    if not 0 <= i < len(stage1) << a + b:
        return 0
    block = stage2[stage1[i >> a + b] << a | i >> b & (1 << a) - 1]
    return stage3[block << b | i & (1 << b) - 1]


def lookup_bit(table, split, cp):
    # runtime.c's printable and pys_unicode_case_ignorable
    return lookup(table, split, cp >> 3) >> (cp & 7) & 1 if cp >= 0 else 0


def mapped(records, pool, value, cp, kind):
    # runtime.c's pys_unicode_case_map, of unicode_case's value for cp
    entry = records[(value >> 3) * 4 + kind]
    if entry >> 30 == 1:
        at = entry & 0xFFFF
        packed = pool[at] | pool[at + 1] << 21
        return packed | pool[at + 2] << 42 if entry >> 16 & 1 else packed
    return cp + (entry - (1 << 32) if entry >> 31 else entry)


@functools.cache
def tables():
    # (properties, case, records, pool, ignorable, printable): the tables' stages and the case
    # mappings, each value checked for every code point through this file's copies of
    # runtime.c's lookups, with what runtime.py assumes of them
    properties = [flags(cp) for cp in range(LIMIT)]
    ignorable = [case_ignorable(cp) for cp in range(LIMIT)]
    shown = [printable(cp) for cp in range(LIMIT)]
    pool, sequences, records, numbers, values = [], {}, [], {}, []
    for cp in range(LIMIT):
        record = []
        for kind in range(len(KINDS)):
            packed = case_map(cp, kind)
            if packed >> 21:
                seq = tuple(packed >> 21 * i & 0x1FFFFF for i in range(3 if packed >> 42 else 2))
                if seq not in sequences:
                    sequences[seq] = len(pool)
                    pool.extend(seq)
                record.append(SPECIAL | (len(seq) - 2) << 16 | sequences[seq])
            else:
                if not -(1 << 29) <= packed - cp < 1 << 29:
                    raise RuntimeError(f"U+{cp:04X}: distance {packed - cp} does not fit")
                record.append(packed - cp & 0xFFFFFFFF)
            if sum(utf8_len(packed >> 21 * i & 0x1FFFFF) for i in range(3) if i == 0 or packed >> 21 * i) > 3 * utf8_len(cp):
                raise RuntimeError(f"U+{cp:04X}: {KINDS[kind]} mapping is more than three times its bytes")
        record = tuple(record)
        if record not in numbers:
            numbers[record] = len(numbers)
            records.extend(record)
        values.append(numbers[record] << 3 | case_flags(cp))
    if len(pool) > 0xFFFF or max(pool) > 0xFFFF:
        raise RuntimeError("the pool of full mappings does not fit 16 bits")
    if records[:4] != [0, 0, 0, 0] or max(values) > 0xFFFF:
        raise RuntimeError("record 0 is not the mapping to itself, or a record's number does not fit")
    property_table, case_table = stages(properties, PROPERTY_SPLIT, LOW), stages(values, CASE_SPLIT, LOW)
    ignorable_table = stages(bits(ignorable), IGNORABLE_SPLIT, 0)
    printable_table = stages(bits(shown), PRINTABLE_SPLIT, LOW >> 3)
    # (the stages alone hold every code point too)
    staged = ([],) + property_table[1:], ([],) + case_table[1:], ([],) + printable_table[1:]
    for (_, stage1, stage2, stage3), (a, b) in ((property_table, PROPERTY_SPLIT), (case_table, CASE_SPLIT),
                                                (ignorable_table, IGNORABLE_SPLIT), (printable_table, PRINTABLE_SPLIT)):
        if any(stage2[:1 << a]) or any(stage3[:1 << b]):
            raise RuntimeError("block 0 of a stage holds a value")
    for cp in range(LIMIT):
        ch = chr(cp)
        value = lookup(case_table, CASE_SPLIT, cp)
        if lookup(property_table, PROPERTY_SPLIT, cp) != properties[cp] or value != values[cp]:
            raise RuntimeError(f"U+{cp:04X}: a value does not survive its stages")
        if lookup_bit(ignorable_table, IGNORABLE_SPLIT, cp) != ignorable[cp] or lookup_bit(printable_table, PRINTABLE_SPLIT, cp) != shown[cp]:
            raise RuntimeError(f"U+{cp:04X}: case-ignorable or printable does not survive its stages")
        if (lookup(staged[0], PROPERTY_SPLIT, cp) != properties[cp] or lookup(staged[1], CASE_SPLIT, cp) != value
                or lookup_bit(staged[2], PRINTABLE_SPLIT, cp) != shown[cp]):
            raise RuntimeError(f"U+{cp:04X}: its stages differ from its direct value")
        if ((ch + "A").title()[-1] == "a") != (value & 7 != 0):
            raise RuntimeError(f"U+{cp:04X}: cased is not upper, lower or title")
        if value >> 3 and any(mapped(records, pool, value, cp, kind) != case_map(cp, kind) for kind in range(len(KINDS))):
            raise RuntimeError(f"U+{cp:04X}: a mapping does not survive its encoding")
    for cp in range(128):
        # runtime.py tests and maps ASCII itself, by its letters' and digits' ranges
        letter, number = chr(cp).isascii() and chr(cp).isalpha(), 48 <= cp <= 57
        low, up = (cp | 32, cp & 223) if letter else (cp, cp)
        if values[cp] & 7 != ((1 if cp < 97 else 2) if letter else 0) or [case_map(cp, kind) for kind in range(4)] != [low, up, up, low]:
            raise RuntimeError(f"U+{cp:04X}: ASCII case differs from runtime.py's")
        if properties[cp] != (1 if letter else 14 if number else 0):
            raise RuntimeError(f"U+{cp:04X}: ASCII classification differs from runtime.py's")
    if case_map(ord(SIGMA), 0) != ord(FINAL_SIGMA) + 1:
        raise RuntimeError("a lone capital sigma does not lower to the non-final form")
    return property_table, case_table, records, pool, ignorable_table, printable_table


def words(name, entries, per):
    kind = "uint8_t" if max(entries) < 1 << 8 else "uint16_t" if max(entries) < 1 << 16 else "uint32_t"
    lines = [f"static const {kind} {name}[] = {{"]
    for i in range(0, len(entries), per):
        lines.append("  " + ", ".join(str(x) if kind == "uint8_t" else f"0x{x:x}" for x in entries[i:i + per]) + ",")
    return lines + ["};"]


def render_case():
    pinned = pinned_version()
    _, table, records, pool, ignorable, _ = tables()
    lines = [CASE_START, f"/* Generated by tools/unicode_classification_tables.py from CPython {pinned}, Unicode 15.1.0.",
             "   record << 3 | upper=1 | lower=2 | title=4 for each code point: unicode_case_low holds the first",
             "   2,048, and unicode_case_1 to _3 are the three stages of all (see unicode_case below).",
             "   unicode_case_records: a record's lower, upper, title and casefold mappings, each the distance to",
             "   the mapped code point, or 1 << 30 | three code points? << 16 | index in unicode_case_pool of a",
             "   full mapping. unicode_case_ignorable_1 to _3: the three stages of a bit for each code point,",
             "   eight to a byte, set for the case-ignorable ones (see pys_unicode_case_ignorable below).",
             "   Do not edit: regenerate with --write; --check verifies every code point. */"]
    for name, stage in zip(("low", "1", "2", "3"), table):
        lines += words(f"unicode_case_{name}", stage, 24 if max(stage) < 256 else 16)
    lines += words("unicode_case_records", records, 8) + words("unicode_case_pool", pool, 16)
    for name, stage in zip(("1", "2", "3"), ignorable[1:]):
        lines += words(f"unicode_case_ignorable_{name}", stage, 24)
    return "\n".join(lines + [CASE_END])


def render():
    pinned = pinned_version()
    table, printable_table = tables()[0], tables()[5]
    lines = [START, f"/* Generated by tools/unicode_classification_tables.py from CPython {pinned}, Unicode 15.1.0.",
             "   A byte for each code point: alpha=1, digit=2, decimal=4, numeric=8. unicode_property_low holds",
             "   the first 2,048, and unicode_property_1 to _3 are the three stages of all (see unicode_property",
             "   below). unicode_printable_low and _1 to _3: a bit for each code point, eight to a byte, set for",
             "   the printable ones, likewise (see printable below).",
             "   Do not edit: regenerate with --write; --check verifies every code point. */"]
    for name, stage in zip(("low", "1", "2", "3"), table):
        lines += words(f"unicode_property_{name}", stage, 24 if max(stage) < 256 else 16)
    for name, stage in zip(("low", "1", "2", "3"), printable_table):
        lines += words(f"unicode_printable_{name}", stage, 24)
    return "\n".join(lines + [END])


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
        print("Unicode 15.1.0 property and case tables match all 1,114,112 code points")


if __name__ == "__main__":
    main()
