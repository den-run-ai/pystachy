# chr(128..255) makes standalone bytes in Pystachy, but Unicode characters in CPython.
# When a byte cannot start a complete UTF-8 sequence, fnmatch/re use that byte's value.
# Compare matching results without printing the intentionally invalid UTF-8 strings.
import fnmatch
import re

for value in [128, 191, 192, 193, 194, 223, 224, 233, 239, 240, 244, 245, 255]:
    char = chr(value)
    print("reversed", value, fnmatch.translate("[" + char + "-a]") == r"(?s:(?!))\Z")
    for pattern in ["[" + char + "-a]", "[a-" + char + "]", "[" + char + "-]", "[-" + char + "]",
                    "[!" + char + "-a]", "[" + char + "-a-]"]:
        print([fnmatch.fnmatchcase(name, pattern) for name in ["a", "z", "-", char, "é", "ê", "Ā", "😀"]])
    # The regex tokenizer must also retain just one byte before syntax, or at the end.
    print("regex", re.fullmatch(char, char) is not None, re.fullmatch(char + "+", char * 2) is not None,
          re.fullmatch("[a-" + char + "]", char) is not None,
          re.fullmatch(re.escape(char), char) is not None,
          re.fullmatch("(" + char + ")", char) is not None,
          re.fullmatch(char + r"\d", char + "1") is not None)

for raw in [chr(233) + chr(128), chr(240) + chr(128) + chr(128), chr(194) + "x"]:
    for pattern in ["[" + raw + "-a]", "[a-" + raw + "]", "[" + raw + "-]", "[" + raw + "]",
                    "[" + raw + "-ê]"]:
        print("truncated", [fnmatch.fnmatchcase(name, pattern)
                            for name in [chr(233), chr(128), chr(240), chr(194), "x", "a", "-", "ê"]])
    print("regex truncated", re.fullmatch(raw, raw) is not None,
          re.fullmatch(raw + "?", raw) is not None)

# Mixed raw-byte and valid UTF-8 endpoints must compare by value, not by their first byte.
for left, right in [(chr(233), "ê"), ("ê", chr(233)), (chr(255), "Ā"), ("Ā", chr(255)),
                    (chr(233), "😀"), ("😀", chr(233))]:
    pattern = "[" + left + "-" + right + "]"
    print("mixed", fnmatch.fnmatchcase(left, pattern), fnmatch.fnmatchcase(right, pattern),
          fnmatch.fnmatchcase("-", pattern))
