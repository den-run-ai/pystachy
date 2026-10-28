# pystachy: dynamic-any
# Focused port regression: original cases, not an upstream-suite claim.
import json
from typing import Any
from json_repair import loads, repair_json


def main() -> None:
    document: Any = loads('{tool: "search", arguments: {limit: 3, flags: [true, null,],},}')
    flags: list[Any] = document['arguments']['flags']
    flags.append({'ok': False})
    print(json.dumps(document), flags is document['arguments']['flags'])
    for text in ['{"step":1}\n{"step":2}', '{"pass":fal', 'prefix {"x":[1,2]} suffix',
                 '"key": [true, null]}', '{"line":"a\nb",}', '{"n":1.25e+3,}']:
        print(repair_json(text))
    print(repair_json('{“a”: “one, two”, “b”: true}', stream_stable=True))
    print(repair_json('{"tool":"a","tool":"b"}', strict=True))
    value: Any = loads('{"emoji":"\\ud83d\\ude00",}')
    emoji: str = value['emoji']
    print([ord(char) for char in emoji])
    print(repair_json('{name: "é",}', ensure_ascii=False))
    logged: Any = repair_json('{unquoted: false}', logging=True)
    print(json.dumps(logged[0]), len(logged[1]) > 0)
    try:
        loads('"a": 1}', strict=True)
    except ValueError as exc:
        print(type(exc).__name__, str(exc))


main()
