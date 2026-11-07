# pystachy: dynamic-any
# Multilingual repair must use Unicode character classes, including non-BMP
# letters and numeric keys. These cases supplement the pinned upstream replay.
import json
from json_repair import loads, repair_json
from typing import Any


for text in ['[é]', '{界:1}', '{город:Москва}', '{المدينة:دبي}',
             '{नाम:नमस्ते}', '{𐐀:𐐨}', '{²:1, Ⅳ:2, ١:3}',
             '{code:123é, other:42界}', '[١٢, １２, ², Ⅳ]',
             '{e\u0301:a\u0301, \u0301x:1}', '[😀, \u0378, \ue000, é]',
             '\u3000{\u00a0é\u2003:\u202f界,\u3000}\u0085',
             '{数:9223372036854775808, items:[é, {界:-9223372036854775809}]}',
             '{é:, 界:2}', '"界":1}', '{é:1}{界:2}']:
    print(repair_json(text, ensure_ascii=False))
    value: Any = loads(text, skip_json_loads=True, stream_stable=True)
    print(json.dumps(value))
    try:
        print(repair_json(text, strict=True))
    except ValueError as exc:
        print(type(exc).__name__, str(exc))

logged: Any = loads('{город:Москва, 值:"\ud83d\ude00",}', logging=True)
print(json.dumps(logged[0]), len(logged[1]))
value_text: str = logged[0]['值']
print([ord(char) for char in value_text])
