# Byte scans stop on ASCII delimiters; JSON still reports Unicode code-point
# positions. Long and short spans exercise either side of the optional threshold.
import json

def main() -> None:
    for count in [0, 1, 31, 63, 64, 125, 126, 127, 128, 129, 255, 511, 4096]:
        for unit in ["a", "é", "界", "🙂"]:
            text = unit * count + "tail"
            doc = '["' + text + '","escaped\\nend"]'
            values = json.loads(doc)
            if isinstance(values, list):
                first = values[0]
                if isinstance(first, str):
                    print(count, unit, len(first), first == text, values[1] == "escaped\nend")
                else:
                    raise AssertionError("string expected")
            else:
                raise AssertionError("array expected")
            for suffix in ["\x00", "\x01", "\n", "\\q"]:
                bad = '"' + text + suffix + '"'
                try:
                    json.loads(bad)
                    print("unexpected success")
                except json.JSONDecodeError as error:
                    print(error.pos, error.lineno, error.colno)


main()
