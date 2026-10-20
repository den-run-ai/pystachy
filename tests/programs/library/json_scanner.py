# The decoder scans the text's UTF-8 bytes. It must still report character positions
# after multibyte text, keep lone surrogates that a str holds, give repeated object keys
# (including keys that share a length and first character) their own values, and
# decode integers on both sides of its 18-digit fast path. Recorded with CPython.
import json


def show(source: str) -> None:
    try:
        value = json.loads(source)
        print("V", json.dumps(value), ascii(json.dumps(value, ensure_ascii=False)))
    except json.JSONDecodeError as exc:
        print("E", exc.msg, exc.pos, exc.lineno, exc.colno)


def main() -> None:
    bs = chr(92)
    high = chr(0xD83D)
    low = chr(0xDE80)
    # character positions after multibyte text, in and between strings
    for source in [
        '["é", "雪"] x', '["🚀", tru]', '"é' + chr(1) + '"', '"雪' + bs + 'x"',
        '"é' + bs + 'u12"', '"é' + bs + 'u12é"', '["é" "é"]', '{"é" 1}', '{"é": 1, 2}',
        '"éé', '[é]', '{"a": 1}' + chr(0xFEFF), '\n\n  "é"\n x', '{"雪": [1, 2,]}',
        '{"🚀": {"é": [true, fals]}}', chr(0xA0) + "1", "[1]" + chr(0x3000),
    ]:
        show(source)
    # documents holding lone surrogates; adjacent raw surrogates stay two characters
    for source in [
        '"' + chr(0xD800) + '"', '"' + high + low + '"', '"' + high + bs + "ude80" + low + '"',
        '{"' + chr(0xDC00) + '": [1, "' + chr(0xD800) + 'é"]}', '[1, "' + chr(0xD800) + '", tru]',
        '{"' + high + '": 1, "' + low + '": 2, "' + high + '": 3}',
    ]:
        show(source)
        value = json.loads(source) if not source.endswith("tru]") else None
        if isinstance(value, str):
            print(len(value), [ord(c) for c in value])
    # keys repeated across records, colliding or escaped
    for source in [
        '[{"id": 1, "name": "a"}, {"id": 2, "name": "b"}, {"name": "c", "id": 3}]',
        '[{"ab": 1, "ac": 2}, {"ac": 3, "ab": 4}, {"ab": 5, "ba": 6}]',
        '[{"aa": 1, "' + "a" * 66 + '": 2}, {"' + "a" * 66 + '": 3, "aa": 4}]',
        '[{"a' + bs + '"b": 1}, {"a' + bs + 'u0062": 2, "ab": 3, "a' + bs + '"b": 4}]',
        '[{"": 1}, {"": 2, "x": 3}, {"x": 4}]', '[{"é": 1, "雪": 2}, {"雪": 3, "é": 4, "e": 5}]',
        '{"k": 1, "k' + bs + 'n": 2, "k": 3}',
    ]:
        show(source)
        value = json.loads(source)
        if isinstance(value, list):
            for row in value:
                if isinstance(row, dict):
                    print([len(key) for key in row])
    # integers around the 18-digit fast path, and other number forms
    for source in [
        "999999999999999999", "-999999999999999999", "1000000000000000000",
        "-1000000000000000000", "1234567890123456789", "-9223372036854775807",
        "[0, -0, 10, -10, 0.5, -0.5]", "0e5", "-0.0e-0", "1E+2", "1.5e-3", "2.5E3", "1e-400",
        "0.1000000000000000055511151231257827", "1.7976931348623157e308",
        "[NaN,Infinity,-Infinity,null,true,false]", '{"a":-Infinity,"b":NaN}',
        "-Infinityx", "-I", "Infinit", "\t[\r\n1 ,\t2\n]\r\n",
    ]:
        show(source)
        value = json.loads(source) if source not in ("-Infinityx", "-I", "Infinit") else None
        if isinstance(value, int) and not isinstance(value, bool):
            print(value // 7, value % 7)


main()
