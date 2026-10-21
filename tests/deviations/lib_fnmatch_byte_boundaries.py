# Private traversal helpers have no CPython fnmatch counterpart. Forward and backward
# traversal must agree on code-point boundaries, including Latin-1/control characters.
# Historical output labels describe the former byte-oriented implementation; chr(128..255)
# now makes valid Unicode characters, so these inputs no longer test malformed UTF-8.
import fnmatch

for char in [chr(128), chr(191), chr(192), chr(193), chr(194), chr(233), chr(240), chr(244), chr(245), chr(255)]:
    print("byte", fnmatch._next_char(char, 0) == 1, fnmatch._last_char(char) == 0,
          fnmatch._next_char(char + "-", 0) == 1, fnmatch._last_char("a" + char) == 1)

for text in [chr(233) + chr(128), chr(240) + chr(128) + chr(128), chr(194) + "x", "a" + chr(128)]:
    print("truncated", fnmatch._next_char(text, 0) == 1, fnmatch._last_char(text) == len(text) - 1)

for char in ["é", "中", "😀"]:
    for text in [char, "a" + char, chr(233) + char, chr(128) + char]:
        start = len(text) - len(char)
        print("complete", fnmatch._last_char(text) == start, fnmatch._next_char(text, start) == len(text))
    text = char + chr(128)
    print("trailing byte", fnmatch._last_char(text) == len(char), fnmatch._next_char(text, 0) == len(char))

# Adjacent chr() results remain separate code points, even if their low eight bits would
# form an overlong or out-of-range UTF-8 byte sequence. BMP, astral and surrogate values
# each traverse as one code point.
for text in [chr(224) + chr(159) + chr(191), chr(240) + chr(143) + chr(191) + chr(191),
             chr(244) + chr(144) + chr(128) + chr(128)]:
    print("not utf8", fnmatch._next_char(text, 0) == 1, fnmatch._last_char(text) == len(text) - 1)
for text in [chr(0x800), chr(0x10000), chr(0x10FFFF), chr(0xD800)]:
    print("utf8", fnmatch._next_char(text, 0) == len(text), fnmatch._last_char("a" + text) == 1,
          fnmatch._char_value(text) == ord(text))
