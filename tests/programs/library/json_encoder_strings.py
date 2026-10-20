# json.dumps() copies a string that needs no escape whole and escapes the others character by
# character: every ASCII character alone and inside text, non-ASCII text around escapes, long
# runs on either side of one escape, keys, and lone surrogates, in both ensure_ascii modes.
import json


def show(value: "json.JSONValue") -> None:
    print(ascii(json.dumps(value)), ascii(json.dumps(value, ensure_ascii=False)))


def main() -> None:
    for cp in range(128):
        show(chr(cp))
        show("ab" + chr(cp) + "cd")
    for s in ["\u00e9", "\u07ff", "\u0800", "\u2028", "\ufeff", "\uffff", "\U00010000", "\U0001f600",
              "\U0010ffff", "\u00e9\n", "\t\u65e5\u672c", "a\"\u00e9\"b", "\U0001f600\\\U0001f600",
              "\x7f\u00e9\x7f", "", "plain text"]:
        show(s)
    long = "x" * 40
    show([long, long + "\n", "\n" + long, long + "\u00e9" + long, long + "\\"])
    show({"plain": 1, "tab\tkey": 2, "\u00e9": 3, "q\"": {"\x00": None}})
    print(json.dumps({"b\n": 1, "a\t": 2, "a": 3}, sort_keys=True, separators=(",", ":")))
    show([chr(0xD800) + "x", "x" + chr(0xDFFF)])


main()
