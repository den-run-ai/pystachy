import json


def main() -> None:
    for source in [
        '"é 日本語 🚀"', r'"\u00e9\u65e5\ud83d\ude80"', r'"\u0000\b\f\n\r\t\/\\\""',
        r'"\ud800"', r'"\udc00"', r'"\ud800x\udc00"', r'"\ud800\u0041"',
        r'"\ud800\ud800"', r'"\udbff\udfff"', r'"\u007f\u0080\u00ff"',
        '{"é": "☃", "🚀": ["é", "\\ud800"]}',
    ]:
        value = json.loads(source)
        print(json.dumps(value))
        print(ascii(json.dumps(value, ensure_ascii=False)))
        print(json.dumps(json.loads(json.dumps(value))))
        if isinstance(value, str):
            print(len(value), [ord(c) for c in value])

    # Positions count characters even after non-ASCII strings and newlines.
    for source in ['{"é":1,}', '{\n "🚀": [1,]\n}', '["日本語", falseX]', '"é\n"']:
        try:
            json.loads(source)
        except json.JSONDecodeError as exc:
            print(exc.msg, exc.pos, exc.lineno, exc.colno)


main()
