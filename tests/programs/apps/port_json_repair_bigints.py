# pystachy: dynamic-any
# Valid JSON must not reach heuristic repair merely because a token exceeds int64.
# Record against this same port under CPython, whose normal JSON decoder promotes.
import json
from typing import Any
from json_repair import loads, repair_json


for source in ["12345678901234567890", "-12345678901234567890",
               "9223372036854775808", "-9223372036854775809"]:
    print(repair_json(source))
    value: Any = loads(source)
    print(type(value).__name__, str(value))

source = '{"n":12345678901234567890,"s":"\\uD83D\\uDE00"}'
value = loads(source)
emoji: str = value["s"]
print(json.dumps(value), len(emoji), ord(emoji[0]))
print(repair_json(source, ensure_ascii=False))
logged: Any = loads(source, logging=True)
print(json.dumps(logged[0]), logged[1])

# Strict mode still takes the valid-JSON path for empty and duplicate keys.
# Both small and wide cases establish that this is a fallback bug, not a new policy.
for source in ['{"":7}', '{"":12345678901234567890}',
               '{"n":1,"n":7}', '{"n":1,"n":12345678901234567890}',
               '{"n":12345678901234567890,"n":7}']:
    print(repair_json(source, strict=True))
    value = loads(source, strict=True)
    print(json.dumps(value))

source = '{"n":12345678901234567890,"nan":NaN,"p":Infinity,"m":-Infinity}'
print(repair_json(source))
value = loads(source)
print(type(value["nan"]).__name__, value["nan"] != value["nan"],
      value["p"] > 0, value["m"] < 0)

# raw_decode is also used to prove that inserting a missing brace is sufficient.
for skip in [False, True]:
    for source in ['"n":12345678901234567890}', '"n":-12345678901234567890}',
                   '{n:12345678901234567890,}',
                   '{"n":12345678901234567890} trailing prose']:
        print(repair_json(source, skip_json_loads=skip))

try:
    repair_json('"n":12345678901234567890}', strict=True)
except ValueError as exc:
    print("strict", str(exc))

# Callers can retain and mutate both parts of a logged result. Exercise the
# valid-JSON path and the repair parser with a nested integer wider than int64.
for source in ['{"items":[9223372036854775808]}', '{items:[9223372036854775808,],}']:
    logged = loads(source, logging=True)
    items: Any = logged[0]["items"]
    events: Any = logged[1]
    assert str(items[0]) == "9223372036854775808"
    items.append("after")
    logged[0]["same"] = items
    assert logged[0]["same"] is logged[0]["items"]
    assert logged[0]["items"][1] == "after"
    events.append(logged[0])
    assert logged[1][-1] is logged[0]
    assert loads(source, logging=True)[0]["items"] == [items[0]]

# Malformed braces can select array repair even when the input looks like an object.
logged = loads("{1, 2}", logging=True)
assert isinstance(logged[0], list)
items = logged[0]
items.append(3)
assert logged[0] == [1, 2, 3]
print("logged document and log aliases preserved")
