# Pystachy reads a UTF-8 file's bytes without checking them, where CPython raises
# UnicodeDecodeError (see the text section of docs/language/compatibility.md), so loads()
# can receive text that is not UTF-8; a Latin-1 write makes those bytes. loads() decodes
# such text as the character-by-character decoder did: a byte that starts no UTF-8
# sequence is one character, in values, repeated keys and error positions, and no
# UnicodeDecodeError escapes.
import json
import os


def main() -> None:
    path = "json_invalid_utf8_" + str(os.getpid()) + ".json"
    try:
        for raw in ['{"caf\xe9": 1}', '["ok", "\xff\xfe", 3] x', '{"a\xe2\x82": [1, tru]}',
                    '[{"k\xe9": 1}, {"k\xe9": 2}, {"k\xe9\\u00e9": 3}]',
                    '{"\xed\xa0": 1, "\xed\xa0\x80": 2, "x": "\xe9\xe9"}', '"\xe9\\q"',
                    '\n  ["\xe9\xe9\xe9",\n tru]', '["\xf0\x9f\x9a\x80", "\xf0\x9f"] x']:
            with open(path, "w", encoding="latin-1") as stream:
                stream.write(raw)
            with open(path) as stream:
                text = stream.read()  # (CPython raises UnicodeDecodeError here)
            try:
                value = json.loads(text)
                print("V", ascii(json.dumps(value)), ascii(json.dumps(value, ensure_ascii=False)))
            except json.JSONDecodeError as exc:
                print("E", exc.msg, exc.pos, exc.lineno, exc.colno)
    finally:
        os.remove(path)


main()
